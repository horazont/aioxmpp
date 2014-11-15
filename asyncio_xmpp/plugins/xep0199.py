"""
XEP-0199: XMPP Ping support
###########################
"""

import asyncio_xmpp.stanza as stanza

from asyncio_xmpp.utils import *

namespaces.xep0199_ping = "urn:xmpp:ping"

class Ping(stanza.StanzaElementBase):
    TAG = "{{{}}}ping".format(namespaces.xep0199_ping)

    def __init__(self, *args, nsmap={}, **kwargs):
        nsmap = dict(nsmap)
        nsmap[None] = namespaces.xep0199_ping
        super().__init__(*args, nsmap=nsmap, **kwargs)

def register(lookup):
    ns = lookup.get_namespace(namespaces.xep0199_ping)
    ns["ping"] = Ping
