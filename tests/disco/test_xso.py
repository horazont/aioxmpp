import unittest

import aioxmpp.disco as disco
import aioxmpp.disco.xso as disco_xso
import aioxmpp.xso as xso

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
        self.assertTrue(disco_xso.Identity.category.required)

    def test_type_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.type_,
            xso.Attr
        )
        self.assertEqual(
            (None, "type"),
            disco_xso.Identity.type_.tag
        )
        self.assertTrue(disco_xso.Identity.type_.required)

    def test_name_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.name,
            xso.Attr
        )
        self.assertEqual(
            (None, "name"),
            disco_xso.Identity.name.tag
        )
        self.assertFalse(disco_xso.Identity.name.required)

    def test_lang_attr(self):
        self.assertIsInstance(
            disco_xso.Identity.lang,
            xso.LangAttr
        )


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
        self.assertTrue(disco_xso.Feature.var.required)


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
        self.assertFalse(disco_xso.InfoQuery.node.required)

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
        self.assertTrue(disco_xso.Item.jid.required)

    def test_name_attr(self):
        self.assertIsInstance(
            disco_xso.Item.name,
            xso.Attr
        )
        self.assertEqual(
            (None, "name"),
            disco_xso.Item.name.tag
        )
        self.assertFalse(disco_xso.Item.name.required)

    def test_node_attr(self):
        self.assertIsInstance(
            disco_xso.Item.node,
            xso.Attr
        )
        self.assertEqual(
            (None, "node"),
            disco_xso.Item.node.tag
        )
        self.assertFalse(disco_xso.Item.node.required)


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
        self.assertFalse(disco_xso.ItemsQuery.node.required)
