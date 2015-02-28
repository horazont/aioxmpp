import abc
import copy

import lxml.builder

from . import stanza, errors
from .utils import *

__all__ = ["lookup"]

lookup = etree.ElementNamespaceClassLookup()

def configure_xmpp_parser(parser):
    """
    Return an instance of *cls* (which is, by default, an
    :class:`lxml.etree.XMLPullParser`), which is configured to parse an XMPP XML
    stream.
    """
    parser.set_element_class_lookup(lookup)

class XMLStreamContext:
    DEFAULT_PARSER_OPTIONS = {
        "resolve_entities": True
    }

    def __init__(self, *, parser_options={}):
        super().__init__()
        use_parser_options = self.DEFAULT_PARSER_OPTIONS
        use_parser_options.update(parser_options)
        self._parser = self._mk_parser(use_parser_options)

    @abc.abstractclassmethod
    def _mk_parser(cls, options):
        """
        Create and return a new parser for this object. This is called during
        construction of the :class:`XMLStreamContext` base class. The *options*
        argument receives the :attr:`DEFAULT_PARSER_OPTIONS`, updated with any
        options passed to the constructor via the *parser_options* argument.
        """

    @property
    def parser(self):
        return self._parser

class XMLStreamReceiverContext(XMLStreamContext):
    STREAM_HEADER_TAG = "{{{}}}stream".format(namespaces.xmlstream)

    def __init__(self, *, parser_options={}):
        super().__init__(parser_options=parser_options)
        self._stream_id = None
        self._root = None
        self._closed = False
        self._ready = False

    @classmethod
    def _mk_parser(cls, options):
        parser = etree.XMLPullParser(
            ("start", "end", "comment", "pi"),
            **options)
        configure_xmpp_parser(parser)
        return parser

    def _process_stream_header(self, node):
        docinfo = node.getroottree().docinfo
        if    (docinfo.doctype or
               docinfo.externalDTD or
               docinfo.internalDTD or
               docinfo.system_url):
            raise errors.SendStreamError(
                "restricted-xml",
                "usage of dtd is not allowed")

        version = node.get("version")
        if version is None:
            raise errors.SendStreamError(
                "unsupported-version",
                text="missing version tag")

        try:
            version = tuple(map(int, version.split(".")))
        except (ValueError, TypeError):
            raise errors.SendStreamError(
                "unsupported-version",
                text="malformed version")

        if version[0] != 1:
            raise errors.SendStreamError(
                "unsupported-version",
                text="unsupported version")

        self._stream_id = node.get("id")
        self._root = node

    def _process_stream_footer(self):
        self._root = None
        self._stream_id = None
        self.close()

    def close(self):
        if self._closed:
            return

        self._parser.close()
        self._closed = True
        self._ready = False

    def feed(self, data):
        try:
            self._parser.feed(data)
        except etree.XMLSyntaxError as err:
            # XXX: these error codes are taken from the libxml2 API
            # documentation, and selected defensively
            if 26 <= err.code <= 30:
                raise errors.SendStreamError(
                    "restricted-xml",
                    text="entities not allowed")
            raise

    def read_stream_level_nodes(self):
        if not self._ready:
            raise RuntimeError("Call start() first until result is positive")

        if self._closed:
            yield None
            return

        for ev, node in self._parser.read_events():
            # detect duplicate stream headers
            if     (ev == "start" and
                    node.getparent() is self._root and
                    node.tag == self.STREAM_HEADER_TAG):
                raise errors.SendStreamError(
                    "unsupported-stanza-type",
                    text="duplicate stream header")
            elif ev == "end":
                if node.getparent() is None:
                    # end of stream
                    yield None
                    self._process_stream_footer()
                elif node.getparent() is self._root:
                    self._root.remove(node)
                    yield node
            elif ev == "comment":
                raise errors.SendStreamError(
                    "restricted-xml",
                    text="comments not allowed")
            elif ev == "pi":
                raise errors.SendStreamError(
                    "restricted-xml",
                    text="processing instructions not allowed")

    @property
    def ready(self):
        return self._ready

    @property
    def root(self):
        return self._root

    def start(self):
        if self._ready:
            return True

        if self._closed:
            raise RuntimeError("Calling start() on closed receiver")

        for ev, node in self._parser.read_events():
            if ev == "start" and node.getparent() is None:
                if node.tag != self.STREAM_HEADER_TAG:
                    raise errors.SendStreamError(
                        "invalid-namespace",
                        text="Invalid root element: {}".format(node.tag)
                    )

                assert self._stream_id is None
                self._process_stream_header(node)
                self._ready = True
                break

        return self._ready

    @property
    def stream_id(self):
        return self._stream_id

