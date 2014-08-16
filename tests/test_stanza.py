import itertools
import unittest

import asyncio_xmpp.stanza as stanza

from asyncio_xmpp.utils import etree, namespaces

class TestError(unittest.TestCase):
    def setUp(self):
        self.appdef = etree.fromstring(b"""<data />""")

    def test_init(self):
        err = stanza.Error()
        self.assertEqual(
            "{{{}}}undefined-condition".format(namespaces.stanzas),
            err[0].tag)
        self.assertEqual(
            err[0].tag.partition("}")[2],
            err.condition)

    def test_conditions(self):
        err = stanza.Error()
        err.condition = "bad-request"
        self.assertEqual(
            "{{{}}}bad-request".format(namespaces.stanzas),
            err[0].tag)

    def test_text(self):
        err = stanza.Error()
        self.assertIsNone(
            err.find(stanza.Error._TEXT_ELEMENT))
        err.text = "foo"
        self.assertEqual(
            err.find(stanza.Error._TEXT_ELEMENT).text,
            "foo")
        err.text = None
        self.assertIsNone(
            err.find(stanza.Error._TEXT_ELEMENT).text)
        self.assertEqual(
            len(err),
            2)
        del err.text
        self.assertEqual(
            len(err),
            1)

    def test_application_defined(self):
        err = stanza.Error()
        self.assertEqual(len(err), 1)
        err.application_defined_condition = self.appdef
        self.assertEqual(len(err), 2)
        self.assertIs(err[-1], self.appdef)
        with self.assertRaises(ValueError):
            err.application_defined_condition = None

        del err.application_defined_condition
        self.assertEqual(len(err), 1)

    def test_mixed(self):
        # the main idea of this is that we MUST be able to randomly modify the
        # .text and .application_defined_condition attributes without blowing
        # the structure up

        err = stanza.Error()
        err.application_defined_condition = self.appdef
        err.text = "foo"
        self.assertEqual(
            err[1].tag,
            stanza.Error._TEXT_ELEMENT)
        self.assertIs(
            err[2],
            self.appdef)

    def test_init_from_xmltext(self):
        # we have to correctly parse even totally mixed up elements
        lookup = etree.ElementNamespaceClassLookup()
        lookup.get_namespace("jabber:client")["error"] = stanza.Error
        parser = etree.XMLParser()
        parser.set_element_class_lookup(lookup)

        prefix = b'<error xmlns="jabber:client">'
        parts = [
            b'<bad-request xmlns="urn:ietf:params:xml:ns:xmpp-stanzas" />',
            b'<text xmlns="urn:ietf:params:xml:ns:xmpp-stanzas">foobar</text>',
            b'<data />',
        ]
        suffix = b'</error>'

        for permutation in itertools.permutations(parts):
            err = etree.fromstring(
                prefix+b"".join(permutation)+suffix,
                parser=parser)

            self.assertEqual("bad-request",
                             err.condition)
            self.assertEqual("foobar",
                             err.text)
            self.assertEqual("{jabber:client}data",
                             err.application_defined_condition.tag)

    def test_detect_errors_in_xmltext(self):
        # but we reject malformed elements
        lookup = etree.ElementNamespaceClassLookup()
        lookup.get_namespace("jabber:client")["error"] = stanza.Error
        parser = etree.XMLParser()
        parser.set_element_class_lookup(lookup)

        # but we insert undefined condition in empty error elements implicitly
        err = etree.fromstring(b'<error xmlns="jabber:client" />',
                               parser=parser)
        self.assertEqual(
            err.condition,
            "undefined-condition")

        with self.assertRaises(ValueError):
            etree.fromstring(
                b'<error xmlns="jabber:client">'
                b'<bad-request xmlns="urn:ietf:params:xml:ns:xmpp-stanzas" />'
                b'<bad-request xmlns="urn:ietf:params:xml:ns:xmpp-stanzas" />'
                b'</error>',
                parser=parser)

        with self.assertRaises(ValueError):
            etree.fromstring(
                b'<error xmlns="jabber:client">'
                b'<text xmlns="urn:ietf:params:xml:ns:xmpp-stanzas">foo</text>'
                b'<text xmlns="urn:ietf:params:xml:ns:xmpp-stanzas">foo</text>'
                b'</error>',
                parser=parser)

        with self.assertRaises(ValueError):
            etree.fromstring(
                b'<error xmlns="jabber:client">'
                b'<data />'
                b'<foo />'
                b'</error>',
                parser=parser)
