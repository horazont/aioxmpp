import aioxmpp.forms
import aioxmpp.stanza
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
namespaces.xep0060_errors = "http://jabber.org/protocol/pubsub#errors"


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

    def __init__(self, affiliation, node=None):
        super().__init__()
        self.affiliation = affiliation
        self.node = node


class Affiliations(xso.XSO):
    TAG = (namespaces.xep0060, "affiliations")

    node = xso.Attr(
        "node",
        default=None
    )

    affiliations = xso.ChildList(
        [Affiliation],
    )

    def __init__(self, affiliations=[], node=None):
        super().__init__()
        self.affiliations[:] = affiliations
        self.node = node


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


class Default(xso.XSO):
    TAG = (namespaces.xep0060, "default")

    node = xso.Attr(
        "node",
        default=None
    )

    type_ = xso.Attr(
        "type",
        validator=xso.RestrictToSet({
            "leaf",
            "collection",
        }),
        default="leaf",
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

    def __init__(self, jid, node=None):
        super().__init__()
        self.jid = jid
        self.node = node


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

    def __init__(self, jid, node=None, subid=None, *, subscription=None):
        super().__init__()
        self.jid = jid
        self.node = node
        self.subid = subid
        self.subscription = subscription


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


@aioxmpp.stanza.IQ.as_payload_class
class Request(xso.XSO):
    TAG = (namespaces.xep0060, "pubsub")

    payload = xso.Child([
        Affiliations,
        Create,
        Default,
        Items,
        Publish,
        Retract,
        Subscribe,
        Subscription,
        Subscriptions,
        Unsubscribe,
    ])

    options = xso.Child([
        Options,
    ])

    configure = xso.Child([
        Configure,
    ])

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


ClosedNode = aioxmpp.stanza.make_application_error(
    "ClosedNode",
    (namespaces.xep0060_errors, "closed-node"),
)

ConfigurationRequired = aioxmpp.stanza.make_application_error(
    "ConfigurationRequired",
    (namespaces.xep0060_errors, "configuration-required"),
)

InvalidJID = aioxmpp.stanza.make_application_error(
    "InvalidJID",
    (namespaces.xep0060_errors, "invalid-jid"),
)

InvalidOptions = aioxmpp.stanza.make_application_error(
    "InvalidOptions",
    (namespaces.xep0060_errors, "invalid-options"),
)

InvalidPayload = aioxmpp.stanza.make_application_error(
    "InvalidPayload",
    (namespaces.xep0060_errors, "invalid-payload"),
)

InvalidSubID = aioxmpp.stanza.make_application_error(
    "InvalidSubID",
    (namespaces.xep0060_errors, "invalid-subid"),
)

ItemForbidden = aioxmpp.stanza.make_application_error(
    "ItemForbidden",
    (namespaces.xep0060_errors, "item-forbidden"),
)

ItemRequired = aioxmpp.stanza.make_application_error(
    "ItemRequired",
    (namespaces.xep0060_errors, "item-required"),
)

JIDRequired = aioxmpp.stanza.make_application_error(
    "JIDRequired",
    (namespaces.xep0060_errors, "jid-required"),
)

MaxItemsExceeded = aioxmpp.stanza.make_application_error(
    "MaxItemsExceeded",
    (namespaces.xep0060_errors, "max-items-exceeded"),
)

MaxNodesExceeded = aioxmpp.stanza.make_application_error(
    "MaxNodesExceeded",
    (namespaces.xep0060_errors, "max-nodes-exceeded"),
)

NodeIDRequired = aioxmpp.stanza.make_application_error(
    "NodeIDRequired",
    (namespaces.xep0060_errors, "nodeid-required"),
)

NotInRosterGroup = aioxmpp.stanza.make_application_error(
    "NotInRosterGroup",
    (namespaces.xep0060_errors, "not-in-roster-group"),
)

NotSubscribed = aioxmpp.stanza.make_application_error(
    "NotSubscribed",
    (namespaces.xep0060_errors, "not-subscribed"),
)

PayloadTooBig = aioxmpp.stanza.make_application_error(
    "PayloadTooBig",
    (namespaces.xep0060_errors, "payload-too-big"),
)

PayloadRequired = aioxmpp.stanza.make_application_error(
    "PayloadRequired",
    (namespaces.xep0060_errors, "payload-required"),
)

PendingSubscription = aioxmpp.stanza.make_application_error(
    "PendingSubscription",
    (namespaces.xep0060_errors, "pending-subscription"),
)

PresenceSubscriptionRequired = aioxmpp.stanza.make_application_error(
    "PresenceSubscriptionRequired",
    (namespaces.xep0060_errors, "presence-subscription-required"),
)

SubIDRequired = aioxmpp.stanza.make_application_error(
    "SubIDRequired",
    (namespaces.xep0060_errors, "subid-required"),
)

TooManySubscriptions = aioxmpp.stanza.make_application_error(
    "TooManySubscriptions",
    (namespaces.xep0060_errors, "too-many-subscriptions"),
)


@aioxmpp.stanza.Error.as_application_condition
class Unsupported(xso.XSO):
    TAG = (namespaces.xep0060_errors, "unsupported")

    feature = xso.Attr(
        "feature",
        validator=xso.RestrictToSet({
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
        })
    )


# foo
