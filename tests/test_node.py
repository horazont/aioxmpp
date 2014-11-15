import asyncio
import base64
import unittest

import asyncio_xmpp.protocol as protocol
import asyncio_xmpp.hooks as hooks
import asyncio_xmpp.node as node
import asyncio_xmpp.plugins.rfc6120 as rfc6120

from asyncio_xmpp.utils import *

class SSLWrapperMock:
    def __init__(self, loop, protocol):
        super().__init__()
        self._loop = loop
        self._protocol = protocol

    @asyncio.coroutine
    def starttls(self, ssl_context=None, server_hostname=None):
        tester = self._protocol._tester
        tester.assertFalse(self._protocol._closed)
        tester.assertTrue(self._protocol._action_sequence)
        to_recv, to_send = self._protocol._action_sequence.pop(0)
        tester.assertTrue(to_recv.startswith("!starttls@"),
                          "Unexpected starttls attempt by the client")
        hostname = to_recv[10:] or None
        tester.assertEqual(server_hostname, hostname)

    def close(self):
        pass

class XMLStreamMock:
    def __init__(self, tester, *, loop=None):
        super().__init__()
        self._closed = False
        self._loop = loop or asyncio.get_event_loop()
        self._tester = tester
        self._action_sequence = list()
        self._stream_level_node_hooks = hooks.NodeHooks()
        protocol.XMLStream._rx_reset(self)
        tree_root, self.E = protocol.make_xmlstream_sender(
            self._rx_parser,
            "jabber:client")
        self._tx_makeelement = tree_root.makeelement

    def connection_made(self, transport):
        self._closed = False

    def close(self):
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence)
        to_recv, to_send = self._action_sequence.pop(0)
        self._tester.assertEqual(to_recv, "!close")
        self._tester.assertFalse(to_send)
        self._closed = True

    def reset_stream(self):
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence)
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
        self._tester.assertFalse(self._closed)
        self._tester.assertTrue(self._action_sequence)
        to_recv, to_send = self._action_sequence.pop(0)
        # print("foo", node)
        self._tester.assertNotEqual(
            to_recv, "!close",
            "Unexpected node sent by the client")
        # print("bar")
        # XXX: this needs to be done better. maybe we need a comparision method
        # on stanzas.
        save_id = node.attrib.pop("id", None)
        self._tester.assertTreeEqual(to_recv, node)
        if save_id is not None:
            node.set("id", save_id)
        for node_to_send in to_send:
            if hasattr(node_to_send, "id") and hasattr(node, "id"):
                # print(node_to_send)
                node_to_send.id = node.id
            self.mock_receive_node(node_to_send)

    def send_node(self, node):
        self._tx_send_node(node)

    @property
    def stream_level_hooks(self):
        return self._stream_level_node_hooks

    _send_andor_wait_for = protocol.XMLStream._send_andor_wait_for
    wait_for = protocol.XMLStream.wait_for
    send_and_wait_for = protocol.XMLStream.send_and_wait_for
    stream_error = protocol.XMLStream.stream_error
    _make_from_template = protocol.XMLStream._make_from_template
    make_iq = protocol.XMLStream.make_iq

class TestableClient(node.Client):
    # this merely overrides the construction of the xmlstream so that we can
    # hook our mockable stream into it

    def __init__(self, mocked_transport, mocked_stream,
                 client_jid, password, *args, **kwargs):
        self.__mocked_transport = mocked_transport
        self.__mocked_stream = mocked_stream
        @asyncio.coroutine
        def password_provider(*args):
            return password
        super().__init__(client_jid, password_provider, *args, **kwargs)

    @asyncio.coroutine
    def _connect_xmlstream(self):
        self.__mocked_stream._Client__features_future = \
            self.__mocked_stream.wait_for(
                [
                    "{http://etherx.jabber.org/streams}features",
                ],
                timeout=1)
        return self.__mocked_transport, self.__mocked_stream

