########################################################################
# File name: xso.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import aioxmpp.forms
import aioxmpp.stanza
import aioxmpp.xso as xso

from enum import Enum

from aioxmpp.utils import namespaces


class Feature(Enum):
    ACCESS_AUTHORIZE = \
        "http://jabber.org/protocol/pubsub#access-authorize"
    ACCESS_OPEN = \
        "http://jabber.org/protocol/pubsub#access-open"
    ACCESS_PRESENCE = \
        "http://jabber.org/protocol/pubsub#access-presence"
    ACCESS_ROSTER = \
        "http://jabber.org/protocol/pubsub#access-roster"
    ACCESS_WHITELIST = \
        "http://jabber.org/protocol/pubsub#access-whitelist"
    AUTO_CREATE = \
        "http://jabber.org/protocol/pubsub#auto-create"
    AUTO_SUBSCRIBE = \
        "http://jabber.org/protocol/pubsub#auto-subscribe"
    COLLECTIONS = \
        "http://jabber.org/protocol/pubsub#collections"
    CONFIG_NODE = \
        "http://jabber.org/protocol/pubsub#config-node"
    CREATE_AND_CONFIGURE = \
        "http://jabber.org/protocol/pubsub#create-and-configure"
    CREATE_NODES = \
        "http://jabber.org/protocol/pubsub#create-nodes"
    DELETE_ITEMS = \
        "http://jabber.org/protocol/pubsub#delete-items"
    DELETE_NODES = \
        "http://jabber.org/protocol/pubsub#delete-nodes"
    FILTERED_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#filtered-notifications"
    GET_PENDING = \
        "http://jabber.org/protocol/pubsub#get-pending"
    INSTANT_NODES = \
        "http://jabber.org/protocol/pubsub#instant-nodes"
    ITEM_IDS = \
        "http://jabber.org/protocol/pubsub#item-ids"
    LAST_PUBLISHED = \
        "http://jabber.org/protocol/pubsub#last-published"
    LEASED_SUBSCRIPTION = \
        "http://jabber.org/protocol/pubsub#leased-subscription"
    MANAGE_SUBSCRIPTIONS = \
        "http://jabber.org/protocol/pubsub#manage-subscriptions"
    MEMBER_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#member-affiliation"
    META_DATA = \
        "http://jabber.org/protocol/pubsub#meta-data"
    MODIFY_AFFILIATIONS = \
        "http://jabber.org/protocol/pubsub#modify-affiliations"
    MULTI_COLLECTION = \
        "http://jabber.org/protocol/pubsub#multi-collection"
    MULTI_SUBSCRIBE = \
        "http://jabber.org/protocol/pubsub#multi-subscribe"
    OUTCAST_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#outcast-affiliation"
    PERSISTENT_ITEMS = \
        "http://jabber.org/protocol/pubsub#persistent-items"
    PRESENCE_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#presence-notifications"
    PRESENCE_SUBSCRIBE = \
        "http://jabber.org/protocol/pubsub#presence-subscribe"
    PUBLISH = \
        "http://jabber.org/protocol/pubsub#publish"
    PUBLISH_OPTIONS = \
        "http://jabber.org/protocol/pubsub#publish-options"
    PUBLISH_ONLY_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#publish-only-affiliation"
    PUBLISHER_AFFILIATION = \
        "http://jabber.org/protocol/pubsub#publisher-affiliation"
    PURGE_NODES = \
        "http://jabber.org/protocol/pubsub#purge-nodes"
    RETRACT_ITEMS = \
        "http://jabber.org/protocol/pubsub#retract-items"
    RETRIEVE_AFFILIATIONS = \
        "http://jabber.org/protocol/pubsub#retrieve-affiliations"
    RETRIEVE_DEFAULT = \
        "http://jabber.org/protocol/pubsub#retrieve-default"
    RETRIEVE_ITEMS = \
        "http://jabber.org/protocol/pubsub#retrieve-items"
    RETRIEVE_SUBSCRIPTIONS = \
        "http://jabber.org/protocol/pubsub#retrieve-subscriptions"
    SUBSCRIBE = \
        "http://jabber.org/protocol/pubsub#subscribe"
    SUBSCRIPTION_OPTIONS = \
        "http://jabber.org/protocol/pubsub#subscription-options"
    SUBSCRIPTION_NOTIFICATIONS = \
        "http://jabber.org/protocol/pubsub#subscription-notifications"


