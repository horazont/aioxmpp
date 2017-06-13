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
import aioxmpp.forms.xso as forms_xso
import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

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

    category = xso.Attr(tag="category")
    type_ = xso.Attr(tag="type")
    name = xso.Attr(tag="name", default=None)
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

    def __eq__(self, other):
        try:
            return (self.category == other.category and
                    self.type_ == other.type_ and
                    self.name == other.name and
                    self.lang == other.lang)
        except AttributeError:
            return NotImplemented

    def __repr__(self):
        return "{}.{}(category={!r}, type_={!r}, name={!r}, lang={!r})".format(
            self.__class__.__module__,
            self.__class__.__qualname__,
            self.category,
            self.type_,
            self.name,
            self.lang)


class Feature(xso.XSO):
    """
    A feature declaration. The keyword argument to the constructor can be used
    to initialize the attribute of the :class:`Feature` instance.

    .. attribute:: var

       The namespace which identifies the feature.

    """

    TAG = (namespaces.xep0030_info, "feature")

    var = xso.Attr(tag="var")

    def __init__(self, var):
        super().__init__()
        self.var = var


class FeatureSet(xso.AbstractElementType):
    def get_xso_types(self):
        return [Feature]

    def unpack(self, item):
        return item.var

    def pack(self, var):
        return Feature(var)


@stanza.IQ.as_payload_class
class InfoQuery(xso.CapturingXSO):
    """
    A query for features and identities of an entity. The keyword arguments to
    the constructor can be used to initialize the attributes. Note that
    `identities` and `features` must be iterables of :class:`Identity` and
    :class:`Feature`, respectively; these iterables are evaluated and the items
    are stored in the respective attributes.

    .. attribute:: node

       The node at which the query is directed.

    .. attribute:: identities

       The identities of the entity, as :class:`Identity` instances. Each
       entity has at least one identity.

    .. attribute:: features

       The features of the entity, as a set of strings. Each string represents
       a :class:`Feature` instance with the corresponding :attr:`~.Feature.var`
       attribute.

    .. attribute:: captured_events

       If the object was created by parsing an XML stream, this attribute holds
       a list of events which were used when parsing it.

       Otherwise, this is :data:`None`.

       .. versionadded:: 0.5

    .. automethod:: to_dict

    """
    __slots__ = ("captured_events",)

    TAG = (namespaces.xep0030_info, "query")

    node = xso.Attr(tag="node", default=None)

    identities = xso.ChildList([Identity])

    features = xso.ChildValueList(
        FeatureSet(),
        container_type=set
    )

    exts = xso.ChildList([forms_xso.Data])

    def __init__(self, *, identities=(), features=(), node=None):
        super().__init__()
        self.captured_events = None
        self.identities.extend(identities)
        self.features.update(features)
        if node is not None:
            self.node = node

    def to_dict(self):
        """
        Convert the query result to a normalized JSON-like
        representation.

        The format is a subset of the format used by the `capsdb`__. Obviously,
        the node name and hash type are not included; otherwise, the format is
        identical.

        __ https://github.com/xnyhps/capsdb
        """
        identities = []
        for identity in self.identities:
            identity_dict = {
                "category": identity.category,
                "type": identity.type_,
            }
            if identity.lang is not None:
                identity_dict["lang"] = identity.lang.match_str
            if identity.name is not None:
                identity_dict["name"] = identity.name
            identities.append(identity_dict)

        features = sorted(self.features)

        forms = []
        for form in self.exts:
            forms.append({
                field.var: list(field.values)
                for field in form.fields
                if field.var is not None
            })

        result = {
            "identities": identities,
            "features": features,
            "forms": forms
        }

        return result

    def _set_captured_events(self, events):
        self.captured_events = events


class Item(xso.XSO):
    """
    An item declaration. The keyword arguments to the constructor can be used
    to initialize the attributes of the :class:`Item` instance.

    .. attribute:: jid

       :class:`~aioxmpp.JID` of the entity represented by the item.

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
    )

    name = xso.Attr(
        tag="name",
        default=None,
    )

    node = xso.Attr(
        tag="node",
        default=None,
    )

    def __init__(self, jid, name=None, node=None):
        super().__init__()
        self.jid = jid
        self.name = name
        self.node = node


@stanza.IQ.as_payload_class
class ItemsQuery(xso.XSO):
    """
    A query for items at a specific entity. The keyword arguments to the
    constructor can be used to initialize the attributes of the
    :class:`ItemsQuery`. Note that `items` must be an iterable of :class:`Item`
    instances. The iterable will be evaluated and the items will be stored in
    the :attr:`items` attribute.

    .. attribute:: node

       Node at which the query is directed

    .. attribute:: items

       The items at the addressed entity.

    """
    TAG = (namespaces.xep0030_items, "query")

    node = xso.Attr(tag="node", default=None)

    items = xso.ChildList([Item])

    def __init__(self, *, node=None, items=()):
        super().__init__()
        self.items.extend(items)
        if node is not None:
            self.node = node
