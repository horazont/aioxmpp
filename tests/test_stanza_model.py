import functools
import unittest
import unittest.mock

import lxml.sax

import asyncio_xmpp.stanza_model as stanza_model
import asyncio_xmpp.stanza_types as stanza_types

from asyncio_xmpp.utils import etree

from .testutils import XMLTestCase


class TestStanzaClass(unittest.TestCase):
    def test_init(self):
        class Cls(metaclass=stanza_model.StanzaClass):
            TAG = None, "foo"

        self.assertIsNone(Cls.TEXT_PROPERTY)

    def test_forbid_malformed_tag(self):
        with self.assertRaisesRegexp(TypeError,
                                     "TAG attribute has incorrect type"):
            class Cls(metaclass=stanza_model.StanzaClass):
                TAG = "foo", "bar", "baz"

        with self.assertRaisesRegexp(TypeError,
                                     "TAG attribute has incorrect type"):
            class Cls(metaclass=stanza_model.StanzaClass):
                TAG = "foo",

    def test_normalize_tag(self):
        class Cls(metaclass=stanza_model.StanzaClass):
            TAG = "foo"
        self.assertEqual(
            (None, "foo"),
            Cls.TAG)

    def test_collect_text_property(self):
        class Cls(metaclass=stanza_model.StanzaClass):
            TAG = "foo"
            prop = stanza_model.Text()

        self.assertIs(
            Cls.prop,
            Cls.TEXT_PROPERTY)

    def test_collect_child_property(self):
        class ClsA(metaclass=stanza_model.StanzaClass):
            TAG = "foo"
        class ClsB(metaclass=stanza_model.StanzaClass):
            TAG = "bar"
        class ClsC(metaclass=stanza_model.StanzaClass):
            TAG = "baz"

        class Cls(metaclass=stanza_model.StanzaClass):
            c1 = stanza_model.Child([ClsA, ClsB])
            c2 = stanza_model.Child([ClsC])

        self.assertDictEqual(
            {
                ClsA.TAG: Cls.c1,
                ClsB.TAG: Cls.c1,
                ClsC.TAG: Cls.c2,
            },
            Cls.CHILD_MAP)
        self.assertSetEqual(
            {Cls.c1, Cls.c2},
            Cls.CHILD_PROPS)

    def test_forbid_ambiguous_children(self):
        class ClsA(metaclass=stanza_model.StanzaClass):
            TAG = "foo"
        class ClsB(metaclass=stanza_model.StanzaClass):
            TAG = "foo"

        with self.assertRaisesRegexp(TypeError, "ambiguous Child properties"):
            class Cls(metaclass=stanza_model.StanzaClass):
                c1 = stanza_model.Child([ClsA])
                c2 = stanza_model.Child([ClsB])

    def test_collect_attr_property(self):
        class Cls(metaclass=stanza_model.StanzaClass):
            attr1 = stanza_model.Attr("foo")
            attr2 = stanza_model.Attr("bar")
            attr3 = stanza_model.Attr("baz")

        self.assertDictEqual(
            {
                (None, "foo"): Cls.attr1,
                (None, "bar"): Cls.attr2,
                (None, "baz"): Cls.attr3,
            },
            Cls.ATTR_MAP)

    def test_forbid_duplicate_text_property(self):
        with self.assertRaises(TypeError):
            class Cls(metaclass=stanza_model.StanzaClass):
                TAG = "foo"
                propa = stanza_model.Text()
                propb = stanza_model.Text()