namespaces.xep0060_features = Feature
namespaces.xep0060 = "http://jabber.org/protocol/pubsub"
namespaces.xep0060_errors = "http://jabber.org/protocol/pubsub#errors"
namespaces.xep0060_event = "http://jabber.org/protocol/pubsub#event"
namespaces.xep0060_owner = "http://jabber.org/protocol/pubsub#owner"


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

    data = xso.Child([
        aioxmpp.forms.Data,
    ])

    def __init__(self, *, node=None, data=None):
        super().__init__()
        self.node = node
        self.data = data


class Item(xso.XSO):
    TAG = (namespaces.xep0060, "item")

    id_ = xso.Attr(
        "id",
        default=None
    )

    registered_payload = xso.Child([], strict=True)

    unregistered_payload = xso.Collector()

    def __init__(self, id_=None):
        super().__init__()
        self.id_ = id_


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

    items = xso.ChildList(
        [Item]
    )

    def __init__(self, node, subid=None, max_items=None):
        super().__init__()
        self.node = node
        self.subid = subid
        self.max_items = max_items


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

    def __init__(self, jid, node=None, subid=None):
        super().__init__()
        self.jid = jid
        self.node = node
        self.subid = subid


class PublishOptions(xso.XSO):
    TAG = (namespaces.xep0060, "publish-options")

    data = xso.Child([
        aioxmpp.forms.Data,
    ])


class Publish(xso.XSO):
    TAG = (namespaces.xep0060, "publish")

    node = xso.Attr(
        "node",
    )

    item = xso.Child([
        Item
    ])


class Retract(xso.XSO):
    TAG = (namespaces.xep0060, "retract")

    node = xso.Attr(
        "node",
    )

    item = xso.Child([
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
            "unconfigured",
        }),
        default=None
    )

    subscribe_options = xso.Child(
        [SubscribeOptions]
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

    def __init__(self, *, subscriptions=[], node=None):
        super().__init__()
        self.node = node
        self.subscriptions[:] = subscriptions


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

    def __init__(self, jid, node=None, subid=None):
        super().__init__()
        self.jid = jid
        self.node = node
        self.subid = subid


@aioxmpp.stanza.IQ.as_payload_class
class Request(xso.XSO):
    """
    This XSO represents the ``<pubsub/>`` IQ payload from the generic pubsub
    namespace (``http://jabber.org/protocol/pubsub``). It can carry different
    types of payload.

    .. attribute:: payload

       This is the generic payload attribute. It supports the following
       classes:

       .. autosummary::

          Affiliations
          Create
          Default
          Items
          Publish
          Retract
          Subscribe
          Subscription
          Subscriptions
          Unsubscribe

    .. attribute:: options

       As :class:`Options` may both be used independently and along with
       another :attr:`payload`, they have their own attribute.

       Independent of their use, :class:`Options` objects are always available
       here. If they are used without another payload, the :attr:`payload`
       attribute is :data:`None`.

    .. attribute:: configure

       As :class:`Configure` may both be used independently and along with
       another :attr:`payload`, it has its own attribute.

       Independent of their use, :class:`Configure` objects are always
       available here. If they are used without another payload, the
       :attr:`payload` attribute is :data:`None`.

    """
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

    publish_options = xso.Child([
        PublishOptions,
    ])

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


aioxmpp.stanza.Message.xep0060_request = xso.Child([
    Request
])


class EventAssociate(xso.XSO):
    TAG = (namespaces.xep0060_event, "associate")

    node = xso.Attr(
        "node",
    )


class EventDisassociate(xso.XSO):
    TAG = (namespaces.xep0060_event, "disassociate")

    node = xso.Attr(
        "node",
    )


class EventCollection(xso.XSO):
    TAG = (namespaces.xep0060_event, "collection")

    assoc = xso.Child([
        EventAssociate,
        EventDisassociate,
    ])


class EventRedirect(xso.XSO):
    TAG = (namespaces.xep0060_event, "redirect")

    uri = xso.Attr(
        "uri",
    )

    def __init__(self, uri):
        super().__init__()
        self.uri = uri


class EventDelete(xso.XSO):
    TAG = (namespaces.xep0060_event, "delete")

    _redirect = xso.Child([
        EventRedirect,
    ])

    node = xso.Attr(
        "node",
    )

    def __init__(self, node, *, redirect_uri=None):
        super().__init__()
        self.node = node
        if redirect_uri is not None:
            self._redirect = EventRedirect(redirect_uri)

    @property
    def redirect_uri(self):
        if self._redirect is None:
            return None
        return self._redirect.uri

    @redirect_uri.setter
    def redirect_uri(self, value):
        if value is None:
            del self._redirect
            return
        self._redirect = EventRedirect(value)

    @redirect_uri.deleter
    def redirect_uri(self):
        del self._redirect


class EventRetract(xso.XSO):
    TAG = (namespaces.xep0060_event, "retract")

    id_ = xso.Attr(
        "id",
    )

    def __init__(self, id_):
        super().__init__()
        self.id_ = id_


class EventItem(xso.XSO):
    TAG = (namespaces.xep0060_event, "item")

    id_ = xso.Attr(
        "id",
        default=None,
    )

    node = xso.Attr(
        "node",
        default=None,
    )

    publisher = xso.Attr(
        "publisher",
        default=None,
    )

    registered_payload = xso.Child([], strict=True)

    unregistered_payload = xso.Collector()

    def __init__(self, payload, *, id_=None):
        super().__init__()
        self.registered_payload = payload
        self.id_ = id_


class EventItems(xso.XSO):
    TAG = (namespaces.xep0060_event, "items")

    node = xso.Attr(
        "node",
    )

    retracts = xso.ChildList([EventRetract])

    items = xso.ChildList([EventItem])

    def __init__(self, node, *, items=[], retracts=[]):
        super().__init__()
        self.items[:] = items
        self.retracts[:] = retracts
        self.node = node


class EventPurge(xso.XSO):
    TAG = (namespaces.xep0060_event, "purge")

    node = xso.Attr(
        "node",
    )


class EventSubscription(xso.XSO):
    TAG = (namespaces.xep0060_event, "subscription")

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
            "unconfigured",
        }),
        default=None
    )

    expiry = xso.Attr(
        "expiry",
        type_=xso.DateTime(),
    )


