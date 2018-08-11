########################################################################
# File name: test_xml.py
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
import collections
import contextlib
import io
import itertools
import unittest
import unittest.mock

import lxml.sax

import xml.sax as xml_sax
import xml.sax.handler as saxhandler

import aioxmpp.xml as xml
import aioxmpp.structs as structs
import aioxmpp.errors as errors
import aioxmpp.xso as xso

from aioxmpp.utils import etree, namespaces

from aioxmpp.xmltestutils import XMLTestCase


# this tree is extracted from http://api.met.no, the API of the norwegian
# meterological institute. This data is under CC-BY-SA.
TEST_TREE = b"""<weatherdata xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://api.met.no/weatherapi/locationforecast/1.9/schema" created="2015-03-02T19:40:26Z">
   <meta>
      <model name="LOCAL" termin="2015-03-02T12:00:00Z" runended="2015-03-02T15:39:25Z" nextrun="2015-03-03T04:00:00Z" from="2015-03-02T20:00:00Z" to="2015-03-05T06:00:00Z" />
      <model name="EC.GEO.0.25" termin="2015-03-02T12:00:00Z" runended="2015-03-02T19:04:34Z" nextrun="2015-03-02T20:00:00Z" from="2015-03-05T09:00:00Z" to="2015-03-12T12:00:00Z" />
      </meta>
   <product class="pointData">
      <time datatype="forecast" from="2015-03-02T20:00:00Z" to="2015-03-02T20:00:00Z">
         <location altitude="288" latitude="51.0000" longitude="13.0000">
            <temperature id="TTT" unit="celsius" value="2.1"/>
            <windDirection id="dd" deg="232.7" name="SW"/>
            <windSpeed id="ff" mps="5.4" beaufort="3" name="Lett bris"/>
            <humidity value="72.7" unit="percent"/>
            <pressure id="pr" unit="hPa" value="1007.5"/>
            <cloudiness id="NN" percent="70.4"/>
            <fog id="FOG" percent="0.0"/>
            <lowClouds id="LOW" percent="0.6"/>
            <mediumClouds id="MEDIUM" percent="69.8"/>
            <highClouds id="HIGH" percent="0.0"/>
            <dewpointTemperature id="TD" unit="celsius" value="-2.5"/>
         </location>
      </time>
      <time datatype="forecast" from="2015-03-02T19:00:00Z" to="2015-03-02T20:00:00Z">
         <location altitude="288" latitude="51.0000" longitude="13.0000">
            <precipitation unit="mm" value="0.0" minvalue="0.0" maxvalue="0.0"/>
<symbol id="PartlyCloud" number="3"/>
         </location>
      </time>
</product></weatherdata>"""
# end of data extracted from http://api.met.no

TEST_ESCAPING_TREE = (
    b"<foo bar='with &#10;linebreak'>and also\n"
    b"text with linebreaks, even DOS-ones\r\n"
    b"</foo>"
)


class Cls(xso.XSO):
    TAG = ("uri:foo", "bar")

    DECLARE_NS = {}


class TestxmlValidateNameValue_str(unittest.TestCase):
    NAME_START_CHAR = (
        set([
            ":",
            "_",
        ]) |
        set(chr(ch) for ch in range(ord("a"), ord("z")+1)) |
        set(chr(ch) for ch in range(ord("A"), ord("Z")+1)) |
        set(chr(ch) for ch in range(0xc0, 0xd7)) |
        set(chr(ch) for ch in range(0xd8, 0xf7)) |
        set(chr(ch) for ch in range(0xf8, 0x300)) |
        set(chr(ch) for ch in range(0x370, 0x37e)) |
        set(chr(ch) for ch in range(0x37f, 0x2000)) |
        set(chr(ch) for ch in range(0x200c, 0x200e)) |
        set(chr(ch) for ch in range(0x2070, 0x2190)) |
        set(chr(ch) for ch in range(0x2c00, 0x2ff0)) |
        set(chr(ch) for ch in range(0x3001, 0xd800)) |
        set(chr(ch) for ch in range(0xf900, 0xfdd0)) |
        set(chr(ch) for ch in range(0xfdf0, 0xfffe)) |
        set(chr(ch) for ch in range(0x10000, 0xf0000))
    )

    NAME_CHAR = (
        NAME_START_CHAR |
        set(["-", ".", "\u00b7"]) |
        set(chr(ch) for ch in range(ord("0"), ord("9")+1)) |
        set(chr(ch) for ch in range(0x0300, 0x0370)) |
        set(chr(ch) for ch in range(0x203f, 0x2041))
    )

    def test_foo(self):
        self.assertTrue(xml.xmlValidateNameValue_str("foo"))

    def test_greater_than(self):
        self.assertFalse(xml.xmlValidateNameValue_str("foo>"))

    def test_less_than(self):
        self.assertFalse(xml.xmlValidateNameValue_str("foo<"))

    def test_zero_length(self):
        self.assertFalse(xml.xmlValidateNameValue_str(""))

    def test_exhaustive_singlechar(self):
        range_iter = itertools.chain(
            # exclude surrogates
            range(0, 0xd800),
            range(0xe000, 0xf0000)
        )

        for cp in range_iter:
            s = chr(cp)
            self.assertEqual(
                xml.xmlValidateNameValue_str(s),
                s in self.NAME_START_CHAR,
                hex(cp)
            )

    def test_dualchar_additional(self):
        # we only test a low range here for speed and because the upper range
        # is identical
        range_iter = itertools.chain(
            range(0, 0xd800),
        )

        for cp in range_iter:
            ch = chr(cp)
            s = "x" + ch
            self.assertEqual(
                xml.xmlValidateNameValue_str(s),
                ch in self.NAME_CHAR,
                hex(cp)
            )