class TestStanzaObject(XMLTestCase):
    def _unparse_test(self, obj, tree):
        parent = etree.Element("foo")
        obj.unparse_to_node(parent)
        self.assertSubtreeEqual(
            tree,
            parent
        )

    def setUp(self):
        class Cls(stanza_model.StanzaObject):
            TAG = "bar"

        self.Cls = Cls
        self.obj = Cls()

    def test_property_storage(self):
        self.obj._stanza_props["key"] = "value"

    def test_unparse_to_node_create_node(self):
        self._unparse_test(
            self.obj,
            etree.fromstring("<foo><bar/></foo>")
        )

    def test_unparse_to_node_handle_text(self):
        class Cls(stanza_model.StanzaObject):
            TAG = "bar"
            text = stanza_model.Text()

        obj = Cls()
        obj.text = "foobar"

        self._unparse_test(
            obj,
            etree.fromstring("<foo><bar>foobar</bar></foo>")
        )

    def test_unparse_to_node_handle_child(self):
        class ClsLeaf(stanza_model.StanzaObject):
            TAG = "baz"
            text = stanza_model.Text()

        class Cls(stanza_model.StanzaObject):
            TAG = "bar"
            child = stanza_model.Child([ClsLeaf])

        obj = Cls()
        obj.child = ClsLeaf()
        obj.child.text = "fnord"

        self._unparse_test(
            obj,
            etree.fromstring("<foo><bar><baz>fnord</baz></bar></foo>")
        )

    def test_unparse_to_node_handle_attr(self):
        class Cls(stanza_model.StanzaObject):
            TAG = "bar"
            attr = stanza_model.Attr("baz")

        obj = Cls()
        obj.attr = "fnord"

        self._unparse_test(
            obj,
            etree.fromstring("<foo><bar baz='fnord'/></foo>")
        )

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
        class ClsA(stanza_model.StanzaObject):
            test_str = stanza_model.Text(default="bar")
        class ClsB(stanza_model.StanzaObject):
            test_int = stanza_model.Text(type_=stanza_types.Integer())
        self.ClsA = ClsA
        self.ClsB = ClsB
        self.obja = ClsA()
        self.objb = ClsB()

    def test_default(self):
        self.assertEqual(
            "bar",
            self.obja.test_str)

    def test_string_from_node(self):
        self.ClsA.test_str.from_value(
            self.obja,
            "foo"
        )
        self.assertEqual(
            "foo",
            self.obja.test_str)

    def test_int_from_node(self):
        self.ClsB.test_int.from_value(
            self.objb,
            "123",
        )
        self.assertEqual(
            123,
            self.objb.test_int)

    def test_int_to_node(self):
        el = etree.Element("node")
        self.objb.test_int = 123
        self.ClsB.test_int.to_node(
            self.objb,
            el)
        self.assertEqual(
            "123",
            el.text)

    def tearDown(self):
        del self.obja
        del self.objb
        del self.ClsA
        del self.ClsB


class TestChild(XMLTestCase):
    def setUp(self):
        class ClsLeaf(stanza_model.StanzaObject):
            TAG = "bar"

        class ClsA(stanza_model.StanzaObject):
            TAG = "foo"
            test_child = stanza_model.Child([ClsLeaf])

        self.ClsLeaf = ClsLeaf
        self.ClsA = ClsA

    def test_match_map(self):
        self.assertDictEqual(
            {self.ClsLeaf.TAG: self.ClsLeaf},
            self.ClsA.test_child.get_tag_map()
        )

    def test_forbid_duplicate_tags(self):
        class ClsLeaf2(stanza_model.StanzaObject):
            TAG = "bar"

        with self.assertRaisesRegexp(ValueError, "ambiguous children"):
            stanza_model.Child([self.ClsLeaf, ClsLeaf2])

    def test_from_events(self):
        dest = []
        def mock_fun(ev_args):
            dest.append(ev_args)
            while True:
                value = yield
                dest.append(value)
                if value[0] == "stop":
                    return "bar"

        Cls = unittest.mock.MagicMock()
        Cls.TAG = None, "foo"
        Cls.parse_events = mock_fun

        prop = stanza_model.Child([Cls])

        instance = unittest.mock.MagicMock()
        instance._stanza_props = {}

        gen = prop.from_events(instance, (None, "foo", {}))
        next(gen)
        with self.assertRaises(StopIteration) as ctx:
            gen.send(("stop",))
        self.assertEqual(
            "bar",
            ctx.exception.value
        )
        self.assertSequenceEqual(
            [
                (None, "foo", {}),
                ("stop",)
            ],
            dest)
        self.assertDictEqual(
            {prop: "bar"},
            instance._stanza_props)

    def test_to_node(self):
        obj = self.ClsA()
        obj.test_child = unittest.mock.MagicMock()
        parent = etree.Element("foo")
        self.ClsA.test_child.to_node(obj, parent)
        self.assertSequenceEqual(
            [
                unittest.mock.call.unparse_to_node(parent)
            ],
            obj.test_child.mock_calls
        )

    def tearDown(self):
        del self.ClsA
        del self.ClsLeaf


