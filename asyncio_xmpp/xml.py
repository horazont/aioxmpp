import ctypes

libxml2 = ctypes.cdll.LoadLibrary("libxml2.so")

def xmlValidateNameValue_str(s):
    return bool(xmlValidateNameValue_buf(s.encode("utf-8")))

def xmlValidateNameValue_buf(b):
    if b"\0" in b:
        return False
    return bool(libxml2.xmlValidateNameValue(b))

import xml.sax
import xml.sax.saxutils

import lxml.sax

from .utils import namespaces, etree


class AbortStream(Exception):
    pass


class AbortableContext:
    def __init__(self, cm):
        self._cm = cm
        self._cm_exit = type(cm).__exit__

    def __enter__(self):
        self._value = type(self._cm).__enter__(self._cm)
        return self._value

    def __exit__(self, exc_type, exc_value, exc_tb):
        if not issubclass(exc_type, AbortStream):
            return self._cm_exit(self._cm, exc_value, exc_type, exc_tb)


class XMPPXMLGenerator:
    def __init__(self, out, encoding="utf-8", short_empty_elements=True):
        self._write = out.write
        self._ns_map_stack = [({}, {}, 0)]
        self._curr_ns_map = {}
        self._encoding = encoding
        self._short_empty_elements = short_empty_elements
        self._pending_start_element = False
        self._ns_prefixes_floating_in = {}
        self._ns_prefixes_floating_out = {}
        self._ns_auto_prefixes_floating_in = set()
        self._ns_decls_floating_in = {}
        self._ns_counter = 0

    def _qname(self, name, attr=False):
        if ":" in name or not xmlValidateNameValue_str(name[1]):
            raise ValueError("invalid name: {!r}".format(name[1]))
        if name[0]:
            if name[0] == "http://www.w3.org/XML/1998/namespace":
                return "xml:" + name[1]
            try:
                prefix = self._curr_ns_map[name[0]]
            except KeyError:
                try:
                    prefix = self._ns_decls_floating_in[name[0]]
                except KeyError:
                    # namespace is undeclared, we have to declare it..
                    prefix = "ns{}".format(self._ns_counter)
                    self._ns_counter += 1
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
        self._curr_ns_map.update(new_decls)
        self._ns_decls_floating_in = {}
        self._ns_prefixes_floating_in = {}

        return new_prefixes

    def startDocument(self):
        pass

    def startPrefixMapping(self, prefix, uri, *, auto=False):
        if     (prefix is not None and
                (not xmlValidateNameValue_str(prefix) or ":" in prefix)):
            raise ValueError("not a valid prefix: {!r}".format(prefix))

        if auto:
            self._ns_auto_prefixes_floating_in.add(prefix)
        self._ns_prefixes_floating_in[prefix] = uri
        self._ns_decls_floating_in[uri] = prefix

    def startElementNS(self, name, qname, attributes=None):
        self._finish_pending_start_element()
        old_counter = self._ns_counter

        qname = self._qname(name)
        if attributes:
            attrib = [
                (self._qname(attrname, attr=True), value)
                for attrname, value in attributes.items()
            ]
        else:
            attrib = []

        pending_prefixes = self._pin_floating_ns_decls(old_counter)

        self._write(b"<")
        self._write(qname.encode(self._encoding))

        if None in pending_prefixes:
            uri = pending_prefixes.pop(None)
            self._write(b" xmlns=")
            self._write(xml.sax.saxutils.quoteattr(uri).encode(self._encoding))

        for prefix, uri in sorted(pending_prefixes.items()):
            self._write(b" xmlns")
            if prefix:
                self._write(b":")
                self._write(prefix.encode(self._encoding))
            self._write(b"=")
            self._write(
                xml.sax.saxutils.quoteattr(uri).encode(self._encoding)
            )

        for attrname, value in attrib:
            self._write(b" ")
            self._write(attrname.encode(self._encoding))
            self._write(b"=")
            self._write(
                xml.sax.saxutils.quoteattr(value).encode(self._encoding)
            )

        if self._short_empty_elements:
            self._pending_start_element = name
        else:
            self._write(b">")

    def endElementNS(self, name, qname):
        if self._ns_prefixes_floating_out:
            raise RuntimeError("namespace prefix has not been closed")

        if self._pending_start_element == name:
            self._pending_start_element = False
            self._write(b"/>")
        else:
            self._write(b"</")
            self._write(self._qname(name).encode(self._encoding))
            self._write(b">")

        self._curr_ns_map, self._ns_prefixes_floating_out, self._ns_counter = \
            self._ns_map_stack.pop()

    def endPrefixMapping(self, prefix):
        self._ns_prefixes_floating_out.remove(prefix)

    def startElement(self, name, attributes=None):
        raise NotImplementedError("namespace-incorrect documents are "
                                  "not supported")

    def characters(self, chars):
        self._finish_pending_start_element()
        self._write(xml.sax.saxutils.escape(chars).encode(self._encoding))

    def processingInstruction(self, target, data):
        raise ValueError("restricted xml: processing instruction forbidden")

    def skippedEntity(self, name):
        raise NotImplementedError("skippedEntity")

    def setDocumentLocator(self, locator):
        raise NotImplementedError("setDocumentLocator")

    def ignorableWhitespace(self, _):
        raise NotImplementedError("ignorableWhitespace")

    def endElement(self, name):
        self.startElement(name)

    def endDocument(self):
        pass


def write_objects(f, nsmap={}):
    nsmap_to_use = {
        "stream": namespaces.xmlstream
    }
    nsmap_to_use.update(nsmap)

    writer = XMPPXMLGenerator(
        out=f,
        encoding="utf-8",
        short_empty_elements=True)

    # writer.startDocument()
    for prefix, uri in nsmap_to_use.items():
        writer.startPrefixMapping(prefix, uri)
    writer.startElementNS(
        (namespaces.xmlstream, "stream"),
        None,
        {})

    abort = False

    try:
        while True:
            try:
                obj = yield
            except AbortStream:
                abort = True
                return
            parent = etree.Element("_")
            obj.unparse_to_sax(writer)
    finally:
        if not abort:
            writer.endElementNS((namespaces.xmlstream, "stream"), None)
            for prefix in nsmap_to_use:
                writer.endPrefixMapping(prefix)
        else:
            # XXX: I’m nasty. I deserve punishment
            if writer._pending_start_element:
                f.write(b">")
        writer.endDocument()
