import unittest

import asyncio_xmpp.jid as jid

from asyncio_xmpp.utils import *
from asyncio_xmpp.stanza_props import *

class TestStringType(unittest.TestCase):
    def test_passthrough(self):
        t = StringType()
        self.assertEqual(
            t.get("foo", "bar"),
            "foo")
        self.assertEqual(
            t.get("baz", "bar"),
            "baz")

    def test_default_on_None(self):
        t = StringType()
        self.assertEqual(
            t.get(None, "bar"),
            "bar")

    def test_require_string_on_set(self):
        t = StringType()
        with self.assertRaises(ValueError):
            t.set(None)
        with self.assertRaises(ValueError):
            t.set(10)


class TestJIDType(unittest.TestCase):
    def test_parse_jid(self):
        t = JIDType()
        self.assertEqual(
            t.get("foo@bar.test", None),
            jid.JID("foo", "bar.test", None)
        )
        self.assertEqual(
            t.get("foo@bar.test/resource", None),
            jid.JID("foo", "bar.test", "resource")
        )

    def test_default_on_failure(self):
        t = JIDType()
        self.assertEqual(
            t.get("@@", 1),
            1
        )

    def test_default_on_None(self):
        t = JIDType()
        self.assertEqual(
            t.get(None, 1),
            1
        )

class TestEnumType(unittest.TestCase):
    def setUp(self):
        self.t = EnumType(["a", "b", "c"])

    def test_get(self):
        self.assertEqual(
            self.t.get("a", None),
            "a")
        self.assertEqual(
            self.t.get("b", None),
            "b")
        self.assertEqual(
            self.t.get("c", None),
            "c")

    def test_default_on_failure(self):
        self.assertEqual(
            self.t.get("d", "bar"),
            "bar")

    def tearDown(self):
        del self.t

class TestBoolType(unittest.TestCase):
    def test_get(self):
        t = BoolType()
        self.assertIs(True, t.get("true", None))
        self.assertIs(True, t.get("1", None))
        self.assertIs(False, t.get("false", None))
        self.assertIs(False, t.get("0", None))

    def test_set(self):
        t = BoolType()
        self.assertEqual(
            "true",
            t.set("1")
        )
        self.assertEqual(
            "false",
            t.set("")
        )
        self.assertEqual(
            "false",
            t.set(False)
        )
        self.assertEqual(
            "false",
            t.set(())
        )
        self.assertEqual(
            "true",
            t.set([1, 2])
        )

class Testxmlattr(unittest.TestCase):
    def setUp(self):
        self.node = etree.Element("foo")
        self.node.set("bool", "true")
        self.node.set("str", "foobarbaz")
        self.node.set("jid", "foo@bar.test/resource")

    def test_default_is_string(self):
        a = xmlattr(name="str")
        self.assertEqual(
            "foobarbaz",
            a.__get__(self.node, None)
        )

    def test_set(self):
        a = xmlattr(BoolType(), name="bool")
        a.__set__(self.node, True)
        self.assertEqual("true", self.node.get("bool"))

    def test_delete(self):
        a = xmlattr(BoolType(), name="bool")
        a.__delete__(self.node)
        self.assertIsNone(self.node.get("bool"))

    def test_bool(self):
        a = xmlattr(BoolType(), name="bool")
        self.assertIs(
            True,
            a.__get__(self.node, None)
        )

    def test_jid(self):
        a = xmlattr(JIDType(), name="jid")
        self.assertEqual(
            jid.JID("foo", "bar.test", "resource"),
            a.__get__(self.node, None)
        )

    def tearDown(self):
        del self.node


class Testxmltext(unittest.TestCase):
    def setUp(self):
        self.node = etree.Element("foo")
        self.node.text = "foobarbaz"
        self.d = xmltext()

    def test_get(self):
        self.assertEqual(
            "foobarbaz",
            self.d.__get__(self.node, None)
        )

    def test_set(self):
        self.d.__set__(self.node, "fnord")
        self.assertEqual(
            "fnord",
            self.node.text
        )

    def test_delete(self):
        self.d.__delete__(self.node)
        self.assertIsNone(self.node.text)

    def tearDown(self):
        del self.d
        del self.node


class Testxmlchildtext(unittest.TestCase):
    def setUp(self):
        self.node = etree.Element("foo")
        self.child = etree.SubElement(self.node, "bar")
        self.child.text = "foobarbaz"
        self.d = xmlchildtext(tag="bar")

    def test_get(self):
        self.assertEqual(
            "foobarbaz",
            self.d.__get__(self.node, None)
        )

    def test_set(self):
        self.d.__set__(self.node, "fnord")
        self.assertEqual(
            "fnord",
            self.child.text
        )

    def test_hard_delete(self):
        self.assertIn(
            self.child,
            self.node)
        self.d.__delete__(self.node)
        self.assertNotIn(
            self.child,
            self.node)

    def test_soft_delete(self):
        self.d._hard_delete = False
        self.assertIn(
            self.child,
            self.node)
        self.d.__delete__(self.node)
        self.assertIn(
            self.child,
            self.node)
        self.assertIsNone(self.child.text)

    def tearDown(self):
        del self.d
        del self.child
        del self.node
