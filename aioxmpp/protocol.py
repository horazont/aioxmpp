########################################################################
# File name: protocol.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
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
import contextlib
import functools
import logging

from enum import Enum

import xml.sax as sax
import xml.parsers.expat as pyexpat

from . import xml, errors, xso, nonza, stanza, callbacks, statemachine, utils
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
        self._total_len = 0
        self._muted = False
        self._written_mute_marker = False

    def _emit(self):
        self.logger.debug("SENT %r", b"".join(self._pieces))
        self._pieces = []
        self._total_len = 0

    def write(self, data):
        if self._muted:
            if not self._written_mute_marker:
                self._pieces.append(b"<!-- some bytes omitted -->")
                self._written_mute_marker = True
        else:
            self._pieces.append(data)
            self._total_len += len(data)
        result = self.dest.write(data)
        if self._total_len >= 4096:
            self._emit()
        return result

    def flush(self):
        self._emit()
        self._flush()

    @contextlib.contextmanager
    def mute(self):
        self._muted = True
        self._written_mute_marker = False
        try:
            yield
        finally:
            self._muted = False


class XMLStream(asyncio.Protocol):
    """
    XML stream implementation. This is an streaming :class:`asyncio.Protocol`
    which translates the received bytes into XSOs.

    :param to: Domain of the server the stream connects to.
    :type to: :class:`~aioxmpp.JID`
    :param features_future: Use :meth:`features_future` instead.
    :type features_future: :class:`asyncio.Future`
    :param sorted_attributes: Sort attributes deterministically on output
        (debug option; not part of the public interface)
    :type sorted_attributes: :class:`bool`
    :param default_namespace: Set the default namespace to advertise on the
        stream header.
    :type default_namespace: :class:`str`
    :param from_: The value of the from attribute of the stream header.
    :tpye from_: :class:`~aioxmpp.JID` or :data:`None`
    :param base_logger: Parent logger for this stream
    :type base_logger: :class:`logging.Logger`

    `to` must identify the remote server to connect to. This is used as the
    ``to`` attribute on the stream header.

    `features_future` may be a future. The XML stream will set the first
    :class:`~aioxmpp.nonza.StreamFeatures` node it receives as the result of
    the future. The future will also receive any pre-stream-features
    exception.

    `sorted_attributes` is a testing/debugging option to enable sorted output
    of the XML attributes emitted on the stream. See
    :class:`~aioxmpp.xml.XMPPXMLGenerator` for details. Do not use outside of
    unit testing code, as it has a negative performance impact.

    `base_logger` may be a :class:`logging.Logger` instance to use. The XML
    stream will create a child called ``XMLStream`` at that logger and use that
    child for logging purposes. This eases debugging and allows for
    connection-specific loggers.

    .. deprecated:: 0.12

        Using `features_future` as positional or keyword argument is
        deprecated and will be removed in version 1.0. Use
        :meth:`features_future` to obtain a future instead.

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

    Controlling debug output:

    .. automethod:: mute

    Waiting for stream state changes:

    .. automethod:: error_future

    .. automethod:: features_future

    Monitoring stream aliveness:

    .. autoattribute:: deadtime_soft_limit

    .. autoattribute:: deadtime_hard_limit

    Signals:

    .. signal:: on_closing(reason)

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

    .. signal:: on_deadtime_soft_limit_tripped

        Emits when the soft limit dead time has been exceeded.

        See :attr:`deadtime_soft_limit` for general information on the timeout
        handling.

        .. versionadded:: 0.10

    Timeouts:

    .. attribute:: shutdown_timeout

       The maximum time to wait for the peer ``</stream:stream>`` before
       forcing to close the transport and considering the stream closed.

    """

    on_closing = callbacks.Signal()
    on_deadtime_soft_limit_tripped = callbacks.Signal()

    shutdown_timeout = 15

    def __init__(self, to,
                 features_future=None,
                 sorted_attributes=False,
                 base_logger=logging.getLogger("aioxmpp"),
                 default_namespace="jabber:client",
                 from_=None,
                 loop=None):
        self._to = to
        self._from = from_
        self._sorted_attributes = sorted_attributes
        self._logger = base_logger.getChild("XMLStream")
        self._transport = None
        self._exception = None
        self._loop = loop or asyncio.get_event_loop()
        self._features_futures = []
        self._error_futures = []
        if features_future is not None:
            self._features_futures.append(features_future)
            self._error_futures.append(features_future)
        self._smachine = statemachine.OrderedStateMachine(State.READY)
        self._transport_closing = False
        self._default_namespace = default_namespace
        self._monitor = utils.AlivenessMonitor(self._loop)
        self._monitor.on_deadtime_hard_limit_tripped.connect(
            self._deadtime_hard_limit_triggered
        )
        self._monitor.on_deadtime_soft_limit_tripped.connect(
            self.on_deadtime_soft_limit_tripped
        )

        self._closing_future = asyncio.ensure_future(
            self._smachine.wait_for(
                State.CLOSING
            ),
            loop=loop
        )
        self._closing_future.add_done_callback(
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

        if task.cancelled():
            return
        if task.exception() is not None:
            return
        task.result()

    def _fail(self, err):
        self._exception = err
        self.close()

    def _require_connection(self, accept_partial=False):
        if (self._smachine.state == State.OPEN or
                (accept_partial and
                 self._smachine.state == State.STREAM_HEADER_SENT)):
            return

        if self._exception:
            raise self._exception

        raise ConnectionError("xmlstream not connected")

    def _rx_exception(self, exc):
        if isinstance(exc, stanza.StanzaError):
            if self.error_handler:
                self.error_handler(exc.partial_obj, exc)
        elif isinstance(exc, xso.UnknownTopLevelTag):
            if self._smachine.state >= State.CLOSING:
                self._logger.info("ignoring unknown top-level tag, "
                                  "we’re closing")
                return

            raise errors.StreamError(
                condition=errors.StreamErrorCondition.UNSUPPORTED_STANZA_TYPE,
                text="unsupported stanza: {}".format(
                    xso.tag_to_str((exc.ev_args[0], exc.ev_args[1]))
                )) from None
        else:
            context = exc.__context__ or exc.__cause__
            raise exc from context

    def _rx_stream_header(self):
        if self._processor.remote_version != (1, 0):
            raise errors.StreamError(
                errors.StreamErrorCondition.UNSUPPORTED_VERSION,
                text="unsupported version"
            )
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
        for fut in self._features_futures:
            if fut.done():
                continue
            fut.set_result(features)
            try:
                self._error_futures.remove(fut)
            except ValueError:
                pass
        self._features_futures.clear()

    def _rx_feed(self, blob):
        try:
            self._parser.feed(blob)
        except sax.SAXParseException as exc:
            if (exc.getException().args[0].startswith(
                    pyexpat.errors.XML_ERROR_UNDEFINED_ENTITY)):
                # this will raise an appropriate stream error
                xml.XMPPLexicalHandler.startEntity("foo")
            raise errors.StreamError(
                condition=errors.StreamErrorCondition.BAD_FORMAT,
                text=str(exc)
            )
        except errors.StreamError:
            raise
        except Exception:
            self._logger.exception(
                "unexpected exception while parsing stanza"
                " bubbled up through parser. stream so dead.")
            raise errors.StreamError(
                condition=errors.StreamErrorCondition.INTERNAL_SERVER_ERROR,
                text="Internal error while parsing XML. Client logs have more"
                     " details."
            )

    def _deadtime_hard_limit_triggered(self):
        self._logger.debug("dead time hard limit exceeded")
        # pretend full shut-down handshake has happened
        if self._smachine.state != State.CLOSED:
            self._smachine.state = State.CLOSING_STREAM_FOOTER_RECEIVED
        self._transport_closing = True
        if self._transport is not None:
            self._transport.abort()
        self._exception = self._exception or ConnectionError(
            "connection timeout (dead time hard limit exceeded)"
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
        self._monitor.deadtime_hard_limit = None
        self._monitor.deadtime_soft_limit = None
        self._closing_future.cancel()

    def data_received(self, blob):
        self._logger.debug("RECV %r", blob)
        self._monitor.notify_received()
        try:
            self._rx_feed(blob)
        except errors.StreamError as exc:
            stanza_obj = nonza.StreamError.from_exception(exc)
            if not self._writer.closed:
                self._writer.send(stanza_obj)
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
            self._logger.warning("unexpected eof_received (in %s state)",
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
        if (self._smachine.state == State.CLOSING or
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

    async def close_and_wait(self):
        """
        Close the XML stream and the underlying transport and wait for for the
        XML stream to be properly terminated.

        The underlying transport may still be open when this coroutine returns,
        but closing has already been initiated.

        The other remarks about :meth:`close` hold.
        """
        self.close()
        await self._smachine.wait_for_at_least(
            State.CLOSING_STREAM_FOOTER_RECEIVED
        )

    def _kill_state(self):
        if self._writer:
            self._writer.abort()

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
        self._debug_wrapper = None

        if self._logger.getEffectiveLevel() <= logging.DEBUG:
            dest = DebugWrapper(self._transport, self._logger)
            self._debug_wrapper = dest
        else:
            dest = self._transport
        self._writer = xml.XMLStreamWriter(
            dest,
            self._to,
            nsmap={None: self._default_namespace},
            from_=self._from,
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
        self._writer.start()
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
        if self._smachine.state == State.READY:
            self._smachine.state = State.CLOSED
            return
        if (self._smachine.state != State.CLOSING and
                self._transport.can_write_eof()):
            self._transport.write_eof()
        self._close_transport()

    def send_xso(self, obj):
        """
        Send an XSO over the stream.

        :param obj: The object to send.
        :type obj: :class:`~.XSO`
        :raises ConnectionError: if the connection is not fully established
                                 yet.
        :raises aioxmpp.errors.StreamError: if a stream error was received or
                                            sent.
        :raises OSError: if the stream got disconnected due to a another
                         permanent transport error
        :raises Exception: if serialisation of `obj` failed

        Calling :meth:`send_xso` while the stream is disconnected,
        disconnecting or still waiting for the remote to send a stream header
        causes :class:`ConnectionError` to be raised. If the stream got
        disconnected due to a transport or stream error, that exception is
        re-raised instead of the :class:`ConnectionError`.

        .. versionchanged:: 0.9

           Exceptions occurring during serialisation of `obj` are re-raised and
           *no* content is sent over the stream. The stream is still valid and
           usable afterwards.

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

    async def starttls(self, ssl_context, post_handshake_callback=None):
        """
        Start TLS on the transport and wait for it to complete.

        The `ssl_context` and `post_handshake_callback` arguments are forwarded
        to the transports
        :meth:`aioopenssl.STARTTLSTransport.starttls` coroutine method.

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

        await self._transport.starttls(ssl_context, post_handshake_callback)
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

    def features_future(self):
        """
        Return a future which will receive the next XML stream features (as
        return value) or the next XML stream error (as exception), whichever
        happens first.

        It is safe to cancel this future at any time.
        """
        fut = self.error_future()
        self._features_futures.append(fut)
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

    @contextlib.contextmanager
    def mute(self):
        """
        A context-manager which prohibits logging of data sent over the stream.

        Data sent over the stream is replaced with
        ``<!-- some bytes omitted -->``. This is mainly useful during
        authentication.
        """
        if self._debug_wrapper is None:
            yield
        else:
            with self._debug_wrapper.mute():
                yield

    @property
    def deadtime_soft_limit(self):
        """
        This is part of the timeout handling of :class:`XMLStream` objects. The
        timeout handling works like this:

        * There exist two timers, *soft* and *hard* limit.
        * Reception of *any* data resets both timers.
        * When the *soft* limit timer is triggered, the
          :meth:`on_deadtime_soft_limit_tripped` signal is emitted. Nothing
          else happens. The user is expected to do something which would cause
          the server to send data to prevent the *hard* limit from tripping.
        * When the *hard* limit timer is triggered, the stream is considered
          dead and it is aborted and closed with an appropriate
          :class:`ConnectionError`.

        This attribute controls the timeout for the *soft* limit timer, as
        :class:`datetime.timedelta`. The default is :data:`None`, which
        disables the timer altogether.

        .. versionadded:: 0.10
        """
        return self._monitor.deadtime_soft_limit

    @deadtime_soft_limit.setter
    def deadtime_soft_limit(self, value):
        self._monitor.deadtime_soft_limit = value

    @property
    def deadtime_hard_limit(self):
        """
        This is part of the timeout handling of :class:`XMLStream` objects.
        See :attr:`deadtime_soft_limit` for details.

        This attribute controls the timeout for the *hard* limit timer, as
        :class:`datetime.timedelta`. The default is :data:`None`, which
        disables the timer altogether.

        Setting the *hard* limit timer to :data:`None` means that the
        :class:`XMLStream` will never timeout by itself.

        .. versionadded:: 0.10
        """
        return self._monitor.deadtime_hard_limit

    @deadtime_hard_limit.setter
    def deadtime_hard_limit(self, value):
        self._monitor.deadtime_hard_limit = value


async def send_and_wait_for(xmlstream, send, wait_for,
                            timeout=None,
                            cb=None):
    fut = asyncio.Future()
    wait_for = list(wait_for)

    def receive(obj):
        nonlocal fut, stack
        if cb is not None:
            cb(obj)
        fut.set_result(obj)
        stack.close()

    failure_future = xmlstream.error_future()

    with contextlib.ExitStack() as stack:
        for anticipated_cls in wait_for:
            xmlstream.stanza_parser.add_class(
                anticipated_cls,
                receive)
            stack.callback(
                xmlstream.stanza_parser.remove_class,
                anticipated_cls,
            )

        for to_send in send:
            xmlstream.send_xso(to_send)

        done, pending = await asyncio.wait(
            [
                fut,
                failure_future,
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for other_fut in pending:
            other_fut.cancel()

        if fut in done:
            return fut.result()

        if failure_future in done:
            failure_future.result()
        else:
            failure_future.cancel()

        raise TimeoutError()


async def reset_stream_and_get_features(xmlstream, timeout=None):
    xmlstream.reset()
    fut = xmlstream.features_future()
    if timeout is not None:
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError from None
    else:
        result = await xmlstream.features_future()
    return result


def send_stream_error_and_close(
        xmlstream,
        condition,
        text,
        custom_condition=None):
    xmlstream.send_xso(nonza.StreamError(
        condition=condition,
        text=text))
    if custom_condition is not None:
        logger.warning(
            "custom_condition argument to send_stream_error_and_close"
            " not implemented",
        )
    xmlstream.close()
