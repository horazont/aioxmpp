########################################################################
# File name: xml.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.xml` --- XML utilities and interfaces for handling XMPP XML streams
#######################################################################################

This module provides a few classes and functions which are useful when
generating and parsing XML streams for XMPP.

Generating XML streams
======================

The most useful class here is the :class:`XMPPXMLGenerator`:

.. autoclass:: XMPPXMLGenerator

.. autoclass:: XMLStreamWriter

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

"""  # NOQA: E501

import copy
import contextlib
import io

import xml.sax
import xml.sax.saxutils

from enum import Enum

from . import errors, structs, xso
from .utils import namespaces


_NAME_START_CHAR = [
    [ord(":"), ord("_")],
    range(ord("a"), ord("z")+1),
    range(ord("A"), ord("Z")+1),
    range(0xc0, 0xd7),
    range(0xd8, 0xf7),
    range(0xf8, 0x300),
    range(0x370, 0x37e),
    range(0x37f, 0x2000),
    range(0x200c, 0x200e),
    range(0x2070, 0x2190),
    range(0x2c00, 0x2ff0),
    range(0x3001, 0xd800),
    range(0xf900, 0xfdd0),
    range(0xfdf0, 0xfffe),
    range(0x10000, 0xf0000),
]

_NAME_CHAR = _NAME_START_CHAR + [
    [ord("-"), ord("."), 0xb7],
    range(ord("0"), ord("9")+1),
    range(0x0300, 0x0370),
    range(0x203f, 0x2041),
]
_NAME_CHAR.sort(key=lambda x: x[0])


def xmlValidateNameValue_str(s):
    if not s:
        return False
    ch = ord(s[0])
    if not any(ch in range_ for range_ in _NAME_START_CHAR):
        return False
    return all(
        any(ch in range_ for range_ in _NAME_CHAR)
        for ch in map(ord, s)
    )


def is_valid_cdata_str(s):
    for c in s:
        o = ord(c)
        if o >= 32:
            continue
        if o < 9 or 11 <= o <= 12 or 14 <= o <= 31:
            return False

    return True


class XMPPXMLGenerator:
    """
    Class to generate XMPP-conforming XML bytes.

    :param out: File-like object to which the bytes are written.
    :param short_empty_elements: Write empty elements as ``<foo/>`` instead of
        ``<foo></foo>``.
    :type short_empty_elements: :class:`bool`
    :param sorted_attributes: Sort the attributes in the output. Note: this
        comes with a performance penalty. See below.
    :type sorted_attributes: :class:`bool`
    :param additional_escapes: Sequence of characters to escape in CDATA.
    :type additional_escapes: :class:`~collections.abc.Iterable` of
        1-codepoint :class:`str` objects.

    :class:`XMPPXMLGenerator` works similar to
    :class:`xml.sax.saxutils.XMLGenerator`, but has a few key differences:

    * It supports **only** namespace-conforming XML documents
    * It automatically chooses namespace prefixes if a namespace has not been
      declared, while avoiding to use prefixes at all if possible
    * It is in general stricter on (explicit) namespace declarations, to avoid
      ambiguities
    * It always uses utf-8 ☺
    * It allows explicit flushing

    `out` must be a file-like supporting both :meth:`file.write` and
    :meth:`file.flush`.

    If `short_empty_elements` is true, empty elements are rendered as
    ``<foo/>`` instead of ``<foo></foo>``, unless a flush occurs before the
    call to :meth:`endElementNS`, in which case the opening is finished before
    flushing, thus the long form is generated.

    If `sorted_attributes` is true, attributes are emitted in the lexical order
    of their qualified names (except for namespace declarations, which are
    always sorted and always before the normal attributes). The default is not
    to do this, for performance. During testing, however, it is useful to have
    a consistent oder on the attributes.

    All characters in `additional_escapes` are escaped using XML entities. Note
    that ``<``, ``>`` and ``&`` are always escaped. `additional_escapes` is
    converted to a dictionary for use with :func:`~xml.sax.saxutils.escape` and
    :func:`~xml.sax.saxutils.quoteattr`. Passing a dictionary to
    `additional_escapes` or passing multi-character strings as elements of
    `additional_escapes` is **not** supported since it may be (ab-)used to
    create invalid XMPP XML. `additional_escapes` affects both CDATA in XML
    elements as well as attribute values.

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

    .. automethod:: buffer

    """
    def __init__(self, out,
                 short_empty_elements=True,
                 sorted_attributes=False,
                 additional_escapes=[]):
        self._write = out.write
        if hasattr(out, "flush"):
            self._flush = out.flush
        else:
            self._flush = None

        self._short_empty_elements = short_empty_elements
        self._sorted_attributes = sorted_attributes

        self._additional_escapes = {
            char: "&#{};".format(ord(char))
            for char in additional_escapes
        }

        # NOTE: when adding state, make sure to handle it in buffer() and to
        # add tests that buffer() handles it correctly
        self._ns_map_stack = [({}, set(), 0)]
        self._curr_ns_map = {}
        self._pending_start_element = False
        self._ns_prefixes_floating_in = {}
        self._ns_prefixes_floating_out = set()
        self._ns_auto_prefixes_floating_in = set()
        self._ns_decls_floating_in = {}
        self._ns_counter = -1

        # for buffer()
        self._buf = None
        self._buf_in_use = False

    def _roll_prefix(self, attr):
        if not attr and None not in self._ns_prefixes_floating_in:
            return None

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
                if attr and prefix is None:
                    raise KeyError()
            except KeyError:
                try:
                    prefix = self._curr_ns_map[name[0]]
                    if prefix in self._ns_prefixes_floating_in:
                        raise KeyError()
                    if attr and prefix is None:
                        raise KeyError()
                except KeyError:
                    # namespace is undeclared, we have to declare it..
                    prefix = self._roll_prefix(attr)
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
        old_ns_map = self._curr_ns_map
        self._ns_map_stack.append(
            (
                old_ns_map,
                set(new_prefixes) - self._ns_auto_prefixes_floating_in,
                old_counter
            )
        )

        new_ns_map = dict(new_decls)
        cleared_new_prefixes = dict(new_prefixes)
        for uri, prefix in old_ns_map.items():
            try:
                new_uri = new_prefixes[prefix]
            except KeyError:
                pass
            else:
                if new_uri != uri:
                    # -> the entry must be dropped because the prefix is
                    # re-assigned
                    continue

            # use setdefault: new entries (as assigned in new_ns_map =
            # dict(...)) need to win over old entries
            new_ns_map.setdefault(uri, prefix)

            try:
                new_uri = cleared_new_prefixes[prefix]
            except KeyError:
                pass
            else:
                if new_uri == uri:
                    del cleared_new_prefixes[prefix]

        self._curr_ns_map = new_ns_map
        self._ns_decls_floating_in = {}
        self._ns_prefixes_floating_in = {}
        self._ns_auto_prefixes_floating_in.clear()

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
        automatically be chosen. To avoid unnecessary performance penalties,
        do not use prefixes of the form ``"ns{:d}".format(n)``, for any
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
                xml.sax.saxutils.quoteattr(
                    value,
                    self._additional_escapes,
                ).encode("utf-8")
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
        if not is_valid_cdata_str(chars):
            raise ValueError("control characters are not allowed in "
                             "well-formed XML")
        self._write(xml.sax.saxutils.escape(
            chars,
            self._additional_escapes,
        ).encode("utf-8"))

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

    @contextlib.contextmanager
    def _save_state(self):
        """
        Helper context manager for :meth:`buffer` which saves the whole state.

        This is broken out in a separate method for readability and tested
        indirectly by testing :meth:`buffer`.
        """
        ns_prefixes_floating_in = copy.copy(self._ns_prefixes_floating_in)
        ns_prefixes_floating_out = copy.copy(self._ns_prefixes_floating_out)
        ns_decls_floating_in = copy.copy(self._ns_decls_floating_in)
        curr_ns_map = copy.copy(self._curr_ns_map)
        ns_map_stack = copy.copy(self._ns_map_stack)
        pending_start_element = self._pending_start_element
        ns_counter = self._ns_counter
        # XXX: I have been unable to find a test justifying copying this :/
        # for completeness, I’m still doing it
        ns_auto_prefixes_floating_in = \
            copy.copy(self._ns_auto_prefixes_floating_in)
        try:
            yield
        except:  # NOQA: E722
            self._ns_prefixes_floating_in = ns_prefixes_floating_in
            self._ns_prefixes_floating_out = ns_prefixes_floating_out
            self._ns_decls_floating_in = ns_decls_floating_in
            self._pending_start_element = pending_start_element
            self._curr_ns_map = curr_ns_map
            self._ns_map_stack = ns_map_stack
            self._ns_counter = ns_counter
            self._ns_auto_prefixes_floating_in = ns_auto_prefixes_floating_in
            raise

    @contextlib.contextmanager
    def buffer(self):
        """
        Context manager to temporarily buffer the output.

        :raise RuntimeError: If two :meth:`buffer` context managers are used
                             nestedly.

        If the context manager is left without exception, the buffered output
        is sent to the actual sink. Otherwise, it is discarded.

        In addition to the output being buffered, buffer also captures the
        entire state of the XML generator and restores it to the previous state
        if the context manager is left with an exception.

        This can be used to fail-safely attempt to serialise a subtree and
        return to a well-defined state if serialisation fails.

        :meth:`flush` is not called automatically.

        If :meth:`flush` is called while a :meth:`buffer` context manager is
        active, no actual flushing happens (but unfinished opening tags are
        closed as usual, see the `short_empty_arguments` parameter).
        """
        if self._buf_in_use:
            raise RuntimeError("nested use of buffer() is not supported")
        self._buf_in_use = True
        old_write = self._write
        old_flush = self._flush

        if self._buf is None:
            self._buf = io.BytesIO()
        else:
            try:
                self._buf.seek(0)
                self._buf.truncate()
            except BufferError:
                # we need a fresh buffer for this, the other is still in use.
                self._buf = io.BytesIO()

        self._write = self._buf.write
        self._flush = None
        try:
            with self._save_state():
                yield
            old_write(self._buf.getbuffer())
            if old_flush:
                old_flush()
        finally:
            self._buf_in_use = False
            self._write = old_write
            self._flush = old_flush


class XMLStreamWriter:
    """
    A convenient class to write a standard conforming XML stream.

    :param f: File-like object to write to.
    :param to: Address to which the connection is addressed.
    :type to: :class:`aioxmpp.JID`
    :param from_: Optional address from which the connection originates.
    :type from_: :class:`aioxmpp.JID`
    :param version: Version of the XML stream protocol.
    :type version: :class:`tuple` of (:class:`int`, :class:`int`)
    :param nsmap: Mapping of namespaces to declare at the stream header.

    .. note::

       The constructor *does not* send a stream header. :meth:`start` must be
       called explicitly to send a stream header.

    The generated stream header follows :rfc:`6120` and has the ``to`` and
    ``version`` attributes as well as optionally the ``from`` attribute
    (controlled by `from_`). In addition, the namespace prefixes defined by
    `nsmap` (mapping prefixes to namespace URIs) are declared on the stream
    header.

    .. note::

       It is unfortunately not allowed to use namespace prefixes in stanzas
       which were declared in stream headers as convenient as that would be.
       The option is thus only useful to declare the default namespace for
       stanzas.

    .. autoattribute:: closed

    The following methods are used to generate output:

    .. automethod:: start

    .. automethod:: send

    .. automethod:: abort

    .. automethod:: close
    """

    def __init__(self, f, to,
                 from_=None,
                 version=(1, 0),
                 nsmap={},
                 sorted_attributes=False):
        super().__init__()
        self._to = to
        self._from = from_
        self._version = version
        self._writer = XMPPXMLGenerator(
            out=f,
            short_empty_elements=True,
            sorted_attributes=sorted_attributes)
        self._nsmap_to_use = {
            "stream": namespaces.xmlstream
        }
        self._nsmap_to_use.update(nsmap)
        self._closed = False

    @property
    def closed(self):
        """
        True if the stream has been closed by :meth:`abort` or :meth:`close`.
        Read-only.
        """
        return self._closed

    def start(self):
        """
        Send the stream header as described above.
        """
        attrs = {
            (None, "to"): str(self._to),
            (None, "version"): ".".join(map(str, self._version))
        }
        if self._from:
            attrs[None, "from"] = str(self._from)

        self._writer.startDocument()
        for prefix, uri in self._nsmap_to_use.items():
            self._writer.startPrefixMapping(prefix, uri)
        self._writer.startElementNS(
            (namespaces.xmlstream, "stream"),
            None,
            attrs)
        self._writer.flush()

    def send(self, xso):
        """
        Send a single XML stream object.

        :param xso: Object to serialise and send.
        :type xso: :class:`aioxmpp.xso.XSO`
        :raises Exception: from any serialisation errors, usually
                           :class:`ValueError`.

        Serialise the `xso` and send it over the stream. If any serialisation
        error occurs, no data is sent over the stream and the exception is
        re-raised; the :meth:`send` method thus provides strong exception
        safety.

        .. warning::

           The behaviour of :meth:`send` after :meth:`abort` or :meth:`close`
           and before :meth:`start` is undefined.

        """
        with self._writer.buffer():
            xso.xso_serialise_to_sax(self._writer)

    def abort(self):
        """
        Abort the stream.

        The stream is flushed and the internal data structures are cleaned up.
        No stream footer is sent. The stream is :attr:`closed` afterwards.

        If the stream is already :attr:`closed`, this method does nothing.
        """
        if self._closed:
            return
        self._closed = True
        self._writer.flush()
        del self._writer

    def close(self):
        """
        Close the stream.

        The stream footer is sent and the internal structures are cleaned up.

        If the stream is already :attr:`closed`, this method does nothing.
        """
        if self._closed:
            return
        self._closed = True
        self._writer.endElementNS((namespaces.xmlstream, "stream"), None)
        for prefix in self._nsmap_to_use:
            self._writer.endPrefixMapping(prefix)
        self._writer.endDocument()
        del self._writer


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
        self.remote_lang = None

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
        self._stanza_parser.lang = self.remote_lang

    def processingInstruction(self, target, foo):
        raise errors.StreamError(
            errors.StreamErrorCondition.RESTRICTED_XML,
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
                errors.StreamErrorCondition.INVALID_NAMESPACE,
                "stream has invalid namespace or localname"
            )

        attributes = dict(attributes)
        try:
            self.remote_version = tuple(
                map(int, attributes.pop((None, "version"), "0.9").split("."))
            )
        except ValueError as exc:
            raise errors.StreamError(
                errors.StreamErrorCondition.UNSUPPORTED_VERSION,
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
                errors.StreamErrorCondition.UNDEFINED_CONDITION,
                "from attribute required in response header"
            )
        try:
            self.remote_id = attributes.pop((None, "id"))
        except KeyError:
            raise errors.StreamError(
                errors.StreamErrorCondition.UNDEFINED_CONDITION,
                "id attribute required in response header"
            )

        try:
            lang = attributes.pop((namespaces.xml, "lang"))
        except KeyError:
            self.remote_lang = None
        else:
            self.remote_lang = structs.LanguageTag.fromstr(lang)

        if self._stanza_parser is not None:
            self._stanza_parser.lang = self.remote_lang

        if self.on_stream_header:
            self.on_stream_header()

        self._state = ProcessorState.STREAM_HEADER_PROCESSED
        self._depth += 1

    def _end_element_exception_handling(self):
        self._state = ProcessorState.STREAM_HEADER_PROCESSED
        exc = self._stored_exception
        self._stored_exception = None
        if self.on_exception:
            self.on_exception(exc)
        else:
            raise exc

    def endElementNS(self, name, qname):
        if self._state == ProcessorState.STREAM_HEADER_PROCESSED:
            self._depth -= 1
            if self._depth > 0:
                try:
                    return self._driver.endElementNS(name, qname)
                except Exception as exc:
                    self._stored_exception = exc
                    self._state = ProcessorState.EXCEPTION_BACKOFF
                    if self._depth == 1:
                        self._end_element_exception_handling()
            else:
                if self.on_stream_footer:
                    self.on_stream_footer()
                self._state = ProcessorState.STREAM_FOOTER_PROCESSED

        elif self._state == ProcessorState.EXCEPTION_BACKOFF:
            self._depth -= 1
            if self._depth == 1:
                self._end_element_exception_handling()
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
            errors.StreamErrorCondition.RESTRICTED_XML,
            "comments are not allowed in XMPP"
        )

    @classmethod
    def startDTD(cls, name, publicId, systemId):
        raise errors.StreamError(
            errors.StreamErrorCondition.RESTRICTED_XML,
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
                errors.StreamErrorCondition.RESTRICTED_XML,
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
    x.xso_serialise_to_sax(gen)
    return buf.getvalue().decode("utf8")


def write_single_xso(x, dest):
    """
    Write a single XSO `x` to a binary file-like object `dest`.
    """
    gen = XMPPXMLGenerator(dest,
                           short_empty_elements=True,
                           sorted_attributes=True)
    x.xso_serialise_to_sax(gen)


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