class TestAttr(XMLTestCase):
    def test_name_attribute(self):
        prop = stanza_model.Attr("foo")
        self.assertEqual(
            (None, "foo"),
            prop.name
        )

        prop = stanza_model.Attr((None, "foo"))
        self.assertEqual(
            (None, "foo"),
            prop.name
        )

        prop = stanza_model.Attr(("bar", "foo"))
        self.assertEqual(
            ("bar", "foo"),
            prop.name
        )

    def test_from_value_and_type(self):
        instance = unittest.mock.MagicMock()
        instance._stanza_props = {}

        prop = stanza_model.Attr("foo", type_=stanza_types.Integer())
        prop.from_value(instance, "123")

        self.assertDictEqual(
            {
                prop: 123,
            },
            instance._stanza_props
        )

    def test_to_node(self):
        el = etree.Element("foo")
        prop = stanza_model.Attr("foo", type_=stanza_types.Bool())
        instance = unittest.mock.MagicMock()
        instance._stanza_props = {prop: True}

        prop.to_node(instance, el)
        self.assertSubtreeEqual(
            etree.fromstring("<foo foo='true'/>"),
            el)


class TestSAXDriver(unittest.TestCase):
    def setUp(self):
        self.l = []

    def catchall(self):
        while True:
            try:
                self.l.append((yield))
            except GeneratorExit as exc:
                self.l.append(exc)
                raise

    def test_forwards_startstop_events(self):
        tree = etree.fromstring("<foo/>")
        sd = stanza_model.SAXDriver(self.catchall)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", None, "foo", {}),
                ("end",)
            ],
            self.l
        )

        sd.close()

    def test_forwards_text_events(self):
        tree = etree.fromstring("<foo>bar</foo>")
        sd = stanza_model.SAXDriver(self.catchall)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", None, "foo", {}),
                ("text", "bar"),
                ("end",)
            ],
            self.l
        )

        sd.close()

    def test_forwards_nested_elements(self):
        tree = etree.fromstring("<foo><bar/></foo>")
        sd = stanza_model.SAXDriver(self.catchall)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", None, "foo", {}),
                ("start", None, "bar", {}),
                ("end",),
                ("end",)
            ],
            self.l
        )

        sd.close()

    def test_forwards_attributes(self):
        tree = etree.fromstring("<foo><bar a='b'/></foo>")
        sd = stanza_model.SAXDriver(self.catchall)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", None, "foo", {}),
                ("start", None, "bar", {(None, "a"): "b"}),
                ("end",),
                ("end",)
            ],
            self.l
        )

        sd.close()

    def test_forwards_namespaces(self):
        tree = etree.fromstring("<foo xmlns='uri:bar' />")
        sd = stanza_model.SAXDriver(self.catchall)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", "uri:bar", "foo", {}),
                ("end",)
            ],
            self.l
        )

        sd.close()

    def test_collect_result(self):
        l = []
        results = []
        def returning_coroutine():
            nonlocal l
            while True:
                data = yield
                l.append(data)
                if data[0] == "end":
                    return "foo"

        def catch_result(value):
            nonlocal results
            results.append(value)

        tree = etree.fromstring("<foo/>")
        sd = stanza_model.SAXDriver(
            returning_coroutine,
            on_emit=catch_result)
        lxml.sax.saxify(tree, sd)
        lxml.sax.saxify(tree, sd)

        self.assertSequenceEqual(
            [
                ("start", None, "foo", {}),
                ("end",),
            ]*2,
            l)
        self.assertSequenceEqual(
            ["foo"]*2,
            results)

        sd.close()

    def test_close_forwards_to_generator(self):
        sd = stanza_model.SAXDriver(self.catchall)
        sd.startElementNS((None, "foo"), "foo", {})
        sd.close()

        self.assertIsInstance(self.l[-1], GeneratorExit)

    def tearDown(self):
        del self.l


# class Testguard_wrap(unittest.TestCase):
#     def catchall(self):
#         while True:
#             ev_type, *_ = yield
#             if ev_type == "stop":
#                 return

#     def test_requires_proper_generator(self):
#         gw = stanza_model.guard_wrap([])
#         with self.assertRaisesRegexp(RuntimeError, "not a generator"):
#             gw.send(None)

#     def test_requires_fresh_generator(self):
#         gen = self.catchall()
#         next(gen)
#         gw = stanza_model.guard_wrap(gen)
#         with self.assertRaisesRegexp(RuntimeError, "invalid generator state"):
#             gw.send(None)

#     def test_enforce_end_boundary(self):
#         gw = stanza_model.guard_wrap(self.catchall())
#         gw.send(None)
#         gw.send(("start", ))
#         with self.assertRaisesRegexp(RuntimeError, "unexpected return"):
#             gw.send(("stop", ))


