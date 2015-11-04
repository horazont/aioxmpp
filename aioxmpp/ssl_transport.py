# This specific file can be used under the conditions of the Apache 2.0
# license. The full license can be found in COPYING.apache20 in the root of
# this software repository.
"""
:mod:`ssl_transport` --- A transport for asyncio using :mod:`OpenSSL`
#######################################################################

This module provides a socket-based :class:`~asyncio.Transport` for
:mod:`asyncio` which supports deferred TLS as used by the STARTTLS
mechanism. In addition it uses :mod:`OpenSSL` instead of the built-in
:mod:`ssl` module, to provide this and more sophisticated functionality.

The following function can be used to create a connection using the
:class:`STARTTLSTransport`, which itself is documented below:

.. autofunction:: create_starttls_connection

The transport implementation is documented below:

.. autoclass:: STARTTLSTransport(loop, rawsock, protocol, ssl_context, [waiter=None], [use_starttls=False], [post_handshake_callback=None], [peer_hostname=None], [server_hostname=None])
   :members:

"""

import asyncio
import logging
import socket

from enum import Enum

import OpenSSL.SSL

from . import errors

logger = logging.getLogger(__name__)


class _State(Enum):
    RAW_OPEN               = 0x0000
    RAW_EOF_RECEIVED       = 0x0001

    TLS_HANDSHAKING        = 0x0300
    TLS_OPEN               = 0x0100
    TLS_EOF_RECEIVED       = 0x0101
    TLS_SHUTTING_DOWN      = 0x0102
    TLS_SHUT_DOWN          = 0x0103

    CLOSED                 = 0x0003

    @property
    def eof_received(self):
        return bool(self.value & 0x0001)

    @property
    def tls_started(self):
        return bool(self.value & 0x0100)

    @property
    def tls_handshaking(self):
        return bool(self.value & 0x0200)

    @property
    def is_writable(self):
        return not bool(self.value & 0x0002)

    @property
    def is_open(self):
        return (self.value & 0x3) == 0


