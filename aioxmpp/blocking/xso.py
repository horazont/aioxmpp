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
import aioxmpp
import aioxmpp.xso

from aioxmpp.utils import namespaces

namespaces.xep0191 = "urn:xmpp:blocking"


# this XSO represents a single block list item.
class BlockItem(aioxmpp.xso.XSO):
    # define the tag we are matching for
    # tags consist of an XML namespace URI and an XML element
    TAG = (namespaces.xep0191, "item")

    # bind the ``jid`` python attribute to refer to the ``jid`` XML attribute.
    # in addition, automatic conversion between actual JID objects and XML
    # character data is requested by specifying the `type_` argument as
    # xso.JID() object.
    jid = aioxmpp.xso.Attr(
        "jid",
        type_=aioxmpp.xso.JID()
    )


# we now declare a custom type to convert between JID objects and BlockItem
# instances.
# we can use this custom type together with xso.ChildValueList to access the
# list of <item xmlns="urn:xmpp:blocking" /> elements like a normal python list
# of JIDs.
class BlockItemType(aioxmpp.xso.AbstractElementType):
    # unpack converts from the "raw" XSO to the
    # "rich" python representation, in this case a JID object
    # think of unpack like of a high-level struct.unpack: we convert
    # wire-format (XML trees) to python values
    def unpack(self, item):
        return item.jid

    # pack is the reverse operation of unpack
    def pack(self, jid):
        item = BlockItem()
        item.jid = jid
        return item

    # we have to tell the XSO framework what XSO types are supported by this
    # element type
    def get_xso_types(self):
        return [BlockItem]


# the decorator tells the IQ stanza class that this is a valid payload; that is
# required to be able to *receive* payloads of this type (sending works without
# that decorator, but is not recommended)
@aioxmpp.stanza.IQ.as_payload_class
class BlockList(aioxmpp.xso.XSO):
    TAG = (namespaces.xep0191, "blocklist")

    # this does not get an __init__ method, since the client never
    # creates a BlockList with entries.

    # xso.ChildValueList uses an AbstractElementType (like the one we defined
    # above) to convert between child XSO instances and other python objects.
    # it is accessed like a normal list, but when parsing/serialising, the
    # elements are converted to XML structures using the given type.
    items = aioxmpp.xso.ChildValueList(
        BlockItemType()
    )


@aioxmpp.stanza.IQ.as_payload_class
class BlockCommand(aioxmpp.xso.XSO):
    TAG = (namespaces.xep0191, "block")

    def __init__(self, jids_to_block=None):
        if jids_to_block is not None:
            self.items[:] = jids_to_block

    items = aioxmpp.xso.ChildValueList(
        BlockItemType()
    )


@aioxmpp.stanza.IQ.as_payload_class
class UnblockCommand(aioxmpp.xso.XSO):
    TAG = (namespaces.xep0191, "unblock")

    def __init__(self, jids_to_block=None):
        if jids_to_block is not None:
            self.items[:] = jids_to_block

    items = aioxmpp.xso.ChildValueList(
        BlockItemType()
    )