class EventConfiguration(xso.XSO):
    TAG = (namespaces.xep0060_event, "configuration")

    node = xso.Attr(
        "node",
        default=None
    )

    data = xso.Child([
        aioxmpp.forms.Data,
    ])


class Event(xso.XSO):
    TAG = (namespaces.xep0060_event, "event")

    payload = xso.Child([
        EventCollection,
        EventConfiguration,
        EventDelete,
        EventItems,
        EventPurge,
        EventSubscription,
    ])

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


aioxmpp.stanza.Message.xep0060_event = xso.Child([
    Event
])


class OwnerAffiliation(xso.XSO):
    TAG = (namespaces.xep0060_owner, "affiliation")

    affiliation = xso.Attr(
        "affiliation",
        validator=xso.RestrictToSet({
            "member",
            "outcast",
            "owner",
            "publisher",
            "publish-only",
            "none",
        }),
        validate=xso.ValidateMode.ALWAYS,
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
    )

    def __init__(self, jid, affiliation):
        super().__init__()
        self.jid = jid
        self.affiliation = affiliation


class OwnerAffiliations(xso.XSO):
    TAG = (namespaces.xep0060_owner, "affiliations")

    affiliations = xso.ChildList([OwnerAffiliation])

    node = xso.Attr(
        "node",
    )

    def __init__(self, node, *, affiliations=[]):
        super().__init__()
        self.node = node
        self.affiliations[:] = affiliations


class OwnerConfigure(xso.XSO):
    TAG = (namespaces.xep0060_owner, "configure")

    node = xso.Attr(
        "node",
        default=None,
    )

    data = xso.Child([
        aioxmpp.forms.Data,
    ])

    def __init__(self, node=None):
        super().__init__()
        self.node = node


class OwnerDefault(xso.XSO):
    TAG = (namespaces.xep0060_owner, "default")

    data = xso.Child([
        aioxmpp.forms.Data,
    ])


