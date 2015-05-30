"""
:mod:`~aioxmpp.protocol` --- XML Stream implementation
######################################################

This module contains the :class:`XMLStream` class, which implements the XML
stream protocol used by XMPP. It makes extensive use of the :mod:`aioxmpp.xml`
module and the :mod:`aioxmpp.xso` subpackage to parse and serialize XSOs
received and sent on the stream.

In addition, helper functions to work with :class:`XMLStream` instances are
provided; these are not included in the class itself because they provide
additional functionality solely based on the public interface of the
class. Separating them helps with testing.

.. autoclass:: XMLStream

Utilities for XML streams
=========================

.. autofunction:: send_and_wait_for

.. autofunction:: reset_stream_and_get_features

Enumerations
============

.. autoclass:: Mode

.. autoclass:: State

"""

import asyncio
import inspect
import logging

from enum import Enum

import xml.sax as sax
import xml.parsers.expat as pyexpat

from . import xml, errors, xso, stream_xsos, stanza, callbacks
from .utils import namespaces

logger = logging.getLogger(__name__)


class Mode(Enum):
    """
    Possible modes of connection for an XML stream. These define the namespaces
    used.

    .. attribute:: C2S

       A client stream connected to a server. This is the default mode and,
       currently, the only available mode.

    """
    C2S = namespaces.client


class State(Enum):
    """
    The possible states of a :class:`XMLStream`:

    .. attribute:: CLOSED

       The initial state; this is the case when no underlying transport is
       connected. This state is entered from any other state when the
       underlying transport calls :meth:`XMLStream.connection_lost` on the xml
       stream.

    .. attribute:: STREAM_HEADER_SENT

       After a :class:`asyncio.Transport` calls
       :meth:`XMLStream.connection_made` on the xml stream, it sends the stream
       header and enters this state.

    .. attribute:: OPEN

       When the stream header of the peer is received, this state is entered
       and the XML stream can be used for sending and receiving XSOs.

    .. attribute:: CLOSING

       After :meth:`XMLStream.close` is called, this state is entered. The
       underlying transport was asked to close itself.

    """

    CLOSED = 0
    STREAM_HEADER_SENT = 1
    OPEN = 2
    CLOSING = 3


