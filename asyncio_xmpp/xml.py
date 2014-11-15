from . import plugins, stanza
from .utils import *

__all__ = ["lookup"]

lookup = etree.ElementNamespaceClassLookup()

for ns in [lookup.get_namespace("jabber:client")]:
    ns["iq"] = stanza.IQ
    ns["presence"] = stanza.Presence
    ns["error"] = stanza.Error
    ns["message"] = stanza.Message

plugins.rfc6120.register(lookup)
plugins.xep0199.register(lookup)