class OwnerRedirect(xso.XSO):
    TAG = (namespaces.xep0060_owner, "redirect")

    uri = xso.Attr(
        "uri",
    )

    def __init__(self, uri):
        super().__init__()
        self.uri = uri


class OwnerDelete(xso.XSO):
    TAG = (namespaces.xep0060_owner, "delete")

    _redirect = xso.Child([OwnerRedirect])

    node = xso.Attr(
        "node",
    )

    def __init__(self, node, *, redirect_uri=None):
        super().__init__()
        self.node = node
        if redirect_uri is not None:
            self._redirect = OwnerRedirect(redirect_uri)

    @property
    def redirect_uri(self):
        if self._redirect is None:
            return None
        return self._redirect.uri

    @redirect_uri.setter
    def redirect_uri(self, value):
        if value is None:
            del self._redirect
            return
        self._redirect = OwnerRedirect(value)

    @redirect_uri.deleter
    def redirect_uri(self):
        del self._redirect


class OwnerPurge(xso.XSO):
    TAG = (namespaces.xep0060_owner, "purge")

    node = xso.Attr(
        "node",
    )

    def __init__(self, node):
        super().__init__()
        self.node = node


class OwnerSubscription(xso.XSO):
    TAG = (namespaces.xep0060_owner, "subscription")

    subscription = xso.Attr(
        "subscription",
        validator=xso.RestrictToSet({
            "none",
            "pending",
            "subscribed",
            "unconfigured",
        }),
        validate=xso.ValidateMode.ALWAYS
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
    )

    def __init__(self, jid, subscription):
        super().__init__()
        self.jid = jid
        self.subscription = subscription


class OwnerSubscriptions(xso.XSO):
    TAG = (namespaces.xep0060_owner, "subscriptions")

    node = xso.Attr(
        "node",
    )

    subscriptions = xso.ChildList([OwnerSubscription])

    def __init__(self, node, *, subscriptions=[]):
        super().__init__()
        self.node = node
        self.subscriptions[:] = subscriptions


@aioxmpp.stanza.IQ.as_payload_class
class OwnerRequest(xso.XSO):
    TAG = (namespaces.xep0060_owner, "pubsub")

    payload = xso.Child([
        OwnerAffiliations,
        OwnerConfigure,
        OwnerDefault,
        OwnerDelete,
        OwnerPurge,
        OwnerSubscriptions,
    ])

    def __init__(self, payload):
        super().__init__()
        self.payload = payload


