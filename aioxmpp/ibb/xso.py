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


namespaces.xep0047 = "http://jabber.org/protocol/ibb"


class IBBStanzaType(enum.Enum):
    """
    Enumeration of the the two stanza types supported by IBB for
    transporting data.

   .. attribute:: IQ

      Send the in-band bytestream data using IQ stanzas. This is
      recommended and default. The reply mechanism of IQ allows
      tracking the connectivitiy and implements basic rate limiting,
      since we wait for the reply to the previous message before
      sending a new one.

   .. attribute:: MESSAGE

      Send the in-band bytestream data using Message stanzas. This is
      not recommended since lost packages due to intermittent
      connectivity failures will not be obvious.
    """
    IQ = "iq"
    MESSAGE = "message"


@stanza.IQ.as_payload_class
class Open(xso.XSO):
    TAG = (namespaces.xep0047, "open")

    block_size = xso.Attr("block-size", type_=xso.Integer())

    # XXX: sid should be restricted to NMTOKEN
    sid = xso.Attr("sid", type_=xso.String())

    stanza = xso.Attr(
        "stanza",
        type_=xso.EnumCDataType(IBBStanzaType),
        default=IBBStanzaType.IQ,
    )


@stanza.IQ.as_payload_class
class Close(xso.XSO):
    TAG = (namespaces.xep0047, "close")
    sid = xso.Attr("sid", type_=xso.String())


@stanza.IQ.as_payload_class
class Data(xso.XSO):
    TAG = (namespaces.xep0047, "data")

    seq = xso.Attr("seq", type_=xso.Integer())
    sid = xso.Attr("sid", type_=xso.String())
    content = xso.Text(type_=xso.Base64Binary())

    def __init__(self, sid, seq, content):
        self.seq = seq
        self.sid = sid
        self.content = content


stanza.Message.xep0047_data = xso.Child([Data])