class XMLStream(asyncio.Protocol):
    """
    XML stream implementation. This is an streaming :class:`asyncio.Protocol`
    which translates the received bytes into XSOs.

    *to* must be a domain :class:`~aioxmpp.structs.JID` which identifies the
    domain to which the stream shall connect.

    *features_future* must be a :class:`asyncio.Future` instance; the XML
    stream will set the first :class:`~aioxmpp.stream_xsos.StreamFeatures` node
    it receives as the result of the future.

    *sorted_attributes* is mainly for unittesting purposes; this is an argument
    to the :class:`~aioxmpp.xml.XMPPXMLGenerator` and slows down the XML
    serialization, but produces deterministic results, which is important for
    testing. Generally, it is preferred to leave this argument at its default.

    *base_logger* may be a :class:`logging.Logger` instance to use. The XML
    stream will create a child called ``XMLStream`` at that logger and use that
    child for logging purposes. This eases debugging and allows for
    connection-specific loggers.

    Receiving XSOs:

    .. attribute:: stanza_parser

       A :class:`~aioxmpp.xso.XSOParser` instance which is wired to a
       :class:`~aioxmpp.xml.XMPPXMLProcessor` which processes the received
       bytes.

       To receive XSOs over the XML stream, use :attr:`stanza_parser` and
       register class callbacks on it using
       :meth:`~aioxmpp.xso.XSOParser.add_class`.

    Sending XSOs:

    .. automethod:: send_xso

    Manipulating stream state:

    .. automethod:: starttls

    .. automethod:: reset

    .. automethod:: close

    Signals:

    .. autoattribute:: on_failure

       A :class:`~aioxmpp.callbacks.Signal` which fires when the underlying
       transport of the stream reports an error or when a stream error is
       received. The signal is fired with the corresponding exception as the
       only argument.

       When the callback is fired, the stream is already in
       :attr:`~State.CLOSED` state.

    """

    on_failure = callbacks.Signal()

    def __init__(self, to,
                 features_future,
                 sorted_attributes=False,
                 base_logger=logging.getLogger("aioxmpp")):
        self._to = to
        self._sorted_attributes = sorted_attributes
        self._state = State.CLOSED
        self._logger = base_logger.getChild("XMLStream")
        self._transport = None
        self._features_future = features_future
        self._exception = None
        self.stanza_parser = xso.XSOParser()
        self.stanza_parser.add_class(stream_xsos.StreamError,
                                     self._rx_stream_error)
        self.stanza_parser.add_class(stream_xsos.StreamFeatures,
                                     self._rx_stream_features)

    def _invalid_transition(self, to, via=None):
        text = "invalid state transition: from={} to={}".format(
            self._state,
            to)
        if via:
            text += " (via: {})".format(via)
        return RuntimeError(text)

    def _invalid_state(self, at=None):
        text = "invalid state: {}".format(self._state)
        if at:
            text += " (at: {})".format(at)
        return RuntimeError(text)

    def _fail(self, err):
        # TODO: shall we do something pointful with the error here?
        self._exception = err
        self.close()

    def _require_connection(self, accept_partial=False):
        if     (self._state == State.OPEN
                or (accept_partial
                    and self._state == State.STREAM_HEADER_SENT)):
            return

        if self._exception:
            raise self._exception

        raise ConnectionError("xmlstream not connected")

    def _rx_exception(self, exc):
        try:
            raise exc
        except stanza.PayloadParsingError as exc:
            iq_response = exc.partial_obj.make_reply(type_="error")
            iq_response.error = stanza.Error(
                condition=(namespaces.stanzas, "bad-request"),
                type_="modify",
                text=str(exc.__context__)
            )
            self._writer.send(iq_response)
        except stanza.UnknownIQPayload as exc:
            iq_response = exc.partial_obj.make_reply(type_="error")
            iq_response.error = stanza.Error(
                condition=(namespaces.stanzas, "feature-not-implemented"),
                type_="cancel",
            )
            self._writer.send(iq_response)
        except xso.UnknownTopLevelTag as exc:
            raise errors.StreamError(
                condition=(namespaces.streams, "unsupported-stanza-type"),
                text="unsupported stanza: {}".format(
                    xso.tag_to_str((exc.ev_args[0], exc.ev_args[1]))
                )) from None
        except:
            raise

    def _rx_stream_header(self):
        if self._processor.remote_version != (1, 0):
            raise errors.StreamError(
                (namespaces.streams, "unsupported-version"),
                text="unsupported version")
        self._state = State.OPEN

    def _rx_stream_error(self, err):
        self._fail(err.to_exception())

    def _rx_stream_footer(self):
        self.close()

    def _rx_stream_features(self, features):
        self.stanza_parser.remove_class(stream_xsos.StreamFeatures)
        self._features_future.set_result(features)
        self._features_future = None

    def _rx_feed(self, blob):
        try:
            self._parser.feed(blob)
        except sax.SAXParseException as exc:
            if     (exc.getException().args[0].startswith(
                    pyexpat.errors.XML_ERROR_UNDEFINED_ENTITY)):
                # this will raise an appropriate stream error
                xml.XMPPLexicalHandler.startEntity("foo")
            raise errors.StreamError(
                condition=(namespaces.streams, "bad-format"),
                text=str(exc)
            )
        except errors.StreamError as exc:
            raise
        except Exception as exc:
            self._logger.exception(
                "unexpected exception while parsing stanza"
                " bubbled up through parser. stream so ded.")
            raise errors.StreamError(
                condition=(namespaces.streams, "internal-server-error"),
                text="Internal error while parsing XML. Client logs have more"
                     " details."
            )

    def connection_made(self, transport):
        if self._state != State.CLOSED:
            raise self._invalid_state("connection_made")

        assert self._transport is None
        self._transport = transport
        self._writer = None
        self._exception = None
        # we need to set the state before we call reset()
        self._state = State.STREAM_HEADER_SENT
        self.reset()

    def connection_lost(self, exc):
        if self._state == State.CLOSED:
            return
        self._state = State.CLOSED
        self._exception = self._exception or exc
        self._kill_state()
        self._writer = None
        self._transport = None

        if self._exception is not None:
            self.on_failure(self._exception)

    def data_received(self, blob):
        self._logger.debug("RECV %r", blob)
        try:
            self._rx_feed(blob)
        except errors.StreamError as exc:
            stanza_obj = stream_xsos.StreamError.from_exception(exc)
            self._writer.send(stanza_obj)
            self._fail(exc)

    def close(self):
        """
        Close the XML stream and the underlying transport.

        This gracefully shuts down the XML stream and the transport, if
        possible by writing the eof using :meth:`asyncio.Transport.write_eof`
        after sending the stream footer.

        After a call to :meth:`close`, no other stream manipulating or sending
        method can be called; doing so will result in a
        :class:`ConnectionError` exception or any exception caused by the
        transport during shutdown.

        Calling :meth:`close` while the stream is closing or closed is a
        no-op.
        """
        if self._state == State.CLOSING or self._state == State.CLOSED:
            return
        self._state = State.CLOSING
        self._writer.close()
        if self._transport.can_write_eof():
            self._transport.write_eof()
        self._transport.close()

    def _kill_state(self):
        if self._writer:
            if inspect.getgeneratorstate(self._writer) == "GEN_SUSPENDED":
                try:
                    self._writer.throw(xml.AbortStream())
                except StopIteration:
                    pass
            else:
                self._writer = None

        self._processor = None
        self._parser = None

    def _reset_state(self):
        self._kill_state()

        self._processor = xml.XMPPXMLProcessor()
        self._processor.stanza_parser = self.stanza_parser
        self._processor.on_stream_header = self._rx_stream_header
        self._processor.on_stream_footer = self._rx_stream_footer
        self._processor.on_exception = self._rx_exception
        self._parser = xml.make_parser()
        self._parser.setContentHandler(self._processor)

        self._writer = xml.write_objects(
            self._transport,
            self._to,
            nsmap={None: "jabber:client"},
            sorted_attributes=self._sorted_attributes)

    def reset(self):
        """
        Reset the stream by discarding all state and re-sending the stream
        header.

        Calling :meth:`reset` when the stream is disconnected or currently
        disconnecting results in either :class:`ConnectionError` being raised
        or the exception which caused the stream to die (possibly a received
        stream error or a transport error) to be reraised.

        :meth:`reset` puts the stream into :attr:`~State.STREAM_HEADER_SENT`
        state and it cannot be used for sending XSOs until the peer stream
        header has been received. Usually, this is not a problem as stream
        resets only occur during stream negotiation and stream negotiation
        typically waits for the peers feature node to arrive first.
        """
        self._require_connection(accept_partial=True)
        self._reset_state()
        next(self._writer)
        self._state = State.STREAM_HEADER_SENT

    def send_xso(self, obj):
        """
        Send an XSO *obj* over the stream.

        Calling :meth:`send_xso` while the stream is disconnected,
        disconnecting or still waiting for the remote to send a stream header
        causes :class:`ConnectionError` to be raised. If the stream got
        disconnected due to a transport or stream error, that exception is
        re-raised instead of the :class:`ConnectionError`.
        """
        self._require_connection()
        self._writer.send(obj)

    def can_starttls(self):
        """
        Return true if the transport supports STARTTLS and false otherwise.

        If the stream is currently not connected, this returns false.
        """
        return (hasattr(self._transport, "can_starttls") and
                self._transport.can_starttls())

    @asyncio.coroutine
    def starttls(self, ssl_context, post_handshake_callback=None):
        """
        Start TLS on the transport and wait for it to complete.

        The *ssl_context* and *post_handshake_callback* arguments are forwarded
        to the transports
        :meth:`~aioxmpp.ssl_transport.STARTTLSTransport.starttls` coroutine
        method.

        If the transport does not support starttls, :class:`RuntimeError` is
        raised; support for starttls can be discovered by querying
        :meth:`can_starttls`.

        After :meth:`starttls` returns, you must call :meth:`reset`. Any other
        method may fail in interesting ways as the internal state is discarded
        when starttls succeeds, for security reasons. :meth:`reset` re-creates
        the internal structures.
        """
        self._require_connection()
        if not self.can_starttls():
            raise RuntimeError("starttls not available on transport")

        yield from self._transport.starttls(ssl_context,
                                            post_handshake_callback)
        self._reset_state()

    @property
    def transport(self):
        """
        The underlying :class:`asyncio.Transport` instance. This attribute is
        :data:`None` if the :class:`XMLStream` is currently not connected.

        This attribute cannot be set.
        """
        return self._transport

    @property
    def state(self):
        """
        The current :class:`State` of the XML stream.

        This attribute cannot be set.
        """
        return self._state