class XMLStreamSenderContext(XMLStreamContext):
    def __init__(self, default_namespace, *,
                 override_parser=None,
                 parser_options={}):
        if override_parser:
            parser_options["__override"] = override_parser

        self.nsmap = {}
        if default_namespace:
            self.nsmap[None] = default_namespace
            self._namespace_prefix = "{{{}}}".format(default_namespace)
        else:
            self._namespace_prefix = ""

        root_nsmap = self.nsmap.copy()
        root_nsmap["stream"] = namespaces.xmlstream

        super().__init__(parser_options=parser_options)
        self.root = self._parser.makeelement(
            "{{{}}}stream".format(namespaces.xmlstream),
            nsmap=root_nsmap)
        self.E = lxml.builder.ElementMaker(
            nsmap=self.nsmap,
            makeelement=self.makeelement)

        # verify that parser works correctly
        # XXX: rewrite is due
        # assert isinstance(self.makeelement("{jabber:client}iq"), stanza.IQ)
        # assert isinstance(self.E("{jabber:client}iq"), stanza.IQ)

    def __call__(self, *args, **kwargs):
        return self.E(*args, **kwargs)

    @classmethod
    def _mk_parser(cls, options):
        try:
            return parser_options["__override"]
        except:
            # if options == cls.DEFAULT_PARSER_OPTIONS:
            #     return etree.get_default_parser()
            parser = etree.XMLParser(**options)
            configure_xmpp_parser(parser)
            return parser

    def makeelement(self, *args, nsmap={}, **kwargs):
        if nsmap:
            use_nsmap = copy.copy(self.nsmap)
            use_nsmap.update(nsmap)
        else:
            use_nsmap = self.nsmap
        return self._parser.makeelement(*args,
                                        nsmap=use_nsmap,
                                        **kwargs)

    def default_ns_builder(self, namespace):
        return self.custom_builder(namespace=namespace,
                                   nsmap={None: namespace})

    def custom_builder(self, **kwargs):
        return lxml.builder.ElementMaker(
            makeelement=self._parser.makeelement,
            **kwargs)

    def _make_generic(self, localname, *,
                      to=None, from_=None,
                      type_=None, id_=None):
        el = self.E(self._namespace_prefix + localname)
        # verify that construction worked properly
        # XXX: rewrite is due
        # assert el.__class__ is not lxml.etree._Element
        if to is not None:
            el.to = to
        if from_ is not None:
            el.from_ = from_
        if type_ is not None:
            el.type_ = type_
        if id_ is not None:
            el.id_ = id_
        return el

    def make_iq(self, *, to=None, from_=None, type_=None, id_=None):
        return self._make_generic("iq",
                                  to=to, from_=from_,
                                  type_=type_, id_=id_)

    def make_message(self, *, to=None, from_=None, type_=None, id_=None):
        return self._make_generic("message",
                                  to=to, from_=from_,
                                  type_=type_, id_=id_)

    def make_presence(self, *, to=None, from_=None, type_=None, id_=None):
        return self._make_generic("presence",
                                  to=to, from_=from_,
                                  type_=type_, id_=id_)

    def make_reply(self, stanza, **kwargs):
        return stanza._make_reply(self, **kwargs)

_new_parser = etree.XMLParser(**XMLStreamContext.DEFAULT_PARSER_OPTIONS)
configure_xmpp_parser(_new_parser)
etree.set_default_parser(_new_parser)
del _new_parser

default_tx_context = XMLStreamSenderContext("jabber:client")

makeelement = default_tx_context.makeelement
E = default_tx_context.E
