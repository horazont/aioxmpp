import unittest

import aioxmpp.disco.xso as disco_xso
import aioxmpp.forms.xso as forms_xso
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza
import aioxmpp.xso as xso
import aioxmpp.xso.model as xso_model

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_info_namespace(self):
        self.assertEqual(
            "http://jabber.org/protocol/disco#info",
            namespaces.xep0030_info
        )

    def test_items_namespace(self):
        self.assertEqual(
            "http://jabber.org/protocol/disco#items",
            namespaces.xep0030_items
        )


class TestIdentity(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(disco_xso.Identity, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0030_info, "identity"),
            disco_xso.Identity.TAG
        )

    def test_category_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.category,
            xso.Attr
        )
        self.assertEqual(
            (None, "category"),
            disco_xso.Identity.category.tag
        )
        self.assertIs(
            xso.NO_DEFAULT,
            disco_xso.Identity.category.default
        )

    def test_type_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.type_,
            xso.Attr
        )
        self.assertEqual(
            (None, "type"),
            disco_xso.Identity.type_.tag
        )
        self.assertIs(
            xso.NO_DEFAULT,
            disco_xso.Identity.type_.default
        )

    def test_name_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.name,
            xso.Attr
        )
        self.assertEqual(
            (None, "name"),
            disco_xso.Identity.name.tag
        )
        self.assertIs(disco_xso.Identity.name.default, None)

    def test_lang_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.lang,
            xso.LangAttr
        )
        self.assertIsNone(
            disco_xso.Identity.lang.default
        )

    def test_init(self):
        ident = disco_xso.Identity()
        self.assertEqual("client", ident.category)
        self.assertEqual("bot", ident.type_)
        self.assertIsNone(ident.name)
        self.assertIsNone(ident.lang)

        ident = disco_xso.Identity(
            category="account",
            type_="anonymous",
            name="Foobar",
            lang=structs.LanguageTag.fromstr("de")
        )
        self.assertEqual("account", ident.category)
        self.assertEqual("anonymous", ident.type_)
        self.assertEqual("Foobar", ident.name)
        self.assertEqual(structs.LanguageTag.fromstr("DE"), ident.lang)


class TestFeature(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(disco_xso.Feature, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0030_info, "feature"),
            disco_xso.Feature.TAG
        )

    def test_var_attr(self):
        self.assertIsInstance(
            disco_xso.Feature.var,
            xso.Attr
        )
        self.assertEqual(
            (None, "var"),
            disco_xso.Feature.var.tag
        )
        self.assertIs(
            xso.NO_DEFAULT,
            disco_xso.Feature.var.default
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            disco_xso.Feature()

        f = disco_xso.Feature(var="foobar")
        self.assertEqual("foobar", f.var)


class TestInfoQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(disco_xso.InfoQuery, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0030_info, "query"),
            disco_xso.InfoQuery.TAG
        )

    def test_node_attr(self):
        self.assertIsInstance(
            disco_xso.InfoQuery.node,
            xso.Attr
        )
        self.assertEqual(
            (None, "node"),
            disco_xso.InfoQuery.node.tag
        )
        self.assertIs(disco_xso.InfoQuery.node.default, None)

    def test_identities_attr(self):
        self.assertIsInstance(
            disco_xso.InfoQuery.identities,
            xso.ChildList
        )
        self.assertSetEqual(
            {disco_xso.Identity},
            set(disco_xso.InfoQuery.identities._classes)
        )

    def test_features_attr(self):
        self.assertIsInstance(
            disco_xso.InfoQuery.features,
            xso.ChildList
        )
        self.assertSetEqual(
            {disco_xso.Feature},
            set(disco_xso.InfoQuery.features._classes)
        )

    def test_exts_attr(self):
        self.assertIsInstance(
            disco_xso.InfoQuery.exts,
            xso.ChildList
        )
        self.assertSetEqual(
            {forms_xso.Data},
            set(disco_xso.InfoQuery.exts._classes)
        )

    def test_init(self):
        iq = disco_xso.InfoQuery()
        self.assertFalse(iq.features)
        self.assertFalse(iq.identities)
        self.assertIsNone(iq.node)

        iq = disco_xso.InfoQuery(node="foobar",
                                 features=(1, 2),
                                 identities=(3,))
        self.assertIsInstance(iq.features, xso_model.XSOList)
        self.assertSequenceEqual(
            [1, 2],
            iq.features
        )
        self.assertIsInstance(iq.identities, xso_model.XSOList)
        self.assertSequenceEqual(
            [3],
            iq.identities
        )
        self.assertEqual("foobar", iq.node)

    def test_registered_at_IQ(self):
        self.assertIn(
            disco_xso.InfoQuery.TAG,
            stanza.IQ.CHILD_MAP
        )

    def test_to_dict(self):
        q = disco_xso.InfoQuery()
        q.identities.extend([
            disco_xso.Identity(
                category="client",
                type_="pc",
                name="foobar"
            ),
            disco_xso.Identity(
                category="client",
                type_="pc",
                name="baz",
                lang=structs.LanguageTag.fromstr("en-GB")
            ),
        ])

        q.features.extend(
            disco_xso.Feature(var)
            for var in [
                "foo",
                "bar",
                "baz",
            ]
        )

        f = forms_xso.Data()
        f.fields.extend([
            forms_xso.Field(type_="hidden",
                            var="FORM_TYPE",
                            values=[
                                "fnord",
                            ]),
            forms_xso.Field(type_="text-single",
                            var="uiae",
                            values=[
                                "nrtd",
                                "asdf",
                            ]),
            forms_xso.Field(type_="fixed"),
        ])
        q.exts.append(f)

        self.assertDictEqual(
            q.to_dict(),
            {
                "features": [
                    "foo",
                    "bar",
                    "baz",
                ],
                "identities": [
                    {
                        "category": "client",
                        "type": "pc",
                        "name": "foobar",
                    },
                    {
                        "category": "client",
                        "type": "pc",
                        "name": "baz",
                        "lang": "en-gb",
                    },
                ],
                "forms": {
                    "fnord": {
                        "uiae": [
                            "nrtd",
                            "asdf",
                        ]
                    }
                }
            }
        )


