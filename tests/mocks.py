"""
:mod:`tests.mocks` --- Hacks on internal structures to mock functionality
#########################################################################

This module contains classes which are mainly hacks on actual classes from
:mod:`asyncio_xmpp`.

.. warning::

   Never ever use these classes in production! They are only meant for testing,
   and some expose very dangerous behaviour (for example replacing the random
   number generator for :mod:`asyncio_xmpp.sasl`).

   Do not even *import* this module in production code (it should not even be
   available, as tests are not installed).

"""
import asyncio
import logging

import asyncio_xmpp.protocol as protocol
import asyncio_xmpp.node as node
import asyncio_xmpp.hooks as hooks
import asyncio_xmpp.xml as xml
import asyncio_xmpp.security_layer as security_layer
import asyncio_xmpp.sasl as sasl

from asyncio_xmpp.utils import *

logger = logging.getLogger(__name__)

class BangSuccess(Exception):
    """
    This is raised by the ``"!success"`` string action. Can be used to
    e.g. abort a SASL negotiation if the intent of the client is already clear
    enough.
    """

    def __init__(self):
        super().__init__("!success")

def assertTreeEqual(tester, t1, t2, with_tail=False):
    tester.assertEqual(t1.tag, t2.tag)
    tester.assertEqual(t1.text, t2.text)
    tester.assertDictEqual(dict(t1.attrib), dict(t2.attrib))
    tester.assertEqual(len(t1), len(t2))
    for c1, c2 in zip(t1, t2):
        assertTreeEqual(tester, c1, c2, with_tail=True)
    if with_tail:
        tester.assertEqual(t1.tail, t2.tail)

