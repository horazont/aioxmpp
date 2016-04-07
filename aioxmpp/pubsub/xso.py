import aioxmpp.forms
import aioxmpp.xso as xso

from enum import Enum

from aioxmpp.utils import namespaces


class Features(Enum):
    ACCESS_AUTHORIZE = "http://jabber.org/protocol/pubsub#access-authorize"
    ACCESS_OPEN = "http://jabber.org/protocol/pubsub#access-open"
    ACCESS_PRESENCE = "http://jabber.org/protocol/pubsub#access-presence"
    ACCESS_ROSTER = "http://jabber.org/protocol/pubsub#access-roster"
    ACCESS_WHITELIST = "http://jabber.org/protocol/pubsub#access-whitelist"
    AUTO_CREATE = "http://jabber.org/protocol/pubsub#auto-create"
    AUTO_SUBSCRIBE = "http://jabber.org/protocol/pubsub#auto-subscribe"
    COLLECTIONS = "http://jabber.org/protocol/pubsub#collections"
    CONFIG_NODE = "http://jabber.org/protocol/pubsub#config-node"
    CREATE_AND_CONFIGURE = \
        "http://jabber.org/protocol/pubsub#create-and-configure"
    CREATE_NODES = "http://jabber.org/protocol/pubsub#create-nodes"
    DELETE_ITEMS = "http://jabber.org/protocol/pubsub#delete-items"
    DELETE_NODES = "http://jabber.org/protocol/pubsub#delete-nodes"
    FILTERED_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#filtered-notifications"
    GET_PENDING = "http://jabber.org/protocol/pubsub#get-pending"
    INSTANT_NODES = "http://jabber.org/protocol/pubsub#instant-nodes"
    ITEM_IDS = "http://jabber.org/protocol/pubsub#item-ids"
    LAST_PUBLISHED = "http://jabber.org/protocol/pubsub#last-published"
    LEASED_SUBSCRIPTION = \
        "http://jabber.org/protocol/pubsub#leased-subscription"
    MANAGE_SUBSCRIPTIONS = \
        "http://jabber.org/protocol/pubsub#manage-subscriptions"
    MEMBER_AFFILIATION = "http://jabber.org/protocol/pubsub#member-affiliation"
    META_DATA = "http://jabber.org/protocol/pubsub#meta-data"
    MODIFY_AFFILIATIONS = \
        "http://jabber.org/protocol/pubsub#modify-affiliations"
    MULTI_COLLECTION = "http://jabber.org/protocol/pubsub#multi-collection"
    MULTI_SUBSCRIBE = "http://jabber.org/protocol/pubsub#multi-subscribe"
    OUTCAST_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#outcast-affiliation"
    PERSISTENT_ITEMS = "http://jabber.org/protocol/pubsub#persistent-items"
    PRESENCE_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#presence-notifications"
    PRESENCE_SUBSCRIBE = "http://jabber.org/protocol/pubsub#presence-subscribe"
    PUBLISH = "http://jabber.org/protocol/pubsub#publish"
    PUBLISH_OPTIONS = "http://jabber.org/protocol/pubsub#publish-options"
    PUBLISH_ONLY_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#publish-only-affiliation"
    PUBLISHER_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#publisher-affiliation"
    PURGE_NODES = "http://jabber.org/protocol/pubsub#purge-nodes"
    RETRACT_ITEMS = "http://jabber.org/protocol/pubsub#retract-items"
    RETRIEVE_AFFILIATIONS = \
        "http://jabber.org/protocol/pubsub#retrieve-affiliations"
    RETRIEVE_DEFAULT = "http://jabber.org/protocol/pubsub#retrieve-default"
    RETRIEVE_DEFAULT_SUB = \
        "http://jabber.org/protocol/pubsub#retrieve-default-sub"
    RETRIEVE_ITEMS = "http://jabber.org/protocol/pubsub#retrieve-items"
    RETRIEVE_SUBSCRIPTIONS = \
        "http://jabber.org/protocol/pubsub#retrieve-subscriptions"
    SUBSCRIBE = "http://jabber.org/protocol/pubsub#subscribe"
    SUBSCRIPTION_OPTIONS = \
        "http://jabber.org/protocol/pubsub#subscription-options"
    SUBSCRIPTION_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#subscription-notifications"


