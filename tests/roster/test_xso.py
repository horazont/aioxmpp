import unittest

import aioxmpp.roster.xso as roster_xso
import aioxmpp.stanza as stanza
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.xso.model as xso_model

from aioxmpp.utils import namespaces


TEST_JID = structs.JID.fromstr("foo@bar.example")


class TestNamespaces(unittest.TestCase):
    def test_roster_namespace(self):
        self.assertEqual(
            "jabber:iq:roster",
            namespaces.rfc6121_roster
        )

    def test_roster_versioning_namespace(self):
        self.assertEqual(
            "urn:xmpp:features:rosterver",
            namespaces.rfc6121_roster_versioning
        )


class TestGroup(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.rfc6121_roster, "group"),
            roster_xso.Group.TAG
        )

    def test_name_attr(self):
        self.assertIsInstance(
            roster_xso.Group.name,
            xso.Text
        )

    def test_init(self):
        g = roster_xso.Group()
        self.assertIsNone(g.name)

        g = roster_xso.Group(name="foobar")
        self.assertEqual("foobar", g.name)


class TestItem(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.rfc6121_roster, "item"),
            roster_xso.Item.TAG
        )

    def test_approved_attr(self):
        self.assertIsInstance(
            roster_xso.Item.approved,
            xso.Attr
        )
        self.assertEqual(
            (None, "approved"),
            roster_xso.Item.approved.tag
        )
        self.assertIsInstance(
            roster_xso.Item.approved.type_,
            xso.Bool
        )
        self.assertEqual(
            False,
            roster_xso.Item.approved.default
        )

    def test_ask_attr(self):
        self.assertIsInstance(
            roster_xso.Item.ask,
            xso.Attr
        )
        self.assertEqual(
            (None, "ask"),
            roster_xso.Item.ask.tag
        )
        self.assertIsInstance(
            roster_xso.Item.ask.validator,
            xso.RestrictToSet
        )
        self.assertEqual(
            xso.ValidateMode.ALWAYS,
            roster_xso.Item.ask.validate
        )
        self.assertSetEqual(
            {
                None,
                "subscribe",
            },
            roster_xso.Item.ask.validator.values
        )
        self.assertEqual(
            None,
            roster_xso.Item.ask.default
        )

    def test_jid_attr(self):
        self.assertIsInstance(
            roster_xso.Item.jid,
            xso.Attr
        )
        self.assertEqual(
            (None, "jid"),
            roster_xso.Item.jid.tag
        )
        self.assertIsInstance(
            roster_xso.Item.jid.type_,
            xso.JID
        )

    def test_name_attr(self):
        self.assertIsInstance(
            roster_xso.Item.name,
            xso.Attr
        )
        self.assertEqual(
            (None, "name"),
            roster_xso.Item.name.tag
        )

    def test_subscription_attr(self):
        self.assertIsInstance(
            roster_xso.Item.subscription,
            xso.Attr
        )
        self.assertEqual(
            (None, "subscription"),
            roster_xso.Item.subscription.tag
        )
        self.assertIsInstance(
            roster_xso.Item.subscription.validator,
            xso.RestrictToSet
        )
        self.assertEqual(
            xso.ValidateMode.ALWAYS,
            roster_xso.Item.subscription.validate
        )
        self.assertSetEqual(
            {
                "none",
                "to",
                "from",
                "both",
                "remove",
            },
            roster_xso.Item.subscription.validator.values
        )

    def test_groups_attr(self):
        self.assertIsInstance(
            roster_xso.Item.groups,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                roster_xso.Group
            },
            set(roster_xso.Item.groups._classes)
        )

    def test_init(self):
        jid = structs.JID.fromstr("foo@bar.example")
        item = roster_xso.Item(jid)
        self.assertEqual(item.jid, jid)
        self.assertIsNone(item.name)
        self.assertSequenceEqual([], item.groups)
        self.assertEqual("none", item.subscription)
        self.assertIs(False, item.approved)
        self.assertIsNone(item.ask)

        group = roster_xso.Group()
        item = roster_xso.Item(
            jid=jid,
            name="foobar",
            groups=(group,),
            subscription="to",
            approved=True,
            ask="subscribe"
        )

        self.assertEqual(jid, item.jid)
        self.assertEqual("foobar", item.name)
        self.assertSequenceEqual([group], item.groups)
        self.assertIsInstance(item.groups, xso_model.XSOList)
        self.assertEqual("to", item.subscription)
        self.assertIs(True, item.approved)
        self.assertEqual("subscribe", item.ask)


class TestQuery(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.rfc6121_roster, "query"),
            roster_xso.Query.TAG
        )

    def test_declare_ns(self):
        self.assertDictEqual(
            roster_xso.Query.DECLARE_NS,
            {
                None: namespaces.rfc6121_roster
            }
        )

    def test_ver_attr(self):
        self.assertIsInstance(
            roster_xso.Query.ver,
            xso.Attr
        )
        self.assertEqual(
            (None, "ver"),
            roster_xso.Query.ver.tag
        )
        self.assertIs(
            roster_xso.Query.ver.default,
            None
        )

    def test_items_attr(self):
        self.assertIsInstance(
            roster_xso.Query.items,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                roster_xso.Item
            },
            set(roster_xso.Query.items._classes)
        )

    def test_init(self):
        q = roster_xso.Query()
        self.assertIsNone(q.ver)
        self.assertSequenceEqual([], q.items)

        item = roster_xso.Item(TEST_JID)
        q = roster_xso.Query(
            ver="foobar",
            items=(item,)
        )
        self.assertEqual("foobar", q.ver)
        self.assertSequenceEqual([item], q.items)
        self.assertIsInstance(q.items, xso_model.XSOList)

    def test_is_registered_as_iq_payload(self):
        self.assertIn(
            roster_xso.Query.TAG,
            stanza.IQ.CHILD_MAP
        )


class TestRosterVersioningFeature(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            roster_xso.RosterVersioningFeature,
            xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.rfc6121_roster_versioning, "ver"),
            roster_xso.RosterVersioningFeature.TAG
        )

    def test_is_registered_as_feature(self):
        self.assertIn(
            roster_xso.RosterVersioningFeature.TAG,
            stream_xsos.StreamFeatures.CHILD_MAP
        )
