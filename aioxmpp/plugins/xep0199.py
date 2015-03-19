"""
XEP-0199: XMPP Ping support
###########################
"""

import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0199_ping = "urn:xmpp:ping"


class Ping(xso.XSO):
    TAG = (namespaces.xep0199_ping, "ping")
    DECLARE_NS = {
        None: namespaces.xep0199_ping
    }
