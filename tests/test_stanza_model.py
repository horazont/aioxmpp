import unittest

import asyncio_xmpp.stanza_model as stanza_model
import asyncio_xmpp.stanza_types as stanza_types

from asyncio_xmpp.utils import etree


class TestStanzaObject(unittest.TestCase):
    def setUp(self):
        class Cls(stanza_model.StanzaObject):
            pass

        self.Cls = Cls
        self.obj = Cls()

    def test_property_storage(self):
        self.obj._stanza_props["key"] = "value"

    def tearDown(self):
        del self.obj
        del self.Cls


class Test_PropBase(unittest.TestCase):
    def setUp(self):
        self.default = object()
        class Cls(stanza_model.StanzaObject):
            prop = stanza_model._PropBase(default=self.default)
        self.Cls = Cls
        self.obj = Cls()

    def test_get_unset(self):
        self.assertIs(
            self.default,
            self.obj.prop)

    def test_set_get_cycle(self):
        self.obj.prop = "foo"
        self.assertEqual(
            "foo",
            self.obj.prop)

    def test_get_on_class(self):
        self.assertIsInstance(
            self.Cls.prop,
            stanza_model._PropBase)

    def tearDown(self):
        del self.obj
        del self.Cls
        del self.default


class TestText(unittest.TestCase):
    def setUp(self):
        class Cls(stanza_model.StanzaObject):
            test_str = stanza_model.Text(default="bar")
            test_int = stanza_model.Text(type_=stanza_types.Integer())
        self.Cls = Cls
        self.obj = Cls()

    def test_default(self):
        self.assertEqual(
            "bar",
            self.obj.test_str)

    def test_string_from_node(self):
        self.Cls.test_str.from_node(
            self.obj,
            etree.fromstring("<node>foo</node>")
        )
        self.assertEqual(
            "foo",
            self.obj.test_str)

    def test_int_from_node(self):
        self.Cls.test_int.from_node(
            self.obj,
            etree.fromstring("<node>123</node>")
        )
        self.assertEqual(
            123,
            self.obj.test_int)

    def test_int_to_node(self):
        el = etree.Element("node")
        self.obj.test_int = 123
        self.Cls.test_int.to_node(
            self.obj,
            el)
        self.assertEqual(
            "123",
            el.text)

    def tearDown(self):
        del self.obj
        del self.Cls
