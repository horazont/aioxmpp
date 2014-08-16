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
namespaces.sasl = "urn:ietf:params:xml:ns:xmpp-sasl"
namespaces.stanzas = "urn:ietf:params:xml:ns:xmpp-stanzas"

def split_tag(tag):
    prefix, _, suffix = tag.partition("}")
    if not _:
        localname = prefix
        namespace = None
    else:
        localname = suffix
        namespace = prefix[1:]

    return namespace, localname
