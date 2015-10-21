import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0115_caps = "http://jabber.org/protocol/caps"


class Caps(xso.XSO):
    TAG = (namespaces.xep0115_caps, "c")

    node = xso.Attr("node")

    hash_ = xso.Attr(
        "hash",
        validator=xso.Nmtoken(),
        validate=xso.ValidateMode.FROM_CODE
    )

    ver = xso.Attr("ver")

    ext = xso.Attr("ext", default=None)


stanza.Presence.xep0115_caps = xso.Child([Caps])
