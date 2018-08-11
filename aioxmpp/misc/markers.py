########################################################################
# File name: markers.py
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
import aioxmpp.xso

from ..stanza import Message

from aioxmpp.utils import namespaces

namespaces.xep0333_markers = "urn:xmpp:chat-markers:0"


class Marker(aioxmpp.xso.XSO):
    id_ = aioxmpp.xso.Attr(
        "id"
    )


class ReceivedMarker(Marker):
    TAG = (namespaces.xep0333_markers, "received")


class DisplayedMarker(Marker):
    TAG = (namespaces.xep0333_markers, "displayed")


class AcknowledgedMarker(Marker):
    TAG = (namespaces.xep0333_markers, "acknowledged")


Message.xep0333_marker = aioxmpp.xso.Child([
    ReceivedMarker,
    DisplayedMarker,
    AcknowledgedMarker,
])

Message.xep0333_markable = aioxmpp.xso.ChildFlag(
    (namespaces.xep0333_markers, "markable"),
)
