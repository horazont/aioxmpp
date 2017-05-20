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
import aioxmpp.hashes
import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0115_caps = "http://jabber.org/protocol/caps"
namespaces.xep0390_caps = "urn:xmpp:caps"


class Caps115(xso.XSO):
    """
    An entity capabilities extension for :class:`~.Presence`.

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


class Caps390(aioxmpp.hashes.HashesParent, xso.XSO):
    TAG = namespaces.xep0390_caps, "c"


stanza.Presence.xep0115_caps = xso.Child([Caps115])
stanza.Presence.xep0390_caps = xso.Child([Caps390])
