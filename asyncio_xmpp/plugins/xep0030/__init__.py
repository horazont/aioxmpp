from asyncio_xmpp.utils import *

from . import stanza

def register(lookup):
    ns = lookup.get_namespace(namespaces.xep0030_disco_info)
    ns["query"] = stanza.InfoQuery
    ns["identity"] = stanza.Identity

    ns = lookup.get_namespace(namespaces.xep0030_disco_items)
    ns["query"] = stanza.ItemQuery
    ns["item"] = stanza.Item
