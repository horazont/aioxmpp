import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0115_caps = "http://jabber.org/protocol/caps"


class Caps(xso.XSO):
    TAG = (namespaces.xep0115_caps, "c")

    node = xso.Attr(
        "node",
        required=True,
    )

    hash_ = xso.Attr(
        "hash",
        required=True,
        validator=xso.Nmtoken(),
        validate=xso.ValidateMode.FROM_CODE
    )

    ver = xso.Attr(
        "ver",
        required=True
    )

    ext = xso.Attr(
        "ext"
    )