class TestItem(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(disco_xso.Item, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0030_items, "item"),
            disco_xso.Item.TAG
        )

    def test_jid_attr(self):
        self.assertIsInstance(
            disco_xso.Item.jid,
            xso.Attr
        )
        self.assertEqual(
            (None, "jid"),
            disco_xso.Item.jid.tag
        )
        self.assertIsInstance(
            disco_xso.Item.jid.type_,
            xso.JID
        )
        self.assertIs(
            disco_xso.Item.jid.default,
            xso.NO_DEFAULT
        )

    def test_name_attr(self):
        self.assertIsInstance(
            disco_xso.Item.name,
            xso.Attr
        )
        self.assertEqual(
            (None, "name"),
            disco_xso.Item.name.tag
        )
        self.assertIs(disco_xso.Item.name.default, None)

    def test_node_attr(self):
        self.assertIsInstance(
            disco_xso.Item.node,
            xso.Attr
        )
        self.assertEqual(
            (None, "node"),
            disco_xso.Item.node.tag
        )
        self.assertIs(disco_xso.Item.node.default, None)

    def test_unknown_child_policy(self):
        self.assertEqual(
            xso.UnknownChildPolicy.DROP,
            disco_xso.Item.UNKNOWN_CHILD_POLICY
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            disco_xso.Item()
        jid = structs.JID.fromstr("foo@bar.example/baz")

        item = disco_xso.Item(jid)
        self.assertIsNone(item.name)
        self.assertIsNone(item.node)

        item = disco_xso.Item(jid=jid, name="fnord", node="test")
        self.assertEqual(jid, item.jid)
        self.assertEqual("fnord", item.name)
        self.assertEqual("test", item.node)


class TestItemsQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(disco_xso.ItemsQuery, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0030_items, "query"),
            disco_xso.ItemsQuery.TAG
        )

    def test_node_attr(self):
        self.assertIsInstance(
            disco_xso.ItemsQuery.node,
            xso.Attr
        )
        self.assertEqual(
            (None, "node"),
            disco_xso.ItemsQuery.node.tag
        )
        self.assertIs(disco_xso.ItemsQuery.node.default, None)

    def test_items_attr(self):
        self.assertIsInstance(
            disco_xso.ItemsQuery.items,
            xso.ChildList
        )
        self.assertSetEqual(
            {disco_xso.Item},
            set(disco_xso.ItemsQuery.items._classes)
        )

    def test_registered_at_IQ(self):
        self.assertIn(
            disco_xso.ItemsQuery.TAG,
            stanza.IQ.CHILD_MAP
        )

    def test_init(self):
        iq = disco_xso.ItemsQuery()
        self.assertIsNone(iq.node)
        self.assertFalse(iq.items)

        iq = disco_xso.ItemsQuery(node="test", items=(1, 2))
        self.assertEqual("test", iq.node)
        self.assertIsInstance(iq.items, xso_model.XSOList)
        self.assertSequenceEqual(
            [1, 2],
            iq.items
        )
