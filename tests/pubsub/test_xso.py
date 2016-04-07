import unittest

import aioxmpp.forms as forms
import aioxmpp.pubsub.xso as pubsub_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_features(self):
        self.assertIs(
            namespaces.xep0060_features,
            pubsub_xso.Features
        )

    def test_core(self):
        self.assertEqual(
            namespaces.xep0060,
            "http://jabber.org/protocol/pubsub"
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

    def test_items(self):
        self.assertIsInstance(
            pubsub_xso.Publish.items,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.Publish.items._classes,
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

    def test_items(self):
        self.assertIsInstance(
            pubsub_xso.Retract.items,
            xso.ChildList,
        )
        self.assertSetEqual(
            pubsub_xso.Retract.items._classes,
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
                "unsubscribed"
            }
        )
        self.assertIs(
            pubsub_xso.Subscription.subscription.default,
            None
        )


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
                pubsub_xso.Subscribe,
                pubsub_xso.Subscription,
                pubsub_xso.Subscriptions,
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



# foo