class TestXMPPXMLGenerator(XMLTestCase):
    def setUp(self):
        self.buf = io.BytesIO()

    def tearDown(self):
        del self.buf

    def test_declaration(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            self.buf.getvalue()
        )

    def test_reject_namespaceless_stuff(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(NotImplementedError):
            gen.startElement(None, None)
        with self.assertRaises(NotImplementedError):
            gen.endElement(None)

    def test_reject_invalid_prefix(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startPrefixMapping(">", "uri:foo")
        with self.assertRaises(ValueError):
            gen.startPrefixMapping(":", "uri:foo")

    def test_reject_invalid_attribute_name(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, {(None, ">"): "bar"})

    def test_reject_invalid_element_name(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, ">"), None, None)

    def test_element_with_explicit_namespace_setup(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("ns")
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?><ns:foo xmlns:ns="uri:foo"/>',
            self.buf.getvalue()
        )

    def test_element_without_explicit_namespace_setup(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>',
            self.buf.getvalue()
        )

    def test_detection_of_unclosed_namespace(self):
        gen = xml.XMPPXMLGenerator(self.buf)
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
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startElementNS(("uri:bar", "e1"), None, {("uri:fnord", "a"): "v"})
        gen.endElementNS(("uri:bar", "e1"), None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<ns:foo xmlns:ns="uri:foo">'
            b'<e1 xmlns="uri:bar" xmlns:ns0="uri:fnord" ns0:a="v"/>'
            b'</ns:foo>',
            self.buf.getvalue()
        )

    def test_auto_namespacing_per_element(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startElementNS(("uri:bar", "e"), None, {("uri:fnord", "a"): "v"})
        gen.endElementNS(("uri:bar", "e"), None)
        gen.startElementNS(("uri:bar", "e"), None, {("uri:baz", "a"): "v"})
        gen.endElementNS(("uri:bar", "e"), None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<ns:foo xmlns:ns="uri:foo">'
            b'<e xmlns="uri:bar" xmlns:ns0="uri:fnord" ns0:a="v"/>'
            b'<e xmlns="uri:bar" xmlns:ns0="uri:baz" ns0:a="v"/>'
            b'</ns:foo>',
            self.buf.getvalue()
        )

    def test_namespaceless_root(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo/>',
            self.buf.getvalue()
        )

    def test_attributes(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
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
                b'<?xml version="1.0"?><foo bar="1" fnord="2"/>',
                b'<?xml version="1.0"?><foo fnord="2" bar="1"/>',
            }
        )

    def test_attributes_sortedattrs(self):
        gen = xml.XMPPXMLGenerator(self.buf,
                                   short_empty_elements=True,
                                   sorted_attributes=True)
        gen.startDocument()
        gen.startElementNS(
            (None, "foo"),
            None,
            {
                (None, "bar"): "1",
                (None, "fnord"): "2",
                ("uri:foo", "baz"): "3"
            }
        )
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns:ns0="uri:foo" bar="1" fnord="2" ns0:baz="3"/>',
            self.buf.getvalue()
        )

    def test_attribute_ns_autogeneration(self):
        gen = xml.XMPPXMLGenerator(self.buf)
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
            b'<?xml version="1.0"?>'
            b'<foo xmlns:ns="uri:foo" xmlns:ns0="uri:bar"'
            b' a="1" ns:b="2" ns0:b="3"/>',
            self.buf.getvalue()
        )

    def test_text(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.characters("foobar")
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo>foobar</foo>",
            self.buf.getvalue()
        )

    def test_text_escaping(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.characters("<fo&o>")
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo>&lt;fo&amp;o&gt;</foo>",
            self.buf.getvalue()
        )

    def test_text_escaping_additional(self):
        gen = xml.XMPPXMLGenerator(
            self.buf,
            additional_escapes="\r\nf",
        )
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.characters("<fo&\r\no>")
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo>&lt;&#102;o&amp;&#13;&#10;o&gt;</foo>",
            self.buf.getvalue()
        )

    def test_attribute_escaping_additional(self):
        gen = xml.XMPPXMLGenerator(
            self.buf,
            additional_escapes="\r\na",
        )
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, {(None, "foo"): "b\r\nar"})
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo foo="b&#13;&#10;&#97;r"/>',
            self.buf.getvalue()
        )

    def test_interleave_setup_and_teardown_of_namespaces(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
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
            b'<?xml version="1.0"?>'
            b'<ns0:foo xmlns:ns0="uri:foo">'
            b'<ns1:e1 xmlns:ns1="uri:bar"/>'
            b'<ns1:e2 xmlns:ns1="uri:baz"/>'
            b'</ns0:foo>',
            self.buf.getvalue()
        )

    def test_complex_tree(self):
        tree = etree.fromstring(TEST_TREE)
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        lxml.sax.saxify(tree, gen)

        tree2 = etree.fromstring(self.buf.getvalue())

        self.assertSubtreeEqual(
            tree,
            tree2)

    def test_additional_escape_full_roundtrip(self):
        tree = etree.fromstring(TEST_ESCAPING_TREE)
        gen = xml.XMPPXMLGenerator(self.buf,
                                   short_empty_elements=True,
                                   additional_escapes="a\r\n")
        lxml.sax.saxify(tree, gen)

        tree2 = etree.fromstring(self.buf.getvalue())

        self.assertSubtreeEqual(
            tree,
            tree2)

        self.assertNotIn(b"\r", self.buf.getvalue())

    def test_reject_processing_instruction(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        with self.assertRaisesRegex(ValueError,
                                    "restricted xml: processing instruction"):
            gen.processingInstruction("foo", "bar")

    def test_reject_multiple_assignments_for_prefix(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("a", "uri:foo")
        with self.assertRaises(ValueError):
            gen.startPrefixMapping("a", "uri:bar")

    def test_no_duplicate_auto_assignments_of_prefixes(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping("ns0", "uri:foo")
        gen.startElementNS(("uri:bar", "foo"), None, None)
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endElementNS(("uri:bar", "foo"), None)
        gen.endPrefixMapping("ns0")
        gen.endDocument()

        self.assertSubtreeEqual(
            etree.fromstring(
                "<foo xmlns='uri:bar'>"
                "<foo xmlns='uri:foo' />"
                "</foo>"),
            etree.fromstring(self.buf.getvalue())
        )

    def test_reject_control_characters_in_characters(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startElementNS(("uri:bar", "foo"), None, None)
        for i in set(range(32)) - {9, 10, 13}:
            with self.assertRaises(ValueError):
                gen.characters(chr(i))

    def test_skippedEntity_not_implemented(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        with self.assertRaises(NotImplementedError):
            gen.skippedEntity("foo")

    def test_setDocumentLocator_not_implemented(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        with self.assertRaises(NotImplementedError):
            gen.setDocumentLocator("foo")

    def test_ignorableWhitespace_not_implemented(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        with self.assertRaises(NotImplementedError):
            gen.ignorableWhitespace("foo")

    def test_reject_unnamespaced_element_if_default_namespace_is_set(self):
        gen = xml.XMPPXMLGenerator(self.buf)
        gen.startDocument()
        gen.startPrefixMapping(None, "uri:foo")
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, None)

    def test_properly_handle_empty_root(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo/>",
            self.buf.getvalue()
        )

    def test_finish_partially_opened_element_on_flush(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.flush()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo>",
            self.buf.getvalue()
        )
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo></foo>",
            self.buf.getvalue()
        )

    def test_implicit_xml_prefix(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startElementNS(
            ("http://www.w3.org/XML/1998/namespace", "foo"), None, None)
        gen.endElementNS(("http://www.w3.org/XML/1998/namespace", "foo"),
                         None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<xml:foo/>",
            self.buf.getvalue()
        )

    def test_non_short_empty_elements(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=False)
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, None)
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b"<foo></foo>",
            self.buf.getvalue()
        )

    def test_flush(self):
        buf = unittest.mock.MagicMock()

        gen = xml.XMPPXMLGenerator(buf, short_empty_elements=True)
        gen.flush()

        self.assertSequenceEqual(
            [
                unittest.mock.call.flush.__bool__(),
                unittest.mock.call.flush(),
            ],
            buf.mock_calls
        )

    def test_reject_colon_in_element_name(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo:bar"), None, None)

    def test_reject_invalid_element_names(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo*bar"), None, None)
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "\u0002bar"), None, None)
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "\u0000"), None, None)

    def test_reject_xmlns_attributes(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, {
                (None, "xmlns"): "foobar"
            })
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, {
                (None, "xmlns:foo"): "foobar"
            })

    def test_reject_reserved_prefixes(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startPrefixMapping("xmlns", "uri:foo")
        with self.assertRaises(ValueError):
            gen.startPrefixMapping("xml", "uri:foo")

    def test_catch_non_tuple_attribute(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        with self.assertRaises(ValueError):
            gen.startElementNS((None, "foo"), None, {
                "fo": "foobar"
            })

    def test_works_without_flush(self):
        class Backend:
            def write(self, data):
                pass

        gen = xml.XMPPXMLGenerator(Backend())
        gen.startDocument()
        gen.startElementNS((None, "foo"), None, {})
        gen.flush()
        gen.endElementNS((None, "foo"), None)
        gen.endDocument()
        gen.flush()

    def test_redeclaration_of_namespace_prefixes(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping("ns0", "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.startPrefixMapping("ns0", "uri:bar")
        gen.startElementNS(("uri:foo", "bar"), None, {("uri:baz", "a"): "v"})
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping("ns0")
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("ns0")
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<ns0:foo xmlns:ns0="uri:foo">'
            b'<bar xmlns="uri:foo" xmlns:ns0="uri:bar" xmlns:ns1="uri:baz"'
            b' ns1:a="v"/>'
            b'</ns0:foo>',
            self.buf.getvalue()
        )

    def test_redeclaration_of_default_namespace(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.startPrefixMapping(None, "uri:bar")
        gen.startElementNS(("uri:foo", "bar"), None, {})
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping(None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo">'
            b'<ns0:bar xmlns="uri:bar" xmlns:ns0="uri:foo"/>'
            b'</foo>',
            self.buf.getvalue()
        )

    def test_deduplication_of_prefix_declarations(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "bar"), None, {})
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping(None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo">'
            b'<bar/>'
            b'</foo>',
            self.buf.getvalue()
        )

    def test_deduplication_of_prefix_declarations_x(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "bar"), None, {})
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping(None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo">'
            b'<bar/>'
            b'</foo>',
            self.buf.getvalue()
        )

    def test_always_use_innermost_prefix_mapping(self):
        gen = xml.XMPPXMLGenerator(self.buf, short_empty_elements=True)
        gen.startDocument()
        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.startPrefixMapping("foo", "uri:foo")
        gen.startElementNS(("uri:foo", "bar"), None, {})
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping("foo")
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo">'
            b'<foo:bar xmlns:foo="uri:foo"/>'
            b'</foo>',
            self.buf.getvalue()
        )

    def test_buffer_buffers_output_and_sends_it_to_sink_on_exit(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with gen.buffer():
            gen.startPrefixMapping(None, "uri:foo")
            gen.startElementNS(("uri:foo", "foo"), None, {})
            gen.endElementNS(("uri:foo", "foo"), None)
            gen.endPrefixMapping(None)
            gen.flush()

            self.assertEqual(
                b'<?xml version="1.0"?>',
                b"".join(args[0] for _, args, _ in buf.write.mock_calls),
            )

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>'
            b'<foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_buffer_uses_flush_after_write(self):
        buf = unittest.mock.Mock(["write", "flush"])

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        buf.flush.reset_mock()

        with gen.buffer():
            gen.startPrefixMapping(None, "uri:foo")
            gen.startElementNS(("uri:foo", "foo"), None, {})
            gen.endElementNS(("uri:foo", "foo"), None)
            gen.endPrefixMapping(None)

            self.assertEqual(
                b'<?xml version="1.0"?>',
                b"".join(args[0] for _, args, _ in buf.write.mock_calls),
            )

        buf.flush.assert_called_once_with()

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>'
            b'<foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_buffer_can_deal_with_missing_flush(self):
        buf = unittest.mock.Mock(["write"])

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with gen.buffer():
            gen.startPrefixMapping(None, "uri:foo")
            gen.startElementNS(("uri:foo", "foo"), None, {})
            gen.endElementNS(("uri:foo", "foo"), None)
            gen.endPrefixMapping(None)

            self.assertEqual(
                b'<?xml version="1.0"?>',
                b"".join(args[0] for _, args, _ in buf.write.mock_calls),
            )

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>'
            b'<foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_buffer_buffers_output_and_discards_it_on_exception(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        class FooException(Exception):
            pass

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startPrefixMapping(None, "uri:foo")
                gen.startElementNS(("uri:foo", "foo"), None, {})
                gen.endElementNS(("uri:foo", "foo"), None)
                gen.endPrefixMapping(None)
                gen.flush()

                self.assertEqual(
                    b'<?xml version="1.0"?>',
                    b"".join(args[0] for _, args, _ in buf.write.mock_calls),
                )

                raise FooException()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping(None)

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo"/>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_nested_buffering_not_supported(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with self.assertRaisesRegex(
                RuntimeError,
                r"nested use of buffer\(\) is not supported"):
            with gen.buffer():
                with gen.buffer():
                    pass

    def test_sequential_buffering_supported(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with gen.buffer():
            gen.startPrefixMapping(None, "uri:foo")
            gen.startElementNS(("uri:foo", "foo"), None, {})
            gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo">',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with gen.buffer():
            gen.characters("foobar")

            self.assertEqual(
                b'<?xml version="1.0"?><foo xmlns="uri:foo">',
                b"".join(args[0] for _, args, _ in buf.write.mock_calls),
            )

            gen.endElementNS(("uri:foo", "foo"), None)
            gen.endPrefixMapping(None)

            self.assertEqual(
                b'<?xml version="1.0"?><foo xmlns="uri:foo">',
                b"".join(args[0] for _, args, _ in buf.write.mock_calls),
            )

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo">foobar</foo>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_sequential_buffering_with_exceptions_supported(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        class FooException(Exception):
            pass

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startPrefixMapping(None, "uri:foo")
                gen.startElementNS(("uri:foo", "foo"), None, {})
                gen.endElementNS(("uri:foo", "foo"), None)
                gen.endPrefixMapping(None)
                gen.flush()
                raise FooException()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        with gen.buffer():
            gen.startPrefixMapping(None, "uri:foo")
            gen.startElementNS(("uri:foo", "foo"), None, {})
            gen.characters("foobar")
            gen.endElementNS(("uri:foo", "foo"), None)
            gen.endPrefixMapping(None)

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo">foobar</foo>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

    def test_sequential_buffering_can_optimise(self):
        buf = unittest.mock.Mock(io.BytesIO)

        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        buf.reset_mock()

        with contextlib.ExitStack() as stack:
            bio = stack.enter_context(unittest.mock.patch("io.BytesIO"))

            with gen.buffer():
                bio.assert_called_once_with()
                gen.startPrefixMapping(None, "uri:foo")
                gen.startElementNS(("uri:foo", "foo"), None, {})
                gen.flush()

            self.assertEqual(
                b'<foo xmlns="uri:foo">',
                b"".join(args[0] for _, args, _ in bio().write.mock_calls),
            )

            buf.write.assert_called_once_with(bio().getbuffer())
            buf.reset_mock()
            bio.reset_mock()

            with gen.buffer():
                bio.assert_not_called()
                bio().seek.assert_called_once_with(0)
                bio().truncate.assert_called_once_with()
                gen.characters("foobar")
                gen.endElementNS(("uri:foo", "foo"), None)
                gen.endPrefixMapping(None)

            self.assertEqual(
                b'foobar</foo>',
                b"".join(args[0] for _, args, _ in bio().write.mock_calls),
            )

            buf.write.assert_called_once_with(bio().getbuffer())

    def test_sequential_buffering_can_deal_with_delayed_buffers(self):
        m = unittest.mock.Mock()
        buf = unittest.mock.Mock(io.BytesIO)
        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            b"".join(args[0] for _, args, _ in buf.write.mock_calls),
        )

        buf.reset_mock()

        bio_cls = io.BytesIO

        def generate_bios():
            i = 0
            while True:
                name = "bio{}".format(i)
                bio = unittest.mock.Mock(bio_cls)
                setattr(m, name, bio)
                yield getattr(m, name)
                i += 1

        generator = generate_bios()

        with contextlib.ExitStack() as stack:
            bio = stack.enter_context(unittest.mock.patch("io.BytesIO"))
            bio.side_effect = generator

            with gen.buffer():
                bio.assert_called_once_with()
                gen.startPrefixMapping(None, "uri:foo")
                gen.startElementNS(("uri:foo", "foo"), None, {})
                gen.flush()

            self.assertEqual(
                b'<foo xmlns="uri:foo">',
                b"".join(args[0] for _, args, _ in m.bio0.write.mock_calls),
            )

            buf.write.assert_called_once_with(m.bio0.getbuffer())
            buf.reset_mock()
            bio.reset_mock()
            bio.side_effect = generator

            m.bio0.truncate.side_effect = BufferError()

            with gen.buffer():
                bio.assert_called_once_with()
                gen.characters("foobar")
                gen.endElementNS(("uri:foo", "foo"), None)
                gen.endPrefixMapping(None)

            self.assertEqual(
                b'foobar</foo>',
                b"".join(args[0] for _, args, _ in m.bio1.write.mock_calls),
            )

            buf.write.assert_called_once_with(m.bio1.getbuffer())

    def test_buffer_provides_exception_safety_for_startPrefixMapping(self):
        buf = io.BytesIO()
        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            buf.getvalue(),
        )

        class FooException(Exception):
            pass

        gen.startPrefixMapping(None, "uri:foo")

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startPrefixMapping("foo", "uri:foo")
                raise FooException()

        gen.startPrefixMapping("foo", "uri:bar")
        gen.startElementNS(("uri:foo", "foo"), None, {})
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?><foo xmlns="uri:foo" xmlns:foo="uri:bar">',
            buf.getvalue(),
        )

    def test_buffer_provides_exception_safety_for_startElementNS(self):
        buf = io.BytesIO()
        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            buf.getvalue(),
        )

        class FooException(Exception):
            pass

        gen.startPrefixMapping(None, "uri:foo")

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startElementNS(("uri:foo", "foo"), None,
                                   {("uri:bar", "a"): "y"})
                raise FooException()

        gen.startPrefixMapping("foo", "uri:bar")
        gen.startElementNS(("uri:foo", "foo"), None, {("uri:bar", "a"): "x"})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("foo")
        gen.endPrefixMapping(None)
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo" xmlns:foo="uri:bar" foo:a="x"/>',
            buf.getvalue(),
        )

    def test_buffer_provides_exception_safety_for_nested_startElementNS(self):
        buf = io.BytesIO()
        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            buf.getvalue(),
        )

        class FooException(Exception):
            pass

        gen.startPrefixMapping(None, "uri:foo")
        gen.startElementNS(("uri:foo", "bar"), None, {})

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startElementNS(("uri:foo", "bar"), None)
                raise FooException()

        gen.startPrefixMapping("foo", "uri:bar")
        gen.startElementNS(("uri:foo", "foo"), None, {("uri:bar", "a"): "x"})
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endPrefixMapping("foo")
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endPrefixMapping(None)
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<bar xmlns="uri:foo">'
            b'<foo xmlns:foo="uri:bar" foo:a="x"/></bar>',
            buf.getvalue(),
        )

    def test_buffer_provides_exception_safety_for_auto_namespaces(self):
        buf = io.BytesIO()
        gen = xml.XMPPXMLGenerator(buf)
        gen.startDocument()
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>',
            buf.getvalue(),
        )

        class FooException(Exception):
            pass

        gen.startElementNS(("uri:foo", "bar"), None, {})

        with self.assertRaises(FooException):
            with gen.buffer():
                gen.startElementNS(("uri:bar", "bar"), None)
                raise FooException()

        gen.startPrefixMapping("x", "uri:bar")
        gen.startElementNS(("uri:fnord", "foo"), None, {("uri:bar", "a"): "x"})
        gen.endElementNS(("uri:fnord", "foo"), None)
        gen.endPrefixMapping("x")
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.flush()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<bar xmlns="uri:foo">'
            b'<foo xmlns="uri:fnord" xmlns:x="uri:bar" x:a="x"/>'
            b'</bar>',
            buf.getvalue(),
        )

    def test_attributes_in_ns_get_prefix_even_if_ns_matches_default(self):
        gen = xml.XMPPXMLGenerator(self.buf, sorted_attributes=True)
        gen.startDocument()
        gen.startElementNS(("uri:foo", "foo"), None, {
            ("uri:foo", "a"): "v",
            (None, "a"): "v"
        })
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo" xmlns:ns0="uri:foo" a="v" ns0:a="v"/>',
            self.buf.getvalue()
        )

    def test_attributes_in_ns_get_prefix_even_if_ns_matches_parent_default(self):
        gen = xml.XMPPXMLGenerator(self.buf, sorted_attributes=True)
        gen.startDocument()
        gen.startElementNS(("uri:foo", "foo"), None, None)
        gen.startElementNS(("uri:foo", "bar"), None, {
            ("uri:foo", "a"): "v",
            (None, "a"): "v"
        })
        gen.endElementNS(("uri:foo", "bar"), None)
        gen.endElementNS(("uri:foo", "foo"), None)
        gen.endDocument()
        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<foo xmlns="uri:foo">'
            b'<bar xmlns:ns0="uri:foo" a="v" ns0:a="v"/>'
            b'</foo>',
            self.buf.getvalue()
        )

    def test_auto_prefixes_are_cleared_when_pinned(self):
        # this transcript was found while running an e2e test of private_xml

        gen = xml.XMPPXMLGenerator(self.buf, sorted_attributes=True)
        gen.startDocument()

        gen.startPrefixMapping(
            None,
            'jabber:client'
        )
        gen.startPrefixMapping(
            'stream',
            'stream'
        )
        gen.startElementNS(
            ('stream', 'stream'),
            None,
            {},
        )

        gen.startElementNS(
            ('jabber:client', 'iq'),
            None,
            {(None, 'id'): 'xjDMHg9cpq0zJQxfzwYAP', (None, 'type'): 'set'}
        )
        gen.startPrefixMapping(None, 'jabber:iq:private')
        gen.startElementNS(('jabber:iq:private', 'query'), None, {})
        gen.startElementNS(
            ('urn:example:unregistered', 'example'),
            'ns00:example',
            {}
        )
        gen.startElementNS(
            ('urn:example:unregistered', 'payload'),
            'ns00:payload',
            {}
        )
        gen.endElementNS(('urn:example:unregistered', 'payload'),
                         'ns00:payload')
        gen.endElementNS(('urn:example:unregistered', 'example'),
                         'ns00:example')
        gen.endElementNS(('jabber:iq:private', 'query'), None)
        gen.endPrefixMapping(None)
        gen.endElementNS(('jabber:client', 'iq'), None)

        gen.startPrefixMapping(None, 'urn:xmpp:sm:3')
        gen.startElementNS(('urn:xmpp:sm:3', 'r'), None, {})
        gen.endElementNS(('urn:xmpp:sm:3', 'r'), None)

        # originally, this call raised a KeyError
        gen.endPrefixMapping(None)

        gen.endElementNS(('stream', 'stream'), None)
        gen.endPrefixMapping(None)
        gen.endPrefixMapping('stream')
        gen.endDocument()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<stream:stream xmlns="jabber:client" xmlns:stream="stream">'
            b'<iq id="xjDMHg9cpq0zJQxfzwYAP" type="set">'
            b'<query xmlns="jabber:iq:private">'
            b'<example xmlns="urn:example:unregistered">'
            b'<payload/>'
            b'</example>'
            b'</query>'
            b'</iq>'
            b'<r xmlns="urn:xmpp:sm:3"/>'
            b'</stream:stream>',
            self.buf.getvalue()
        )



