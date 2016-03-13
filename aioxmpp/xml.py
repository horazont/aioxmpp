"""
:mod:`~aioxmpp.xml` --- XML utilities and interfaces for handling XMPP XML streams
#######################################################################################

This module provides a few classes and functions which are useful when
generating and parsing XML streams for XMPP.

Generating XML streams
======================

The most useful class here is the :class:`XMPPXMLGenerator`:

.. autoclass:: XMPPXMLGenerator

The following generator function can be used to send several
:class:`~.stanza_model.XSO` instances along an XMPP stream without
bothering with any cleanup.

.. autofunction:: write_xmlstream

.. autofunction:: write_objects

.. autoclass:: AbortStream

Processing XML streams
======================

To convert streams of SAX events to :class:`~.stanza_model.XSO`
instances, the following classes and functions can be used:

.. autoclass:: XMPPXMLProcessor

.. autoclass:: XMPPLexicalHandler

.. autofunction:: make_parser

Utility functions
=================

.. autofunction:: serialize_single_xso

.. autofunction:: write_single_xso

.. autofunction:: read_xso

.. autofunction:: read_single_xso

"""

import ctypes
import io
import os

import xml.sax
import xml.sax.saxutils

from enum import Enum

from . import errors, structs, xso
from .utils import namespaces


if os.uname().sysname == 'Darwin':
    libxml2 = ctypes.cdll.LoadLibrary('libxml2.dylib')
else:
    libxml2 = ctypes.cdll.LoadLibrary('libxml2.so')


def xmlValidateNameValue_str(s):
    return bool(xmlValidateNameValue_buf(s.encode("utf-8")))


def xmlValidateNameValue_buf(b):
    if b"\0" in b:
        return False
    return bool(libxml2.xmlValidateNameValue(b))


class AbortStream(Exception):
    """
    This is a signal exception which causes :func:`write_xmlstream` to stop
    immediately without closing the stream.
    """


