import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.rfc6121_roster = "jabber:iq:roster"


class Group(xso.XSO):
    """
    A group declaration for a contact in a roster.

    .. attribute:: name

       The name of the group.

    """
    TAG = (namespaces.rfc6121_roster, "group")

    name = xso.Text()


class Item(xso.XSO):
    """
    A contact item in a roster.

    .. attribute:: jid

       The bare :class:`~.structs.JID` of the contact.

    .. attribute:: name

       The optional display name of the contact.

    .. attribute:: groups

       A :class:`~aioxmpp.xso.model.XSOList` of :class:`Group` instances which
       describe the roster groups in which the contact is.

    The following attributes represent the subscription status of the
    contact. A client **must not** set these attributes when sending roster
    items to the server. To change subscription status, use presence stanzas of
    the respective type.

    .. attribute:: subscription

       Primary subscription status, one of ``"none"`` (the default), ``"to"``,
       ``"from"`` and ``"both"``.

    .. attribute:: approved

       Whether the subscription has been pre-approved by the owning entity.

    .. attribute:: ask

       Subscription sub-states, one of ``"subscribe"`` and :data:`None`.

    """

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
    """
    A query which fetches data from the roster or sends new items to the
    roster.

    .. attribute:: ver

       The version of the roster, if any. See the RFC for the detailed
       semantics.

    .. attribute:: items

       The items in the roster query.

    """
    TAG = (namespaces.rfc6121_roster, "query")

    ver = xso.Attr(
        "ver",
    )

    items = xso.ChildList([Item])