class TestXMLStreamWriter(unittest.TestCase):
    TEST_TO = structs.JID.fromstr("example.test")
    TEST_FROM = structs.JID.fromstr("foo@example.test")

    STREAM_HEADER = b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams" to="'+str(TEST_TO).encode("utf-8")+b'" version="1.0">'

    def setUp(self):
        self.buf = io.BytesIO()

    def tearDown(self):
        del self.buf

    def _make_gen(self, **kwargs):
        return xml.XMLStreamWriter(self.buf, self.TEST_TO,
                                   sorted_attributes=True,
                                   **kwargs)

    def test_no_writes_before_start(self):
        gen = self._make_gen()

        self.assertEqual(
            b"",
            self.buf.getvalue()
        )

    def test_setup(self):
        gen = self._make_gen()
        gen.start()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER+b'</stream:stream>',
            self.buf.getvalue()
        )

    def test_from(self):
        gen = self._make_gen(from_=self.TEST_FROM)
        gen.start()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            b'<stream:stream '
            b'xmlns:stream="http://etherx.jabber.org/streams" '
            b'from="'+str(self.TEST_FROM).encode("utf-8")+b'" '
            b'to="'+str(self.TEST_TO).encode("utf-8")+b'" '
            b'version="1.0"></stream:stream>',
            self.buf.getvalue()
        )

    def test_reset(self):
        gen = self._make_gen()
        gen.start()
        gen.abort()

        self.assertEqual(
            b'<?xml version="1.0"?>'+self.STREAM_HEADER,
            self.buf.getvalue()
        )

    def test_root_ns(self):
        gen = self._make_gen(nsmap={None: "jabber:client"})
        gen.start()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<stream:stream xmlns="jabber:client" '
            b'xmlns:stream="http://etherx.jabber.org/streams" '
            b'to="'+str(self.TEST_TO).encode("utf-8")+b'" '
            b'version="1.0"></stream:stream>',
            self.buf.getvalue()
        )

    def test_send_object(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_send_object_inherits_namespaces(self):
        obj = Cls()
        gen = self._make_gen(nsmap={"jc": "uri:foo"})
        gen.start()
        gen.send(obj)
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<stream:stream xmlns:jc="uri:foo" '
            b'xmlns:stream="http://etherx.jabber.org/streams" '
            b'to="'+str(self.TEST_TO).encode("utf-8")+b'" '
            b'version="1.0">'
            b'<jc:bar/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_send_handles_serialisation_issues_gracefully(self):
        class Cls(xso.XSO):
            TAG = ("uri:foo", "foo")

            text = xso.Text()

        obj = Cls()
        obj.text = "foo\0"

        gen = self._make_gen(nsmap={"jc": "uri:foo"})
        gen.start()
        with self.assertRaises(ValueError):
            gen.send(obj)

        obj = Cls()
        obj.text = "bar"

        gen.send(obj)
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>'
            b'<stream:stream xmlns:jc="uri:foo" '
            b'xmlns:stream="http://etherx.jabber.org/streams" '
            b'to="'+str(self.TEST_TO).encode("utf-8")+b'" '
            b'version="1.0">'
            b'<foo xmlns="uri:foo">bar</foo>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_close_is_idempotent(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.close()
        gen.close()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_abort_makes_close_noop(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.abort()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>',
            self.buf.getvalue())

    def test_abort_is_idempotent(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.abort()
        gen.abort()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>',
            self.buf.getvalue())

    def test_abort_after_close_is_okay(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.close()
        gen.abort()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>'
            b'</stream:stream>',
            self.buf.getvalue())

    def test_close_makes_send_raise_StopIteration_noop(self):
        obj = Cls()
        gen = self._make_gen()
        gen.start()
        gen.send(obj)
        gen.abort()
        gen.close()

        self.assertEqual(
            b'<?xml version="1.0"?>' +
            self.STREAM_HEADER +
            b'<bar xmlns="uri:foo"/>',
            self.buf.getvalue())


class TestXMPPXMLProcessor(unittest.TestCase):
    VALID_STREAM_HEADER = "".join((
        "<stream:stream xmlns:stream='{}'".format(namespaces.xmlstream),
        " version='1.0' from='example.test' ",
        "to='foo@example.test' id='foobarbaz'>"
    ))

    STREAM_HEADER_TAG = (namespaces.xmlstream, "stream")

    STREAM_HEADER_ATTRS = {
        (None, "from"): "example.test",
        (None, "to"): "foo@example.test",
        (None, "id"): "foobarbaz",
        (None, "version"): "1.0"
    }

    def setUp(self):
        self.proc = xml.XMPPXMLProcessor()
        self.parser = xml.make_parser()
        self.parser.setContentHandler(self.proc)

    def test_reject_processing_instruction(self):
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.processingInstruction("foo", "bar")
        self.assertEqual(
            errors.StreamErrorCondition.RESTRICTED_XML,
            cm.exception.condition
        )

    def test_reject_start_element_without_ns(self):
        with self.assertRaises(RuntimeError):
            self.proc.startElement("foo", {})

    def test_reject_end_element_without_ns(self):
        with self.assertRaises(RuntimeError):
            self.proc.endElement("foo")

    def test_errors_propagate(self):
        self.parser.feed(self.VALID_STREAM_HEADER)
        with self.assertRaises(errors.StreamError):
            self.parser.feed("<!-- foo -->")

    def test_capture_stream_header(self):
        self.assertIsNone(self.proc.remote_version)
        self.assertIsNone(self.proc.remote_from)
        self.assertIsNone(self.proc.remote_to)
        self.assertIsNone(self.proc.remote_id)

        self.proc.startDocument()
        self.proc.startElementNS(
            self.STREAM_HEADER_TAG,
            None,
            self.STREAM_HEADER_ATTRS
        )

        self.assertEqual(
            (1, 0),
            self.proc.remote_version
        )
        self.assertEqual(
            structs.JID.fromstr("example.test"),
            self.proc.remote_from
        )
        self.assertEqual(
            structs.JID.fromstr("foo@example.test"),
            self.proc.remote_to
        )
        self.assertEqual(
            "foobarbaz",
            self.proc.remote_id
        )

    def test_require_stream_header(self):
        self.proc.startDocument()

        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startElementNS((None, "foo"), None, {})
        self.assertEqual(
            errors.StreamErrorCondition.INVALID_NAMESPACE,
            cm.exception.condition
        )

        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startElementNS((namespaces.xmlstream, "bar"), None, {})
        self.assertEqual(
            errors.StreamErrorCondition.INVALID_NAMESPACE,
            cm.exception.condition
        )

    def test_require_stream_header_from(self):
        attrs = self.STREAM_HEADER_ATTRS.copy()
        del attrs[(None, "from")]

        self.proc.startDocument()
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
        self.assertEqual(
            errors.StreamErrorCondition.UNDEFINED_CONDITION,
            cm.exception.condition
        )

    def test_do_not_require_stream_header_to(self):
        attrs = self.STREAM_HEADER_ATTRS.copy()
        del attrs[(None, "to")]

        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
        self.assertIsNone(
            None,
            self.proc.remote_to)

    def test_require_stream_header_id(self):
        attrs = self.STREAM_HEADER_ATTRS.copy()
        del attrs[(None, "id")]

        self.proc.startDocument()
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
        self.assertEqual(
            errors.StreamErrorCondition.UNDEFINED_CONDITION,
            cm.exception.condition
        )

    # def test_check_stream_header_version(self):
    #     attrs = self.STREAM_HEADER_ATTRS.copy()
    #     attrs[None, "version"] = "2.0"

    #     self.proc.startDocument()
    #     with self.assertRaises(errors.StreamError) as cm:
    #         self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
    #     self.assertEqual(
    #         errors.StreamErrorCondition.UNSUPPORTED_VERSION,
    #         cm.exception.condition
    #     )
    #     self.assertEqual(
    #         "2.0",
    #         cm.exception.text
    #     )

    def test_interpret_missing_version_as_0_point_9(self):
        attrs = self.STREAM_HEADER_ATTRS.copy()
        del attrs[None, "version"]

        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
        self.assertEqual(
            (0, 9),
            self.proc.remote_version,
        )

    def test_interpret_parsing_error_as_unsupported_version(self):
        attrs = self.STREAM_HEADER_ATTRS.copy()
        attrs[None, "version"] = "foobar"

        self.proc.startDocument()
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startElementNS(self.STREAM_HEADER_TAG, None, attrs)
        self.assertEqual(
            errors.StreamErrorCondition.UNSUPPORTED_VERSION,
            cm.exception.condition
        )

    def test_forward_to_parser(self):
        results = []

        def recv(obj):
            nonlocal results
            results.append(obj)

        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Cls, recv)

        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.startElementNS(Cls.TAG, None, {})
        self.proc.endElementNS(Cls.TAG, None)

        self.assertEqual(1, len(results))

        self.assertIsInstance(
            results[0],
            Cls)

    def test_end_element_of_stream_header_is_not_forwarded_to_parser(self):
        self.proc.startDocument()
        self.proc._driver = unittest.mock.MagicMock()

        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)

        self.assertSequenceEqual(
            [],
            self.proc._driver.mock_calls)

    def test_require_start_document(self):
        with self.assertRaises(RuntimeError):
            self.proc.startElementNS((None, "foo"), None, {})
        with self.assertRaises(RuntimeError):
            self.proc.endElementNS((None, "foo"), None)
        with self.assertRaises(RuntimeError):
            self.proc.characters("foo")

    def test_parse_complex_class(self):
        results = []

        def recv(obj):
            nonlocal results
            results.append(obj)

        class Bar(xso.XSO):
            TAG = ("uri:foo", "bar")

            text = xso.Text(default=None)

            def __init__(self, text=None):
                super().__init__()
                self.text = text

        class Baz(xso.XSO):
            TAG = ("uri:foo", "baz")

            children = xso.ChildList([Bar])

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

            attr = xso.Attr((None, "attr"))
            bar = xso.Child([Bar])
            baz = xso.Child([Baz])

        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)

        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 self.STREAM_HEADER_ATTRS)

        f = Foo()
        f.attr = "fnord"
        f.bar = Bar()
        f.bar.text = "some text"
        f.baz = Baz()
        f.baz.children.append(Bar("child a"))
        f.baz.children.append(Bar("child b"))

        f.unparse_to_sax(self.proc)

        self.assertEqual(1, len(results))

        f2 = results.pop()
        self.assertEqual(
            f.attr,
            f2.attr
        )
        self.assertEqual(
            f.bar.text,
            f2.bar.text
        )
        self.assertEqual(
            len(f.baz.children),
            len(f2.baz.children)
        )
        for c1, c2 in zip(f.baz.children, f2.baz.children):
            self.assertEqual(c1.text, c2.text)

        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def test_require_end_document_before_restarting(self):
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 self.STREAM_HEADER_ATTRS)
        with self.assertRaises(RuntimeError):
            self.proc.startDocument()
        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        with self.assertRaises(RuntimeError):
            self.proc.startDocument()
        self.proc.endDocument()
        self.proc.startDocument()

    def test_allow_end_document_only_after_stream_has_finished(self):
        with self.assertRaises(RuntimeError):
            self.proc.endDocument()
        self.proc.startDocument()
        with self.assertRaises(RuntimeError):
            self.proc.endDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 self.STREAM_HEADER_ATTRS)
        with self.assertRaises(RuntimeError):
            self.proc.endDocument()
        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def test_disallow_changing_stanza_parser_during_processing(self):
        self.proc.stanza_parser = unittest.mock.MagicMock()
        self.proc.startDocument()
        with self.assertRaises(RuntimeError):
            self.proc.stanza_parser = unittest.mock.MagicMock()

    def test_on_stream_header(self):
        stream_header = ()

        def catch_stream_header():
            nonlocal stream_header
            stream_header = (
                self.proc.remote_from,
                self.proc.remote_to,
                self.proc.remote_version,
                self.proc.remote_id)

        self.assertIsNone(self.proc.on_stream_header)
        self.proc.on_stream_header = catch_stream_header
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)

        self.assertSequenceEqual(
            (
                self.proc.remote_from,
                self.proc.remote_to,
                self.proc.remote_version,
                self.proc.remote_id
            ),
            stream_header)

    def test_on_stream_footer(self):
        catch_stream_footer = unittest.mock.MagicMock()

        self.assertIsNone(self.proc.on_stream_footer)
        self.proc.on_stream_footer = catch_stream_footer
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

        self.assertSequenceEqual(
            [
                unittest.mock.call.__bool__(),
                unittest.mock.call.__call__(),
            ],
            catch_stream_footer.mock_calls
        )

    def test_exception_recovery_and_reporting(self):
        catch_exception = unittest.mock.MagicMock()

        elements = []

        def recv(obj):
            nonlocal elements
            elements.append(obj)

        class Child(xso.XSO):
            TAG = ("uri:foo", "bar")

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

        self.assertIsNone(self.proc.on_exception)
        self.proc.on_exception = catch_exception
        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.startElementNS((None, "foo"), None, {})
        self.proc.startElementNS((None, "bar"), None, {})
        self.proc.characters("foobar")
        self.proc.endElementNS((None, "bar"), None)
        self.proc.endElementNS((None, "foo"), None)

        self.assertSequenceEqual(
            [
                unittest.mock.call.__bool__(),
                unittest.mock.call(unittest.mock.ANY)
            ],
            catch_exception.mock_calls)

        self.proc.startElementNS(("uri:foo", "foo"), None, {})
        self.proc.endElementNS(("uri:foo", "foo"), None)

        self.assertTrue(elements)
        self.assertIsInstance(elements[0], Foo)

        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def test_exception_in_endElementNS_recovery_and_reporting(self):
        catch_exception = unittest.mock.MagicMock()

        elements = []

        def recv(obj):
            nonlocal elements
            elements.append(obj)

        class Child(xso.XSO):
            TAG = ("uri:foo", "bar")

            t = xso.Text(type_=xso.Float())

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

            c = xso.Child([Child])

        self.assertIsNone(self.proc.on_exception)
        self.proc.on_exception = catch_exception
        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.startElementNS(("uri:foo", "foo"), None, {})
        self.proc.startElementNS(("uri:foo", "bar"), None, {})
        self.proc.characters("foobar")
        self.proc.endElementNS(("uri:foo", "bar"), None)
        self.proc.endElementNS(("uri:foo", "foo"), None)

        self.assertSequenceEqual(
            [
                unittest.mock.call.__bool__(),
                unittest.mock.call(unittest.mock.ANY)
            ],
            catch_exception.mock_calls)

        self.proc.startElementNS(("uri:foo", "foo"), None, {})
        self.proc.endElementNS(("uri:foo", "foo"), None)

        self.assertTrue(elements)
        self.assertIsInstance(elements[0], Foo)

        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def test_exception_in_endElementNS_toplevel_recovery_and_reporting(self):
        catch_exception = unittest.mock.MagicMock()

        elements = []

        def recv(obj):
            nonlocal elements
            elements.append(obj)

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

            t = xso.Text(type_=xso.Float())

        self.assertIsNone(self.proc.on_exception)
        self.proc.on_exception = catch_exception
        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.startElementNS(("uri:foo", "foo"), None, {})
        self.proc.characters("foobar")
        self.proc.endElementNS(("uri:foo", "foo"), None)

        self.assertSequenceEqual(
            [
                unittest.mock.call.__bool__(),
                unittest.mock.call(unittest.mock.ANY)
            ],
            catch_exception.mock_calls)

        self.proc.startElementNS(("uri:foo", "foo"), None, {})
        self.proc.endElementNS(("uri:foo", "foo"), None)

        self.assertTrue(elements)
        self.assertIsInstance(elements[0], Foo)

        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def test_exception_reraise_without_handler(self):
        elements = []

        def recv(obj):
            nonlocal elements
            elements.append(obj)

        class Child(xso.XSO):
            TAG = ("uri:foo", "bar")

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)
        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG,
                                 None,
                                 self.STREAM_HEADER_ATTRS)
        self.proc.startElementNS((None, "foo"), None, {})
        self.proc.startElementNS((None, "bar"), None, {})
        self.proc.characters("foobar")
        self.proc.endElementNS((None, "bar"), None)

        with self.assertRaises(ValueError):
            self.proc.endElementNS((None, "foo"), None)

    # def test_depth_limit(self):
    #     def dummy_parser():
    #         while True:
    #             yield

    #     self.assertEqual(
    #         1024,
    #         self.proc.depth_limit)

    #     self.proc.stanza_parser = dummy_parser
    #     self.proc.startDocument()
    #     self.proc.depth_limit = 100

    #     self.proc.startElementNS(self.STREAM_HEADER_TAG,
    #                              None,
    #                              self.STREAM_HEADER_ATTRS)
    #     for i in range(99):
    #         self.proc.startElementNS((None, "foo"), None, {})

    #     with self.assertRaises(errors.StreamError) as cm:
    #         self.proc.startElementNS((None, "foo"), None, {})
    #     self.assertEqual(
    #         errors.StreamErrorCondition.POLICY_VIOLATION,
    #         cm.exception.condition
    #     )

    def test_forwards_xml_lang_to_parser(self):
        results = []

        def recv(obj):
            nonlocal results
            results.append(obj)

        class Foo(xso.XSO):
            TAG = ("uri:foo", "foo")

            attr = xso.LangAttr()

        self.proc.stanza_parser = xso.XSOParser()
        self.proc.stanza_parser.add_class(Foo, recv)

        attrs = dict(self.STREAM_HEADER_ATTRS)
        attrs[namespaces.xml, "lang"] = "en"

        self.proc.startDocument()
        self.proc.startElementNS(self.STREAM_HEADER_TAG, None,
                                 attrs)

        self.proc.startElementNS(Foo.TAG, None, {})
        self.proc.endElementNS(Foo.TAG, None)

        self.assertEqual(1, len(results))

        f = results.pop()
        self.assertEqual(
            f.attr,
            structs.LanguageTag.fromstr("en")
        )

        self.proc.endElementNS(self.STREAM_HEADER_TAG, None)
        self.proc.endDocument()

    def tearDown(self):
        del self.proc
        del self.parser


