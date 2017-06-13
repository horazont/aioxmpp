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
import multidict

import aioxmpp.stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0131_shim = "http://jabber.org/protocol/shim"


class Header(xso.XSO):
    TAG = (namespaces.xep0131_shim, "header")

    name = xso.Attr(
        "name",
    )

    value = xso.Text()

    def __init__(self, name, value):
        super().__init__()
        self.name = name
        self.value = value


class HeaderType(xso.AbstractElementType):
    def get_xso_types(self):
        return [Header]

    def unpack(self, v):
        return v.name, v.value

    def pack(self, v):
        name, value = v
        return Header(
            name,
            value,
        )


class Headers(xso.XSO):
    """
    Represent stanza headers. The headers are accessible at the :attr:`headers`
    attribute.

    .. attribute:: headers

       A :class:`multidict.CIMultiDict` which provides access to the headers.
       The keys are the header names and the values are the values of the
       header. Both must be strings.

    .. seealso::

       :attr:`.Message.xep0131_headers`
          SHIM headers for :class:`~.Message` stanzas

       :attr:`.Presence.xep0131_headers`
          SHIM headers for :class:`~.Presence` stanzas
    """

    TAG = (namespaces.xep0131_shim, "header")

    headers = xso.ChildValueMultiMap(
        HeaderType(),
        mapping_type=multidict.CIMultiDict,
    )


aioxmpp.stanza.Message.xep0131_headers = xso.Child([
    Headers,
])

aioxmpp.stanza.Presence.xep0131_headers = xso.Child([
    Headers,
])
