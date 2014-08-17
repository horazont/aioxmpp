import asyncio
import functools
import logging

import lxml.builder

from . import stanza, plugins, hooks, errors, utils

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

class SendStreamError(Exception):
    def __init__(self, error_tag, text=None):
        super().__init__("Going to send a stream:error (seeing this exception is"
                         " a bug")
        self.error_tag = error_tag
        self.text = text

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
                 *,
                 loop=None,
                 **kwargs):
        super().__init__(**kwargs)
        # client info
        self._to = to
        try:
            self._namespace, = self.MODEMAP[mode]
        except KeyError:
            raise ValueError("Invalid value for mode argument: {}".format(mode))

        # transmitter state
        self._tx_tree_root = None
        self.E = None

        # receiver state
        self._rx_parser = None
        self._rx_lookup = None
        self._rx_stream_root = None
        self._rx_stream_id = None

        # asyncio state
        self._transport = None
        self._loop = loop

        # connection state
        self._stream_level_node_hooks = hooks.NodeHooks()
        self._died = asyncio.Event()
        self._died.set()
        self._closing = False

        # callbacks
        self.on_stream_error = None

    def _rx_close(self):
        """
        Close the parser and reset any receiving state.

        This may trigger the call of node event handlers.
        """
        if self._rx_parser is None:
            return

        try:
            self._rx_parser.close()
        except lxml.etree.XMLSyntaxError:
            # ignore errors on closing
            pass
        self._rx_process()
        self._rx_parser = None
        self._rx_stream_root = None
        self._rx_stream_id = None

    def _rx_end_of_stream(self):
        """
        Handle </stream:stream> being received from the remote end.
        """
        if not self._closing:
            self.close()
            return

        self._rx_close()

    def _rx_feed(self, blob):
        try:
            self._rx_parser.feed(blob)
            self._rx_process()
        except lxml.etree.XMLSyntaxError as err:
            raise SendStreamError(
                "not-well-formed",
                text=str(err))
        except ValueError as err:
            # ValueError is raised by ElementBase subclasses upon content
            # validation
            # As these are only instanciated for the stream level nodes here,
            # treating ValueErrors as critical is sane
            raise SendStreamError(
                "invalid-xml",
                str(err))

    def _rx_process(self):
        """
        Process any pending SAX events produced by the receiving parser.
        """
        for ev, node in self._rx_parser.read_events():
            if ev == "start" and node.tag == self.stream_header_tag:
                self._rx_start_stream(node)
            elif ev == "end":
                if node.getparent() is None:
                    # stream root
                    self._rx_end_of_stream()
                    break
                if node.getparent() != self._rx_stream_root:
                    continue
                node.getparent().remove(node)

                self._rx_process_stream_level_node(node)

    def _rx_process_stream_level_node(self, node):
        try:
            self._stream_level_node_hooks.unicast(node.tag, node)
        except KeyError:
            if node.tag == "{{{}}}error".format(
                    namespaces.xmlstream):
                self._rx_stream_error(node)
            else:
                raise SendStreamError("unsupported-stanza-type")

    def _rx_reset(self):
        self._rx_lookup, self._rx_parser = make_xmlstream_parser()
        self._rx_stream_root = None
        self._rx_stream_id = None

    def _rx_start_stream(self, node):
        if self._rx_stream_root is not None:
            # duplicate <stream:stream>
            raise SendStreamError("unsupported-stanza-type")
        version = node.get("version")
        if version is None:
            raise SendStreamError("unsupported-version")
        try:
            version = tuple(map(int, version.split(".")))
        except (ValueError, TypeError):
            raise SendStreamError("unsupported-version")

        if version[0] != 1:
            raise SendStreamError("unsupported-version")

        self._rx_stream_root = node
        self._rx_stream_id = node.get("id")

    def _rx_stream_error(self, node):
        TEXT_TAG = "{{{}}}text".format(namespaces.streams)

        error_tag = None
        text = None
        application_defined_condition = None
        for child in node:
            ns, name = utils.split_tag(child.tag)
            if child.tag == TEXT_TAG:
                text = text or child.text
            elif ns != namespaces.streams:
                application_defined_condition = (
                    application_defined_condition or name)
            else:
                error_tag = error_tag or name

        err = errors.StreamError(
            error_tag,
            text=text,
            application_defined_condition=application_defined_condition)

        self._stream_level_node_hooks.broadcast_error(err)

        if self.on_stream_error:
            self.on_stream_error(err)
        else:
            logger.error("remote sent %s", str(err))

    def _tx_close(self):
        if self._tx_tree_root is None:
            return
        self._tx_send_footer()
        self._tx_tree_root = None
        self.E = None

    def _tx_reset(self):
        self._tx_tree_root, self.E = make_xmlstream_sender(
            self._rx_parser,
            self._namespace)
        self._tx_makeelement = self._tx_tree_root.makeelement

    def _tx_send_footer(self):
        self._tx_send_raw(b"</stream:stream>")

    def _tx_send_header(self):
        """
        Send a stream header over the wire, using the configuration supplied in
        the constructor.

        Raises :class:`ConnectionError` if not connected to a transport.
        """
        self._tx_send_raw(
            b"""<?xml version="1.0" ?>\n""")
        self._tx_send_raw(
            "<stream:stream"
            " xmlns='{ns}'"
            " xmlns:stream='{stream_ns}'"
            " version='1.0'"
            " to='{to}'>".format(
                ns=self._namespace,
                stream_ns=namespaces.xmlstream,
                to=self._to).encode("utf8"))

    def _tx_send_node(self, node):
        self._tx_send_raw(
            etree.tostring(node,
                           method="xml",
                           encoding="utf8",
                           xml_declaration=False)
        )

    def _tx_send_raw(self, blob):
        """
        Send the given raw *blob* using the underlying transport.

        Raises :class:`ConnectionError` if not connected to a transport.
        """
        if self._transport is None:
            raise ConnectionError("Not connected")
        logger.debug("SEND %s", blob)
        self._transport.write(blob)

    # asyncio Protocol implementation

    def connection_made(self, using_transport):
        self._transport = using_transport
        self.reset_stream()

    def data_received(self, blob):
        logger.debug("RECV %s", blob)
        try:
            self._rx_feed(blob)
        except SendStreamError as err:
            self.stream_error(err.error_tag, err.text)

    def eof_received(self):
        try:
            self.close()
        except:
            logger.exception("during eof_received")
            raise

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def connection_lost(self, exc):
        try:
            if self._rx_parser:
                self._close_parser()
        finally:
            self._transport = None
            self._died.set()
            self._send_root = None
            self.E = None
            self._rx_parser = None
            self._stream_root = None
            self._stream_level_node_hooks.close_all(
                ConnectionError("Disconnected"))

    def starttls_engaged(self, transport):
        pass

    # public API

    def close(self):
        self._rx_close()
        self._tx_close()

    def reset_stream(self):
        self._rx_reset()
        self._tx_reset()
        self._tx_send_header()
        self._died.clear()

    @asyncio.coroutine
    def _send_andor_wait_for(self,
                             nodes_to_send,
                             tags,
                             timeout=None,
                             critical_timeout=True):

        futures = []
        for tag in tags:
            f = asyncio.Future()
            futures.append((tag, f))
            self._stream_level_node_hooks.add_future(tag, f)

        for node in nodes_to_send:
            self.send_node(node)

        done, pending = yield from asyncio.wait(
            [f for _, f in futures],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED)

        # first cancel futures, then retrieve result (result may be an
        # Exception)
        for tag, future in futures:
            if future not in pending:
                continue
            future.cancel()
            try:
                self._stream_level_node_hooks.remove_future(tag, future)
            except KeyError:
                # defensive guard against a maybe race condition
                # (I guess that in some cases, asyncio.wait may catch only one
                # future, but more than one has been fulfilled)
                pass

        if not done:
            if critical_timeout:
                self.stream_error("connection-timeout", None)
                raise ConnectionError("Disconnected")
            raise TimeoutError("Timeout")

        result = next(iter(done)).result()
        return result

    @asyncio.coroutine
    def send_and_wait_for(self,
                          nodes_to_send,
                          tokens,
                          timeout=None,
                          critical_timeout=True):
        return self._send_andor_wait_for(
            nodes_to_send,
            tokens,
            timeout=timeout,
            critical_timeout=critical_timeout)

    def stream_error(self, tag, text):
        node = self._tx_makeelement(
            "{{{}}}error".format(namespaces.xmlstream),
            nsmap={
                "stream": namespaces.xmlstream,
                None: namespaces.streams
            })
        node.append(
            node.makeelement("{{{}}}{}".format(namespaces.streams, tag)))
        if text:
            text_node = node.makeelement(
                "{{{}}}text".format(namespaces.streams))
            text_node.text = text
            node.append(text_node)
        self._tx_send_node(node)
        del node
        self.close()

    @property
    def stream_level_hooks(self):
        return self._stream_level_node_hooks

    def make_iq(self):
        return etree.fromstring(
            b"""<iq xmlns="jabber:client" />""",
            parser=self._rx_parser)

    def make_message(self):
        return etree.fromstring(
            b"""<message xmlns="jabber:client" />""",
            parser=self._rx_parser)

    def make_presence(self):
        return etree.fromstring(
            b"""<presence xmlns="jabber:client" />""",
            parser=self._rx_parser)