class Testmake_parser(unittest.TestCase):
    def setUp(self):
        self.p = xml.make_parser()

    def test_is_incremental(self):
        self.assertTrue(
            hasattr(self.p, "feed")
        )

    def test_namespace_feature_enabled(self):
        self.assertTrue(
            self.p.getFeature(saxhandler.feature_namespaces)
        )

    def test_validation_feature_disabled(self):
        self.assertFalse(
            self.p.getFeature(saxhandler.feature_validation)
        )

    def test_external_ges_feature_disabled(self):
        self.assertFalse(
            self.p.getFeature(saxhandler.feature_external_ges)
        )

    def test_external_pes_feature_disabled(self):
        self.assertFalse(
            self.p.getFeature(saxhandler.feature_external_pes)
        )

    def test_uses_XMPPLexicalHandler(self):
        self.assertIs(
            xml.XMPPLexicalHandler,
            self.p.getProperty(saxhandler.property_lexical_handler)
        )


class TestXMPPLexicalHandler(unittest.TestCase):
    def setUp(self):
        self.proc = xml.XMPPLexicalHandler()

    def test_reject_comments(self):
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.comment("foobar")
        self.assertEqual(
            errors.StreamErrorCondition.RESTRICTED_XML,
            cm.exception.condition
        )
        self.proc.endCDATA()

    def test_reject_dtd(self):
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startDTD("foo", "bar", "baz")
        self.assertEqual(
            errors.StreamErrorCondition.RESTRICTED_XML,
            cm.exception.condition
        )
        self.proc.endDTD()

    def test_reject_non_predefined_entity(self):
        with self.assertRaises(errors.StreamError) as cm:
            self.proc.startEntity("foo")
        self.assertEqual(
            errors.StreamErrorCondition.RESTRICTED_XML,
            cm.exception.condition
        )
        self.proc.endEntity("foo")

    def test_accept_predefined_entity(self):
        for entity in ["amp", "lt", "gt", "apos", "quot"]:
            self.proc.startEntity(entity)
            self.proc.endEntity(entity)

    def test_ignore_cdata(self):
        self.proc.startCDATA()
        self.proc.endCDATA()

    def tearDown(self):
        del self.proc


