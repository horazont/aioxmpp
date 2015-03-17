"""
XEP-0199: XMPP Ping support
###########################
"""

import asyncio_xmpp.stanza_model as stanza_model
import asyncio_xmpp.xml as xml

from asyncio_xmpp.utils import namespaces

namespaces.xep0199_ping = "urn:xmpp:ping"

class Ping(stanza_model.StanzaObject):
    TAG = (namespaces.xep0199_ping, "ping")
    DECLARE_NS = {
        None: namespaces.xep0199_ping
    }
