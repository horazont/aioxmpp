import aioxmpp.xso as xso
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

namespaces.xep0030_info = "http://jabber.org/protocol/disco#info"
namespaces.xep0030_items = "http://jabber.org/protocol/disco#items"


class Identity(xso.XSO):
    TAG = (namespaces.xep0030_info, "identity")

    category = xso.Attr(
        tag="category",
        required=True,
        default="client",
    )

    type_ = xso.Attr(
        tag="type",
        required=True,
        default="bot",
    )

    name = xso.Attr(
        tag="name",
    )

    lang = xso.LangAttr()

    def __init__(self, *,
                 category=None,
                 type_=None,
                 name=None,
                 lang=None):
        super().__init__()
        if category is not None:
            self.category = category
        if type_ is not None:
            self.type_ = type_
        if name is not None:
            self.name = name
        if lang is not None:
            self.lang = lang


class Feature(xso.XSO):
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
    TAG = (namespaces.xep0030_items, "item")

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


@stanza.IQ.as_payload_class
class ItemsQuery(xso.XSO):
    TAG = (namespaces.xep0030_items, "query")

    node = xso.Attr(tag="node")
