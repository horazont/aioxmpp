"""
:mod:`ssl_transport` --- A transport for asyncio using :mod:`OpenSSL`
#######################################################################

"""

import abc
import asyncio
import logging
import socket

from enum import Enum

import OpenSSL.SSL

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
    MAX_SIZE = 256 * 1024

    def __init__(self, loop, rawsock, protocol, ssl_context,
                 waiter=None,
                 use_starttls=False,
                 post_handshake_callback=None,
                 peer_hostname=None,
                 server_hostname=None):
        if not use_starttls and not ssl_context:
            raise ValueError("Cannot have STARTTLS disabled (i.e. immediate TLS"
                             " connection) and without SSL context.")

        super().__init__()
        self._rawsock = rawsock
        self._raw_fd = rawsock.fileno()
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

    def _call_connection_lost_and_clean_up(self, exc):
        """
        Clean up all resources and call the protocols connection lost method.
        """
        self._state = _State.CLOSED;
        try:
            self._protocol.connection_lost(exc)
        finally:
            self._rawsock.close()
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
        if self._state != _State.TLS_HANDSHAKING:
            raise self._invalid_state("_tls_do_handshake called")

        try:
            self._tls_conn.do_handshake()
        except OpenSSL.SSL.WantReadError:
            self._loop.add_reader(self._raw_fd, self._tls_do_handshake)
            return
        except OpenSSL.SSL.WantWriteError:
            self._loop.add_writer(self._raw_fd, self._tls_do_handshake)
            return
        except Exception as exc:
            self._loop.remove_reader(self._raw_fd)
            self._loop.remove_writer(self._raw_fd)
            self._fatal_error(exc, "Fatal error on tls handshake")
            if self._waiter is not None:
                self._waiter.set_exception(exc)
            return
        except BaseException as exc:
            self._loop.remove_reader(self._raw_fd)
            self._loop.remove_writer(self._raw_fd)
            if self._waiter is not None:
                self._waiter.set_exception(exc)
            raise

        self._loop.remove_reader(self._raw_fd)
        self._loop.remove_writer(self._raw_fd)

        # handshake complete

        self._extra.update(
            peercert=self._tls_conn.get_peer_certificate()
        )

        if self._tls_post_handshake_callback:
            task = asyncio.async(self._tls_post_handshake_callback(self))
            task.add_done_callback(self._tls_post_handshake_done)
            self._tls_post_handshake_callback = None
        else:
            self._tls_post_handshake(None)

    def _tls_post_handshake_done(self, task):
        try:
            task.result()
        except BaseException as err:
            self._tls_post_handshake(err)
        else:
            self._tls_post_handshake(None)

    def _tls_post_handshake(self, exc):
        if exc is not None:
            self._fatal_error(exc, "Fatal error on post-handshake callback")
            if self._waiter is not None:
                self._waiter.set_exception(exc)
            return

        self._tls_read_wants_write = False
        self._tls_write_wants_read = False

        self._state = _State.TLS_OPEN

        self._loop.add_reader(self._raw_fd, self._read_ready)
        if self._tls_was_starttls:
            self._loop.call_soon(self._protocol.starttls_made, self)
        else:
            self._loop.call_soon(self._protocol.connection_made, self)
        if self._waiter is not None:
            self._loop.call_soon(self._waiter.set_result, None)

    def _tls_do_shutdown(self):
        if self._state != _State.TLS_SHUTTING_DOWN:
            raise self._invalid_state("_tls_do_shutdown called")

        try:
            self._sock.shutdown()
        except OpenSSL.SSL.WantReadError:
            self._loop.add_reader(self._raw_fd, self._tls_shutdown)
            return
        except OpenSSL.SSL.WantWriteError:
            self._loop.add_writer(self._raw_fd, self._tls_shutdown)
            return
        except Exception as exc:
            # force_close will take care of removing rw handlers
            self._fatal_error(exc, "Fatal error on tls shutdown")
            return
        except BaseException as exc:
            self._loop.remove_reader(self._raw_fd)
            self._loop.remove_writer(self._raw_fd)
            raise

        self._state = _State.TLS_SHUT_DOWN
        # continue to raw shut down
        self._raw_shutdown()

    def _tls_shutdown(self):
        self._state = _State.TLS_SHUTTING_DOWN
        self._tls_do_shutdown()

    def _raw_shutdown(self):
        self._rawsock.shutdown(socket.SHUT_RDWR)
        self._force_close(None)

    def _read_ready(self):
        if self._state.tls_started and self._tls_write_wants_read:
            self._tls_write_wants_read = False
            self._write_ready()

            if self._buffer:
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
                self._loop.add_reader(self._raw_fd, self._read_ready)

        if self._buffer:
            try:
                nsent = self._sock.send(self._buffer)
            except (BlockingIOError, InterruptedError,
                    OpenSSL.SSL.WantWriteError):
                nsent = 0
            except OpenSSL.SSL.WantReadError:
                nsent = 0
                assert self._state.tls_started
                self._tls_read_wants_write = True
                self._tls_write_wants_read = True
            except Exception as err:
                self._fatal_error(err,
                                  "Fatal write error on STARTTLS "
                                  "transport")
                return

            if nsent:
                del self._buffer[:nsent]

        if not self._buffer:
            if not self._tls_read_wants_write:
                self._loop.remove_writer(self._raw_fd)
            if self._closing:
                if self._state.tls_started:
                    self._tls_shutdown()
                else:
                    self._raw_shutdown()

    def _eof_received(self, keep_open):
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
                    logger.warning("result of eof_received() ignored "
                                   "as shut down is improper")
                self._fatal_error(ConnectionError("Underlying transport "
                                                  "closed"))
        else:
            if keep_open:
                self._state = _State.RAW_EOF_RECEIVED
            else:
                self._raw_shutdown()

    # public API

    def abort(self):
        if self._state == _State.CLOSED:
            self._invalid_state("abort() called")
            return

        self._force_close()

    def can_write_eof(self):
        return False

    def close(self):
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
        return self._extra.get(name, default)

    @asyncio.coroutine
    def starttls(self, ssl_context=None,
                 post_handshake_callback=None):
        if ssl_context is not None:
            self._ssl_context = ssl_context
            self._extra.update(
                ssl_context=ssl_context
            )
        if post_handshake_callback is not None:
            self._tls_post_handshake_callback = post_handshake_callback

        self._waiter = asyncio.Future()
        self._initiate_tls()
        try:
            yield from self._waiter
        finally:
            self._waiter = None

    def write(self, data):
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
        raise NotImplementedError("Cannot write_eof() on STARTTLS transport")

@asyncio.coroutine
def create_starttls_connection(
        loop,
        protocol_factory,
        host,
        port,
        ssl_context=None,
        use_starttls=False,
        **kwargs):
    """
    This is roughly a copy of the asyncio implementation of
    :meth:`asyncio.BaseEventLoop.create_connection`.
    """

    host_addrs = yield from loop.getaddrinfo(
        host, port,
        family=socket.AF_INET6,
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

        raise OSError("Multiple exceptions: {}".format(
            ", ".join(map(str, exceptions))))

    protocol = protocol_factory()
    waiter = asyncio.Future(loop=loop)
    transport = STARTTLSTransport(loop, sock, protocol,
                                  ssl_context=ssl_context,
                                  waiter=waiter,
                                  use_starttls=use_starttls,
                                  **kwargs)
    yield from waiter

    return transport, protocol
