import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0115_caps = "http://jabber.org/protocol/caps"


class Caps(xso.XSO):
    """
    An entity capabilities extension for :class:`~.stanza.Presence`.

    .. attribute:: node

       The indicated node, for use with the corresponding info query.

    .. attribute:: hash_

       The hash algorithm used. This is :data:`None` if the legacy format is
       used.

    .. attribute:: ver

       The version (in the legacy format) or the calculated hash.

    .. attribute:: ext

       Only there for backwards compatibility. Not used anymore.

    """
    TAG = (namespaces.xep0115_caps, "c")

    node = xso.Attr("node")

    hash_ = xso.Attr(
        "hash",
        validator=xso.Nmtoken(),
        validate=xso.ValidateMode.FROM_CODE,
        default=None  # to check for legacy
    )

    ver = xso.Attr("ver")

    ext = xso.Attr("ext", default=None)

    def __init__(self, node, ver, hash_):
        super().__init__()
        self.node = node
        self.ver = ver
        self.hash_ = hash_


stanza.Presence.xep0115_caps = xso.Child([Caps], required=False)