class TestClient(unittest.TestCase):
    def assertTreeEqual(self, t1, t2, with_tail=False):
        self.assertEqual(t1.tag, t2.tag)
        self.assertEqual(t1.text, t2.text)
        self.assertDictEqual(dict(t1.attrib), dict(t2.attrib))
        self.assertEqual(len(t1), len(t2))
        for c1, c2 in zip(t1, t2):
            self.assertTreeEqual(c1, c2, with_tail=True)
        if with_tail:
            self.assertEqual(t1.tail, t2.tail)

    def setUp(self):
        self._loop = asyncio.get_event_loop()

    def _make_stream(self):
        wrapper = SSLWrapperMock(
            self._loop,
            XMLStreamMock(
                self,
                loop=self._loop))
        wrapper._protocol.connection_made(wrapper)
        return wrapper, wrapper._protocol

    @asyncio.coroutine
    def _run_client(self, initial_node, transport, stream,
                    client_jid="test@example.com",
                    password="test",
                    *args, **kwargs):
        connecting, done = asyncio.Event(), asyncio.Event()
        connection_err = None

        client = TestableClient(
            transport, stream,
            client_jid,
            password,
            loop=self._loop)

        @asyncio.coroutine
        def catch_error(err):
            nonlocal connection_err
            connection_err = err
            done.set()

        client.register_callback(
            "connecting",
            asyncio.coroutine(lambda x: connecting.set()))
        client.register_callback(
            "connection_failed",
            catch_error)
        client.register_callback(
            "connection_made",
            asyncio.coroutine(lambda: done.set()))

        yield from connecting.wait()

        stream.mock_receive_node(initial_node)

        yield from done.wait()

        yield from client.close()

        if isinstance(connection_err, AssertionError):
            raise connection_err
        return connection_err

    def test_require_starttls(self):
        transport, stream = self._make_stream()
        stream.define_actions(
            [
                ("!close", None)
            ]
        )

        @asyncio.coroutine
        def task():
            err = yield from self._run_client(
                stream.E("{{{}}}features".format(namespaces.xmlstream)),
                transport,
                stream
            )
            self.assertIsInstance(err,
                                  node.StreamNegotiationFailure)

        self._loop.run_until_complete(task())

        stream.mock_finalize()

    def test_negotiate_stream(self):
        transport, stream = self._make_stream()

        bind_response = rfc6120.Bind()
        bind_response.jid = "test@example.com/foo"

        stream.define_actions(
            [
                (stream.E("{{{}}}starttls".format(namespaces.starttls)),
                 [stream.E("{{{}}}proceed".format(namespaces.starttls))]),
                ("!starttls@example.com", None),
                ("!reset",
                 [stream.E(
                     "{{{}}}features".format(namespaces.xmlstream),
                     stream.E(
                         "{{{}}}mechanisms".format(namespaces.sasl),
                         stream.E(
                             "{{{}}}mechanism".format(namespaces.sasl),
                             "PLAIN"
                         )
                     )
                 )]),
                (stream.E(
                    "{{{}}}auth".format(namespaces.sasl),
                    base64.b64encode(b"\0test\0test").decode(),
                    mechanism="PLAIN"),
                 [stream.E("{{{}}}success".format(namespaces.sasl))]),
                ("!reset",
                 [
                     stream.E(
                         "{{{}}}features".format(namespaces.xmlstream),
                         stream.E("{{{}}}bind".format(namespaces.bind))
                     )
                 ]),
                (stream.E(
                    "{{{}}}iq".format(namespaces.client),
                    rfc6120.Bind(),
                    type="set"),
                 [
                     stream.E(
                         "{{{}}}iq".format(namespaces.client),
                         bind_response,
                         type="result")
                 ]),
                ("!close", None),
            ]
        )

        @asyncio.coroutine
        def task():
            features = stream.E(
                "{{{}}}features".format(namespaces.xmlstream),
                stream.E(
                    "{{{}}}starttls".format(namespaces.starttls),
                    stream.E("{{{}}}required".format(namespaces.starttls))
                )
            )
            err = yield from self._run_client(
                features,
                transport,
                stream
            )
            if err is not None:
                raise err

        self._loop.run_until_complete(task())

        stream.mock_finalize()
