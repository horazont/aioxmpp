import asyncio

from enum import Enum

from . import xml, errors
from .utils import namespaces, etree

class Mode(Enum):
    C2S = namespaces.client

class XMLStream(asyncio.Protocol):
    STREAM_HEADER_TEMPLATE = """<?xml version="1.0" ?>
<stream:stream xmlns="{{namespace}}" xmlns:stream="{stream_ns}" \
version="1.0" to="{{to}}">""".format(
        stream_ns=namespaces.xmlstream)

    def __init__(self,
                 to,
                 mode=Mode.C2S,
                 *,
                 loop=None,
                 tx_context=xml.default_tx_context,
                 **kwargs):
        super().__init__(**kwargs)
        self._to = to
        self._namespace = mode.value

        self._tx_context = tx_context
        self._rx_context = None

    # RX handling

    def _rx_init(self):
        pass

    # Protocol interface

    def connection_made(self, transport):
        self._transport = transport
        self._rx_context = xml.XMLStreamReceiverContext()

        transport.write(
            self.STREAM_HEADER_TEMPLATE.format(
                to=self._to,
                namespace=self._namespace,
            ).encode("utf-8")
        )

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        try:
            self._rx_context.feed(data)
            if not self._rx_context.start():
                return

            for node in self._rx_context.read_stream_level_nodes():
                pass
        except errors.SendStreamError as stream_error:
            E = self._tx_context.default_ns_builder(namespaces.streams)
            el = self._tx_context._parser.makeelement(
                "{{{}}}error".format(namespaces.xmlstream),
                nsmap={"stream": namespaces.xmlstream})
            el.append(E(stream_error.error_tag))
            if stream_error.text:
                el.append(E("text", stream_error.text))
            self._transport.write(etree.tostring(el, encoding="utf-8"))
            self.close()

    def eof_received(self):
        self.close()

    def close(self):
        try:
            self._rx_context.close()
        except etree.XMLSyntaxError:
            pass
        self._transport.write(b"</stream:stream>")
        if self._transport.can_write_eof():
            self._transport.write_eof()
        self._transport.close()