class STARTTLSTransport(asyncio.Transport):
    """
    Create a new :class:`asyncio.Transport` which supports TLS and the deferred
    starting of TLS using the :meth:`starttls` method.

    `loop` must be a :class:`asyncio.BaseEventLoop` with support for
    :meth:`BaseEventLoop.add_reader` as well as removal and the writer
    complements.

    `rawsock` must be a :class:`socket.socket` which will be used as the socket
    for the transport. `protocol` must be a :class:`asyncio.Protocol` which
    will be fed the data the transport receives.

    `ssl_context` must be a :class:`OpenSSL.SSL.Context`. It will be used to
    create the :class:`OpenSSL.SSL.Connection` when TLS is enabled on the
    transport.

    `use_starttls` must be a boolean value. If it is true, TLS is not enabled
    immediately. Instead, the user must call :meth:`starttls` to enable TLS on
    the transport. Until that point, the transport is unencrypted. If it is
    false, the TLS handshake is started immediately. This is roughly equivalent
    to calling :meth:`starttls` immediately.

    `peer_hostname` must be either a :class:`str` or :data:`None`. It may be
    used by certificate validators and must be the host name this transport
    actually connected to. That might be (e.g. in the case of XMPP) different
    from the actual domain name the transport communicates with (and for which
    the service must have a valid certificate). This host name may be used by
    certificate validators implementing e.g. DANE.

    `server_hostname` must be either a :class:`str` or :data:`None`. It may be
    used by certificate validators anrd must be the host name for which the
    peer must have a valid certificate (if host name based certificate
    validation is performed). `server_hostname` is also passed via the TLS
    Server Name Indication (SNI) extension if it is given.

    If host names are to be converted to :class:`bytes` by the transport, they
    are encoded using the ``utf-8` codec.

    If `waiter` is not :data:`None`, it must be a
    :class:`asyncio.Future`. After the stream has been established, the futures
    result is set to a value of :data:`None`. If any errors occur, the
    exception is set on the future.

    If `use_starttls` is true, the future is fulfilled immediately after
    construction, as there is no blocking process which needs to take place. If
    `use_starttls` is false and thus TLS negotiation starts right away, the
    future is fulfilled when TLS negotiation is complete.

    `post_handshake_callback` may be a coroutine or :data:`None`. If it is not
    :data:`None`, it is called asynchronously after the TLS handshake and
    blocks the completion of the TLS handshake until it returns.

    It can be used to perform blocking post-handshake certificate verification,
    e.g. using DANE. The coroutine must not return a value. If it encounters an
    error, an appropriate exception should be raised, which will propagate out
    of :meth:`starttls` and/or passed to the `waiter` future.
    """

    MAX_SIZE = 256 * 1024

    def __init__(self, loop, rawsock, protocol, ssl_context,
                 waiter=None,
                 use_starttls=False,
                 post_handshake_callback=None,
                 peer_hostname=None,
                 server_hostname=None):
        if not use_starttls and not ssl_context:
            raise ValueError("Cannot have STARTTLS disabled (i.e. immediate "
                             "TLS connection) and without SSL context.")

        super().__init__()
        self._rawsock = rawsock
        self._raw_fd = rawsock.fileno()
        self._trace_logger = logger.getChild(
            "trace.fd={}".format(self._raw_fd)
        )
        self._sock = rawsock
        self._protocol = protocol
        self._loop = loop
        self._extra = {
            "socket": rawsock,
        }
        self._waiter = waiter
        self._state = None
        self._conn_lost = 0
        self._buffer = bytearray()
        self._ssl_context = ssl_context
        self._extra.update(
            ssl_context=ssl_context,
            conn=None,
            peername=self._rawsock.getpeername(),
            peer_hostname=peer_hostname,
            server_hostname=server_hostname
        )

        # this is a list set of tasks which will also be cancelled if the
        # _waiter is cancelled
        self._chained_pending = set()

        self._paused = False
        self._closing = False

        self._tls_conn = None
        self._tls_read_wants_write = False
        self._tls_write_wants_read = False
        self._tls_post_handshake_callback = post_handshake_callback

        self._state = None
        if not use_starttls:
            self._initiate_tls()
        else:
            self._initiate_raw()

    def _waiter_done(self, fut):
        self._trace_logger.debug("_waiter future done (%r)", fut)
        if fut.cancelled():
            for chained in self._chained_pending:
                self._trace_logger.debug("cancelling chained %r", chained)
                chained.cancel()
            self._chained_pending.clear()

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
        msg = "{what} (invalid in state {state}, closing={closing})".format(
            what=what,
            state=self._state,
            closing=self._closing)
        logger.error(msg)
        # raising is optional :)
        return exc(msg)

    def _fatal_error(self, exc, msg):
        if not isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            self._loop.call_exception_handler({
                "message": msg,
                "exception": exc,
                "transport": self,
                "protocol": self._protocol
            })

        self._force_close(exc)

    def _force_close(self, exc):
        self._trace_logger.debug("_force_close called")
        self._remove_rw()
        if self._state == _State.CLOSED:
            # don’t raise here
            raise self._invalid_state("_force_close called")
            return

        self._state = _State.CLOSED

        if self._buffer:
            self._buffer.clear()

        self._loop.remove_reader(self._raw_fd)
        self._loop.remove_writer(self._raw_fd)
        self._loop.call_soon(self._call_connection_lost_and_clean_up, exc)

    def _remove_rw(self):
        self._trace_logger.debug("clearing readers/writers")
        self._loop.remove_reader(self._raw_fd)
        self._loop.remove_writer(self._raw_fd)

    def _call_connection_lost_and_clean_up(self, exc):
        """
        Clean up all resources and call the protocols connection lost method.
        """

        self._state = _State.CLOSED
        try:
            self._protocol.connection_lost(exc)
        finally:
            self._rawsock.close()
            if self._tls_conn is not None:
                self._tls_conn.set_app_data(None)
                self._tls_conn = None
            self._rawsock = None
            self._protocol = None
            self._loop = None

    def _initiate_raw(self):
        if self._state is not None:
            self._invalid_transition(via="_initiate_raw", to=_State.RAW_OPEN)

        self._state = _State.RAW_OPEN
        self._loop.add_reader(self._raw_fd, self._read_ready)
        self._loop.call_soon(self._protocol.connection_made, self)
        if self._waiter is not None:
            self._loop.call_soon(self._waiter.set_result, None)
            self._waiter = None

    def _initiate_tls(self):
        self._trace_logger.debug("_initiate_tls called")
        if self._state is not None and self._state != _State.RAW_OPEN:
            self._invalid_transition(via="_initiate_tls",
                                     to=_State.TLS_HANDSHAKING)

        self._tls_was_starttls = (self._state == _State.RAW_OPEN)
        self._state = _State.TLS_HANDSHAKING
        self._tls_conn = OpenSSL.SSL.Connection(
            self._ssl_context,
            self._sock)
        self._tls_conn.set_connect_state()
        self._tls_conn.set_app_data(self)
        try:
            self._tls_conn.set_tlsext_host_name(
                self._extra["server_hostname"].encode("IDNA"))
        except KeyError:
            pass
        self._sock = self._tls_conn
        self._extra.update(
            conn=self._tls_conn
        )

        self._tls_do_handshake()

    def _tls_do_handshake(self):
        self._trace_logger.debug("_tls_do_handshake called")
        if self._state != _State.TLS_HANDSHAKING:
            raise self._invalid_state("_tls_do_handshake called")

        try:
            self._tls_conn.do_handshake()
        except OpenSSL.SSL.WantReadError:
            self._trace_logger.debug(
                "registering reader for _tls_do_handshake")
            self._loop.add_reader(self._raw_fd, self._tls_do_handshake)
            return
        except OpenSSL.SSL.WantWriteError:
            self._trace_logger.debug(
                "registering writer for _tls_do_handshake")
            self._loop.add_writer(self._raw_fd, self._tls_do_handshake)
            return
        except Exception as exc:
            self._remove_rw()
            self._fatal_error(exc, "Fatal error on tls handshake")
            if self._waiter is not None:
                self._waiter.set_exception(exc)
            return
        except BaseException as exc:
            self._remove_rw()
            if self._waiter is not None:
                self._waiter.set_exception(exc)
            raise

        self._remove_rw()

        # handshake complete

        self._trace_logger.debug("handshake complete")
        self._extra.update(
            peercert=self._tls_conn.get_peer_certificate()
        )

        if self._tls_post_handshake_callback:
            self._trace_logger.debug("post handshake scheduled via callback")
            task = asyncio.async(self._tls_post_handshake_callback(self))
            task.add_done_callback(self._tls_post_handshake_done)
            self._chained_pending.add(task)
            self._tls_post_handshake_callback = None
        else:
            self._tls_post_handshake(None)

    def _tls_post_handshake_done(self, task):
        self._chained_pending.discard(task)
        try:
            task.result()
        except BaseException as err:
            self._tls_post_handshake(err)
        else:
            self._tls_post_handshake(None)

    def _tls_post_handshake(self, exc):
        self._trace_logger.debug("_tls_post_handshake called")
        if exc is not None:
            self._fatal_error(exc, "Fatal error on post-handshake callback")
            if self._waiter is not None and not self._waiter.done():
                self._waiter.set_exception(exc)
            return

        self._tls_read_wants_write = False
        self._tls_write_wants_read = False

        self._state = _State.TLS_OPEN

        self._loop.add_reader(self._raw_fd, self._read_ready)
        if not self._tls_was_starttls:
            self._loop.call_soon(self._protocol.connection_made, self)
        if self._waiter is not None:
            self._loop.call_soon(self._waiter.set_result, None)

    def _tls_do_shutdown(self):
        self._trace_logger.debug("_tls_do_shutdown called")
        if self._state != _State.TLS_SHUTTING_DOWN:
            raise self._invalid_state("_tls_do_shutdown called")

        try:
            self._sock.shutdown()
        except OpenSSL.SSL.WantReadError:
            self._trace_logger.debug("registering reader for _tls_shutdown")
            self._loop.add_reader(self._raw_fd, self._tls_shutdown)
            return
        except OpenSSL.SSL.WantWriteError:
            self._trace_logger.debug("registering writer for _tls_shutdown")
            self._loop.add_writer(self._raw_fd, self._tls_shutdown)
            return
        except Exception as exc:
            # force_close will take care of removing rw handlers
            self._fatal_error(exc, "Fatal error on tls shutdown")
            return
        except BaseException as exc:
            self._remove_rw()
            raise

        self._remove_rw()
        self._state = _State.TLS_SHUT_DOWN
        # continue to raw shut down
        self._raw_shutdown()

    def _tls_shutdown(self):
        self._state = _State.TLS_SHUTTING_DOWN
        self._tls_do_shutdown()

    def _raw_shutdown(self):
        self._remove_rw()
        self._rawsock.shutdown(socket.SHUT_RDWR)
        self._force_close(None)

    def _read_ready(self):
        if self._state.tls_started and self._tls_write_wants_read:
            self._tls_write_wants_read = False
            self._write_ready()

            if self._buffer:
                self._trace_logger.debug("_read_ready: add writer for more"
                                         " data")
                self._loop.add_writer(self._raw_fd, self._write_ready)

        if self._state.eof_received:
            # no further reading
            return

        try:
            data = self._sock.recv(self.MAX_SIZE)
        except (BlockingIOError, InterruptedError, OpenSSL.SSL.WantReadError):
            pass
        except OpenSSL.SSL.WantWriteError:
            assert self._state.tls_started
            self._tls_read_wants_write = True
            self._trace_logger.debug("_read_ready: swap reader for writer")
            self._loop.remove_reader(self._raw_fd)
            self._loop.add_writer(self._raw_fd, self._write_ready)
        except Exception as err:
            self._fatal_error(err, "Fatal read error on STARTTLS transport")
            return
        else:
            if data:
                self._protocol.data_received(data)
            else:
                keep_open = False
                try:
                    keep_open = bool(self._protocol.eof_received())
                finally:
                    self._eof_received(keep_open)

    def _write_ready(self):
        if self._tls_read_wants_write:
            self._tls_read_wants_write = False
            self._read_ready()

            if not self._paused and not self._state.eof_received:
                self._trace_logger.debug("_write_ready: add reader for more"
                                         " data")
                self._loop.add_reader(self._raw_fd, self._read_ready)

        if self._buffer:
            try:
                nsent = self._sock.send(bytes(self._buffer))
            except (BlockingIOError, InterruptedError,
                    OpenSSL.SSL.WantWriteError):
                nsent = 0
            except OpenSSL.SSL.WantReadError:
                nsent = 0
                assert self._state.tls_started
                self._tls_write_wants_read = True
                self._trace_logger.debug(
                    "_write_ready: swap writer for reader")
                self._loop.remove_writer(self._raw_fd)
                self._loop.add_reader(self._raw_fd, self._read_ready)
            except Exception as err:
                self._fatal_error(err,
                                  "Fatal write error on STARTTLS "
                                  "transport")
                return

            if nsent:
                del self._buffer[:nsent]

        if not self._buffer:
            if not self._tls_read_wants_write:
                self._trace_logger.debug("_write_ready: nothing more to write,"
                                         " removing writer")
                self._loop.remove_writer(self._raw_fd)
            if self._closing:
                if self._state.tls_started:
                    self._tls_shutdown()
                else:
                    self._raw_shutdown()

    def _eof_received(self, keep_open):
        self._trace_logger.debug("_eof_received: removing reader")
        self._loop.remove_reader(self._raw_fd)
        if self._state.tls_started:
            if self._tls_conn.get_shutdown() & OpenSSL.SSL.RECEIVED_SHUTDOWN:
                # proper TLS shutdown going on
                if keep_open:
                    self._state = _State.TLS_EOF_RECEIVED
                else:
                    self._tls_shutdown()
            else:
                if keep_open:
                    self._trace_logger.warning("result of eof_received() "
                                               "ignored as shut down is"
                                               " improper")
                self._fatal_error(ConnectionError("Underlying transport "
                                                  "closed"))
        else:
            if keep_open:
                self._state = _State.RAW_EOF_RECEIVED
            else:
                self._raw_shutdown()

    # public API

    def abort(self):
        """
        Immediately close the stream, without sending remaining buffers or
        performing a proper shutdown.
        """
        if self._state == _State.CLOSED:
            self._invalid_state("abort() called")
            return

        self._force_close()

    def can_write_eof(self):
        """
        Return :data:`False`.

        .. note::

           Writing of EOF (i.e. closing the sending direction of the stream) is
           theoretically possible. However, it was deemed by the author that
           the case is rare enough to neglect it for the sake of implementation
           simplicity.

        """
        return False

    def close(self):
        """
        Close the stream. This performs a proper stream shutdown, except if the
        stream is currently performing a TLS handshake. In that case, calling
        :meth:`close` is equivalent to calling :meth:`abort`.

        Otherwise, the transport waits until all buffers are transmitted.
        """

        if self._state == _State.CLOSED:
            self._invalid_state("close() called")
            return

        if self._state == _State.TLS_HANDSHAKING:
            # hard-close
            self._force_close(None)
        elif self._state == _State.TLS_SHUTTING_DOWN:
            # shut down in progress, nothing to do
            pass
        elif self._buffer:
            # there is data to be send left, first wait for it to transmit ...
            self._closing = True
        elif self._state.tls_started:
            # normal TLS state, nothing left to transmit, shut down
            self._tls_shutdown()
        else:
            # normal non-TLS state, nothing left to transmit, close
            self._raw_shutdown()

    def get_extra_info(self, name, default=None):
        """
        The following extra information is available:

        * ``socket``: the underlying :mod:`socket` object
        * ``ssl_context``: the :class:`OpenSSL.SSL.Context` object to use (this
          may be :data:`None` until :meth:`starttls` has been called)
        * ``conn``: :class:`OpenSSL.SSL.Connection` object (:data:`None` if TLS
          is not enabled (yet))
        * ``peername``: return value of :meth:`socket.Socket.getpeername`
        * ``peer_hostname``: The `peer_hostname` value passed to the
          constructor.
        * ``server_hostname``: The `server_hostname` value passed to the
          constructor.

        """
        return self._extra.get(name, default)

    @asyncio.coroutine
    def starttls(self, ssl_context=None,
                 post_handshake_callback=None):
        """
        Start a TLS stream on top of the socket. This is an invalid operation
        if the stream is not in RAW_OPEN state.

        If `ssl_context` is set, it overrides the `ssl_context` passed to the
        constructor. If `post_handshake_callback` is set, it overrides the
        `post_handshake_callback` passed to the constructor.
        """
        if self._state != _State.RAW_OPEN or self._closing:
            raise self._invalid_state("starttls() called")

        if ssl_context is not None:
            self._ssl_context = ssl_context
            self._extra.update(
                ssl_context=ssl_context
            )
        if post_handshake_callback is not None:
            self._tls_post_handshake_callback = post_handshake_callback

        self._waiter = asyncio.Future()
        self._waiter.add_done_callback(self._waiter_done)
        self._initiate_tls()
        try:
            yield from self._waiter
        finally:
            self._waiter = None

    def write(self, data):
        """
        Write data to the transport. This is an invalid operation if the stream
        is not writable, that is, if it is closed. During TLS negotiation, the
        data is buffered.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError('data argument must be byte-ish (%r)',
                            type(data))

        if not self._state.is_writable or self._closing:
            raise self._invalid_state("write() called")

        if not data:
            return

        if not self._buffer:
            self._loop.add_writer(self._raw_fd, self._write_ready)

        self._buffer.extend(data)

    def write_eof(self):
        """
        Writing the EOF has not been implemented, for the sake of simplicity.
        """
        raise NotImplementedError("Cannot write_eof() on STARTTLS transport")

    def can_starttls(self):
        """
        Return :data:`True`.
        """
        return True


@asyncio.coroutine
def create_starttls_connection(
        loop,
        protocol_factory,
        host=None,
        port=None,
        *,
        sock=None,
        ssl_context=None,
        use_starttls=False,
        **kwargs):
    """
    This is roughly a copy of the asyncio implementation of
    :meth:`asyncio.BaseEventLoop.create_connection`. It returns a pair
    ``(transport, protocol)``, where `transport` is a newly created
    :class:`STARTTLSTransport` instance. The keyword arguments are forwarded to
    the constructor of :class:`STARTTLSTransport`.

    `loop` must be a :class:`asyncio.BaseEventLoop`, with support for
    :meth:`asyncio.BaseEventLoop.add_reader` and the corresponding writer and
    removal functions for sockets.

    `protocol_factory` must be a callable which (without any arguments) returns
    a :class:`asyncio.Protocol` which will be connected to the STARTTLS
    transport.

    `host` and `port` must be a hostname and a port number, or both
    :data:`None`. Both must be :data:`None`, if and only if `sock` is not
    :data:`None`. In that case, `sock` is used instead of a newly created
    socket. `sock` is put into non-blocking mode and must be a stream socket.

    This coroutine returns when the stream is established. If `use_starttls` is
    :data:`False`, this means that the full TLS handshake has to be finished
    for this coroutine to return. Otherwise, no TLS handshake takes place. It
    must be invoked using the :meth:`STARTTLSTransport.starttls` coroutine.
    """

    if host is not None and port is not None:
        host_addrs = yield from loop.getaddrinfo(
            host, port,
            type=socket.SOCK_STREAM)

        exceptions = []

        for family, type, proto, cname, address in host_addrs:
            sock = None
            try:
                sock = socket.socket(family=family, type=type, proto=proto)
                sock.setblocking(False)
                yield from loop.sock_connect(sock, address)
            except OSError as exc:
                if sock is not None:
                    sock.close()
                exceptions.append(exc)
            else:
                break
        else:
            if len(exceptions) == 1:
                raise exceptions[0]

            model = str(exceptions[0])
            if all(str(exc) == model for exc in exceptions):
                raise exceptions[0]

            exc = errors.MultiOSError(
                "could not connect to [{}]:{}".format(host, port),
                exceptions)
            raise exc
    elif sock is None:
        raise ValueError("sock must not be None if host and/or port are None")
    else:
        sock.setblocking(False)

    protocol = protocol_factory()
    waiter = asyncio.Future(loop=loop)
    transport = STARTTLSTransport(loop, sock, protocol,
                                  ssl_context=ssl_context,
                                  waiter=waiter,
                                  use_starttls=use_starttls,
                                  **kwargs)
    yield from waiter

    return transport, protocol