class Testserialize_single_xso(unittest.TestCase):
    def test_simple(self):
        class TestXSO(xso.XSO):
            TAG = ("uri:foo", "bar")
            DECLARE_NS = {
                None: "uri:foo",
            }

            attr = xso.Attr("foo")

        x = TestXSO()
        x.attr = "test"

        self.assertEqual(
            '<bar xmlns="uri:foo" foo="test"/>',
            xml.serialize_single_xso(x)
        )


class Testwrite_single_xso(unittest.TestCase):
    def test_simple(self):
        class TestXSO(xso.XSO):
            TAG = ("uri:foo", "bar")
            DECLARE_NS = {
                None: "uri:foo",
            }

            attr = xso.Attr("foo")

        b = io.BytesIO()
        x = TestXSO()
        x.attr = "test"

        xml.write_single_xso(x, b)

        self.assertEqual(
            b'<bar xmlns="uri:foo" foo="test"/>',
            b.getvalue(),
        )


class Testread_xso(unittest.TestCase):
    def test_read_from_io(self):
        base = unittest.mock.Mock()

        xso_parser = base.XSOParser()
        sax_driver = base.SAXDriver()

        base.mock_calls.clear()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xso.XSOParser",
                base.XSOParser
            ))
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xso.SAXDriver",
                base.SAXDriver
            ))
            stack.enter_context(unittest.mock.patch(
                "xml.sax.make_parser",
                base.make_parser
            ))

            xml.read_xso(base.src, {
                base.A: base.cb,
            })

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.XSOParser(),
                unittest.mock.call.XSOParser().add_class(
                    base.A,
                    base.cb
                ),
                unittest.mock.call.SAXDriver(xso_parser),
                unittest.mock.call.make_parser(),
                unittest.mock.call.make_parser().setFeature(
                    saxhandler.feature_namespaces,
                    True),
                unittest.mock.call.make_parser().setFeature(
                    saxhandler.feature_external_ges,
                    False),
                unittest.mock.call.make_parser().setContentHandler(
                    sax_driver),
                unittest.mock.call.make_parser().parse(base.src)
            ]
        )


