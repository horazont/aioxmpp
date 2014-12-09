import collections.abc

import asyncio_xmpp.stanza as stanza
from asyncio_xmpp.stanza_props import *

from asyncio_xmpp.utils import *

__all__ = [
    "InfoQuery",
    "Identity",
    "Feature",
    "ItemQuery",
    "Item",
]

namespaces.xep0030_disco_items = "http://jabber.org/protocol/disco#items"
namespaces.xep0030_disco_info = "http://jabber.org/protocol/disco#info"

class InfoQuery(stanza.StanzaElementBase):
    TAG = "{{{}}}query".format(namespaces.xep0030_disco_info)
    _FEATURE_NODE = "{{{}}}feature".format(namespaces.xep0030_disco_info)
    _IDENTITY_NODE = "{{{}}}identity".format(namespaces.xep0030_disco_info)

    @staticmethod
    def _map_feature(node):
        return node.get("var")

    @staticmethod
    def _construct_feature(parent, key):
        return etree.SubElement(
            parent,
            self._FEATURE_NODE,
            var=key)

    @property
    def features(self):
        return stanza.TransformedChildrenSetProxy(
            self,
            self._FEATURE_NODE,
            self._construct_feature,
            self._map_feature)

    @property
    def identities(self):
        return stanza.ChildrenSetProxy(
            self,
            self._IDENTITY_NODE)

    node = xmlattr()

class Identity(stanza.StanzaElementBase):
    TAG = "{{{}}}identity".format(namespaces.xep0030_disco_info)

    category = xmlattr()
    type_ = xmlattr(name="type_")
    name = xmlattr()

class Feature(stanza.StanzaElementBase):
    TAG = "{{{}}}feature".format(namespaces.xep0030_disco_info)

    var = xmlattr()

class ItemQuery(stanza.StanzaElementBase):
    TAG = "{{{}}}query".format(namespaces.xep0030_disco_items)
    _ITEM_NODE = "{{{}}}item".format(namespaces.xep0030_disco_items)

    @property
    def items(self):
        return stanza.ChildrenSetProxy(
            self,
            self._ITEM_NODE)

class Item(stanza.StanzaElementBase):
    TAG = "{{{}}}item".format(namespaces.xep0030_disco_items)

    jid = xmlattr(JIDType())
    name = xmlattr()
