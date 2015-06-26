import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.rfc6121_roster = "jabber:iq:roster"


class Group(xso.XSO):
    TAG = (namespaces.rfc6121_roster, "group")

    name = xso.Text()


class Item(xso.XSO):
    TAG = (namespaces.rfc6121_roster, "item")

    approved = xso.Attr(
        "approved",
        type_=xso.Bool(),
        default=False,
    )

    ask = xso.Attr(
        "ask",
        validator=xso.RestrictToSet({
            None,
            "subscribe",
        }),
        validate=xso.ValidateMode.ALWAYS
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
        required=True,
    )

    name = xso.Attr(
        "name",
    )

    subscription = xso.Attr(
        "subscription",
        validator=xso.RestrictToSet({
            "none",
            "to",
            "from",
            "both",
        }),
        validate=xso.ValidateMode.ALWAYS,
        default="none",
    )

    groups = xso.ChildList([Group])


class Query(xso.XSO):
    TAG = (namespaces.rfc6121_roster, "query")

    ver = xso.Attr(
        "ver",
    )

    items = xso.ChildList([Item])
