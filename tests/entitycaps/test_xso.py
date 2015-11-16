import unittest

import aioxmpp.entitycaps.xso as entitycaps_xso
import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_caps(self):
        self.assertEqual(
            namespaces.xep0115_caps,
            "http://jabber.org/protocol/caps"
        )


class TestCaps(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            entitycaps_xso.Caps,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0115_caps, "c"),
            entitycaps_xso.Caps.TAG
        )

    def test_node_attr(self):
        self.assertIsInstance(
            entitycaps_xso.Caps.node,
            xso.Attr
        )
        self.assertEqual(
            (None, "node"),
            entitycaps_xso.Caps.node.tag
        )
        self.assertIs(
            entitycaps_xso.Caps.node.default,
            xso.NO_DEFAULT
        )

    def test_hash_attr(self):
        self.assertIsInstance(
            entitycaps_xso.Caps.hash_,
            xso.Attr
        )
        self.assertEqual(
            (None, "hash"),
            entitycaps_xso.Caps.hash_.tag
        )
        self.assertIsInstance(
            entitycaps_xso.Caps.hash_.validator,
            xso.Nmtoken
        )
        self.assertEqual(
            xso.ValidateMode.FROM_CODE,
            entitycaps_xso.Caps.hash_.validate
        )
        self.assertIs(
            entitycaps_xso.Caps.hash_.default,
            None
        )

    def test_ver_attr(self):
        self.assertIsInstance(
            entitycaps_xso.Caps.ver,
            xso.Attr
        )
        self.assertEqual(
            (None, "ver"),
            entitycaps_xso.Caps.ver.tag
        )
        self.assertIs(
            entitycaps_xso.Caps.ver.default,
            xso.NO_DEFAULT
        )

    def test_ext_attr(self):
        self.assertIsInstance(
            entitycaps_xso.Caps.ext,
            xso.Attr
        )
        self.assertEqual(
            (None, "ext"),
            entitycaps_xso.Caps.ext.tag
        )
        self.assertIs(
            entitycaps_xso.Caps.ext.default,
            None
        )

    def test_attr_on_Presence(self):
        self.assertIsInstance(
            stanza.Presence.xep0115_caps,
            xso.Child,
        )
        self.assertSetEqual(
            {
                entitycaps_xso.Caps
            },
            set(stanza.Presence.xep0115_caps._classes)
        )

    def test_init(self):
        caps = entitycaps_xso.Caps(
            "node",
            "ver",
            "hash",
        )

        self.assertEqual(caps.node, "node")
        self.assertEqual(caps.ver, "ver")
        self.assertEqual(caps.hash_, "hash")

        with self.assertRaisesRegex(TypeError,
                                    "positional argument"):
            entitycaps_xso.Caps()
