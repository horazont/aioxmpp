import types

import lxml.etree as etree

__all__ = [
    "etree",
    "namespaces"
]

namespaces = types.SimpleNamespace()
namespaces.xmlstream = "http://etherx.jabber.org/streams"
namespaces.client = "jabber:client"
namespaces.starttls = "urn:ietf:params:xml:ns:xmpp-tls"
