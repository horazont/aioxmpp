import collections
import io
import unittest

import asyncio_xmpp.xml as xml
import asyncio_xmpp.stanza_model as stanza_model

from asyncio_xmpp.utils import etree


class Cls(stanza_model.StanzaObject):
    TAG = ("uri:foo", "bar")


class TestxmlValidateNameValue_str(unittest.TestCase):
    def test_foo(self):
        self.assertTrue(xml.xmlValidateNameValue_str("foo"))

    def test_greater_than(self):
        self.assertFalse(xml.xmlValidateNameValue_str("foo>"))

    def test_less_than(self):
        self.assertFalse(xml.xmlValidateNameValue_str("foo<"))


class TestDurableXMLGenerator(unittest.TestCase):
    def setUp(self):
        self.buf = io.BytesIO()

    def test_no_declaration(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.endDocument()

        self.assertFalse(self.buf.getvalue())

    def test_reject_namespaceless_stuff(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(NotImplementedError):
            gen.startElement(None, None)
        with self.assertRaises(NotImplementedError):
            gen.endElement(None)

    def test_reject_invalid_prefix(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startPrefixMapping(">", "uri:foo")
        with self.assertRaises(ValueError):
            gen.startPrefixMapping(":", "uri:foo")

    def test_reject_invalid_attribute_name(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, {(None, ">"): "bar"})

    def test_reject_invalid_element_name(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, ">"), None, None)

    def test_element_with_explicit_namespace_setup(self):
        gen = xml.DurableXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("ns")
        gen.endDocument()

        self.assertEqual(
            b'<ns:foo xmlns:ns="uri:foo"/>',
            self.buf.getvalue()
        )

    def test_element_without_explicit_namespace_setup(self):
        gen = xml.DurableXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<ns0:foo xmlns:ns0="uri:foo"/>',
            self.buf.getvalue()
        )

    def test_detection_of_unclosed_namespace(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns0", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startPrefixMapping("ns0", "uri:bar")
        gen.startElementNS(("uri:bar", "e1"), None, None)
        gen.endElementNS(("uri:bar", "e1"), None)
        with self.assertRaises(RuntimeError):
            gen.startElementNS(("uri:bar", "e2"), None, None)
        with self.assertRaises(RuntimeError):
            gen.startElementNS(("uri:foo", "e2"), None, None)
        with self.assertRaises(RuntimeError):
            gen.endElementNS(("uri:foo", "foo"), None)

    def test_no_need_to_close_auto_generated_prefix(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startElementNS(("uri:bar", "e1"), None, None)
        gen.endElementNS(("uri:bar", "e1"), None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<ns:foo xmlns:ns="uri:foo">'
            b'<ns0:e1 xmlns:ns0="uri:bar"/>'
            b'</ns:foo>',
            self.buf.getvalue()
        )

    def test_auto_namespacing_per_element(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startElementNS(("uri:bar", "e"), None, None)
        gen.endElementNS(("uri:bar", "e"), None)
        gen.startElementNS(("uri:baz", "e"), None, None)
        gen.endElementNS(("uri:baz", "e"), None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<ns:foo xmlns:ns="uri:foo">'
            b'<ns0:e xmlns:ns0="uri:bar"/>'
            b'<ns0:e xmlns:ns0="uri:baz"/>'
            b'</ns:foo>',
            self.buf.getvalue()
        )

    def test_namespaceless_root(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<foo/>',
            self.buf.getvalue()
        )

    def test_attributes(self):
        gen = xml.DurableXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS(
            (None, "foo"),
            None,
            {
                (None, "bar"): "1",
                (None, "fnord"): "2"
            }
        )
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertIn(
            self.buf.getvalue(),
            {
                b'<foo bar="1" fnord="2"/>',
                b'<foo fnord="2" bar="1"/>',
            }
        )

    def test_attribute_ns_autogeneration(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(
            (None, "foo"),
            None,
            collections.OrderedDict([
                ((None, "a"), "1"),
                (("uri:foo", "b"), "2"),
                (("uri:bar", "b"), "3"),
            ])
        )
        gen.endElementNS((None, "foo"), None)
        gen.endPrefixMapping("ns")
        gen.endDocument()

        self.assertEqual(
            b'<foo xmlns:ns="uri:foo" xmlns:ns0="uri:bar"'
            b' a="1" ns:b="2" ns0:b="3"/>',
            self.buf.getvalue()
        )

    def test_text(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.characters("foobar")
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b"<foo>foobar</foo>",
            self.buf.getvalue()
        )

    def test_text_escaping(self):
        gen = xml.DurableXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.characters("<fo&o>")
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b"<foo>&lt;fo&amp;o&gt;</foo>",
            self.buf.getvalue()
        )

    def test_interleave_setup_and_teardown_of_namespaces(self):
        gen = xml.DurableXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping("ns0", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startPrefixMapping("ns1", "uri:bar")
        gen.startElementNS(("uri:bar", "e1"), None, None)
        gen.endElementNS(("uri:bar", "e1"), None)
        gen.startPrefixMapping("ns1", "uri:baz")
        gen.endPrefixMapping("ns1")
        gen.startElementNS(("uri:baz", "e2"), None, None)
        gen.endElementNS(("uri:baz", "e2"), None)
        gen.endPrefixMapping("ns1")
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("ns0")
        gen.endDocument()
        self.assertEqual(
            b'<ns0:foo xmlns:ns0="uri:foo">'
            b'<ns1:e1 xmlns:ns1="uri:bar"/>'
            b'<ns1:e2 xmlns:ns1="uri:baz"/>'
            b'</ns0:foo>',
            self.buf.getvalue()
        )

    def test_complex_tree(self):


    def tearDown(self):
        del self.buf


class Testwrite_objects(unittest.TestCase):
    def setUp(self):
        self.buf = io.BytesIO()

    def test_setup(self):
        gen = xml.write_objects(self.buf)
        next(gen)
        gen.close()

        self.assertEqual(
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"/>',
            self.buf.getvalue()
        )

    def test_reset(self):
        gen = xml.write_objects(self.buf)
        next(gen)
        with self.assertRaises(StopIteration):
            gen.throw(xml.AbortStream())

        self.assertEqual(
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams">',
            self.buf.getvalue()
        )

    def test_root_ns(self):
        gen = xml.write_objects(self.buf, nsmap={None: "jabber:client"})
        next(gen)
        gen.close()

        self.assertEqual(
            b'<stream:stream xmlns="jabber:client" xmlns:stream="http://etherx.jabber.org/streams"/>',
            self.buf.getvalue()
        )

    def test_send_object(self):
        obj = Cls()
        gen = xml.write_objects(self.buf)
        next(gen)
        gen.send(obj)
        gen.close()

        self.assertEqual(
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams">'
            b'<ns0:bar xmlns:ns0="uri:foo"/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_send_object_inherits_namespaces(self):
        obj = Cls()
        gen = xml.write_objects(
            self.buf,
            nsmap={"jc": "uri:foo"})
        next(gen)
        gen.send(obj)
        gen.close()

        self.assertEqual(
            b'<stream:stream xmlns:jc="uri:foo" xmlns:stream="http://etherx.jabber.org/streams">'
            b'<jc:bar/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def tearDown(self):
        del self.buf