class Testread_single_xso(unittest.TestCase):
    def test_uses_read_xso_with_custom_callback(self):
        base = unittest.mock.Mock()

        def read_xso(src, xsomap):
            result = base.read_xso(src, xsomap)
            self.assertEqual(len(xsomap), 1)
            _, cb = next(iter(xsomap.items()))
            cb(result)

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.read_xso",
                new=read_xso
            ))

            result = xml.read_single_xso(base.src, base.Cls)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.read_xso(
                    base.src,
                    {
                        base.Cls: unittest.mock.ANY
                    }
                ),
            ]
        )

        self.assertEqual(
            result,
            base.read_xso()
        )

    def test_reject_non_predefined_entities(self):
        class Root(xso.XSO):
            TAG = "root"

            a = xso.Attr("a")

        bio = io.BytesIO(b"<?xml version='1.0'?><root a='foo&uuml;'/>")
        with self.assertRaises(xml_sax.SAXParseException):
            xml.read_single_xso(bio, Root)


class SomeChild(xso.XSO):
    TAG = "tests/test_xml.py", "child"

    a1 = xso.Attr("a1", type_=xso.Bool())

    text = xso.Text()

class SomeXSO(xso.XSO):
    TAG = "tests/test_xml.py", "root"

    a1 = xso.Attr("a1")
    a2 = xso.Attr("a2", type_=xso.Integer())

    children = xso.ChildList([SomeChild])

    other = xso.Collector()


