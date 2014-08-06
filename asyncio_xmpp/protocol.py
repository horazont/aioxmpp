import asyncio
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
                 stream_plugins=[],
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
        self._stream_plugins = stream_plugins

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
        self.add_stream_level_node_callback(
            "{http://etherx.jabber.org/streams}features",
            self._process_stream_features)

    def _process_stream_level_node(self, node):
        to_remove = set()
        try:
            for tag, callback in self._stream_level_node_callbacks:
                if node.getparent().find(tag) == node:
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

    def _process_stream_features(self, _, node):
        for plugin in self._stream_plugins:
            feature_node = node.find(plugin.feature)
            if feature_node is None:
                continue

            if plugin.start(self, feature_node):
                # abort processing
                return

    def connection_made(self, using_transport):
        self._transport = using_transport
        self._parser = make_xmlstream_parser()
        self._send_root, self.E = make_xmlstream_sender(
            self._namespace)
        self._send_header()
        self._stream_level_node_callbacks = []

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
            del self._send_root
            del self.E
            del self._parser
            del self._stream_root
            del self._stream_level_node_callbacks

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

    def send_raw(self, buf):
        logger.debug("SEND %s", buf)
        self._transport.write(buf)

    def send_node(self, node):
        buf = etree.tostring(node,
                             method="xml",
                             encoding="utf8",
                             xml_declaration=False)
        self.send_raw(buf)
