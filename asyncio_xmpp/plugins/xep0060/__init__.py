from asyncio_xmpp.utils import *

from . import stanza

def register(lookup):
    ns = lookup.get_namespace(namespaces.xep0060_pubsub)
    ns["pubsub"] = stanza.PubSub