class XMPPXMLGenerator:
    """
    :class:`XMPPXMLGenerator` works similar to
    :class:`xml.sax.saxutils.XMLGenerator`, but has a few key differences:

    * It supports **only** namespace-conforming XML documents
    * It automatically chooses namespace prefixes if a namespace has not been
      declared
    * It is in general stricter on (explicit) namespace declarations, to avoid
      ambiguities
    * It always uses utf-8 ☺
    * It allows explicit flushing

    `out` must be a file-like supporting both :meth:`file.write` and
    :meth:`file.flush`. `encoding` specifies the encoding which is used and
    **must** be ``utf-8`` for XMPP.

    If `short_empty_elements` is true, empty elements are rendered as
    ``<foo/>`` instead of ``<foo></foo>``, unless a flush occurs before the
    call to :meth:`endElementNS`, in which case the opening is finished before
    flushing, thus the long form is generated.

    If `sorted_attributes` is :data:`True`, attributes are emitted in the
    lexical order of their qualified names (except for namespace declarations,
    which are always sorted and always before the normal attributes). The
    default is not to do this, for performance. During testing, however, it is
    useful to have a consistent oder on the attributes.

    Implementation of the SAX content handler interface (see
    :class:`xml.sax.handler.ContentHandler`):

    .. automethod:: startDocument

    .. automethod:: startPrefixMapping(prefix, uri)

    .. automethod:: startElementNS

    .. automethod:: characters

    .. automethod:: endElementNS

    .. automethod:: endPrefixMapping

    .. automethod:: endDocument

    The following SAX content handler methods have deliberately not been
    implemented:

    .. automethod:: setDocumentLocator

    .. automethod:: skippedEntity

    .. automethod:: ignorableWhitespace

    .. automethod:: startElement

    .. automethod:: endElement

    These methods produce content which is invalid in XMPP XML streams and thus
    always raise :class:`ValueError`:

    .. automethod:: processingInstruction

    In addition to the SAX content handler interface, the following methods are
    provided:

    .. automethod:: flush

    """
    def __init__(self, out,
                 short_empty_elements=True,
                 sorted_attributes=False):
        self._write = out.write
        if hasattr(out, "flush"):
            self._flush = out.flush
        else:
            self._flush = None
        self._ns_map_stack = [({}, {}, 0)]
        self._curr_ns_map = {}
        self._short_empty_elements = short_empty_elements
        self._sorted_attributes = sorted_attributes
        self._pending_start_element = False
        self._ns_prefixes_floating_in = {}
        self._ns_prefixes_floating_out = {}
        self._ns_auto_prefixes_floating_in = set()
        self._ns_decls_floating_in = {}
        self._ns_counter = -1

    def _roll_prefix(self):
        prefix_number = self._ns_counter + 1
        while True:
            prefix = "ns{}".format(prefix_number)
            if prefix not in self._ns_prefixes_floating_in:
                break
            prefix_number += 1
        self._ns_counter = prefix_number
        return prefix

    def _qname(self, name, attr=False):
        if not isinstance(name, tuple):
            raise ValueError("names must be tuples")

        if ":" in name[1] or not xmlValidateNameValue_str(name[1]):
            raise ValueError("invalid name: {!r}".format(name[1]))

        if name[0]:
            if name[0] == "http://www.w3.org/XML/1998/namespace":
                return "xml:" + name[1]
            try:
                prefix = self._ns_decls_floating_in[name[0]]
            except KeyError:
                try:
                    prefix = self._curr_ns_map[name[0]]
                    if prefix in self._ns_prefixes_floating_in:
                        raise KeyError()
                except KeyError:
                    # namespace is undeclared, we have to declare it..
                    prefix = self._roll_prefix()
                    self.startPrefixMapping(prefix, name[0], auto=True)
            if prefix:
                return ":".join((prefix, name[1]))

        elif   (not attr and
                (None in self._curr_ns_map or
                 None in self._ns_prefixes_floating_in)):
            raise ValueError("cannot create unnamespaced element when "
                             "prefixless namespace is bound")

        return name[1]

    def _finish_pending_start_element(self):
        if not self._pending_start_element:
            return
        self._pending_start_element = False
        self._write(b">")

    def _pin_floating_ns_decls(self, old_counter):
        if self._ns_prefixes_floating_out:
            raise RuntimeError("namespace prefix has not been closed")

        new_decls = self._ns_decls_floating_in
        new_prefixes = self._ns_prefixes_floating_in
        self._ns_map_stack.append(
            (
                self._curr_ns_map.copy(),
                set(new_prefixes) - self._ns_auto_prefixes_floating_in,
                old_counter
            )
        )

        cleared_new_prefixes = dict(new_prefixes)
        for uri, prefix in self._curr_ns_map.items():
            try:
                new_uri = cleared_new_prefixes[prefix]
            except KeyError:
                pass
            else:
                if new_uri == uri:
                    del cleared_new_prefixes[prefix]

        self._curr_ns_map.update(new_decls)
        self._ns_decls_floating_in = {}
        self._ns_prefixes_floating_in = {}

        return cleared_new_prefixes

    def startDocument(self):
        """
        Start the document. This method *must* be called before any other
        content handler method.
        """
        # yes, I know the doctext is not enforced. It might become enforced in
        # a later version though, when I find a compelling reason why it is
        # needed.
        self._write(b'<?xml version="1.0"?>')

    def startPrefixMapping(self, prefix, uri, *, auto=False):
        """
        Start a prefix mapping which maps the given `prefix` to the given
        `uri`.

        Note that prefix mappings are handled transactional. All announcements
        of prefix mappings are collected until the next call to
        :meth:`startElementNS`. At that point, the mappings are collected and
        start to override the previously declared mappings until the
        corresponding :meth:`endElementNS` call.

        Also note that calling :meth:`startPrefixMapping` is not mandatory; you
        can use any namespace you like at any time. If you use a namespace
        whose URI has not been associated with a prefix yet, a free prefix will
        automatically be chosen. To avoid unneccessary performance penalties,
        do not use prefixes of the form ``"{:d}".format(n)``, for any
        non-negative number of `n`.

        It is however required to call :meth:`endPrefixMapping` after a
        :meth:`endElementNS` call for all namespaces which have been announced
        directly before the :meth:`startElementNS` call (except for those which
        have been chosen automatically). Not doing so will result in a
        :class:`RuntimeError` at the next :meth:`startElementNS` or
        :meth:`endElementNS` call.

        During a transaction, it is not allowed to declare the same prefix
        multiple times.
        """

        if     (prefix is not None and
                (prefix == "xml" or
                 prefix == "xmlns" or
                 not xmlValidateNameValue_str(prefix) or
                 ":" in prefix)):
            raise ValueError("not a valid prefix: {!r}".format(prefix))

        if prefix in self._ns_prefixes_floating_in:
            raise ValueError("prefix already declared for next element")
        if auto:
            self._ns_auto_prefixes_floating_in.add(prefix)
        self._ns_prefixes_floating_in[prefix] = uri
        self._ns_decls_floating_in[uri] = prefix

    def startElementNS(self, name, qname, attributes=None):
        """
        Start a sub-element. `name` must be a tuple of ``(namespace_uri,
        localname)`` and `qname` is ignored. `attributes` must be a dictionary
        mapping attribute tag tuples (``(namespace_uri, attribute_name)``) to
        string values. To use unnamespaced attributes, `namespace_uri` can be
        false (e.g. :data:`None` or the empty string).

        To use unnamespaced elements, `namespace_uri` in `name` must be false
        **and** no namespace without prefix must be currently active. If a
        namespace without prefix is active and `namespace_uri` in `name` is
        false, :class:`ValueError` is raised.

        Attribute values are of course automatically escaped.
        """
        self._finish_pending_start_element()
        old_counter = self._ns_counter

        qname = self._qname(name)
        if attributes:
            attrib = [
                (self._qname(attrname, attr=True), value)
                for attrname, value in attributes.items()
            ]
            for attrqname, _ in attrib:
                if attrqname == "xmlns":
                    raise ValueError("xmlns not allowed as attribute name")
        else:
            attrib = []

        pending_prefixes = self._pin_floating_ns_decls(old_counter)

        self._write(b"<")
        self._write(qname.encode("utf-8"))

        if None in pending_prefixes:
            uri = pending_prefixes.pop(None)
            self._write(b" xmlns=")
            self._write(xml.sax.saxutils.quoteattr(uri).encode("utf-8"))

        for prefix, uri in sorted(pending_prefixes.items()):
            self._write(b" xmlns")
            if prefix:
                self._write(b":")
                self._write(prefix.encode("utf-8"))
            self._write(b"=")
            self._write(
                xml.sax.saxutils.quoteattr(uri).encode("utf-8")
            )

        if self._sorted_attributes:
            attrib.sort()

        for attrname, value in attrib:
            self._write(b" ")
            self._write(attrname.encode("utf-8"))
            self._write(b"=")
            self._write(
                xml.sax.saxutils.quoteattr(value).encode("utf-8")
            )

        if self._short_empty_elements:
            self._pending_start_element = name
        else:
            self._write(b">")

    def endElementNS(self, name, qname):
        """
        End a previously started element. `name` must be a ``(namespace_uri,
        localname)`` tuple and `qname` is ignored.
        """
        if self._ns_prefixes_floating_out:
            raise RuntimeError("namespace prefix has not been closed")

        if self._pending_start_element == name:
            self._pending_start_element = False
            self._write(b"/>")
        else:
            self._write(b"</")
            self._write(self._qname(name).encode("utf-8"))
            self._write(b">")

        self._curr_ns_map, self._ns_prefixes_floating_out, self._ns_counter = \
            self._ns_map_stack.pop()

    def endPrefixMapping(self, prefix):
        """
        End a prefix mapping declared with :meth:`startPrefixMapping`. See
        there for more details.
        """
        self._ns_prefixes_floating_out.remove(prefix)

    def startElement(self, name, attributes=None):
        """
        Not supported; only elements with proper namespacing are supported by
        this generator.
        """
        raise NotImplementedError("namespace-incorrect documents are "
                                  "not supported")

    def characters(self, chars):
        """
        Put character data in the currently open element. Special characters
        (such as ``<``, ``>`` and ``&``) are escaped.

        If `chars` contains any ASCII control character, :class:`ValueError` is
        raised.
        """
        self._finish_pending_start_element()
        if any(0 <= ord(c) <= 8 or
               11 <= ord(c) <= 12 or
               14 <= ord(c) <= 31
               for c in chars):
            raise ValueError("control characters are not allowed in "
                             "well-formed XML")
        self._write(xml.sax.saxutils.escape(chars).encode("utf-8"))

    def processingInstruction(self, target, data):
        """
        Not supported; explicitly forbidden in XMPP. Raises
        :class:`ValueError`.
        """
        raise ValueError("restricted xml: processing instruction forbidden")

    def skippedEntity(self, name):
        """
        Not supported; there is no use case. Raises
        :class:`NotImplementedError`.
        """
        raise NotImplementedError("skippedEntity")

    def setDocumentLocator(self, locator):
        """
        Not supported; there is no use case. Raises
        :class:`NotImplementedError`.
        """
        raise NotImplementedError("setDocumentLocator")

    def ignorableWhitespace(self, whitespace):
        """
        Not supported; could be mapped to :meth:`characters`.
        """
        raise NotImplementedError("ignorableWhitespace")

    def endElement(self, name):
        """
        Not supported; only elements with proper namespacing are supported by
        this generator.
        """
        self.startElement(name)

    def endDocument(self):
        """
        This must be called at the end of the document. Note that this does not
        call :meth:`flush`.
        """

    def flush(self):
        """
        Call :meth:`flush` on the object passed to the `out` argument of the
        constructor. In addition, any unfinished opening tags are finished,
        which can lead to expansion of the generated XML code (see note on the
        `short_empty_elements` argument at the class documentation).
        """
        self._finish_pending_start_element()
        if self._flush:
            self._flush()