def as_payload_class(cls):
    """
    Register the given class `cls` as Publish-Subscribe payload on both
    :class:`Item` and :class:`EventItem`.

    Return the class, to allow this to be used as decorator.
    """

    Item.register_child(
        Item.registered_payload,
        cls,
    )

    EventItem.register_child(
        EventItem.registered_payload,
        cls,
    )

    return cls


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
Feature.__docstring___ = \
    """
    .. attribute:: ACCESS_AUTHORIZE
       :annotation: = "http://jabber.org/protocol/pubsub#access-authorize"

       The default node access model is authorize.

    .. attribute:: ACCESS_OPEN
       :annotation: = "http://jabber.org/protocol/pubsub#access-open"

       The default node access model is open.

    .. attribute:: ACCESS_PRESENCE
       :annotation: = "http://jabber.org/protocol/pubsub#access-presence"

       The default node access model is presence.

    .. attribute:: ACCESS_ROSTER
       :annotation: = "http://jabber.org/protocol/pubsub#access-roster"

       The default node access model is roster.

    .. attribute:: ACCESS_WHITELIST
       :annotation: = "http://jabber.org/protocol/pubsub#access-whitelist"

       The default node access model is whitelist.

    .. attribute:: AUTO_CREATE
       :annotation: = "http://jabber.org/protocol/pubsub#auto-create"

       The service supports automatic creation of nodes on first publish.

    .. attribute:: AUTO_SUBSCRIBE
       :annotation: = "http://jabber.org/protocol/pubsub#auto-subscribe"

       The service supports automatic subscription to a nodes based on presence subscription.

    .. attribute:: COLLECTIONS
       :annotation: = "http://jabber.org/protocol/pubsub#collections"

       Collection nodes are supported.

    .. attribute:: CONFIG_NODE
       :annotation: = "http://jabber.org/protocol/pubsub#config-node"

       Configuration of node options is supported.

    .. attribute:: CREATE_AND_CONFIGURE
       :annotation: = "http://jabber.org/protocol/pubsub#create-and-configure"

       Simultaneous creation and configuration of nodes is supported.

    .. attribute:: CREATE_NODES
       :annotation: = "http://jabber.org/protocol/pubsub#create-nodes"

       Creation of nodes is supported.

    .. attribute:: DELETE_ITEMS
       :annotation: = "http://jabber.org/protocol/pubsub#delete-items"

       Deletion of items is supported.

    .. attribute:: DELETE_NODES
       :annotation: = "http://jabber.org/protocol/pubsub#delete-nodes"

       Deletion of nodes is supported.

    .. attribute:: FILTERED_NOTIFICATIONS
       :annotation: = "http://jabber.org/protocol/pubsub#filtered-notifications"

       The service supports filtering of notifications based on Entity Capabilities.

    .. attribute:: GET_PENDING
       :annotation: = "http://jabber.org/protocol/pubsub#get-pending"

       Retrieval of pending subscription approvals is supported.

    .. attribute:: INSTANT_NODES
       :annotation: = "http://jabber.org/protocol/pubsub#instant-nodes"

       Creation of instant nodes is supported.

    .. attribute:: ITEM_IDS
       :annotation: = "http://jabber.org/protocol/pubsub#item-ids"

       Publishers may specify item identifiers.

    .. attribute:: LAST_PUBLISHED
       :annotation: = "http://jabber.org/protocol/pubsub#last-published"

       The service supports sending of the last published item to new subscribers and to newly available resources.

    .. attribute:: LEASED_SUBSCRIPTION
       :annotation: = "http://jabber.org/protocol/pubsub#leased-subscription"

       Time-based subscriptions are supported.

    .. attribute:: MANAGE_SUBSCRIPTIONS
       :annotation: = "http://jabber.org/protocol/pubsub#manage-subscriptions"

       Node owners may manage subscriptions.

    .. attribute:: MEMBER_AFFILIATION
       :annotation: = "http://jabber.org/protocol/pubsub#member-affiliation"

       The member affiliation is supported.

    .. attribute:: META_DATA
       :annotation: = "http://jabber.org/protocol/pubsub#meta-data"

       Node meta-data is supported.

    .. attribute:: MODIFY_AFFILIATIONS
       :annotation: = "http://jabber.org/protocol/pubsub#modify-affiliations"

       Node owners may modify affiliations.

    .. attribute:: MULTI_COLLECTION
       :annotation: = "http://jabber.org/protocol/pubsub#multi-collection"

       A single leaf node can be associated with multiple collections.

    .. attribute:: MULTI_SUBSCRIBE
       :annotation: = "http://jabber.org/protocol/pubsub#multi-subscribe"

       A single entity may subscribe to a node multiple times.

    .. attribute:: OUTCAST_AFFILIATION
       :annotation: = "http://jabber.org/protocol/pubsub#outcast-affiliation"

       The outcast affiliation is supported.

    .. attribute:: PERSISTENT_ITEMS
       :annotation: = "http://jabber.org/protocol/pubsub#persistent-items"

       Persistent items are supported.

    .. attribute:: PRESENCE_NOTIFICATIONS
       :annotation: = "http://jabber.org/protocol/pubsub#presence-notifications"

       Presence-based delivery of event notifications is supported.

    .. attribute:: PRESENCE_SUBSCRIBE
       :annotation: = "http://jabber.org/protocol/pubsub#presence-subscribe"

       Implicit presence-based subscriptions are supported.

    .. attribute:: PUBLISH
       :annotation: = "http://jabber.org/protocol/pubsub#publish"

       Publishing items is supported.

    .. attribute:: PUBLISH_OPTIONS
       :annotation: = "http://jabber.org/protocol/pubsub#publish-options"

       Publication with publish options is supported.

    .. attribute:: PUBLISH_ONLY_AFFILIATION
       :annotation: = "http://jabber.org/protocol/pubsub#publish-only-affiliation"

       The publish-only affiliation is supported.

    .. attribute:: PUBLISHER_AFFILIATION
       :annotation: = "http://jabber.org/protocol/pubsub#publisher-affiliation"

       The publisher affiliation is supported.

    .. attribute:: PURGE_NODES
       :annotation: = "http://jabber.org/protocol/pubsub#purge-nodes"

       Purging of nodes is supported.

    .. attribute:: RETRACT_ITEMS
       :annotation: = "http://jabber.org/protocol/pubsub#retract-items"

       Item retraction is supported.

    .. attribute:: RETRIEVE_AFFILIATIONS
       :annotation: = "http://jabber.org/protocol/pubsub#retrieve-affiliations"

       Retrieval of current affiliations is supported.

    .. attribute:: RETRIEVE_DEFAULT
       :annotation: = "http://jabber.org/protocol/pubsub#retrieve-default"

       Retrieval of default node configuration is supported.

    .. attribute:: RETRIEVE_ITEMS
       :annotation: = "http://jabber.org/protocol/pubsub#retrieve-items"

       Item retrieval is supported.

    .. attribute:: RETRIEVE_SUBSCRIPTIONS
       :annotation: = "http://jabber.org/protocol/pubsub#retrieve-subscriptions"

       Retrieval of current subscriptions is supported.

    .. attribute:: SUBSCRIBE
       :annotation: = "http://jabber.org/protocol/pubsub#subscribe"

       Subscribing and unsubscribing are supported.

    .. attribute:: SUBSCRIPTION_OPTIONS
       :annotation: = "http://jabber.org/protocol/pubsub#subscription-options"

       Configuration of subscription options is supported.

    .. attribute:: SUBSCRIPTION_NOTIFICATIONS
       :annotation: = "http://jabber.org/protocol/pubsub#subscription-notifications"

       Notification of subscription state changes is supported.
    """  # NOQA: E501


