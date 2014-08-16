import asyncio
import functools
import logging

import lxml.builder

from . import stanza, plugins

from .utils import *

logger = logging.getLogger(__name__)

def make_xmlstream_parser():
    lookup = etree.ElementNamespaceClassLookup()

    for ns in [lookup.get_namespace("jabber:client"),
               lookup.get_namespace("jabber:server")]:
        ns["iq"] = stanza.IQ
        ns["presence"] = stanza.Presence
        ns["error"] = stanza.Error
        ns["message"] = stanza.Message

    plugins.rfc6120.register(lookup)

    parser = etree.XMLPullParser(
        ('start', 'end'),
        resolve_entities=False
    )
    parser.set_element_class_lookup(lookup)
    return lookup, parser

def make_xmlstream_sender(parser, namespace):
    nsmap = {
        None: namespace
    }

    root = parser.makeelement(
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
                 event_loop,
                 to,
                 mode="client",
                 **kwargs):
        super().__init__(**kwargs)
        self._transport = None
        self._parser = None
        self._send_tree = None
        self._loop = event_loop

        try:
            self._namespace, = self.MODEMAP[mode]
        except KeyError:
            raise ValueError("Invalid value for mode argument: {}".format(mode))

        self._to = to
        self._stream_level_node_callbacks = []
        self._died = asyncio.Event()
        self._died.set()

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
        try:
            self._parser.close()
        except lxml.etree.XMLSyntaxError:
            # ignore errors on closing
            pass
        self._process_events()
        self._parser = None

    def _process_events(self):
        for ev, node in self._parser.read_events():
            if ev == "start" and node.tag == self.stream_header_tag:
                self._start_stream(node)
            elif ev == "end":
                if node.getparent() != self._stream_root:
                    continue
                node.getparent().remove(node)

                self._process_stream_level_node(node)

    def _start_stream(self, node):
        self._stream_root = node

    def _process_stream_level_node(self, node):
        to_remove = set()
        try:
            for tag, callback in reversed(self._stream_level_node_callbacks):
                if node.tag == tag:
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
        self.reset_stream()

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
            self._send_root = None
            self.E = None
            self._parser = None
            self._stream_root = None
            self._stream_level_node_callbacks = []

    def starttls_engaged(self, transport):
        pass

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

    def reset_stream(self):
        self._lookup, self._parser = make_xmlstream_parser()
        self._send_root, self.E = make_xmlstream_sender(
            self._parser,
            self._namespace)
        self._send_header()
        self._died.clear()

    @asyncio.coroutine
    def _send_andor_wait_for(self,
                             nodes_to_send,
                             tokens,
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

        for node in nodes_to_send:
            self.send_node(node)

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

    @asyncio.coroutine
    def send_and_wait_for(self,
                          nodes_to_send,
                          tokens,
                          timeout=None):
        return self._send_andor_wait_for(nodes_to_send,
                                         tokens,
                                         timeout=timeout)

    @asyncio.coroutine
    def wait_for(self, tokens, timeout=None):
        return self._send_andor_wait_for([], tokens,
                                         timeout=timeout)

    def send_raw(self, buf):
        logger.debug("SEND %s", buf)
        self._transport.write(buf)

    def send_node(self, node):
        buf = etree.tostring(node,
                             method="xml",
                             encoding="utf8",
                             xml_declaration=False)
        self.send_raw(buf)

    def make_iq(self):
        return etree.fromstring(
            b"""<iq xmlns="jabber:client" />""",
            parser=self._parser)

    def make_message(self):
        return etree.fromstring(
            b"""<message xmlns="jabber:client" />""",
            parser=self._parser)

    def make_presence(self):
        return etree.fromstring(
            b"""<presence xmlns="jabber:client" />""",
            parser=self._parser)