class RNGMock:
    def __init__(self, value):
        self._value = value

    def getrandbits(self, bitn):
        if 8*(bitn//8) != bitn:
            raise ValueError("Unsupported bit count")
        return int.from_bytes(self._value[:bitn//8], "little")

sasl._system_random = RNGMock(b"foo")

class TransportMock(asyncio.ReadTransport, asyncio.WriteTransport):
    """
    Mock a :class:`asyncio.Transport`.
    """

    def __init__(self, protocol):
        super().__init__()
        self.closed = False
        self._eof = False
        self._written = b""
        self._protocol = protocol

    def _require_non_eof(self):
        if self._eof:
            raise ConnectionError("Write connection already closed")

    def _require_open(self):
        if self.closed:
            raise ConnectionError("Underlying connection closed")

    def close(self):
        self._require_open()
        self.closed = True
        self._eof = True

    def get_extra_info(self, name, default=None):
        return default

    def abort(self):
        self.close()

    def can_write_eof(self):
        return True

    def write(self, data):
        self._require_non_eof()
        self._written += data

    def writelines(self, list_of_data):
        self.write(b"".join(list_of_data))

    def write_eof(self):
        self._require_non_eof()
        self._eof = True

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass

    def mock_connection_made(self):
        self._protocol.connection_made(self)

    def mock_eof_received(self):
        self._protocol.eof_received()

    def mock_connection_lost(self, exc):
        self._protocol.connection_lost(exc)

    def mock_data_received(self, data):
        self._protocol.data_received(data)

    def mock_pause_writing(self):
        self._protocol.pause_writing()

    def mock_resume_writing(self):
        self._protocol.resume_writing()

    def mock_buffer(self):
        return self._written, self._eof

    def mock_flush_buffer(self):
        buffer = self._written
        self._written = b""
        return buffer

class SSLWrapperMock:
    """
    Mock for :class:`asyncio_xmpp.ssl_wrapper.STARTTLSableTransportProtocol`.

    The *protocol* must be an :class:`XMLStreamMock`, as the
    :class:`SSLWrapperMock` depends on some private attributes to ensure the
    sequence of events is correct.
    """

    def __init__(self, loop, protocol):
        super().__init__()
        self._loop = loop
        self._protocol = protocol

    @asyncio.coroutine
    def starttls(self, ssl_context=None, post_handshake_callback=None):
        """
        Override the STARTTLS sequence. Instead of actually starting a TLS
        transport on the existing socket, only make sure that the test expects
        starttls to happen now. If so, return fake information on the TLS
        transport.
        """

        tester = self._protocol._tester
        tester.assertFalse(self._protocol._closed)
        tester.assertTrue(self._protocol._action_sequence,
                          "Unexpected client action (no actions left)")
        to_recv, to_send = self._protocol._action_sequence.pop(0)
        tester.assertTrue(to_recv.startswith("!starttls"),
                          "Unexpected starttls attempt by the client")
        return self, None

    def close(self):
        pass

class XMLStreamMock:
    """
    High-level mock for :class:`asyncio_xmpp.protocol.XMLStream`.

    *tester* must be a :class:`unittest.TestCase`, as it provides all the
    assertion methods for testing.

    Use :meth:`define_actions` to define a test sequence to run. The
    :class:`XMLStreamMock` only supports request-response testing. Each action
    is a pair of ``(action, reaction)``. *action* must be either a string or a
    :class:`lxml.etree._Element`.

    Whenever a user action is performed on the xml stream, it is compared with
    the current expected *action*. Nodes are compared directly; other actions
    are mapped to strings (see below). If the client action matches the expected
    *action*, the list of nodes provided by *reaction* is sent to the user.

    If the user has not registered stream level hooks for any of the nodes from
    within *reaction*, the test fails. If *reaction* is :data:`None`, the test
    finishes.

    If the *action* does not match or there are no actions left in the list, an
    assertion fails. The client action is only compared against the zeroth
    element of the list, and on a match, the element is removed from the list.

    Special activity which maps to strings:

    * closing the protocol: ``"!close"``
    * resetting the stream: ``"!reset"``
    * calling starttls on the transport: ``"!starttls"``

    To send stimulus to the client (e.g. the first features node), use
    :meth:`mock_receive_node`.
    """

    def __init__(self, tester, *, loop=None):
        super().__init__()
        self._closed = False
        self._loop = loop or asyncio.get_event_loop()
        self._tester = tester
        self._action_sequence = list()
        self._transport = None
        self._stream_level_node_hooks = hooks.NodeHooks()
        protocol.XMLStream._rx_reset(self)
        self.tx_context = xml.default_tx_context
        self.E = self.tx_context

        self.done_event = asyncio.Event(loop=loop)
        self.done_event.clear()

    def connection_made(self, transport):
        self._closed = False
        self._transport = transport

    def hard_close(self, exc):
        self.close()

    def close(self, *, waiter=None):
        logger.debug("remaining actions: %r", self._action_sequence)
        logger.debug("CLIENT ACTION: !close")
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence,
                                "Unexpected client action (no actions left)")
        to_recv, to_send = self._action_sequence.pop(0)
        self._tester.assertEqual(
            to_recv, "!close",
            msg="Expected client to send {}".format(
                etree.tostring(to_recv) if not isinstance(to_recv, str) else "")
        )
        self._tester.assertFalse(to_send)
        self.done_event.set()
        self._closed = True
        if waiter is not None:
            waiter.set_result(None)
        if self.on_connection_lost:
            self.on_connection_lost(None)

    def reset_stream(self):
        logger.debug("remaining actions: %r", self._action_sequence)
        logger.debug("CLIENT ACTION: !reset")
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence,
                                "Unexpected client action (no actions left)")
        to_recv, to_send = self._action_sequence.pop(0)
        self._tester.assertEqual(to_recv, "!reset")
        for node in to_send:
            self.mock_receive_node(node)

    def define_actions(self, action_sequence):
        self._action_sequence[:] = action_sequence

    def mock_receive_node(self, node):
        try:
            self._stream_level_node_hooks.unicast(node.tag, node)
        except KeyError:
            raise AssertionError(
                "Client has no listener for node sent by test: {}".format(node.tag)
            ) from None

    def mock_finalize(self):
        self._tester.assertFalse(
            self._action_sequence,
            "Some expected actions were not performed")

    def _tx_send_node(self, node):
        logger.debug("remaining actions: %r", self._action_sequence)
        logger.debug("CLIENT ACTION: node: %s", etree.tostring(node))
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence,
                                "Unexpected client action (no actions left)")
        to_recv, to_send = self._action_sequence.pop(0)
        # print("foo", node)
        self._tester.assertNotEqual(
            to_recv, "!close",
            "Unexpected node sent by the client: {}".format(
                etree.tostring(node)))
        # print("bar")
        # XXX: this needs to be done better. maybe we need a comparision method
        # on stanzas.
        if node.get("type") in {"set", "get"}:
            save_id = node.attrib.pop("id", None)
        else:
            save_id = None
        assertTreeEqual(self._tester, to_recv, node)

        if to_send == "!success":
            raise BangSuccess()

        if save_id is not None:
            node.set("id", save_id)
        for node_to_send in to_send:
            if     (hasattr(node_to_send, "id_") and hasattr(node, "id_")
                    and node_to_send.type_ in {"result", "error"}):
                # print(node_to_send)
                node_to_send.id_ = node.id_
            self.mock_receive_node(node_to_send)

        if self._action_sequence and self._action_sequence[0][0] == "!close":
            self.done_event.set()

    def send_node(self, node):
        self._tx_send_node(node)

    @property
    def closed(self):
        return self._closed

    @property
    def stream_level_hooks(self):
        return self._stream_level_node_hooks

    _send_andor_wait_for = protocol.XMLStream._send_andor_wait_for
    wait_for = protocol.XMLStream.wait_for
    send_and_wait_for = protocol.XMLStream.send_and_wait_for
    _tx_stream_error = protocol.XMLStream._tx_stream_error
    stream_error = protocol.XMLStream.stream_error
    transport = protocol.XMLStream.transport
    reset_stream_and_get_features = \
        protocol.XMLStream.reset_stream_and_get_features
    close_and_wait = protocol.XMLStream.close_and_wait


