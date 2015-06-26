import aioxmpp.xso as xso
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

namespaces.xep0030_info = "http://jabber.org/protocol/disco#info"
namespaces.xep0030_items = "http://jabber.org/protocol/disco#items"


class Identity(xso.XSO):
    """
    An identity declaration. The keyword arguments to the constructor can be
    used to initialize attributes of the :class:`Identity` instance.

    .. attribute:: category

       The category of the identity. The value is not validated against the
       values in the `registry
       <https://xmpp.org/registrar/disco-categories.html>`_.

    .. attribute:: type_

       The type of the identity. The value is not validated against the values
       in the `registry
       <https://xmpp.org/registrar/disco-categories.html>`_.

    .. attribute:: name

       The optional human-readable name of the identity. See also the
       :attr:`lang` attribute.

    .. attribute:: lang

       The language of the :attr:`name`. This may be not :data:`None` even if
       :attr:`name` is not set due to ``xml:lang`` propagation.

    """
    TAG = (namespaces.xep0030_info, "identity")

    category = xso.Attr(
        tag="category",
        required=True,
    )

    type_ = xso.Attr(
        tag="type",
        required=True,
    )

    name = xso.Attr(
        tag="name",
    )

    lang = xso.LangAttr()

    def __init__(self, *,
                 category="client",
                 type_="bot",
                 name=None,
                 lang=None):
        super().__init__()
        self.category = category
        self.type_ = type_
        if name is not None:
            self.name = name
        if lang is not None:
            self.lang = lang


class Feature(xso.XSO):
    """
    A feature declaration. The keyword argument to the constructor can be used
    to initialize the attribute of the :class:`Feature` instance.

    .. attribute:: var

       The namespace which identifies the feature.

    """

    TAG = (namespaces.xep0030_info, "feature")

    var = xso.Attr(
        tag="var",
        required=True
    )

    def __init__(self, *, var=None):
        super().__init__()
        self.var = var


@stanza.IQ.as_payload_class
class InfoQuery(xso.XSO):
    """
    A query for features and identities of an entity. The keyword arguments to
    the constructor can be used to initialize the attributes. Note that
    *identities* and *features* must be iterables of :class:`Identity` and
    :class:`Feature`, respectively; these iterables are evaluated and the items
    are stored in the respective attributes.

    .. attribute:: node

       The node at which the query is directed.

    .. attribute:: identities

       The identities of the entity, as :class:`Identity` instances. Each
       entity has at least one identity.

    .. attribute:: features

       The features of the entity, as :class:`Feature` instances.

    """
    TAG = (namespaces.xep0030_info, "query")

    node = xso.Attr(tag="node")

    identities = xso.ChildList([Identity])
    features = xso.ChildList([Feature])

    def __init__(self, *, identities=(), features=(), node=None):
        super().__init__()
        self.identities.extend(identities)
        self.features.extend(features)
        if node is not None:
            self.node = node


class Item(xso.XSO):
    """
    An item declaration. The keyword arguments to the constructor can be used
    to initialize the attributes of the :class:`Item` instance.

    .. attribute:: jid

       :class:`~aioxmpp.structs.JID` of the entity represented by the item.

    .. attribute:: node

       Node of the item

    .. attribute:: name

       Name of the item

    """

    TAG = (namespaces.xep0030_items, "item")
    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP

    jid = xso.Attr(
        tag="jid",
        type_=xso.JID(),
        # FIXME: validator for full jid
        required=True,
    )

    name = xso.Attr(
        tag="name"
    )

    node = xso.Attr(
        tag="node"
    )

    def __init__(self, *, jid=None, name=None, node=None):
        super().__init__()
        if jid is not None:
            self.jid = jid
        if name is not None:
            self.name = name
        if node is not None:
            self.node = node


@stanza.IQ.as_payload_class
class ItemsQuery(xso.XSO):
    """
    A query for items at a specific entity. The keyword arguments to the
    constructor can be used to initialize the attributes of the
    :class:`ItemsQuery`. Note that *items* must be an iterable of :class:`Item`
    instances. The iterable will be evaluated and the items will be stored in
    the :attr:`items` attribute.

    .. attribute:: node

       Node at which the query is directed

    .. attribute:: items

       The items at the addressed entity.

    """
    TAG = (namespaces.xep0030_items, "query")

    node = xso.Attr(tag="node")

    items = xso.ChildList([Item])

    def __init__(self, *, node=None, items=()):
        super().__init__()
        self.items.extend(items)
        if node is not None:
            self.node = node