def write_objects(writer, *, autoflush=False):
    """
    Return a generator. All :class:`.xso.XSO` objects sent into the generator
    (using it’s :meth:`send` method) are written to the given
    *writer*. *writer* must be an object supporting the namespace-aware SAX
    interface.

    If *autoflush* is true, :meth:`flush` is called on *writer* after each
    object. Note that not all writers support :meth:`flush`, as it is not part
    of the official SAX specification.
    """
    try:
        while True:
            obj = yield
            obj.unparse_to_sax(writer)
            if autoflush:
                writer.flush()
    except AbortStream:
        pass


def write_xmlstream(f,
                    to,
                    from_=None,
                    version=(1, 0),
                    nsmap={},
                    sorted_attributes=False):
    """
    Return a generator, which writes an XMPP XML stream on the file-like object
    `f`.

    First, the generator writes the stream header and declares all namespaces
    given in `nsmap` plus the xmlstream namespace, then the output is flushed
    and the generator yields.

    `to` must be a :class:`~.structs.JID` which refers to the peer. `from_` may
    be the JID identifying the local side, but see `RFC 6120 for considerations
    <https://tools.ietf.org/html/rfc6120#section-4.7.1>`_. `version` is the
    tuple of integers representing the locally supported XMPP version.

    `sorted_attributes` is passed to the :class:`XMPPXMLGenerator` which is
    used by this function.

    Now, user code can send :class:`~.xso.XSO` objects to the
    generator using its :meth:`send` method. These objects get serialized to
    the XML stream. Any exception raised during that is re-raised and the
    stream is closed.

    Using the :meth:`throw` method to throw a :class:`AbortStream` exception
    will immediately stop the generator without closing the stream
    properly, but with a last flush call to the writer. This can be used to
    reset the stream.
    """
    nsmap_to_use = {
        "stream": namespaces.xmlstream
    }
    nsmap_to_use.update(nsmap)

    attrs = {
        (None, "to"): str(to),
        (None, "version"): ".".join(map(str, version))
    }
    if from_:
        attrs[None, "from"] = str(from_)

    writer = XMPPXMLGenerator(
        out=f,
        short_empty_elements=True,
        sorted_attributes=sorted_attributes)

    writer.startDocument()
    for prefix, uri in nsmap_to_use.items():
        writer.startPrefixMapping(prefix, uri)
    writer.startElementNS(
        (namespaces.xmlstream, "stream"),
        None,
        attrs)
    writer.flush()

    abort = False

    try:
        while True:
            try:
                obj = yield
            except AbortStream:
                abort = True
                return
            obj.unparse_to_sax(writer)
            writer.flush()
    finally:
        if not abort:
            writer.endElementNS((namespaces.xmlstream, "stream"), None)
            for prefix in nsmap_to_use:
                writer.endPrefixMapping(prefix)
            writer.endDocument()
        writer.flush()


