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
import functools
import inspect
import logging

from enum import Enum

import xml.sax as sax
import xml.parsers.expat as pyexpat

from . import xml, errors, xso, nonza, stanza, callbacks, statemachine
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


@functools.total_ordering
class State(Enum):
    """
    The possible states of a :class:`XMLStream`:

    .. attribute:: READY

       The initial state; this is the case when no underlying transport is
       connected.

    .. attribute:: STREAM_HEADER_SENT

       After a :class:`asyncio.Transport` calls
       :meth:`XMLStream.connection_made` on the xml stream, it sends the stream
       header and enters this state.

    .. attribute:: OPEN

       When the stream header of the peer is received, this state is entered
       and the XML stream can be used for sending and receiving XSOs.

    .. attribute:: CLOSING

       After :meth:`XMLStream.close` is called, this state is entered. We sent
       a stream footer and an EOF, if the underlying transport supports
       this. We still have to wait for the peer to close the stream.

       In this state and all following states, :class:`ConnectionError`
       instances are raised whenever an attempt is made to write to the
       stream. The exact instance depends on the reason of the closure.

       In this state, the stream waits for the remote to send a stream footer
       and the connection to shut down. For application purposes, the stream is
       already closed.

    .. attribute:: CLOSING_STREAM_FOOTER_RECEIVED

       At this point, the stream is properly closed on the XML stream
       level. This is the point where :meth:`XMLStream.close_and_wait`
       returns.

    .. attribute:: CLOSED

       This state is entered when the connection is lost in any way. This is
       the final state.

    """

    def __lt__(self, other):
        return self.value < other.value

    READY = 0
    STREAM_HEADER_SENT = 1
    OPEN = 2
    CLOSING = 3
    CLOSING_STREAM_FOOTER_RECEIVED = 4
    CLOSED = 6


class DebugWrapper:
    def __init__(self, dest, logger):
        self.dest = dest
        self.logger = logger
        if hasattr(dest, "flush"):
            self._flush = dest.flush
        else:
            self._flush = lambda: None
        self._pieces = []

    def write(self, data):
        self._pieces.append(data)
        self.dest.write(data)

    def flush(self):
        self.logger.debug("SENT %r", b"".join(self._pieces))
        self._pieces = []
        self._flush


