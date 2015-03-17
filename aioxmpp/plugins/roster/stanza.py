import aioxmpp.stanza as stanza

from aioxmpp.stanza_props import *
from aioxmpp.utils import *

__all__ = [
    "Query",
    "Item",
    "Group"
]

namespaces.roster = "jabber:iq:roster"

class Query(stanza.StanzaElementBase):
    TAG = "{{{}}}query".format(namespaces.roster)

    ver = xmlattr()

    @property
    def items(self):
        return stanza.ChildrenSetProxy(self, Item.TAG)

class Item(stanza.StanzaElementBase):
    TAG = "{{{}}}item".format(namespaces.roster)

    approved = xmlattr(BoolType())
    ask = xmlattr(EnumType(["subscribe"]))
    jid = xmlattr(JIDType())
    subscription = xmlattr(EnumType([
        "none",
        "to",
        "from",
        "both",
        "remove"
    ]))
    name = xmlattr()

    @property
    def groups(self):
        return stanza.ChildrenSetProxy(self, Group.TAG)

class Group(stanza.StanzaElementBase):
    TAG = "{{{}}}group".format(namespaces.roster)

    name = xmltext()