class Teststanza_parser(unittest.TestCase):
    def run_parser(self, stanza_cls, tree):
        results = []

        def catch_result(value):
            nonlocal results
            results.append(value)

        sd = stanza_model.SAXDriver(
            functools.partial(stanza_model.stanza_parser, stanza_cls),
            on_emit = catch_result
        )
        lxml.sax.saxify(tree, sd)

        return results

    def run_parser_one(self, stanza_cls, tree):
        results = self.run_parser(stanza_cls, tree)
        self.assertEqual(1, len(results))
        return results[0]

    def test_parse_text(self):
        class TestStanza(stanza_model.StanzaObject):
            TAG = "uri:bar", "foo"
            contents = stanza_model.Text()
        tree = etree.fromstring("<foo xmlns='uri:bar'>bar</foo>")
        result = self.run_parser_one([TestStanza], tree)
        self.assertIsInstance(result, TestStanza)
        self.assertEqual(result.contents, "bar")

    def test_parse_text_split_in_multiple_events(self):
        class Dummy(stanza_model.StanzaObject):
            TAG = "uri:bar", "dummy"

        class TestStanza(stanza_model.StanzaObject):
            TAG = "uri:bar", "foo"

            contents = stanza_model.Text()
            _ = stanza_model.Child([Dummy])

        tree = etree.fromstring("<foo xmlns='uri:bar'>bar<dummy/>baz</foo>")
        result = self.run_parser_one([TestStanza], tree)
        self.assertIsInstance(result, TestStanza)
        self.assertEqual(result.contents, "barbaz")

    def test_handle_unknown_tag_at_toplevel(self):
        tree = etree.fromstring("<foo />")
        class TestStanza(stanza_model.StanzaObject):
            TAG = "uri:bar", "foo"

        with self.assertRaises(stanza_model.UnknownTopLevelTag) as ctx:
            self.run_parser_one([TestStanza], tree)
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertSequenceEqual(
            (None, "foo", {}),
            ctx.exception.ev_args
        )

    def test_handle_unknown_tag_at_non_toplevel(self):
        tree = etree.fromstring("<foo><bar/></foo>")
        class TestStanza(stanza_model.StanzaObject):
            TAG = None, "foo"

        with self.assertRaises(ValueError):
            self.run_parser_one([TestStanza], tree)

    def test_handle_unknown_attribute(self):
        tree = etree.fromstring("<foo a='bar' />")
        class TestStanza(stanza_model.StanzaObject):
            TAG = None, "foo"

        with self.assertRaises(ValueError):
            self.run_parser_one([TestStanza], tree)

    def test_handle_unknown_text(self):
        tree = etree.fromstring("<foo>bar</foo>")
        class TestStanza(stanza_model.StanzaObject):
            TAG = None, "foo"

        with self.assertRaises(ValueError):
            self.run_parser_one([TestStanza], tree)

    def test_parse_simple_with_another_attribute(self):
        class TestStanza(stanza_model.StanzaObject):
            TAG = "uri:bar", "foo"
            text = stanza_model.Text()
        tree = etree.fromstring("<foo xmlns='uri:bar'>bar</foo>")
        result = self.run_parser_one([TestStanza], tree)
        self.assertIsInstance(result, TestStanza)
        self.assertEqual(result.text, "bar")

    def test_parse_detect_class(self):
        class TestStanzaA(stanza_model.StanzaObject):
            TAG = "uri:bar", "a"

        class TestStanzaB(stanza_model.StanzaObject):
            TAG = "uri:bar", "b"

        tree = etree.fromstring("<a xmlns='uri:bar' />")
        result = self.run_parser_one([TestStanzaA, TestStanzaB], tree)
        self.assertIsInstance(result, TestStanzaA)

        tree = etree.fromstring("<b xmlns='uri:bar' />")
        result = self.run_parser_one([TestStanzaA, TestStanzaB], tree)
        self.assertIsInstance(result, TestStanzaB)

    def test_parse_child(self):
        class Bar(stanza_model.StanzaObject):
            TAG = "bar"

        class Foo(stanza_model.StanzaObject):
            TAG = "foo"

            child = stanza_model.Child([Bar])

        tree = etree.fromstring("<foo><bar/></foo>")
        result = self.run_parser_one([Foo], tree)
        self.assertIsInstance(result, Foo)
        self.assertIsInstance(result.child, Bar)

    def test_parse_attribute(self):
        class Foo(stanza_model.StanzaObject):
            TAG = "foo"

            attr = stanza_model.Attr("bar")

        tree = etree.fromstring("<foo bar='baz'/>")
        result = self.run_parser_one([Foo], tree)
        self.assertEqual(
            "baz",
            result.attr)
