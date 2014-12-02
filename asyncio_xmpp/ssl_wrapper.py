import asyncio
import logging
import ssl
import socket

from .merge_transport import \
    StreamProtocolWrapper, BidirectionalTransportWrapper

logger = logging.getLogger(__name__)

class FlexibleTransportProtocol(
        StreamProtocolWrapper,
        BidirectionalTransportWrapper):

    def __init__(self, protocol):
        super().__init__(protocol)

    @property
    def protocol(self):
        return self._protocol

    @protocol.setter
    def protocol(self, value):
        self._protocol = value

    def connection_made(self, transport):
        self._transport = transport
        return super().connection_made(self)

    def connection_lost(self, exc):
        try:
            return super().connection_lost(exc)
        finally:
            self._transport = None

class STARTTLSableTransportProtocol(FlexibleTransportProtocol):
    def __init__(self, loop, protocol):
        super().__init__(protocol)
        self._loop = loop
        self._starttls_state = False

    @asyncio.coroutine
    def starttls(self, ssl_context=None, server_hostname=None):
        if self._transport is None:
            raise ConnectionError("Not connected to a transport")

        sock = self._transport.get_extra_info("socket")
        sock_fd = sock.fileno()
        ssl_context = ssl_context or ssl.create_default_context()

        # This is a bit hacky, and depends on the implementation of the socket
        # transport :/

        self._loop.remove_reader(sock_fd)
        self._loop.remove_writer(sock_fd)

        self._starttls_state = True
        yield from self._loop.create_connection(
            lambda: self,
            sock=sock,
            ssl=ssl_context,
            server_hostname=server_hostname)

    def connection_lost(self, exc):
        if self._starttls_state:
            socket, _, _ = self._starttls_state
            socket.close()
        super().connection_lost(exc)

    def connection_made(self, transport):
        if self._starttls_state:
            self._starttls_state = False
            self._transport = transport
            self._protocol.starttls_engaged(self)
        else:
            super().connection_made(transport)

    def get_extra_info(self, name, default=None):
        if name == "transport":
            return self._transport
        return default
