import asyncio
import functools
import logging

import lxml.builder

from .utils import *

logger = logging.getLogger(__name__)

def make_xmlstream_parser():
    parser = etree.XMLPullParser(
        ('start', 'end'),
        resolve_entities=False
    )
    return parser

def make_xmlstream_sender(namespace):
    nsmap = {
        "stream": namespaces.xmlstream,
        None: namespace
    }

    root = etree.Element(
        "{{{}}}stream".format(namespaces.xmlstream),
        nsmap=nsmap)

    return root, lxml.builder.ElementMaker(
        namespace=namespace,
        nsmap=nsmap,
        makeelement=root.makeelement)

class XMLStream(asyncio.Protocol):
    MODEMAP = {
        "client": (
            namespaces.client,
        )
    }

    stream_header_tag = "{{{stream_ns}}}stream".format(
        stream_ns=namespaces.xmlstream)

    def __init__(self,
                 to,
                 mode="client",
                 **kwargs):
        super().__init__(**kwargs)
        self._transport = None
        self._parser = None
        self._send_tree = None

        try:
            self._namespace, = self.MODEMAP[mode]
        except KeyError:
            raise ValueError("Invalid value for mode argument: {}".format(mode))

        self._to = to
        self._stream_level_node_callbacks = []
        self._died = asyncio.Event()

    def _send_header(self):
        self.send_raw(
            b"""<?xml version="1.0" ?>\n""")
        self.send_raw(
            "<stream:stream"
            " xmlns='{ns}'"
            " xmlns:stream='{stream_ns}'"
            " version='1.0'"
            " to='{to}'>".format(
                ns=self._namespace,
                stream_ns=namespaces.xmlstream,
                to=self._to).encode("utf8"))

    def _close_parser(self):
        self._parser.close()
        self._process_events()
        self._parser = None

    def _process_events(self):
        for ev, node in self._parser.read_events():
            if ev == "start" and node.tag == self.stream_header_tag:
                self._start_stream(node)
            elif ev == "end":
                if node.getparent() != self._stream_root:
                    continue
                try:
                    self._process_stream_level_node(node)
                finally:
                    node.getparent().remove(node)

    def _start_stream(self, node):
        self._stream_root = node

    def _process_stream_level_node(self, node):
        to_remove = set()
        try:
            for tag, callback in reversed(self._stream_level_node_callbacks):
                if node.getparent().find(tag) is node:
                    result = callback(self, node)
                    if not result:
                        to_remove.append(((is_plain, tag), callback))
        finally:
            if not to_remove:
                return

            reversed_enumerated_callbacks = reversed(
                list(
                    enumerate(
                        self._stream_level_node_callbacks)))
            for i, row in reversed_enumerated_callbacks:
                if row in to_remove:
                   del self._stream_level_node_callbacks[i]

    def connection_made(self, using_transport):
        self._transport = using_transport
        self._parser = make_xmlstream_parser()
        self._send_root, self.E = make_xmlstream_sender(
            self._namespace)
        self._send_header()
        self._died.clear()

    def data_received(self, blob):
        logger.debug("RECV %s", blob)
        self._parser.feed(blob)
        try:
            self._process_events()
        except:
            logger.exception("during data_received")
            raise

    def eof_received(self):
        try:
            self._close_parser()
        except:
            logger.exception("during eof_received")
            raise

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def connection_lost(self, exc):
        try:
            if self._parser:
                self._close_parser()
        finally:
            self._transport = None
            self._died.set()
            del self._send_root
            del self.E
            del self._parser
            del self._stream_root
            self._stream_level_node_callbacks = []

    def starttls_engaged(self, transport):
        logger.info("STARTTLS engaged, resetting stream")
        self.connection_made(transport)

    # public API

    def add_stream_level_node_callback(self,
                                       lxml_qualifier,
                                       callback):
        self._stream_level_node_callbacks.append(
            (lxml_qualifier, callback)
        )

    def remove_stream_level_node_callback(self,
                                          lxml_qualifier,
                                          callback):
        try:
            self._stream_level_node_callbacks.remove(
                (lxml_qualifier, callback)
            )
        except ValueError:
            return False
        return True

    @asyncio.coroutine
    def send_and_wait_for(self,
                          node_to_send,
                          *tokens,
                          timeout=None):
        ev = asyncio.Event()
        pass_node = None
        pass_value = None
        def callback(return_value, self, node):
            nonlocal pass_node, pass_value
            pass_value = return_value
            pass_node = node
            ev.set()
            return False

        for qualifier, return_value in tokens:
            self.add_stream_level_node_callback(
                qualifier,
                functools.partial(callback, return_value))

        self.send_node(node_to_send)

        received = asyncio.async(ev.wait())
        died = asyncio.async(self._died.wait())

        done, pending = yield from asyncio.wait(
            [
                received,
                died
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED)

        if not done:
            raise TimeoutError("Timeout")
        if died in done:
            raise ConnectionError("Disconnected")

        for future in pending:
            future.cancel()

        return pass_node, pass_value

    def send_raw(self, buf):
        logger.debug("SEND %s", buf)
        self._transport.write(buf)

    def send_node(self, node):
        buf = etree.tostring(node,
                             method="xml",
                             encoding="utf8",
                             xml_declaration=False)
        self.send_raw(buf)
