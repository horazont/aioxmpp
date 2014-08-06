import asyncio
import logging

class StreamProtocolWrapper(asyncio.Protocol):
    def __init__(self, protocol, **kwargs):
        super().__init__(**kwargs)
        self._protocol = protocol

    def connection_made(self, transport):
        return self._protocol.connection_made(transport)

    def connection_lost(self, exc):
        return self._protocol.connection_lost(exc)

    def data_received(self, data):
        return self._protocol.data_received(data)

    def eof_received(self):
        return self._protocol.eof_received()

    def pause_writing(self):
        return self._protocol.pause_writing()

    def resume_writing(self):
        return self._protocol.resume_writing()

class BidirectionalTransportWrapper(asyncio.ReadTransport,
                                    asyncio.WriteTransport):
    def __init__(self, transport=None, **kwargs):
        super().__init__(**kwargs)
        self._transport = transport

    # asyncio.BaseTransport interface

    def close(self):
        return self._transport.close()

    def get_extra_info(self, name, default=None):
        return self._transport.get_extra_info(name, default=default)

    # asyncio.WriteTransport interface

    def abort(self):
        return self._transport.abort()

    def can_write_eof(self):
        return self._transport.can_write_eof()

    def get_write_buffer_size(self):
        return self._transport.get_write_buffer_size()

    def set_write_buffer_limits(self, *args, **kwargs):
        return self._transport.set_write_buffer_limits(*args, **kwargs)

    def write(self, data):
        return self._transport.write(data)

    def writelines(self, list_of_data):
        return self._transport.writelines(list_of_data)

    def write_eof(self):
        return self._transport.write_eof()

    # asyncio.ReadTransport interface

    def pause_reading(self):
        return self._transport.pause_reading()

    def resume_reading(self):
        return self._transport.resume_reading()

class MergeStreamTransportReadEndpoint(StreamProtocolWrapper):
    def __init__(self, merge_stream_transport):
        super().__init__(merge_stream_transport)

    def connection_made(self, transport):
        self._protocol._read_connection_made(transport)

    def connection_lost(self, exc):
        self._protocol._read_connection_lost(exc)

class MergeStreamTransportWriteEndpoint(StreamProtocolWrapper):
    def __init__(self, merge_stream_transport):
        super().__init__(merge_stream_transport)

    def connection_made(self, transport):
        self._protocol._write_connection_made(transport)

    def connection_lost(self, exc):
        self._protocol._write_connection_lost(exc)

class MergeStreamTransport(
        StreamProtocolWrapper,
        asyncio.ReadTransport,
        asyncio.WriteTransport):
    """
    Helper class to merge two stream transports, one for reading and one for
    writing.

    Example usage::

      merge_transport = MergeTransport(some_destination_protocol)
      loop.connect_read_pipe(merge_transport.read_endpoint(), sys.stdin)
      loop.connect_write_pipe(merge_transport.write_endpoint(), sys.stdin)

    The *protocol* must support the :class:`asyncio.Protocol` interface with
    support for both reading and writing.

    """

    def __init__(self, protocol):
        super().__init__(protocol)
        self._had_eof = False
        self._read_transport = None
        self._write_transport = None

    def read_endpoint(self):
        return MergeStreamTransportReadEndpoint(self)

    def write_endpoint(self):
        return MergeStreamTransportWriteEndpoint(self)

    def eof_received(self):
        self._had_eof = True
        return self._protocol.eof_received()

    def _connection_lost(self, exc):
        if self._read_transport is not None:
            t = self._read_transport
            self._read_transport = None
            t.close()

        if self._write_transport is not None:
            t = self._write_transport
            self._write_transport = None
            if exc is not None:
                t.abort()
            else:
                t.close()

        self._protocol.connection_lost(None)

    def _read_connection_made(self, transport):
        self._had_eof = False
        self._read_transport = transport
        if self._write_transport:
            self._protocol.connection_made(self)

    def _read_connection_lost(self, exc):
        if self._read_transport is None:
            return

        self._read_transport = None
        if not exc:
            if not self._had_eof:
                self._protocol.eof_received()
            self._had_eof = True
        else:
            self._connection_lost(exc)

    def _write_connection_made(self, transport):
        self._write_transport = transport
        if self._read_transport:
            self._protocol.connection_made(self)

    def _write_connection_lost(self, exc):
        if self._write_transport is None:
            return

        self._write_transport = None
        self._connection_lost(exc)


    # asyncio.WriteTransport interface

    def abort(self):
        return self._write_transport.abort()

    def can_write_eof(self):
        return self._write_transport.can_write_eof()

    def get_write_buffer_size(self):
        return self._write_transport.get_write_buffer_size()

    def set_write_buffer_limits(self, *args, **kwargs):
        return self._write_transport.set_write_buffer_limits(*args, **kwargs)

    def write(self, data):
        return self._write_transport.write(data)

    def writelines(self, list_of_data):
        return self._write_transport.writelines(list_of_data)

    def write_eof(self):
        return self._write_transport.write_eof()

    # asyncio.ReadTransport interface

    def pause_reading(self):
        return self._read_transport.pause_reading()

    def resume_reading(self):
        return self._read_transport.resume_reading()
