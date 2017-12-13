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
import enum

import aioxmpp.xso as xso
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces


namespaces.xep0085 = "http://jabber.org/protocol/chatstates"


class ChatState(enum.Enum):
    """
    Enumeration of the chat states defined by :xep:`0085`:

    .. attribute:: ACTIVE

    .. attribute:: COMPOSING

    .. attribute:: PAUSED

    .. attribute:: INACTIVE

    .. attribute:: GONE
    """
    ACTIVE = (namespaces.xep0085, "active")
    COMPOSING = (namespaces.xep0085, "composing")
    PAUSED = (namespaces.xep0085, "paused")
    INACTIVE = (namespaces.xep0085, "inactive")
    GONE = (namespaces.xep0085, "gone")


stanza.Message.xep0085_chatstate = xso.ChildTag(ChatState, allow_none=True)