class NodeConfigForm(aioxmpp.forms.Form):
    """
    Declaration of the form with type
    ``http://jabber.org/protocol/pubsub#node_config``

    .. autoattribute:: access_model

    .. autoattribute:: body_xslt

    .. autoattribute:: children_association_policy

    .. autoattribute:: children_association_whitelist

    .. autoattribute:: children

    .. autoattribute:: children_max

    .. autoattribute:: collection

    .. autoattribute:: contact

    .. autoattribute:: dataform_xslt

    .. autoattribute:: deliver_notifications

    .. autoattribute:: deliver_payloads

    .. autoattribute:: description

    .. autoattribute:: item_expire

    .. autoattribute:: itemreply

    .. autoattribute:: language

    .. autoattribute:: max_items

    .. autoattribute:: max_payload_size

    .. autoattribute:: node_type

    .. autoattribute:: notification_type

    .. autoattribute:: notify_config

    .. autoattribute:: notify_delete

    .. autoattribute:: notify_retract

    .. autoattribute:: notify_sub

    .. autoattribute:: persist_items

    .. autoattribute:: presence_based_delivery

    .. autoattribute:: publish_model

    .. autoattribute:: purge_offline

    .. autoattribute:: roster_groups_allowed

    .. autoattribute:: send_last_published_item

    .. autoattribute:: tempsub

    .. autoattribute:: subscribe

    .. autoattribute:: title

    .. autoattribute:: type

    """

    FORM_TYPE = 'http://jabber.org/protocol/pubsub#node_config'

    access_model = aioxmpp.forms.ListSingle(
        var='pubsub#access_model',
        label='Who may subscribe and retrieve items'
    )

    body_xslt = aioxmpp.forms.TextSingle(
        var='pubsub#body_xslt',
        label='The URL of an XSL transformation which can be applied to '
        'payloads in order to generate an appropriate message body element.'
    )

    children_association_policy = aioxmpp.forms.ListSingle(
        var='pubsub#children_association_policy',
        label='Who may associate leaf nodes with a collection'
    )

    children_association_whitelist = aioxmpp.forms.JIDMulti(
        var='pubsub#children_association_whitelist',
        label='The list of JIDs that may associate leaf nodes with a '
        'collection'
    )

    children = aioxmpp.forms.TextMulti(
        var='pubsub#children',
        label='The child nodes (leaf or collection) associated with a '
        'collection'
    )

    children_max = aioxmpp.forms.TextSingle(
        var='pubsub#children_max',
        label='The maximum number of child nodes that can be associated with '
        'a collection'
    )

    collection = aioxmpp.forms.TextMulti(
        var='pubsub#collection',
        label='The collection(s) with which a node is affiliated'
    )

    contact = aioxmpp.forms.JIDMulti(
        var='pubsub#contact',
        label='The JIDs of those to contact with questions'
    )

    dataform_xslt = aioxmpp.forms.TextSingle(
        var='pubsub#dataform_xslt',
        label='The URL of an XSL transformation which can be applied to the '
        'payload format in order to generate a valid Data Forms result that '
        'the client could display using a generic Data Forms rendering engine'
    )

    deliver_notifications = aioxmpp.forms.Boolean(
        var='pubsub#deliver_notifications',
        label='Whether to deliver event notifications'
    )

    deliver_payloads = aioxmpp.forms.Boolean(
        var='pubsub#deliver_payloads',
        label='Whether to deliver payloads with event notifications; applies '
        'only to leaf nodes'
    )

    description = aioxmpp.forms.TextSingle(
        var='pubsub#description',
        label='A description of the node'
    )

    item_expire = aioxmpp.forms.TextSingle(
        var='pubsub#item_expire',
        label='Number of seconds after which to automatically purge items'
    )

    itemreply = aioxmpp.forms.ListSingle(
        var='pubsub#itemreply',
        label='Whether owners or publisher should receive replies to items'
    )

    language = aioxmpp.forms.ListSingle(
        var='pubsub#language',
        label='The default language of the node'
    )

    max_items = aioxmpp.forms.TextSingle(
        var='pubsub#max_items',
        label='The maximum number of items to persist'
    )

    max_payload_size = aioxmpp.forms.TextSingle(
        var='pubsub#max_payload_size',
        label='The maximum payload size in bytes'
    )

    node_type = aioxmpp.forms.ListSingle(
        var='pubsub#node_type',
        label='Whether the node is a leaf (default) or a collection'
    )

    notification_type = aioxmpp.forms.ListSingle(
        var='pubsub#notification_type',
        label='Specify the delivery style for notifications'
    )

    notify_config = aioxmpp.forms.Boolean(
        var='pubsub#notify_config',
        label='Whether to notify subscribers when the node configuration '
        'changes'
    )

    notify_delete = aioxmpp.forms.Boolean(
        var='pubsub#notify_delete',
        label='Whether to notify subscribers when the node is deleted'
    )

    notify_retract = aioxmpp.forms.Boolean(
        var='pubsub#notify_retract',
        label='Whether to notify subscribers when items are removed from the '
        'node'
    )

    notify_sub = aioxmpp.forms.Boolean(
        var='pubsub#notify_sub',
        label='Whether to notify owners about new subscribers and unsubscribes'
    )

    persist_items = aioxmpp.forms.Boolean(
        var='pubsub#persist_items',
        label='Whether to persist items to storage'
    )

    presence_based_delivery = aioxmpp.forms.Boolean(
        var='pubsub#presence_based_delivery',
        label='Whether to deliver notifications to available users only'
    )

    publish_model = aioxmpp.forms.ListSingle(
        var='pubsub#publish_model',
        label='The publisher model'
    )

    purge_offline = aioxmpp.forms.Boolean(
        var='pubsub#purge_offline',
        label='Whether to purge all items when the relevant publisher goes '
        'offline'
    )

    roster_groups_allowed = aioxmpp.forms.ListMulti(
        var='pubsub#roster_groups_allowed',
        label='The roster group(s) allowed to subscribe and retrieve items'
    )

    send_last_published_item = aioxmpp.forms.ListSingle(
        var='pubsub#send_last_published_item',
        label='When to send the last published item'
    )

    tempsub = aioxmpp.forms.Boolean(
        var='pubsub#tempsub',
        label='Whether to make all subscriptions temporary, based on '
        'subscriber presence'
    )

    subscribe = aioxmpp.forms.Boolean(
        var='pubsub#subscribe',
        label='Whether to allow subscriptions'
    )

    title = aioxmpp.forms.TextSingle(
        var='pubsub#title',
        label='A friendly name for the node'
    )

    type = aioxmpp.forms.TextSingle(
        var='pubsub#type',
        label='The type of node data, usually specified by the namespace of '
        'the payload (if any)'
    )