class ProcessorState(Enum):
    CLEAN = 0
    STARTED = 1
    STREAM_HEADER_PROCESSED = 2
    STREAM_FOOTER_PROCESSED = 3
    EXCEPTION_BACKOFF = 4


class XMPPXMLProcessor:
    """
    This class is a :class:`xml.sax.handler.ContentHandler`. It
    can be used to parse an XMPP XML stream.

    When used with a :class:`xml.sax.xmlreader.XMLReader`, it gradually
    processes the incoming XML stream. If any restricted XML is encountered, an
    appropriate :class:`~.errors.StreamError` is raised.

    .. warning::

       To achieve compliance with XMPP, it is recommended to use
       :class:`XMPPLexicalHandler` as lexical handler, using
       :meth:`xml.sax.xmlreader.XMLReader.setProperty`::

            parser.setProperty(xml.sax.handler.property_lexical_handler,
                               XMPPLexicalHandler)

       Otherwise, invalid XMPP XML such as comments, entity references and DTD
       declarations will not be caught.

    **Exception handling**: When an exception occurs while parsing a
    stream-level element, such as a stanza, the exception is stored internally
    and exception handling is invoked. During exception handling, all SAX
    events are dropped, until the stream-level element has been completely
    processed by the parser. Then, if available, :attr:`on_exception` is
    called, with the stored exception as the only argument. If
    :attr:`on_exception` is false (e.g. :data:`None`), the exception is
    re-raised from the :meth:`endElementNS` handler, in turn most likely
    destroying the SAX parsers internal state.

    .. attribute:: on_exception

       May be a callable or :data:`None`. If not false, the value will get
       called when exception handling has finished, with the exception as the
       only argument.

    .. attribute:: on_stream_footer

       May be a callable or :data:`None`. If not false, the value will get
       called whenever a stream footer is processed.

    .. attribute:: on_stream_header

       May be a callable or :data:`None`. If not false, the value will get
       called whenever a stream header is processed.

    .. autoattribute:: stanza_parser
    """

    def __init__(self):
        super().__init__()
        self._state = ProcessorState.CLEAN
        self._stanza_parser = None
        self._stored_exception = None
        self.on_stream_header = None
        self.on_stream_footer = None
        self.on_exception = None

        self.remote_version = None
        self.remote_from = None
        self.remote_to = None
        self.remote_id = None

    @property
    def stanza_parser(self):
        """
        A :class:`~.xso.XSOParser` object (or compatible) which will
        receive the sax-ish events used in :mod:`~aioxmpp.xso`. It
        is driven using an instance of :class:`~.xso.SAXDriver`.

        This object can only be set before :meth:`startDocument` has been
        called (or after :meth:`endDocument` has been called).
        """
        return self._stanza_parser

    @stanza_parser.setter
    def stanza_parser(self, value):
        if self._state != ProcessorState.CLEAN:
            raise RuntimeError("invalid state: {}".format(self._state))
        self._stanza_parser = value

    def processingInstruction(self, target, foo):
        raise errors.StreamError(
            (namespaces.streams, "restricted-xml"),
            "processing instructions are not allowed in XMPP"
        )

    def characters(self, characters):
        if self._state == ProcessorState.EXCEPTION_BACKOFF:
            pass
        elif self._state != ProcessorState.STREAM_HEADER_PROCESSED:
            raise RuntimeError("invalid state: {}".format(self._state))
        else:
            self._driver.characters(characters)

    def startDocument(self):
        if self._state != ProcessorState.CLEAN:
            raise RuntimeError("invalid state: {}".format(self._state))
        self._state = ProcessorState.STARTED
        self._depth = 0
        self._driver = xso.SAXDriver(self._stanza_parser)

    def startElement(self, name, attributes):
        raise RuntimeError("incorrectly configured parser: "
                           "startElement called (instead of startElementNS)")

    def endElement(self, name):
        raise RuntimeError("incorrectly configured parser: "
                           "endElement called (instead of endElementNS)")

    def endDocument(self):
        if self._state != ProcessorState.STREAM_FOOTER_PROCESSED:
            raise RuntimeError("invalid state: {}".format(self._state))
        self._state = ProcessorState.CLEAN
        self._driver = None

    def startPrefixMapping(self, prefix, uri):
        pass

    def endPrefixMapping(self, prefix):
        pass

    def startElementNS(self, name, qname, attributes):
        if self._state == ProcessorState.STREAM_HEADER_PROCESSED:
            try:
                self._driver.startElementNS(name, qname, attributes)
            except Exception as exc:
                self._stored_exception = exc
                self._state = ProcessorState.EXCEPTION_BACKOFF
            self._depth += 1
            return
        elif self._state == ProcessorState.EXCEPTION_BACKOFF:
            self._depth += 1
            return
        elif self._state != ProcessorState.STARTED:
            raise RuntimeError("invalid state: {}".format(self._state))

        if name != (namespaces.xmlstream, "stream"):
            raise errors.StreamError(
                (namespaces.streams, "invalid-namespace"),
                "stream has invalid namespace or localname"
            )

        attributes = dict(attributes)
        try:
            self.remote_version = tuple(
                map(int, attributes.pop((None, "version"), "0.9").split("."))
            )
        except ValueError as exc:
            raise errors.StreamError(
                (namespaces.streams, "unsupported-version"),
                str(exc)
            )

        remote_to = attributes.pop((None, "to"), None)
        if remote_to is not None:
            remote_to = structs.JID.fromstr(remote_to)
        self.remote_to = remote_to

        try:
            self.remote_from = structs.JID.fromstr(
                attributes.pop((None, "from"))
            )
        except KeyError:
            raise errors.StreamError(
                (namespaces.streams, "undefined-condition"),
                "from attribute required in response header"
            )
        try:
            self.remote_id = attributes.pop((None, "id"))
        except KeyError:
            raise errors.StreamError(
                (namespaces.streams, "undefined-condition"),
                "id attribute required in response header"
            )

        if self.on_stream_header:
            self.on_stream_header()

        self._state = ProcessorState.STREAM_HEADER_PROCESSED
        self._depth += 1

    def endElementNS(self, name, qname):
        if self._state == ProcessorState.STREAM_HEADER_PROCESSED:
            self._depth -= 1
            if self._depth > 0:
                return self._driver.endElementNS(name, qname)
            else:
                if self.on_stream_footer:
                    self.on_stream_footer()
                self._state = ProcessorState.STREAM_FOOTER_PROCESSED
        elif self._state == ProcessorState.EXCEPTION_BACKOFF:
            self._depth -= 1
            if self._depth == 1:
                self._state = ProcessorState.STREAM_HEADER_PROCESSED
                exc = self._stored_exception
                self._stored_exception = None
                if self.on_exception:
                    self.on_exception(exc)
                else:
                    raise exc
        else:
            raise RuntimeError("invalid state: {}".format(self._state))


