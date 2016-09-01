import contextlib
import unittest
import unittest.mock

import aioxmpp.forms as forms
import aioxmpp.pubsub.xso as pubsub_xso
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


TEST_JID = structs.JID.fromstr("foo@bar.example/baz")


class TestNamespaces(unittest.TestCase):
    def test_features(self):
        self.assertIs(
            namespaces.xep0060_features,
            pubsub_xso.Feature
        )

    def test_core(self):
        self.assertEqual(
            namespaces.xep0060,
            "http://jabber.org/protocol/pubsub"
        )

    def test_errors(self):
        self.assertEqual(
            namespaces.xep0060_errors,
            "http://jabber.org/protocol/pubsub#errors"
        )

    def test_event(self):
        self.assertEqual(
            namespaces.xep0060_event,
            "http://jabber.org/protocol/pubsub#event"
        )

    def test_owner(self):
        self.assertEqual(
            namespaces.xep0060_owner,
            "http://jabber.org/protocol/pubsub#owner"
        )


class TestAffiliation(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Affiliation,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Affiliation.TAG,
            (namespaces.xep0060, "affiliation")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Affiliation.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Affiliation.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Affiliation.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Affiliation.node.default,
            None
        )

    def test_affiliation(self):
        self.assertIsInstance(
            pubsub_xso.Affiliation.affiliation,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Affiliation.affiliation.tag,
            (None, "affiliation")
        )
        self.assertIsInstance(
            pubsub_xso.Affiliation.affiliation.type_,
            xso.String
        )
        self.assertIsInstance(
            pubsub_xso.Affiliation.affiliation.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.Affiliation.affiliation.validator.values,
            {
                "member",
                "none",
                "outcast",
                "owner",
                "publisher",
                "publish-only",
            }
        )
        self.assertIs(
            pubsub_xso.Affiliation.affiliation.default,
            xso.NO_DEFAULT,
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            a = pubsub_xso.Affiliation()

        a = pubsub_xso.Affiliation("owner")
        self.assertEqual(a.node, None)
        self.assertEqual(a.affiliation, "owner")

        a = pubsub_xso.Affiliation("outcast", node="foo")
        self.assertEqual(a.node, "foo")
        self.assertEqual(a.affiliation, "outcast")


class TestAffiliations(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Affiliations,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Affiliations.TAG,
            (namespaces.xep0060, "affiliations")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Affiliations.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Affiliations.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Affiliations.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Affiliations.node.default,
            None
        )

    def test_affiliations(self):
        self.assertIsInstance(
            pubsub_xso.Affiliations.affiliations,
            xso.ChildList
        )
        self.assertSetEqual(
            pubsub_xso.Affiliations.affiliations._classes,
            {
                pubsub_xso.Affiliation
            }
        )

    def test_init(self):
        as_ = pubsub_xso.Affiliations()
        self.assertIsNone(as_.node)
        self.assertSequenceEqual(as_.affiliations, [])

        a1 = pubsub_xso.Affiliation("owner")
        a2 = pubsub_xso.Affiliation("member")
        as_ = pubsub_xso.Affiliations([a1, a2], node="foo")
        self.assertEqual(as_.node, "foo")
        self.assertSequenceEqual(
            as_.affiliations,
            [
                a1, a2
            ]
        )


class TestConfigure(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Configure,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Configure.TAG,
            (namespaces.xep0060, "configure")
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.Configure.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Configure.data._classes,
            {
                forms.Data,
            }
        )


class TestCreate(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Create,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Create.TAG,
            (namespaces.xep0060, "create")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Create.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Create.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Create.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Create.node.default,
            None
        )


class TestDefault(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Default,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Default.TAG,
            (namespaces.xep0060, "default")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Default.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Default.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Default.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Default.node.default,
            None
        )

    def test_type_(self):
        self.assertIsInstance(
            pubsub_xso.Default.type_,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Default.type_.tag,
            (None, "type")
        )
        self.assertIsInstance(
            pubsub_xso.Default.type_.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Default.type_.default,
            "leaf",
        )
        self.assertIsInstance(
            pubsub_xso.Default.type_.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.Default.type_.validator.values,
            {
                "leaf",
                "collection",
            }
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.Default.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Default.data._classes,
            {
                forms.Data,
            }
        )

    def test_init(self):
        d = pubsub_xso.Default()
        self.assertIsNone(d.node)
        self.assertEqual(d.type_, "leaf")
        self.assertIsNone(d.data)

        data = unittest.mock.Mock()
        d = pubsub_xso.Default(node="foo", data=data)
        self.assertEqual(d.node, "foo")
        self.assertIs(d.data, data)


class TestItem(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Item,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Item.TAG,
            (namespaces.xep0060, "item")
        )

    def test_id_(self):
        self.assertIsInstance(
            pubsub_xso.Item.id_,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Item.id_.tag,
            (None, "id")
        )
        self.assertIs(
            pubsub_xso.Item.id_.default,
            None
        )

    def test_registered_payload(self):
        self.assertIsInstance(
            pubsub_xso.Item.registered_payload,
            xso.Child
        )

    def test_unknown_payload(self):
        self.assertIsInstance(
            pubsub_xso.Item.unregistered_payload,
            xso.Collector
        )

    def test_init(self):
        i = pubsub_xso.Item()
        self.assertIsNone(i.id_)
        self.assertFalse(i.registered_payload)
        self.assertFalse(i.unregistered_payload)

        i = pubsub_xso.Item("foo")
        self.assertEqual(i.id_, "foo")


class TestItems(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Items,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Items.TAG,
            (namespaces.xep0060, "items")
        )

    def test_max_items(self):
        self.assertIsInstance(
            pubsub_xso.Items.max_items,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Items.max_items.tag,
            (None, "max_items"),
        )
        self.assertIsInstance(
            pubsub_xso.Items.max_items.type_,
            xso.Integer
        )
        self.assertIsInstance(
            pubsub_xso.Items.max_items.validator,
            xso.NumericRange
        )
        self.assertEqual(
            pubsub_xso.Items.max_items.validator.min_,
            1
        )
        self.assertIs(
            pubsub_xso.Items.max_items.validator.max_,
            None
        )
        self.assertIs(
            pubsub_xso.Items.max_items.default,
            None
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Items.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Items.node.tag,
            (None, "node")
        )
        self.assertIs(
            pubsub_xso.Items.node.default,
            xso.NO_DEFAULT,
        )

    def test_subid(self):
        self.assertIsInstance(
            pubsub_xso.Items.subid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Items.subid.tag,
            (None, "subid")
        )
        self.assertIsInstance(
            pubsub_xso.Items.subid.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Items.subid.default,
            None
        )

    def test_items(self):
        self.assertIsInstance(
            pubsub_xso.Items.items,
            xso.ChildList
        )
        self.assertSetEqual(
            pubsub_xso.Items.items._classes,
            {
                pubsub_xso.Item
            }
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            i = pubsub_xso.Items()

        i = pubsub_xso.Items("foo")
        self.assertEqual(i.node, "foo")
        self.assertIsNone(i.max_items)
        self.assertIsNone(i.subid)

        i = pubsub_xso.Items("foo", max_items=10, subid="bar")
        self.assertEqual(i.node, "foo")
        self.assertEqual(i.max_items, 10)
        self.assertEqual(i.subid, "bar")


class TestOptions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Options,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Options.TAG,
            (namespaces.xep0060, "options")
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.Options.jid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Options.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            pubsub_xso.Options.jid.type_,
            xso.JID
        )
        self.assertIs(
            pubsub_xso.Options.jid.default,
            xso.NO_DEFAULT
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Options.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Options.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Options.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Options.node.default,
            None
        )

    def test_subid(self):
        self.assertIsInstance(
            pubsub_xso.Options.subid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Options.subid.tag,
            (None, "subid")
        )
        self.assertIsInstance(
            pubsub_xso.Options.subid.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Options.subid.default,
            None
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.Options.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Options.data._classes,
            {
                forms.Data,
            }
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            o = pubsub_xso.Options()

        o = pubsub_xso.Options(TEST_JID)
        self.assertEqual(o.jid, TEST_JID)
        self.assertIsNone(o.node)
        self.assertIsNone(o.subid)
        self.assertIsNone(o.data)

        o = pubsub_xso.Options(TEST_JID, node="foo", subid="bar")
        self.assertEqual(o.jid, TEST_JID)
        self.assertEqual(o.node, "foo")
        self.assertEqual(o.subid, "bar")
        self.assertIsNone(o.data)


class TestPublish(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Publish,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Publish.TAG,
            (namespaces.xep0060, "publish")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Publish.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Publish.node.tag,
            (None, "node")
        )
        self.assertIs(
            pubsub_xso.Publish.node.default,
            xso.NO_DEFAULT,
        )

    def test_item(self):
        self.assertIsInstance(
            pubsub_xso.Publish.item,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Publish.item._classes,
            {
                pubsub_xso.Item,
            }
        )


class TestRetract(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Retract,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Retract.TAG,
            (namespaces.xep0060, "retract")
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Retract.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Retract.node.tag,
            (None, "node")
        )
        self.assertIs(
            pubsub_xso.Retract.node.default,
            xso.NO_DEFAULT,
        )

    def test_item(self):
        self.assertIsInstance(
            pubsub_xso.Retract.item,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Retract.item._classes,
            {
                pubsub_xso.Item,
            }
        )

    def test_notify(self):
        self.assertIsInstance(
            pubsub_xso.Retract.notify,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Retract.notify.tag,
            (None, "notify")
        )
        self.assertIsInstance(
            pubsub_xso.Retract.notify.type_,
            xso.Bool
        )
        self.assertIs(
            pubsub_xso.Retract.notify.default,
            False
        )


class TestSubscribe(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Subscribe,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Subscribe.TAG,
            (namespaces.xep0060, "subscribe")
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.Subscribe.jid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscribe.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            pubsub_xso.Subscribe.jid.type_,
            xso.JID
        )
        self.assertIs(
            pubsub_xso.Subscribe.jid.default,
            xso.NO_DEFAULT
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Subscribe.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscribe.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Subscribe.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Subscribe.node.default,
            None
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            s = pubsub_xso.Subscribe()

        s = pubsub_xso.Subscribe(TEST_JID)
        self.assertEqual(s.jid, TEST_JID)
        self.assertEqual(s.node, None)

        s = pubsub_xso.Subscribe(
            TEST_JID.replace(localpart="fnord"),
            node="foo")
        self.assertEqual(s.jid, TEST_JID.replace(localpart="fnord"))
        self.assertEqual(s.node, "foo")


class TestSubscribeOptions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.SubscribeOptions,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.SubscribeOptions.TAG,
            (namespaces.xep0060, "subscribe-options")
        )

    def test_required(self):
        self.assertIsInstance(
            pubsub_xso.SubscribeOptions.required,
            xso.ChildTag
        )
        self.assertSetEqual(
            set(pubsub_xso.SubscribeOptions.required.get_tag_map()),
            {
                (namespaces.xep0060, "required"),
                None,
            }
        )
        self.assertIs(
            pubsub_xso.SubscribeOptions.required.allow_none,
            True
        )


class TestSubscription(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Subscription,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Subscription.TAG,
            (namespaces.xep0060, "subscription")
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.Subscription.jid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscription.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            pubsub_xso.Subscription.jid.type_,
            xso.JID
        )
        self.assertIs(
            pubsub_xso.Subscription.jid.default,
            xso.NO_DEFAULT
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Subscription.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscription.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Subscription.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Subscription.node.default,
            None
        )

    def test_subid(self):
        self.assertIsInstance(
            pubsub_xso.Subscription.subid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscription.subid.tag,
            (None, "subid")
        )
        self.assertIsInstance(
            pubsub_xso.Subscription.subid.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Subscription.subid.default,
            None
        )

    def test_subscription(self):
        self.assertIsInstance(
            pubsub_xso.Subscription.subscription,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscription.subscription.tag,
            (None, "subscription")
        )
        self.assertIsInstance(
            pubsub_xso.Subscription.subscription.type_,
            xso.String
        )
        self.assertIsInstance(
            pubsub_xso.Subscription.subscription.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.Subscription.subscription.validator.values,
            {
                "none",
                "pending",
                "subscribed",
                "unconfigured"
            }
        )
        self.assertIs(
            pubsub_xso.Subscription.subscription.default,
            None
        )

    def test_subscribe_options(self):
        self.assertIsInstance(
            pubsub_xso.Subscription.subscribe_options,
            xso.Child
        )
        self.assertSetEqual(
            pubsub_xso.Subscription.subscribe_options._classes,
            {
                pubsub_xso.SubscribeOptions
            }
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            s = pubsub_xso.Subscription()

        s = pubsub_xso.Subscription(TEST_JID)
        self.assertEqual(s.jid, TEST_JID)
        self.assertIsNone(s.node)
        self.assertIsNone(s.subid)
        self.assertIsNone(s.subscription)

        s = pubsub_xso.Subscription(
            TEST_JID.replace(localpart="fnord"),
            node="foo",
            subid="bar",
            subscription="subscribed")
        self.assertEqual(s.jid, TEST_JID.replace(localpart="fnord"))
        self.assertEqual(s.node, "foo")
        self.assertEqual(s.subid, "bar")
        self.assertEqual(s.subscription, "subscribed")


class TestSubscriptions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Subscriptions,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Subscriptions.TAG,
            (namespaces.xep0060, "subscriptions"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Subscriptions.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Subscriptions.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Subscriptions.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Subscriptions.node.default,
            None
        )

    def test_subscriptions(self):
        self.assertIsInstance(
            pubsub_xso.Subscriptions.subscriptions,
            xso.ChildList
        )
        self.assertSetEqual(
            pubsub_xso.Subscriptions.subscriptions._classes,
            {
                pubsub_xso.Subscription
            }
        )

    def test_init_default(self):
        subs = pubsub_xso.Subscriptions()
        self.assertIsNone(subs.node)
        self.assertSequenceEqual(subs.subscriptions, [])

    def test_init(self):
        subs = pubsub_xso.Subscriptions(
            node="foobar",
            subscriptions=[
                unittest.mock.sentinel.s1,
                unittest.mock.sentinel.s2,
            ]
        )
        self.assertEqual(subs.node, "foobar")

        self.assertSequenceEqual(
            subs.subscriptions,
            [
                unittest.mock.sentinel.s1,
                unittest.mock.sentinel.s2,
            ]
        )


class TestUnsubscribe(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Unsubscribe,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Unsubscribe.TAG,
            (namespaces.xep0060, "unsubscribe")
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.jid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Unsubscribe.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.jid.type_,
            xso.JID
        )
        self.assertIs(
            pubsub_xso.Unsubscribe.jid.default,
            xso.NO_DEFAULT
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Unsubscribe.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Unsubscribe.node.default,
            None
        )

    def test_subid(self):
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.subid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Unsubscribe.subid.tag,
            (None, "subid")
        )
        self.assertIsInstance(
            pubsub_xso.Unsubscribe.subid.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.Unsubscribe.subid.default,
            None
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            u = pubsub_xso.Unsubscribe()

        u = pubsub_xso.Unsubscribe(TEST_JID)
        self.assertEqual(u.jid, TEST_JID)
        self.assertIsNone(u.node)
        self.assertIsNone(u.subid)

        u = pubsub_xso.Unsubscribe(
            TEST_JID.replace(localpart="fnord"),
            node="foo",
            subid="bar",
        )
        self.assertEqual(u.jid, TEST_JID.replace(localpart="fnord"))
        self.assertEqual(u.node, "foo")
        self.assertEqual(u.subid, "bar")


class TestRequest(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Request,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Request.TAG,
            (namespaces.xep0060, "pubsub")
        )

    def test_payload(self):
        self.assertIsInstance(
            pubsub_xso.Request.payload,
            xso.Child
        )
        self.assertSetEqual(
            pubsub_xso.Request.payload._classes,
            {
                pubsub_xso.Affiliations,
                pubsub_xso.Create,
                pubsub_xso.Default,
                pubsub_xso.Items,
                pubsub_xso.Publish,
                pubsub_xso.Retract,
                pubsub_xso.Subscribe,
                pubsub_xso.Subscription,
                pubsub_xso.Subscriptions,
                pubsub_xso.Unsubscribe,
            }
        )

    def test_options(self):
        self.assertIsInstance(
            pubsub_xso.Request.options,
            xso.Child
        )
        self.assertSetEqual(
            pubsub_xso.Request.options._classes,
            {
                pubsub_xso.Options
            }
        )

    def test_configure(self):
        self.assertIsInstance(
            pubsub_xso.Request.configure,
            xso.Child
        )
        self.assertSetEqual(
            pubsub_xso.Request.configure._classes,
            {
                pubsub_xso.Configure
            }
        )

    def test_is_registered_iq_payload(self):
        self.assertIn(
            pubsub_xso.Request,
            stanza.IQ.payload._classes
        )

    def test_Message_attribute(self):
        self.assertIsInstance(
            stanza.Message.xep0060_request,
            xso.Child,
        )
        self.assertSetEqual(
            stanza.Message.xep0060_request._classes,
            {
                pubsub_xso.Request,
            }
        )

    def test_init(self):
        r = pubsub_xso.Request()
        self.assertIsNone(r.payload)

        m = unittest.mock.Mock()
        r = pubsub_xso.Request(m)
        self.assertIs(r.payload, m)


class TestEventAssociate(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventAssociate,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventAssociate.TAG,
            (namespaces.xep0060_event, "associate"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventAssociate.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventAssociate.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventAssociate.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventAssociate.node.default,
            xso.NO_DEFAULT,
        )


class TestEventDisassociate(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventDisassociate,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventDisassociate.TAG,
            (namespaces.xep0060_event, "disassociate"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventDisassociate.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventDisassociate.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventDisassociate.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventDisassociate.node.default,
            xso.NO_DEFAULT,
        )


class TestEventCollection(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventCollection,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventCollection.TAG,
            (namespaces.xep0060_event, "collection"),
        )

    def test_assoc(self):
        self.assertIsInstance(
            pubsub_xso.EventCollection.assoc,
            xso.Child,
        )
        self.assertSetEqual(
            set(pubsub_xso.EventCollection.assoc._classes),
            {
                pubsub_xso.EventAssociate,
                pubsub_xso.EventDisassociate,
            }
        )


class TestEventRedirect(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventRedirect,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventRedirect.TAG,
            (namespaces.xep0060_event, "redirect")
        )

    def test_uri(self):
        self.assertIsInstance(
            pubsub_xso.EventRedirect.uri,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.EventRedirect.uri.tag,
            (None, "uri"),
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.EventRedirect()

    def test_init(self):
        r = pubsub_xso.EventRedirect("foobar")
        self.assertEqual(r.uri, "foobar")


class TestEventDelete(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventDelete,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventDelete.TAG,
            (namespaces.xep0060_event, "delete"),
        )

    def test__redirect(self):
        self.assertIsInstance(
            pubsub_xso.EventDelete._redirect,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.EventDelete._redirect._classes,
            {
                pubsub_xso.EventRedirect,
            }
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventDelete.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventDelete.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventDelete.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventDelete.node.default,
            xso.NO_DEFAULT,
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.EventDelete()

    def test_init(self):
        d = pubsub_xso.EventDelete("node")
        self.assertEqual(d.node, "node")
        self.assertIsNone(d._redirect)

        d = pubsub_xso.EventDelete("bar", redirect_uri="some-uri")
        self.assertEqual(d.node, "bar")
        self.assertIsInstance(d._redirect, pubsub_xso.EventRedirect)
        self.assertEqual(d._redirect.uri, "some-uri")

    def test_redirect_uri_gets_uri_of__redirect(self):
        d = pubsub_xso.EventDelete("foo")
        d._redirect = unittest.mock.Mock()

        self.assertEqual(
            d.redirect_uri,
            d._redirect.uri,
        )

    def test_redirect_uri_returns_none_if_no__redirect_set(self):
        d = pubsub_xso.EventDelete("foo")
        self.assertIsNone(d.redirect_uri)

    def test_setting_redirect_uri_sets__redirect(self):
        d = pubsub_xso.EventDelete("foo")
        d.redirect_uri = "foobar"
        self.assertIsInstance(d._redirect, pubsub_xso.EventRedirect)
        self.assertEqual(
            d._redirect.uri,
            "foobar"
        )

    def test_setting_redirect_uri_to_None_clears__redirect(self):
        d = pubsub_xso.EventDelete("foo")
        d._redirect = unittest.mock.sentinel.foo
        d.redirect_uri = None
        self.assertIsNone(d._redirect)

    def test_deleting_redirect_uri_clears__redirect(self):
        d = pubsub_xso.EventDelete("foo")
        d._redirect = unittest.mock.sentinel.foo
        del d.redirect_uri
        self.assertIsNone(d._redirect)


class TestEventRetract(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventRetract,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventRetract.TAG,
            (namespaces.xep0060_event, "retract"),
        )

    def test_id_(self):
        self.assertIsInstance(
            pubsub_xso.EventRetract.id_,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventRetract.id_.tag,
            (None, "id")
        )
        self.assertIs(
            pubsub_xso.EventRetract.id_.default,
            xso.NO_DEFAULT
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.EventRetract()

    def test_init(self):
        r = pubsub_xso.EventRetract("some-id")
        self.assertEqual(
            r.id_,
            "some-id",
        )


class TestEventItem(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventItem,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventItem.TAG,
            (namespaces.xep0060_event, "item"),
        )

    def test_id_(self):
        self.assertIsInstance(
            pubsub_xso.EventItem.id_,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventItem.id_.tag,
            (None, "id")
        )
        self.assertIs(
            pubsub_xso.EventItem.id_.default,
            None
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventItem.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventItem.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventItem.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventItem.node.default,
            None,
        )

    def test_publisher(self):
        self.assertIsInstance(
            pubsub_xso.EventItem.publisher,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventItem.publisher.tag,
            (None, "publisher")
        )
        self.assertIsInstance(
            pubsub_xso.EventItem.publisher.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventItem.publisher.default,
            None,
        )

    def test_registered_payload(self):
        self.assertIsInstance(
            pubsub_xso.EventItem.registered_payload,
            xso.Child
        )

    def test_unknown_payload(self):
        self.assertIsInstance(
            pubsub_xso.EventItem.unregistered_payload,
            xso.Collector
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            pubsub_xso.EventItem()

        class Foo(xso.XSO):
            pass

        obj = Foo()

        item = pubsub_xso.EventItem(obj)
        self.assertIs(
            item.registered_payload,
            obj
        )

        item = pubsub_xso.EventItem(obj, id_="foo")
        self.assertIs(
            item.registered_payload,
            obj
        )
        self.assertEqual(item.id_, "foo")


class TestEventItems(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventItems,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventItems.TAG,
            (namespaces.xep0060_event, "items"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventItems.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventItems.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventItems.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventItems.node.default,
            xso.NO_DEFAULT,
        )

    def test_retracts(self):
        self.assertIsInstance(
            pubsub_xso.EventItems.retracts,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.EventItems.retracts._classes,
            {
                pubsub_xso.EventRetract,
            }
        )

    def test_items(self):
        self.assertIsInstance(
            pubsub_xso.EventItems.items,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.EventItems.items._classes,
            {
                pubsub_xso.EventItem,
            }
        )

    def test_init_default(self):
        items = pubsub_xso.EventItems()
        self.assertSequenceEqual(items.items, [])
        self.assertSequenceEqual(items.retracts, [])
        self.assertIsNone(items.node)

    def test_init(self):
        items_list = [
            unittest.mock.sentinel.item1,
            unittest.mock.sentinel.item2,
        ]

        retracts_list = [
            unittest.mock.sentinel.retract1,
            unittest.mock.sentinel.retract2,
        ]

        items = pubsub_xso.EventItems(
            items=items_list,
            retracts=retracts_list,
            node="foo"
        )

        self.assertSequenceEqual(
            items.items,
            items_list,
        )

        self.assertSequenceEqual(
            items.retracts,
            retracts_list,
        )

        self.assertEqual(items.node, "foo")

        self.assertIsNot(items.items, items_list)
        self.assertIsNot(items.retracts, retracts_list)


class TestEventPurge(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventPurge,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventPurge.TAG,
            (namespaces.xep0060_event, "purge"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventPurge.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventPurge.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventPurge.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventPurge.node.default,
            xso.NO_DEFAULT,
        )


class TestEventSubscription(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventSubscription,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventSubscription.TAG,
            (namespaces.xep0060_event, "subscription"),
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.EventSubscription.jid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventSubscription.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.jid.type_,
            xso.JID
        )
        self.assertIs(
            pubsub_xso.EventSubscription.jid.default,
            xso.NO_DEFAULT
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventSubscription.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventSubscription.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventSubscription.node.default,
            None
        )

    def test_subid(self):
        self.assertIsInstance(
            pubsub_xso.EventSubscription.subid,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventSubscription.subid.tag,
            (None, "subid")
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.subid.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventSubscription.subid.default,
            None
        )

    def test_subscription(self):
        self.assertIsInstance(
            pubsub_xso.EventSubscription.subscription,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventSubscription.subscription.tag,
            (None, "subscription")
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.subscription.type_,
            xso.String
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.subscription.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.EventSubscription.subscription.validator.values,
            {
                "none",
                "pending",
                "subscribed",
                "unconfigured"
            }
        )
        self.assertIs(
            pubsub_xso.EventSubscription.subscription.default,
            None
        )

    def test_expiry(self):
        self.assertIsInstance(
            pubsub_xso.EventSubscription.expiry,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.EventSubscription.expiry.tag,
            (None, "expiry"),
        )
        self.assertIsInstance(
            pubsub_xso.EventSubscription.expiry.type_,
            xso.DateTime,
        )


class TestEventConfiguration(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.EventConfiguration,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.EventConfiguration.TAG,
            (namespaces.xep0060_event, "configuration"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.EventConfiguration.node,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.EventConfiguration.node.tag,
            (None, "node")
        )
        self.assertIsInstance(
            pubsub_xso.EventConfiguration.node.type_,
            xso.String
        )
        self.assertIs(
            pubsub_xso.EventConfiguration.node.default,
            None
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.EventConfiguration.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.EventConfiguration.data._classes,
            {
                forms.Data,
            }
        )


class TestEvent(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Event,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.Event.TAG,
            (namespaces.xep0060_event, "event"),
        )

    def test_payload(self):
        self.assertIsInstance(
            pubsub_xso.Event.payload,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.Event.payload._classes,
            {
                pubsub_xso.EventCollection,
                pubsub_xso.EventConfiguration,
                pubsub_xso.EventDelete,
                pubsub_xso.EventItems,
                pubsub_xso.EventPurge,
                pubsub_xso.EventSubscription,
            }
        )

    def test_is_message_payload(self):
        self.assertIsInstance(
            stanza.Message.xep0060_event,
            xso.Child,
        )
        self.assertSetEqual(
            stanza.Message.xep0060_event._classes,
            {
                pubsub_xso.Event,
            }
        )

    def test_init_default(self):
        ev = pubsub_xso.Event()
        self.assertIsNone(ev.payload)

    def test_init(self):
        items = pubsub_xso.EventItems()
        ev = pubsub_xso.Event(items)
        self.assertIs(ev.payload, items)


class TestOwnerAffiliation(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerAffiliation,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerAffiliation.TAG,
            (namespaces.xep0060_owner, "affiliation"),
        )

    def test_affiliation(self):
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliation.affiliation,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerAffiliation.affiliation.tag,
            (None, "affiliation"),
        )
        self.assertIs(
            pubsub_xso.OwnerAffiliation.affiliation.default,
            xso.NO_DEFAULT,
        )
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliation.affiliation.validator,
            xso.RestrictToSet,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerAffiliation.affiliation.validator.values,
            {
                "member",
                "none",
                "outcast",
                "owner",
                "publisher",
                "publish-only",
            }
        )
        self.assertEqual(
            pubsub_xso.OwnerAffiliation.affiliation.validate,
            xso.ValidateMode.ALWAYS,
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliation.jid,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerAffiliation.jid.tag,
            (None, "jid"),
        )
        self.assertIs(
            pubsub_xso.OwnerAffiliation.jid.default,
            xso.NO_DEFAULT,
        )
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliation.jid.type_,
            xso.JID,
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            a = pubsub_xso.OwnerAffiliation()

        a = pubsub_xso.OwnerAffiliation(TEST_JID, "owner")
        self.assertEqual(a.jid, TEST_JID)
        self.assertEqual(a.affiliation, "owner")


class TestOwnerAffiliations(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerAffiliations,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerAffiliations.TAG,
            (namespaces.xep0060_owner, "affiliations"),
        )

    def test_affiliations(self):
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliations.affiliations,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerAffiliations.affiliations._classes,
            {
                pubsub_xso.OwnerAffiliation,
            }
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.OwnerAffiliations.node,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerAffiliations.node.tag,
            (None, "node"),
        )
        self.assertIs(
            pubsub_xso.OwnerAffiliations.node.default,
            xso.NO_DEFAULT,
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerAffiliations()

    def test_init(self):
        as_ = pubsub_xso.OwnerAffiliations("foo")
        self.assertEqual(as_.node, "foo")
        self.assertSequenceEqual(as_.affiliations, [])

        as_ = pubsub_xso.OwnerAffiliations(
            "foo",
            affiliations=[
                unittest.mock.sentinel.a1,
                unittest.mock.sentinel.a2,
            ]
        )
        self.assertEqual(as_.node, "foo")
        self.assertSequenceEqual(
            as_.affiliations,
            [
                unittest.mock.sentinel.a1,
                unittest.mock.sentinel.a2,
            ]
        )


class TestOwnerConfigure(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerConfigure,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerConfigure.TAG,
            (namespaces.xep0060_owner, "configure"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.OwnerConfigure.node,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerConfigure.node.tag,
            (None, "node"),
        )
        self.assertIs(
            pubsub_xso.OwnerConfigure.node.default,
            None,
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.OwnerConfigure.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerConfigure.data._classes,
            {
                forms.Data,
            }
        )


class TestOwnerDefault(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerDefault,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerDefault.TAG,
            (namespaces.xep0060_owner, "default"),
        )

    def test_data(self):
        self.assertIsInstance(
            pubsub_xso.OwnerDefault.data,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerDefault.data._classes,
            {
                forms.Data,
            }
        )


class TestOwnerRedirect(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerRedirect,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerRedirect.TAG,
            (namespaces.xep0060_owner, "redirect"),
        )

    def test_uri(self):
        self.assertIsInstance(
            pubsub_xso.OwnerRedirect.uri,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerRedirect.uri.tag,
            (None, "uri"),
        )
        self.assertIs(
            pubsub_xso.OwnerRedirect.uri.default,
            xso.NO_DEFAULT,
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerRedirect()

    def test_init(self):
        r = pubsub_xso.OwnerRedirect("uri")
        self.assertEqual(r.uri, "uri")


class TestOwnerDelete(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerDelete,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerDelete.TAG,
            (namespaces.xep0060_owner, "delete"),
        )

    def test__redirect(self):
        self.assertIsInstance(
            pubsub_xso.OwnerDelete._redirect,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerDelete._redirect._classes,
            {
                pubsub_xso.OwnerRedirect,
            }
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.OwnerDelete.node,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerDelete.node.tag,
            (None, "node"),
        )
        self.assertIs(
            pubsub_xso.OwnerDelete.node.default,
            xso.NO_DEFAULT,
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerDelete()

    def test_init(self):
        d = pubsub_xso.OwnerDelete("node")
        self.assertEqual(d.node, "node")
        self.assertIsNone(d._redirect)

        d = pubsub_xso.OwnerDelete(
            "other-node",
            redirect_uri="foo",
        )
        self.assertEqual(d.node, "other-node")
        self.assertIsInstance(d._redirect, pubsub_xso.OwnerRedirect)
        self.assertEqual(
            d._redirect.uri,
            "foo"
        )

    def test_redirect_uri_gets_uri_of__redirect(self):
        d = pubsub_xso.OwnerDelete("foo")
        d._redirect = unittest.mock.Mock()

        self.assertEqual(
            d.redirect_uri,
            d._redirect.uri,
        )

    def test_redirect_uri_returns_none_if_no__redirect_set(self):
        d = pubsub_xso.OwnerDelete("foo")
        self.assertIsNone(d.redirect_uri)

    def test_setting_redirect_uri_sets__redirect(self):
        d = pubsub_xso.OwnerDelete("foo")
        d.redirect_uri = "foobar"
        self.assertIsInstance(d._redirect, pubsub_xso.OwnerRedirect)
        self.assertEqual(
            d._redirect.uri,
            "foobar"
        )

    def test_setting_redirect_uri_to_None_clears__redirect(self):
        d = pubsub_xso.OwnerDelete("foo")
        d._redirect = unittest.mock.sentinel.foo
        d.redirect_uri = None
        self.assertIsNone(d._redirect)

    def test_deleting_redirect_uri_clears__redirect(self):
        d = pubsub_xso.OwnerDelete("foo")
        d._redirect = unittest.mock.sentinel.foo
        del d.redirect_uri
        self.assertIsNone(d._redirect)


class TestOwnerPurge(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerPurge,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerPurge.TAG,
            (namespaces.xep0060_owner, "purge"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.OwnerPurge.node,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerPurge.node.tag,
            (None, "node"),
        )
        self.assertIs(
            pubsub_xso.OwnerPurge.node.default,
            xso.NO_DEFAULT,
        )


class TestOwnerSubscription(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerSubscription,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerSubscription.TAG,
            (namespaces.xep0060_owner, "subscription"),
        )

    def test_subscription(self):
        self.assertIsInstance(
            pubsub_xso.OwnerSubscription.subscription,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerSubscription.subscription.tag,
            (None, "subscription"),
        )
        self.assertIs(
            pubsub_xso.OwnerSubscription.subscription.default,
            xso.NO_DEFAULT,
        )
        self.assertIsInstance(
            pubsub_xso.OwnerSubscription.subscription.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.OwnerSubscription.subscription.validator.values,
            {
                "none",
                "pending",
                "subscribed",
                "unconfigured",
            }
        )
        self.assertEqual(
            pubsub_xso.OwnerSubscription.subscription.validate,
            xso.ValidateMode.ALWAYS,
        )

    def test_jid(self):
        self.assertIsInstance(
            pubsub_xso.OwnerSubscription.jid,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerSubscription.jid.tag,
            (None, "jid"),
        )
        self.assertIs(
            pubsub_xso.OwnerSubscription.jid.default,
            xso.NO_DEFAULT,
        )
        self.assertIsInstance(
            pubsub_xso.OwnerSubscription.jid.type_,
            xso.JID
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerSubscription()

    def test_init(self):
        s = pubsub_xso.OwnerSubscription(
            TEST_JID,
            "subscribed"
        )

        self.assertEqual(s.jid, TEST_JID)
        self.assertEqual(s.subscription, "subscribed")


class TestOwnerSubscriptions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerSubscriptions,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerSubscriptions.TAG,
            (namespaces.xep0060_owner, "subscriptions"),
        )

    def test_node(self):
        self.assertIsInstance(
            pubsub_xso.OwnerSubscriptions.node,
            xso.Attr,
        )
        self.assertEqual(
            pubsub_xso.OwnerSubscriptions.node.tag,
            (None, "node"),
        )
        self.assertIs(
            pubsub_xso.OwnerSubscriptions.node.default,
            xso.NO_DEFAULT,
        )

    def test_subscriptions(self):
        self.assertIsInstance(
            pubsub_xso.OwnerSubscriptions.subscriptions,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerSubscriptions.subscriptions._classes,
            {
                pubsub_xso.OwnerSubscription,
            }
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerSubscriptions()

    def test_init(self):
        ss = pubsub_xso.OwnerSubscriptions("node")
        self.assertEqual(ss.node, "node")
        self.assertSequenceEqual(ss.subscriptions, [])

        ss = pubsub_xso.OwnerSubscriptions(
            "node",
            subscriptions=[
                unittest.mock.sentinel.s1,
                unittest.mock.sentinel.s2,
            ]
        )
        self.assertEqual(ss.node, "node")
        self.assertSequenceEqual(
            ss.subscriptions,
            [
                unittest.mock.sentinel.s1,
                unittest.mock.sentinel.s2,
            ]
        )


class TestOwnerRequest(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.OwnerRequest,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pubsub_xso.OwnerRequest.TAG,
            (namespaces.xep0060_owner, "pubsub"),
        )

    def test_payload(self):
        self.assertIsInstance(
            pubsub_xso.OwnerRequest.payload,
            xso.Child,
        )
        self.assertSetEqual(
            pubsub_xso.OwnerRequest.payload._classes,
            {
                pubsub_xso.OwnerAffiliations,
                pubsub_xso.OwnerConfigure,
                pubsub_xso.OwnerDefault,
                pubsub_xso.OwnerDelete,
                pubsub_xso.OwnerPurge,
                pubsub_xso.OwnerSubscriptions,
            }
        )

    def test_is_registered_iq_payload(self):
        self.assertIn(
            pubsub_xso.OwnerRequest,
            stanza.IQ.payload._classes
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            pubsub_xso.OwnerRequest()

    def test_init(self):
        r = pubsub_xso.OwnerRequest(unittest.mock.sentinel.payload)
        self.assertEqual(
            r.payload,
            unittest.mock.sentinel.payload
        )


class Testas_payload_class(unittest.TestCase):
    def test_registers_at_EventItem_and_Item(self):
        with contextlib.ExitStack() as stack:
            at_Item = stack.enter_context(
                unittest.mock.patch.object(
                    pubsub_xso.Item,
                    "register_child"
                )
            )

            at_EventItem = stack.enter_context(
                unittest.mock.patch.object(
                    pubsub_xso.EventItem,
                    "register_child"
                )
            )

            result = pubsub_xso.as_payload_class(
                unittest.mock.sentinel.cls
            )

        self.assertIs(result, unittest.mock.sentinel.cls)

        at_Item.assert_called_with(
            pubsub_xso.Item.registered_payload,
            unittest.mock.sentinel.cls,
        )

        at_EventItem.assert_called_with(
            pubsub_xso.EventItem.registered_payload,
            unittest.mock.sentinel.cls,
        )


class TestSimpleErrors(unittest.TestCase):
    ERROR_CLASSES = [
        ("ClosedNode", "closed-node"),
        ("ConfigurationRequired", "configuration-required"),
        ("InvalidJID", "invalid-jid"),
        ("InvalidOptions", "invalid-options"),
        ("InvalidPayload", "invalid-payload"),
        ("InvalidSubID", "invalid-subid"),
        ("ItemForbidden", "item-forbidden"),
        ("ItemRequired", "item-required"),
        ("JIDRequired", "jid-required"),
        ("MaxItemsExceeded", "max-items-exceeded"),
        ("MaxNodesExceeded", "max-nodes-exceeded"),
        ("NodeIDRequired", "nodeid-required"),
        ("NotInRosterGroup", "not-in-roster-group"),
        ("NotSubscribed", "not-subscribed"),
        ("PayloadTooBig", "payload-too-big"),
        ("PayloadRequired", "payload-required"),
        ("PendingSubscription", "pending-subscription"),
        ("PresenceSubscriptionRequired",
         "presence-subscription-required"),
        ("SubIDRequired", "subid-required"),
        ("TooManySubscriptions", "too-many-subscriptions"),
    ]

    def _run_tests(self, func):
        for clsname, *args in self.ERROR_CLASSES:
            cls = getattr(pubsub_xso, clsname)
            func(cls, args)

    def _test_is_xso(self, cls, args):
        self.assertTrue(issubclass(
            cls,
            xso.XSO
        ))

    def test_is_xso(self):
        self._run_tests(self._test_is_xso)

    def _test_tag(self, cls, args):
        self.assertEqual(
            (namespaces.xep0060_errors, args[0]),
            cls.TAG
        )

    def test_tag(self):
        self._run_tests(self._test_tag)

    def _test_is_application_error(self, cls, args):
        self.assertIn(
            cls,
            stanza.Error.application_condition._classes
        )

    def test_is_application_error(self):
        self._run_tests(self._test_is_application_error)


class TestUnsupported(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pubsub_xso.Unsupported,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0060_errors, "unsupported"),
            pubsub_xso.Unsupported.TAG
        )

    def test_feature(self):
        self.assertIsInstance(
            pubsub_xso.Unsupported.feature,
            xso.Attr
        )
        self.assertEqual(
            pubsub_xso.Unsupported.feature.tag,
            (None, "feature")
        )
        self.assertIsInstance(
            pubsub_xso.Unsupported.feature.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            pubsub_xso.Unsupported.feature.validator.values,
            {
                "access-authorize",
                "access-open",
                "access-presence",
                "access-roster",
                "access-whitelist",
                "auto-create",
                "auto-subscribe",
                "collections",
                "config-node",
                "create-and-configure",
                "create-nodes",
                "delete-items",
                "delete-nodes",
                "filtered-notifications",
                "get-pending",
                "instant-nodes",
                "item-ids",
                "last-published",
                "leased-subscription",
                "manage-subscriptions",
                "member-affiliation",
                "meta-data",
                "modify-affiliations",
                "multi-collection",
                "multi-subscribe",
                "outcast-affiliation",
                "persistent-items",
                "presence-notifications",
                "presence-subscribe",
                "publish",
                "publish-options",
                "publish-only-affiliation",
                "publisher-affiliation",
                "purge-nodes",
                "retract-items",
                "retrieve-affiliations",
                "retrieve-default",
                "retrieve-items",
                "retrieve-subscriptions",
                "subscribe",
                "subscription-options",
                "subscription-notifications",
            }
        )
        self.assertIs(
            pubsub_xso.Unsupported.feature.default,
            xso.NO_DEFAULT
        )

    def test_is_application_error(self):
        self.assertIn(
            pubsub_xso.Unsupported,
            stanza.Error.application_condition._classes
        )


# foo
