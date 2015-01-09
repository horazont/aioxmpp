"""
:mod:`~asyncio_xmpp.protocol` --- :class:`asyncio.Protocol` implementation for an xmlstream
###########################################################################################

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

STREAM_ERROR_TAGS = {
    "bad-format",
    "bad-namespace-prefix",
    "conflict",
    "connection-timeout",
    "host-gone",
    "host-unknown",
    "improper-addressing",
    "internal-server-error",
    "invalid-from",
    "invalid-namespace",
    "invalid-xml",
    "not-authorized",
    "not-well-formed",
    "policy-violation",
    "remote-connection-failed",
    "reset",
    "resource-constraint",
    "restricted-xml",
    "see-other-host",
    "system-shutdown",
    "undefined-condition",
    "unsupported-encoding",
    "unsupported-feature",
    "unsupported-stanza-type",
    "unsupported-version",
}

class Mode(Enum):
    """
    Mode for an XML stream, which can be either client-to-server or server-to-server.
    """

    #: client-to-server mode (uses the ``jabber:client`` namespace)
    C2S = namespaces.client
    CLIENT = namespaces.client

    def __repr__(self):
        return ".".join([type(self).__qualname__, self.name])

class _State(Enum):
    """
    The values are bitmasks with internal definition. Do not change light
    heartedly. Use of the value outside any methods of this class MUST NOT
    happen.
    """

    #: connection_made not called yet
    UNCONNECTED = 0x00

    #: connection_made has been called, but stream header not yet received
    #: (stream not usable yet)
    CONNECTED = 0x01

    #: stream header has been received, stream is usable
    STREAM_HEADER_RECEIVED = 0x03

    #: </stream:stream> sent and write_eof() on transport called, but
    #: </stream:stream> not received
    TX_CLOSED_RX_OPEN = 0x10

    #: </stream:stream> received, but </stream:stream> not sent yet, underlying
    #: transport still fully open
    TX_OPEN_RX_CLOSED = 0x20

    #: both sides have been terminated, we are waiting for connection_lost
    CLOSING = 0x40

    @property
    def rx_open(self):
        """
        :data:`True` if the receiving side of the transport is still usable,
        :data:`False` otherwise.
        """
        return (bool(self.value & _State.TX_CLOSED_RX_OPEN.value) or
                self.connected)

    @property
    def tx_open(self):
        """
        :data:`True` if the sending side of the transport is still usable,
        :data:`False` otherwise.
        """
        return (bool(self.value & _State.TX_OPEN_RX_CLOSED.value) or
                self.connected)

    @property
    def connected(self):
        """
        :data:`True` if the transport is still fully open, :data:`False`
        otherwise.
        """
        return bool(self.value & _State.CONNECTED.value)

    @property
    def stream_usable(self):
        """
        :data:`True` if the stream is usable, :data:`False` otherwise.
        """
        bitmask = _State.STREAM_HEADER_RECEIVED.value
        return bool((self.value & bitmask) == bitmask)

    def with_closed_rx(self):
        if self == _State.TX_CLOSED_RX_OPEN:
            return _State.CLOSING
        elif not self.connected:
            return self
        else:
            return _State.TX_OPEN_RX_CLOSED

    def with_closed_tx(self):
        if self == _State.TX_OPEN_RX_CLOSED:
            return _State.CLOSING
        elif not self.connected:
            return self
        else:
            return _State.TX_CLOSED_RX_OPEN


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
        # main state
        self._state = _State.UNCONNECTED

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
        self._closing = False
        self._waiter = None
        self._conn_exc = None

        # callbacks
        self.on_stream_error = None
        self.on_starttls_engaged = None
        self.on_connection_lost = None

    def _invalid_transition(self, via=None, to=None):
        via_text = (" via {}".format(via)) if via is not None else ""
        to_text = (" to {}".format(to)) if to is not None else ""
        msg = "Invalid state transition (from {}{}{})".format(
            self._state,
            via_text,
            to_text
        )
        logger.error(msg)
        raise RuntimeError(msg)

    def _invalid_state(self, what, exc=RuntimeError):
        msg = "{what} (invalid in state {state})".format(
            what=what,
            state=self._state)
        logger.error(msg)
        # raising is optional :)
        return exc(msg)

    def _rx_close(self):
        if not self._state.rx_open:
            return

        try:
            self._rx_context.close()
        except lxml.etree.XMLSyntaxError:
            pass

        self._state = self._state.with_closed_rx()
        self._transport.close()
        self._rx_context = None

    def _rx_end_of_stream(self):
        if self._state.stream_usable:
            self.close()
        elif self._state.connected:
            self._invalid_state("received end of stream before header")
        elif self._state.rx_open:
            self._rx_close()
        else:
            raise self._invalid_state("received end of stream")

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
            self._state = _State.STREAM_HEADER_RECEIVED

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
        logger.error("remote sent %s", str(err))
        self.hard_close(err)

    def _tx_close(self):
        if not self._state.tx_open:
            return

        self._tx_send_footer()
        if self._transport.can_write_eof():
            self._transport.write_eof()
        self._state = self._state.with_closed_tx()

    def _tx_reset(self):
        self._tx_send_header()

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
                           xml_declaration=False,
                           with_tail=False)
        )

    def _tx_send_raw(self, blob):
        """
        Send the given raw *blob* using the underlying transport.

        Raises :class:`ConnectionError` if not connected to a transport.
        """
        if not self._state.tx_open:
            raise self._invalid_state("attempt to transmit data",
                                      exc=ConnectionError)

        logger.debug("SEND %s", blob)
        self._transport.write(blob)

    def _tx_stream_error(self, tag, text, custom_error=None):
        if tag not in STREAM_ERROR_TAGS:
            raise ValueError("{!r} is not a valid stream error".format(tag))

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
        if custom_error:
            if not custom_error.startswith("{") or custom_error.startswith(
                    "{"+namespaces.xmlstream+"}"):
                raise ValueError("Custom error has incorrect namespace")
            node.append(node.makeelement(custom_error))
        self._tx_send_node(node)
        del node

    # asyncio Protocol implementation

    def connection_made(self, using_transport):
        if self._state != _State.UNCONNECTED:
            raise self._invalid_transition(via="connection_made")

        self._transport = using_transport
        self._state = _State.CONNECTED
        self._conn_exc = None
        self.reset_stream()

    def data_received(self, blob):
        if not self._state.rx_open:
            self._invalid_state("received data")
            return

        logger.debug("RECV %s", blob)
        try:
            self._rx_feed(blob)
        except errors.SendStreamError as err:
            self._tx_stream_error(err.error_tag, err.text)
            self.hard_close(ConnectionError("Stream error was sent: {}".format(err)))

    def eof_received(self):
        if self._state == _State.UNCONNECTED:
            self._invalid_state("received eof")
            return

        try:
            if self._state.rx_open:
                self._rx_close()
        except:
            logger.exception("during eof_received")
            raise

        return True

    def pause_writing(self):
        logger.warn("pause_writing not implemented")

    def resume_writing(self):
        logger.warn("resume_writing not implemented")

    def connection_lost(self, exc):
        if self._state == _State.UNCONNECTED:
            raise self._invalid_transition(via="connection_lost")
        exc = exc or self._conn_exc
        try:
            if self._state != _State.CLOSING:
                # cannot send anything anymore, assume closed tx
                self._state = self._state.with_closed_tx()
                self.close()
            self._state = _State.UNCONNECTED
        finally:
            if self._waiter is not None:
                if exc:
                    self._loop.call_soon(self._waiter.set_exception, exc)
                else:
                    self._loop.call_soon(self._waiter.set_result, None)
                self._waiter = None
            self._rx_context = None
            self._transport = None
            self._stream_level_node_hooks.close_all(
                ConnectionError("Disconnected"))
            if self.on_connection_lost:
                self.on_connection_lost(exc)

    def starttls_made(self, transport):
        if self.on_starttls_engaged:
            self.on_starttls_engaged(transport)

    # public API

    def hard_close(self, exc):
        """
        Force closing of the stream, without waiting for the remote side to
        close the stream, too.
        """
        if self._state == _State.UNCONNECTED:
            logger.warning("trying to hard-close an unconnected stream",
                           stack_info=True)
            return

        self._conn_exc = exc
        self._tx_close()
        self._rx_close()

    def close(self, *, waiter=None):
        """
        Close our side of the stream. The stream will remain open until the
        remote side closes the stream, too.

        If *waiter* is not :data:`None`, it must be a
        :class:`asyncio.Future`. This future will receive either the result
        :data:`None` (if the stream shuts down successfully) or an exception if
        the stream terminates non-cleanly.
        """

        if self._state == _State.UNCONNECTED:
            # logger.warning("trying to close an unconnected stream",
            #                stack_info=True)
            if waiter:
                self._loop.call_soon(waiter.set_result, None)
            return

        self._waiter = waiter
        if self._state.connected or self._state.tx_open:
            self._tx_close()
            return False
        elif self._state.rx_open:
            self._rx_close()
            return True
        else:
            try:
                raise self._invalid_state("close() called")
            except Exception as err:
                self._loop.call_soon(self._waiter.set_exception, err)
                self._waiter = None
                raise

    @asyncio.coroutine
    def close_and_wait(self, timeout=None):
        """
        Close and wait for the stream to be closed.

        If *timeout* is not :data:`None` and the remote side takes longer than
        that to reply, the stream is closed using :meth:`hard_close`.

        This calls :meth:`close` with a *waiter* future internally.
        """

        logger.debug("closing stream and waiting for closure (timeout=%r)",
                     timeout)
        fut = asyncio.Future()
        self.close(waiter=fut)
        try:
            if timeout is not None:
                yield from asyncio.wait_for(fut, timeout=timeout)
            else:
                yield from fut
        except asyncio.TimeoutError:
            if not fut.done() or fut.cancelled():
                logger.debug("timeout while closing, performing hard close")
                # we have to guard against the case that the future raises a
                # timeout error
                self.hard_close(None)
            raise

    @property
    def closed(self):
        return not self._state.connected

    def reset_stream(self):
        if not self._state.connected:
            raise self._invalid_transition(via="reset_stream",
                                           to=_State.CONNECTED)
        self._rx_reset()
        self._tx_reset()
        self._state = _State.CONNECTED

    @asyncio.coroutine
    def reset_stream_and_get_features(self, timeout):
        future = self.wait_for(
            [
                "{{{}}}features".format(namespaces.xmlstream)
            ],
            timeout=timeout
        )
        try:
            self.reset_stream()
        except:
            future.cancel()
            raise
        return (yield from future)

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
                    logger.warn("critical timeout while waiting for any of %r",
                                tags)
                    yield from self.stream_error("connection-timeout", None)
                    raise ConnectionError("Disconnected")
                raise TimeoutError("Timeout")

            result = next(iter(done)).result()
            return result

        return waiter_task(futures, timeout, critical_timeout)

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
        if not self._state.stream_usable:
            raise ConnectionError("Stream is not usable (state is {})".format(
                self._state))
        self._tx_send_node(node)

    @asyncio.coroutine
    def stream_error(self, tag, text, custom_error=None, timeout=2):
        self._tx_stream_error(tag, text, custom_error=custom_error)
        try:
            yield from self.close_and_wait(timeout=timeout)
        except asyncio.TimeoutError:
            pass

    @property
    def stream_level_hooks(self):
        return self._stream_level_node_hooks

    @property
    def transport(self):
        return self._transport