@asyncio.coroutine
def send_and_wait_for(xmlstream, send, wait_for, timeout=None):
    fut = asyncio.Future()
    wait_for = list(wait_for)

    def cleanup():
        for anticipated_cls in wait_for:
            xmlstream.stanza_parser.remove_class(anticipated_cls)

    def receive(obj):
        nonlocal fut
        fut.set_result(obj)
        cleanup()

    for anticipated_cls in wait_for:
        xmlstream.stanza_parser.add_class(
            anticipated_cls,
            receive)

    try:
        for to_send in send:
            xmlstream.send_xso(to_send)

        if timeout is not None and timeout >= 0:
            return (yield from asyncio.wait_for(fut, timeout))

        return (yield from fut)
    except:
        cleanup()
        raise


@asyncio.coroutine
def reset_stream_and_get_features(xmlstream, timeout=None):
    fut = asyncio.Future()

    def cleanup():
        xmlstream.stanza_parser.remove_class(stream_xsos.StreamFeatures)

    def receive(obj):
        nonlocal fut
        fut.set_result(obj)
        cleanup()

    xmlstream.stanza_parser.add_class(
        stream_xsos.StreamFeatures,
        receive)

    try:
        xmlstream.reset()

        if timeout is not None and timeout >= 0:
            return (yield from asyncio.wait_for(fut, timeout))

        return (yield from fut)
    except:
        cleanup()
        raise


def send_stream_error_and_close(
        xmlstream,
        condition,
        text,
        custom_condition=None):
    xmlstream.send_xso(stream_xsos.StreamError(
        condition=condition,
        text=text))
    if custom_condition is not None:
        logger.warn("custom_condition argument to send_stream_error_and_close"
                    " not implemented")
    xmlstream.close()