class TestableClient(node.Client):
    """
    This is not a mock in the classical sense, but a full
    :class:`asyncio_xmpp.node.Client` class, with one exception: The XML stream
    is not connected to an actual transport, but with the *mocked_transport* and
    *mocked_stream* provided in the constructor.

    If *mocked_transport* is :data:`None`, a new :class:`SSLWrapperMock` is
    created and used as transport. The ``connection_made`` event is always sent
    by this class, no matter if the transport has been created or passed.

    If *inital_node* is not :data:`None`, it must be a single
    :class:`lxml.etree._Element`, which is injected immediately after the xml
    stream has been "connected".
    """

    def __init__(self, mocked_stream,
                 client_jid, password, *args,
                 initial_node=None,
                 mocked_transport=None,
                 **kwargs):
        self.__mocked_transport = mocked_transport or SSLWrapperMock(
            mocked_stream._loop,
            mocked_stream)
        self.__mocked_stream = mocked_stream
        self.__initial_node = initial_node
        @asyncio.coroutine
        def password_provider(*args):
            return password
        super().__init__(
            client_jid,
            security_layer.tls_with_password_based_authentication(
                password_provider),
            *args, **kwargs)

    @asyncio.coroutine
    def _connect_xmlstream(self):
        self.__mocked_stream.connection_made(self.__mocked_transport)
        self.__mocked_stream._Client__features_future = \
            self.__mocked_stream.wait_for(
                [
                    "{http://etherx.jabber.org/streams}features",
                ],
                timeout=1)
        self.__mocked_stream.mock_receive_node(self.__initial_node)
        self.__mocked_stream.on_connection_lost = \
            self._handle_xmlstream_connection_lost
        self._xmlstream = self.__mocked_stream
        return self.__mocked_transport, self.__mocked_stream