namespaces.xep0060_features = Features
namespaces.xep0060 = "http://jabber.org/protocol/pubsub"


class Affiliation(xso.XSO):
    TAG = (namespaces.xep0060, "affiliation")

    node = xso.Attr(
        "node",
        default=None
    )

    affiliation = xso.Attr(
        "affiliation",
        validator=xso.RestrictToSet({
            "member",
            "none",
            "outcast",
            "owner",
            "publisher",
            "publish-only",
        }),
    )


class Affiliations(xso.XSO):
    TAG = (namespaces.xep0060, "affiliations")

    node = xso.Attr(
        "node",
        default=None
    )

    affiliations = xso.ChildList(
        [Affiliation],
    )


class Configure(xso.XSO):
    TAG = (namespaces.xep0060, "configure")

    data = xso.Child([
        aioxmpp.forms.Data,
    ])


class Create(xso.XSO):
    TAG = (namespaces.xep0060, "create")

    node = xso.Attr(
        "node",
        default=None
    )


class Item(xso.XSO):
    TAG = (namespaces.xep0060, "item")

    id_ = xso.Attr(
        "id",
        default=None
    )

    registered_payload = xso.Child([])

    unregistered_payload = xso.Collector()


class Items(xso.XSO):
    TAG = (namespaces.xep0060, "items")

    max_items = xso.Attr(
        (None, "max_items"),
        type_=xso.Integer(),
        validator=xso.NumericRange(min_=1),
        default=None,
    )

    node = xso.Attr(
        "node",
    )

    subid = xso.Attr(
        "subid",
        default=None
    )


class Options(xso.XSO):
    TAG = (namespaces.xep0060, "options")

    jid = xso.Attr(
        "jid",
        type_=xso.JID()
    )

    node = xso.Attr(
        "node",
        default=None
    )

    subid = xso.Attr(
        "subid",
        default=None
    )

    data = xso.Child([
        aioxmpp.forms.Data,
    ])


class Publish(xso.XSO):
    TAG = (namespaces.xep0060, "publish")

    node = xso.Attr(
        "node",
    )

    items = xso.ChildList([
        Item
    ])


class Retract(xso.XSO):
    TAG = (namespaces.xep0060, "retract")

    node = xso.Attr(
        "node",
    )

    items = xso.ChildList([
        Item
    ])

    notify = xso.Attr(
        "notify",
        type_=xso.Bool(),
        default=False,
    )


class Subscribe(xso.XSO):
    TAG = (namespaces.xep0060, "subscribe")

    jid = xso.Attr(
        "jid",
        type_=xso.JID()
    )

    node = xso.Attr(
        "node",
        default=None
    )


class SubscribeOptions(xso.XSO):
    TAG = (namespaces.xep0060, "subscribe-options")

    required = xso.ChildTag(
        [
            (namespaces.xep0060, "required"),
        ],
        allow_none=True
    )


class Subscription(xso.XSO):
    TAG = (namespaces.xep0060, "subscription")

    jid = xso.Attr(
        "jid",
        type_=xso.JID()
    )

    node = xso.Attr(
        "node",
        default=None
    )

    subid = xso.Attr(
        "subid",
        default=None
    )

    subscription = xso.Attr(
        "subscription",
        validator=xso.RestrictToSet({
            "none",
            "pending",
            "subscribed",
            "unsubscribed",
        }),
        default=None
    )


class Subscriptions(xso.XSO):
    TAG = (namespaces.xep0060, "subscriptions")

    node = xso.Attr(
        "node",
        default=None
    )

    subscriptions = xso.ChildList(
        [Subscription],
    )


class Unsubscribe(xso.XSO):
    TAG = (namespaces.xep0060, "unsubscribe")

    jid = xso.Attr(
        "jid",
        type_=xso.JID()
    )

    node = xso.Attr(
        "node",
        default=None
    )

    subid = xso.Attr(
        "subid",
        default=None
    )


class Request(xso.XSO):
    TAG = (namespaces.xep0060, "pubsub")

    payload = xso.Child([
        Affiliations,
        Create,
        Subscribe,
        Subscription,
        Subscriptions,
    ])

    options = xso.Child([
        Options,
    ])

    configure = xso.Child([
        Configure,
    ])


# foo