class XMPPLexicalHandler:
    """
    A `lexical handler
    <http://www.saxproject.org/apidoc/org/xml/sax/ext/LexicalHandler.html>`_
    which rejects certain contents which are invalid in an XMPP XML stream:

    * comments,
    * dtd declarations,
    * non-predefined entities.

    The class can be used as lexical handler directly; all methods are
    stateless and can be used both on the class and on objects of the class.

    """
    PREDEFINED_ENTITIES = {"amp", "lt", "gt", "apos", "quot"}

    @classmethod
    def comment(cls, data):
        raise errors.StreamError(
            (namespaces.streams, "restricted-xml"),
            "comments are not allowed in XMPP"
        )

    @classmethod
    def startDTD(cls, name, publicId, systemId):
        raise errors.StreamError(
            (namespaces.streams, "restricted-xml"),
            "DTD declarations are not allowed in XMPP"
        )

    @classmethod
    def endDTD(cls):
        pass

    @classmethod
    def startCDATA(cls):
        pass

    @classmethod
    def endCDATA(cls):
        pass

    @classmethod
    def startEntity(cls, name):
        if name not in cls.PREDEFINED_ENTITIES:
            raise errors.StreamError(
                (namespaces.streams, "restricted-xml"),
                "non-predefined entities are not allowed in XMPP"
            )

    @classmethod
    def endEntity(cls, name):
        pass