class TestFullstack(XMLTestCase):
    def test_fullstack_test(self):
        DATA = (
            '<root xmlns="tests/test_xml.py" a1="foo" a2="10">'
            '<child a1="true">Text of child 1</child>'
            '<child a1="false">Text of child 2</child>'
            '<other-child>Text of unknown child 1</other-child>'
            '<other-child a1="foobar">Text of unknown child 2</other-child>'
            '</root>'
        )

        tree1 = etree.fromstring(DATA)

        with io.BytesIO(DATA.encode("utf-8")) as f:
            as_xso = xml.read_single_xso(f, SomeXSO)

        self.assertEqual(as_xso.a1, "foo")
        self.assertEqual(as_xso.a2, 10)

        self.assertEqual(len(as_xso.children), 2)

        self.assertEqual(
            as_xso.children[0].a1,
            True,
        )
        self.assertEqual(
            as_xso.children[0].text,
            "Text of child 1",
        )

        self.assertEqual(
            as_xso.children[1].a1,
            False,
        )
        self.assertEqual(
            as_xso.children[1].text,
            "Text of child 2",
        )

        self.assertEqual(
            len(as_xso.other),
            2,
        )

        with io.BytesIO() as f:
            xml.write_single_xso(as_xso, f)
            serialised = f.getvalue()

        # there is no need for named prefixes!
        self.assertNotIn(
            b'xmlns:',
            serialised,
        )

        print("serialised to {}".format(serialised))

        tree2 = etree.fromstring(serialised)

        self.assertSubtreeEqual(tree1, tree2)