class XMLStream(asyncio.Protocol):
    """
    XML stream implementation. This is an streaming :class:`asyncio.Protocol`
    which translates the received bytes into XSOs.

    `to` must be a domain :class:`~aioxmpp.structs.JID` which identifies the
    domain to which the stream shall connect.

    `features_future` must be a :class:`asyncio.Future` instance; the XML
    stream will set the first :class:`~aioxmpp.nonza.StreamFeatures` node
    it receives as the result of the future.

    `sorted_attributes` is mainly for unittesting purposes; this is an argument
    to the :class:`~aioxmpp.xml.XMPPXMLGenerator` and slows down the XML
    serialization, but produces deterministic results, which is important for
    testing. Generally, it is preferred to leave this argument at its default.

    `base_logger` may be a :class:`logging.Logger` instance to use. The XML
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

    .. attribute:: error_handler

       This should be assigned a callable, taking two arguments: a
       :class:`xso.XSO` instance, which is the partial(!) top-level stream
       element and an exception indicating the failure.

       Partial here means that it is not guaranteed that anything but the
       attributes on the partial XSO itself are there. Any children or text
       payload is most likely missing, as it probably caused the error.

       .. versionadded:: 0.4

    Sending XSOs:

    .. automethod:: send_xso

    Manipulating stream state:

    .. automethod:: starttls

    .. automethod:: reset

    .. automethod:: close

    .. automethod:: abort

    Signals:

    .. signal:: on_closing

       A :class:`~aioxmpp.callbacks.Signal` which fires when the underlying
       transport of the stream reports an error or when a stream error is
       received. The signal is fired with the corresponding exception as the
       only argument.

       If the stream gets closed by the application without any error, the
       argument is :data:`None`.

       By the time the callback fires, the stream is already unusable for
       sending stanzas. It *may* however still receive stanzas, if the stream
       shutdown was initiated by the application and the peer has not yet send
       its stream footer.

       If the application is not able to handle these stanzas, it is legitimate
       to disconnect their handlers from the :attr:`stanza_parser`; the stream
       will be able to deal with unhandled top level stanzas correctly at this
       point (by ignoring them).

    Timeouts:

    .. attribute:: shutdown_timeout

       The maximum time to wait for the peer ``</stream:stream>`` before
       forcing to close the transport and considering the stream closed.

    """

    on_closing = callbacks.Signal()
    shutdown_timeout = 15

    def __init__(self, to,
                 features_future,
                 sorted_attributes=False,
                 base_logger=logging.getLogger("aioxmpp"),
                 loop=None):
        self._to = to
        self._sorted_attributes = sorted_attributes
        self._logger = base_logger.getChild("XMLStream")
        self._transport = None
        self._features_future = features_future
        self._exception = None
        self._loop = loop or asyncio.get_event_loop()
        self._error_futures = []
        self._smachine = statemachine.OrderedStateMachine(State.READY)
        self._transport_closing = False

        asyncio.async(
            self._smachine.wait_for(
                State.CLOSING
            ),
            loop=loop
        ).add_done_callback(
            self._stream_starts_closing
        )

        self.stanza_parser = xso.XSOParser()
        self.stanza_parser.add_class(nonza.StreamError,
                                     self._rx_stream_error)
        self.stanza_parser.add_class(nonza.StreamFeatures,
                                     self._rx_stream_features)
        self.error_handler = None

    def _invalid_transition(self, to, via=None):
        text = "invalid state transition: from={} to={}".format(
            self._smachine.state,
            to)
        if via:
            text += " (via: {})".format(via)
        return RuntimeError(text)

    def _invalid_state(self, at=None):
        text = "invalid state: {}".format(self._smachine.state)
        if at:
            text += " (at: {})".format(at)
        return RuntimeError(text)

    def _close_transport(self):
        if self._transport_closing:
            return
        self._transport_closing = True
        self._transport.close()

    def _stream_starts_closing(self, task):
        exc = self._exception
        if exc is None:
            exc = ConnectionError("stream shut down")

        self.on_closing(self._exception)
        for fut in self._error_futures:
            if not fut.done():
                fut.set_exception(exc)
        self._error_futures.clear()

        if task.exception() is not None:
            # this happens if we skip over the CLOSING state, which implies
            # that the stream footer has been seen; no reason to worry about
            # the timeout in that case.
            return
        task.result()

        asyncio.async(
            self._stream_footer_timeout(),
            loop=self._loop
        ).add_done_callback(lambda x: x.result())

    @asyncio.coroutine
    def _stream_footer_timeout(self):
        self._logger.debug(
            "waiting for at most %s seconds for peer stream footer",
            self.shutdown_timeout
        )
        yield from asyncio.sleep(self.shutdown_timeout)
        if self._smachine.state >= State.CLOSING_STREAM_FOOTER_RECEIVED:
            # state already reached, stop
            return
        self._logger.info("timeout while waiting for stream footer")
        self._close_transport()
        self._smachine.state = State.CLOSING_STREAM_FOOTER_RECEIVED

    def _fail(self, err):
        self._exception = err
        self.close()

    def _require_connection(self, accept_partial=False):
        if     (self._smachine.state == State.OPEN
                or (accept_partial
                    and self._smachine.state == State.STREAM_HEADER_SENT)):
            return

        if self._exception:
            raise self._exception

        raise ConnectionError("xmlstream not connected")

    def _rx_exception(self, exc):
        if isinstance(exc, (stanza.PayloadParsingError,
                            stanza.UnknownIQPayload)):
            if self.error_handler:
                self.error_handler(exc.partial_obj, exc)
        elif isinstance(exc, xso.UnknownTopLevelTag):
            if self._smachine.state >= State.CLOSING:
                self._logger.info("ignoring unknown top-level tag, "
                                  "we’re closing")
                return

            raise errors.StreamError(
                condition=(namespaces.streams, "unsupported-stanza-type"),
                text="unsupported stanza: {}".format(
                    xso.tag_to_str((exc.ev_args[0], exc.ev_args[1]))
                )) from None
        else:
            context = exc.__context__ or exc.__cause__
            raise exc from context

    def _rx_stream_header(self):
        if self._processor.remote_version != (1, 0):
            raise errors.StreamError(
                (namespaces.streams, "unsupported-version"),
                text="unsupported version")
        self._smachine.state = State.OPEN

    def _rx_stream_error(self, err):
        self._fail(err.to_exception())

    def _rx_stream_footer(self):
        if self._smachine.state < State.CLOSING:
            # any other state, this is an issue
            if self._exception is None:
                self._fail(ConnectionError("stream closed by peer"))
            self.close()
        elif self._smachine.state >= State.CLOSING_STREAM_FOOTER_RECEIVED:
            self._logger.info("late stream footer received")
            return

        self._close_transport()
        self._smachine.state = State.CLOSING_STREAM_FOOTER_RECEIVED

    def _rx_stream_features(self, features):
        self.stanza_parser.remove_class(nonza.StreamFeatures)
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
        if self._smachine.state != State.READY:
            raise self._invalid_state("connection_made")

        assert self._transport is None
        self._transport = transport
        self._writer = None
        self._exception = None
        # we need to set the state before we call reset()
        self._smachine.state = State.STREAM_HEADER_SENT
        self.reset()

    def connection_lost(self, exc):
        # in connection_lost, we really cannot do anything except shutting down
        # the stream without sending any more data
        if self._smachine.state == State.CLOSED:
            return
        self._smachine.state = State.CLOSED
        self._exception = self._exception or exc
        self._kill_state()
        self._writer = None
        self._transport = None

    def data_received(self, blob):
        self._logger.debug("RECV %r", blob)
        try:
            self._rx_feed(blob)
        except errors.StreamError as exc:
            stanza_obj = nonza.StreamError.from_exception(exc)
            try:
                self._writer.send(stanza_obj)
            except StopIteration:
                pass
            self._fail(exc)
            # shutdown, we do not really care about </stream:stream> by the
            # server at this point
            self._close_transport()

    def eof_received(self):
        if self._smachine.state == State.OPEN:
            # close and set to EOF received
            self.close()
            # common actions below
        elif (self._smachine.state == State.CLOSING or
              self._smachine.state == State.CLOSING_STREAM_FOOTER_RECEIVED):
            # these states are fine, common actions below
            pass
        else:
            self._logger.warn("unexpected eof_received (in %s state)",
                              self._smachine.state)
            # common actions below

        self._smachine.state = State.CLOSING_STREAM_FOOTER_RECEIVED
        self._close_transport()

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
        if     (self._smachine.state == State.CLOSING or
                self._smachine.state == State.CLOSED):
            return
        self._writer.close()
        if self._transport.can_write_eof():
            self._transport.write_eof()
        if self._smachine.state == State.STREAM_HEADER_SENT:
            # at this point, we cannot wait for the peer to send
            # </stream:stream>
            self._close_transport()
        self._smachine.state = State.CLOSING

    @asyncio.coroutine
    def close_and_wait(self):
        """
        Close the XML stream and the underlying transport and wait for for the
        XML stream to be properly terminated.

        The underlying transport may still be open when this coroutine returns,
        but closing has already been initiated.

        The other remarks about :meth:`close` hold.
        """
        self.close()
        yield from self._smachine.wait_for_at_least(
            State.CLOSING_STREAM_FOOTER_RECEIVED
        )

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

        if self._logger.getEffectiveLevel() <= logging.DEBUG:
            dest = DebugWrapper(self._transport, self._logger)
        else:
            dest = self._transport
        self._writer = xml.write_xmlstream(
            dest,
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
        self._smachine.rewind(State.STREAM_HEADER_SENT)

    def abort(self):
        """
        Abort the stream by writing an EOF if possible and closing the
        transport.

        The transport is closed using :meth:`asyncio.BaseTransport.close`, so
        buffered data is sent, but no more data will be received. The stream is
        in :attr:`State.CLOSED` state afterwards.

        This also works if the stream is currently closing, that is, waiting
        for the peer to send a stream footer. In that case, the stream will be
        closed locally as if the stream footer had been received.

        .. versionadded:: 0.5
        """
        if self._smachine.state == State.CLOSED:
            return
        if     (self._smachine.state != State.CLOSING and
                self._transport.can_write_eof()):
            self._transport.write_eof()
        self._close_transport()

    def send_xso(self, obj):
        """
        Send an XSO `obj` over the stream.

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

        The `ssl_context` and `post_handshake_callback` arguments are forwarded
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

    def error_future(self):
        """
        Return a future which will receive the next XML stream error as
        exception.

        It is safe to cancel the future at any time.
        """
        fut = asyncio.Future(loop=self._loop)
        self._error_futures.append(fut)
        return fut

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
        return self._smachine.state


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

    failure_future = xmlstream.error_future()

    for anticipated_cls in wait_for:
        xmlstream.stanza_parser.add_class(
            anticipated_cls,
            receive)

    try:
        for to_send in send:
            xmlstream.send_xso(to_send)

        done, pending = yield from asyncio.wait(
            [
                fut,
                failure_future,
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
            loop=xmlstream._loop)

        for other_fut in pending:
            other_fut.cancel()

        if fut in done:
            return fut.result()

        if failure_future in done:
            failure_future.result()

        raise TimeoutError()
    except:
        cleanup()
        raise


@asyncio.coroutine
def reset_stream_and_get_features(xmlstream, timeout=None):
    fut = asyncio.Future()

    def cleanup():
        xmlstream.stanza_parser.remove_class(nonza.StreamFeatures)

    def receive(obj):
        nonlocal fut
        fut.set_result(obj)
        cleanup()

    failure_future = xmlstream.error_future()

    xmlstream.stanza_parser.add_class(
        nonza.StreamFeatures,
        receive)

    try:
        xmlstream.reset()

        done, pending = yield from asyncio.wait(
            [
                fut,
                failure_future,
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
            loop=xmlstream._loop)

        for other_fut in pending:
            other_fut.cancel()

        if fut in done:
            return fut.result()

        if failure_future in done:
            failure_future.result()

        raise TimeoutError()
    except:
        cleanup()
        raise


def send_stream_error_and_close(
        xmlstream,
        condition,
        text,
        custom_condition=None):
    xmlstream.send_xso(nonza.StreamError(
        condition=condition,
        text=text))
    if custom_condition is not None:
        logger.warn("custom_condition argument to send_stream_error_and_close"
                    " not implemented")
    xmlstream.close()