def make_parser():
    """
    Create a parser which is suitably configured for parsing an XMPP XML
    stream. It comes equipped with :class:`XMPPLexicalHandler`.
    """
    p = xml.sax.make_parser()
    p.setFeature(xml.sax.handler.feature_namespaces, True)
    p.setFeature(xml.sax.handler.feature_external_ges, False)
    p.setProperty(xml.sax.handler.property_lexical_handler,
                  XMPPLexicalHandler)
    return p


def serialize_single_xso(x):
    """
    Serialize a single XSO `x` to a string. This is potentially very slow and
    should only be used for debugging purposes. It is generally more efficient
    to use a :class:`XMPPXMLGenerator` to stream elements.
    """
    buf = io.BytesIO()
    gen = XMPPXMLGenerator(buf,
                           short_empty_elements=True,
                           sorted_attributes=True)
    x.unparse_to_sax(gen)
    return buf.getvalue().decode("utf8")


def write_single_xso(x, dest):
    """
    Write a single XSO `x` to a binary file-like object `dest`.
    """
    gen = XMPPXMLGenerator(dest,
                           short_empty_elements=True,
                           sorted_attributes=True)
    x.unparse_to_sax(gen)


def read_xso(src, xsomap):
    """
    Read a single XSO from a binary file-like input `src` containing an XML
    document.

    `xsomap` must be a mapping which maps :class:`~.XSO` subclasses
    to callables. These will be registered at a newly created
    :class:`.xso.XSOParser` instance which will be used to parse the  document
    in `src`.

    The `xsomap` is thus used to determine the class parsing the root element
    of the XML document. This can be used to support multiple versions.
    """

    xso_parser = xso.XSOParser()

    for class_, cb in xsomap.items():
        xso_parser.add_class(class_, cb)

    driver = xso.SAXDriver(xso_parser)

    parser = xml.sax.make_parser()
    parser.setFeature(
        xml.sax.handler.feature_namespaces,
        True)
    parser.setFeature(
        xml.sax.handler.feature_external_ges,
        False)
    parser.setContentHandler(driver)

    parser.parse(src)


def read_single_xso(src, type_):
    """
    Read a single :class:`~.XSO` of the given `type_` from the binary file-like
    input `src` and return the instance.
    """

    result = None

    def cb(instance):
        nonlocal result
        result = instance

    read_xso(src, {type_: cb})

    return result
