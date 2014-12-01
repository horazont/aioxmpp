"""
:mod:`asyncio_xmpp.protocol` --- :class:`asyncio.Protocol` implementation for an xmlstream
##########################################################################################

The :class:`.XMLStream` lass provides an high-level interface to an XMPP
xmlstream. The corresponding section in the user guide can be found at
:ref:`ug-xmlstream`.

.. autoclass:: XMLStream(to, [mode=Mode.C2S], *, [loop], [tx_context])
   :members:

"""

import asyncio
import copy
import functools
import logging

import lxml.builder

from enum import Enum

from . import stanza, hooks, errors, utils, xml

from .utils import *

logger = logging.getLogger(__name__)

class Mode(Enum):
    """
    Mode for an XML stream, which can be either client-to-server or server-to-server.
    """

    #: client-to-server mode (uses the ``jabber:client`` namespace)
    C2S = namespaces.client
    CLIENT = namespaces.client

    def __repr__(self):
        return ".".join([type(self).__qualname__, self.name])

class XMLStream(asyncio.Protocol):
    """
    Provide an element-level interface to an XML stream. The stream header is
    configured in the constructor. *to* is the corresponding stream header
    attribute. *mode* must be a :class:`Mode` value which determines the mode of
    the stream, either client-to-server or server-to-server. The default is
    client-to-server (:attr:`Mode.C2S`).

    *tx_context* must be an :class:`~asyncio_xmpp.xml.XMLStreamSenderContext`
    with appropriate default namespace for this type of xml stream (either
    client or server). The default is usable for client streams, but not for
    server streams.

    *loop* must be an :class:`asyncio.BaseEventLoop` or :data:`None`. It is used
    in any calls to the :mod:`asyncio` module where usage of an explicit event
    loop argument is supported.
    """

    stream_header_tag = "{{{stream_ns}}}stream".format(
        stream_ns=namespaces.xmlstream)

    def __init__(self,
                 to,
                 mode=Mode.C2S,
                 *,
                 loop=None,
                 tx_context=xml.default_tx_context,
                 **kwargs):
        super().__init__(**kwargs)
        # client info
        self._to = to
        self._namespace = mode.value

        # sender utils
        self.tx_context = tx_context

        # receiver state
        self._rx_context = None

        # asyncio state
        self._transport = None
        self._loop = loop

        # connection state
        self._stream_level_node_hooks = hooks.NodeHooks()
        self._died = asyncio.Event()
        self._died.set()
        self._closing = False

        # callbacks
        self.on_stream_error = None
        self.on_starttls_engaged = None
        self.on_connection_lost = None

    def _rx_close(self):
        """
        Close the parser and reset any receiving state.

        This may trigger the call of node event handlers.
        """
        if self._rx_context is None:
            return

        try:
            self._rx_context.close()
        except lxml.etree.XMLSyntaxError:
            # ignore errors on closing
            pass
        self._transport.close()
        self._rx_context = None

    def _rx_end_of_stream(self):
        """
        Handle </stream:stream> being received from the remote end.
        """
        if not self._closing:
            self.close()
            return

        self._rx_close()

    def _rx_feed(self, blob):
        try:
            self._rx_context.feed(blob)
            self._rx_process()
        except lxml.etree.XMLSyntaxError as err:
            raise errors.SendStreamError(
                "not-well-formed",
                text=str(err))

    def _rx_process(self):
        """
        Process any pending SAX events produced by the receiving parser.
        """

        if not self._rx_context.ready:
            if not self._rx_context.start():
                return

        for node in self._rx_context.read_stream_level_nodes():
            logger.debug("node recv’d: %s", node)
            if node is None:
                self._rx_end_of_stream()
            else:
                if hasattr(node, "validate"):
                    try:
                        node.validate()
                    except ValueError as err:
                        # ValueError is raised by ElementBase subclasses upon
                        # content validation
                        # As these are only instanciated for the stream level
                        # nodes here, treating ValueErrors as critical is sane
                        raise errors.SendStreamError(
                            "invalid-xml",
                            str(err))

                self._rx_process_stream_level_node(node)

    def _rx_process_stream_level_node(self, node):
        try:
            self._stream_level_node_hooks.unicast(node.tag, node)
        except KeyError:
            if node.tag == "{{{}}}error".format(
                    namespaces.xmlstream):
                self._rx_stream_error(node)
            else:
                raise errors.SendStreamError(
                    "unsupported-stanza-type",
                    text="no handler for {}".format(node.tag))

    def _rx_reset(self):
        self._rx_context = xml.XMLStreamReceiverContext()

    def _rx_stream_error(self, node):
        TEXT_TAG = "{{{}}}text".format(namespaces.streams)

        error_tag = None
        text = None
        application_defined_condition = None
        for child in node:
            ns, name = utils.split_tag(child.tag)
            if child.tag == TEXT_TAG:
                text = text or child.text
            elif ns != namespaces.streams:
                application_defined_condition = (
                    application_defined_condition or name)
            else:
                error_tag = error_tag or name

        err = errors.StreamError(
            error_tag,
            text=text,
            application_defined_condition=application_defined_condition)

        self._stream_level_node_hooks.broadcast_error(err)

        if self.on_stream_error:
            self.on_stream_error(err)
        else:
            logger.error("remote sent %s", str(err))
            self.close()

    def _tx_close(self):
        self._tx_send_footer()
        if self._transport.can_write_eof():
            self._transport.write_eof()

    def _tx_reset(self):
        pass

    def _tx_send_footer(self):
        self._tx_send_raw(b"</stream:stream>")

    def _tx_send_header(self):
        """
        Send a stream header over the wire, using the configuration supplied in
        the constructor.

        Raises :class:`ConnectionError` if not connected to a transport.
        """
        self._tx_send_raw(
            b"""<?xml version="1.0" ?>\n""")
        self._tx_send_raw(
            "<stream:stream"
            " xmlns='{ns}'"
            " xmlns:stream='{stream_ns}'"
            " version='1.0'"
            " to='{to}'>".format(
                ns=self._namespace,
                stream_ns=namespaces.xmlstream,
                to=self._to).encode("utf8"))

    def _tx_send_node(self, node):
        self._tx_send_raw(
            etree.tostring(node,
                           method="xml",
                           encoding="utf8",
                           xml_declaration=False)
        )

    def _tx_send_raw(self, blob):
        """
        Send the given raw *blob* using the underlying transport.

        Raises :class:`ConnectionError` if not connected to a transport.
        """
        if self._transport is None:
            raise ConnectionError("Not connected")
        logger.debug("SEND %s", blob)
        self._transport.write(blob)

    # asyncio Protocol implementation

    def connection_made(self, using_transport):
        self._transport = using_transport
        self.reset_stream()

    def data_received(self, blob):
        logger.debug("RECV %s", blob)
        try:
            self._rx_feed(blob)
        except errors.SendStreamError as err:
            self.stream_error(err.error_tag, err.text)

    def eof_received(self):
        try:
            self.close()
        except:
            logger.exception("during eof_received")
            raise

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def connection_lost(self, exc):
        try:
            self.close()
        finally:
            self._transport = None
            self._died.set()
            self._send_root = None
            self.E = None
            self._rx_context = None
            self._stream_level_node_hooks.close_all(
                ConnectionError("Disconnected"))

    def starttls_engaged(self, transport):
        if self.on_starttls_engaged:
            self.on_starttls_engaged(transport)

    # public API

    def close(self):
        if self._closing:
            return
        self._closing = True
        self._tx_close()
        self._rx_close()

    def reset_stream(self):
        self._rx_reset()
        self._tx_reset()
        self._tx_send_header()
        self._died.clear()

    def _send_andor_wait_for(self,
                             nodes_to_send,
                             tags,
                             timeout=None,
                             critical_timeout=True):
        # print("send_andor_wait_for {} {}".format(nodes_to_send, tags))
        futures = []
        for tag in tags:
            f = asyncio.Future()
            futures.append((tag, f))
            self._stream_level_node_hooks.add_future(tag, f)

        for node in nodes_to_send:
            # print("sending node {}".format(node))
            self.send_node(node)
            # print("sent node")

        @asyncio.coroutine
        def waiter_task(futures, timeout, critical_timeout):
            done, pending = yield from asyncio.wait(
                [f for _, f in futures],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED)

            # first cancel futures, then retrieve result (result may be an
            # Exception)
            for tag, future in futures:
                if future not in pending:
                    continue
                future.cancel()
                try:
                    self._stream_level_node_hooks.remove_future(tag, future)
                except KeyError:
                    # defensive guard against a maybe race condition
                    # (I guess that in some cases, asyncio.wait may catch only
                    # one future, but more than one has been fulfilled)
                    pass

            if not done:
                if critical_timeout:
                    self.stream_error("connection-timeout", None)
                    raise ConnectionError("Disconnected")
                raise TimeoutError("Timeout")

            result = next(iter(done)).result()
            return result

        return asyncio.async(
            waiter_task(futures, timeout, critical_timeout),
            loop=self._loop)

    @asyncio.coroutine
    def send_and_wait_for(self,
                          nodes_to_send,
                          tokens,
                          timeout=None,
                          critical_timeout=True):
        return self._send_andor_wait_for(
            nodes_to_send,
            tokens,
            timeout=timeout,
            critical_timeout=critical_timeout)

    def wait_for(self, tokens, timeout=None, critical_timeout=True):
        return self._send_andor_wait_for(
            [],
            tokens,
            timeout=timeout,
            critical_timeout=critical_timeout)

    def send_node(self, node):
        self._tx_send_node(node)

    def stream_error(self, tag, text):
        node = self.tx_context.makeelement(
            "{{{}}}error".format(namespaces.xmlstream),
            nsmap={
                "stream": namespaces.xmlstream,
                None: namespaces.streams
            })
        node.append(
            node.makeelement("{{{}}}{}".format(namespaces.streams, tag)))
        if text:
            text_node = node.makeelement(
                "{{{}}}text".format(namespaces.streams))
            text_node.text = text
            node.append(text_node)
        self._tx_send_node(node)
        del node
        self.close()

    @property
    def stream_level_hooks(self):
        return self._stream_level_node_hooks
