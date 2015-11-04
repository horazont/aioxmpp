import types

import lxml.etree as etree

__all__ = [
    "etree",
    "namespaces",
]

namespaces = types.SimpleNamespace()
namespaces.xmlstream = "http://etherx.jabber.org/streams"
namespaces.client = "jabber:client"
namespaces.starttls = "urn:ietf:params:xml:ns:xmpp-tls"
namespaces.sasl = "urn:ietf:params:xml:ns:xmpp-sasl"
namespaces.stanzas = "urn:ietf:params:xml:ns:xmpp-stanzas"
namespaces.streams = "urn:ietf:params:xml:ns:xmpp-streams"
namespaces.stream_management = "urn:xmpp:sm:3"
namespaces.bind = "urn:ietf:params:xml:ns:xmpp-bind"
namespaces.aioxmpp_internal = "https://zombofant.net/xmlns/aioxmpp#internal"
namespaces.xml = "http://www.w3.org/XML/1998/namespace"
