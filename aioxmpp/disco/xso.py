import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0030_info = "http://jabber.org/protocol/disco#info"
namespaces.xep0030_items = "http://jabber.org/protocol/disco#items"


class Identity(xso.XSO):
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


class Feature(xso.XSO):
    TAG = (namespaces.xep0030_info, "feature")

    var = xso.Attr(
        tag="var",
        required=True
    )


class InfoQuery(xso.XSO):
    TAG = (namespaces.xep0030_info, "query")

    node = xso.Attr(tag="node")

    identities = xso.ChildList([Identity])
    features = xso.ChildList([Feature])


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


class ItemsQuery(xso.XSO):
    TAG = (namespaces.xep0030_items, "query")

    node = xso.Attr(tag="node")
