"""
XEP-0199: XMPP Ping support
###########################
"""

import aioxmpp.stanza_model as stanza_model
import aioxmpp.xml as xml

from aioxmpp.utils import namespaces

namespaces.xep0199_ping = "urn:xmpp:ping"

class Ping(stanza_model.StanzaObject):
    TAG = (namespaces.xep0199_ping, "ping")
    DECLARE_NS = {
        None: namespaces.xep0199_ping
    }
