import types

import lxml.etree as etree

__all__ = [
    "etree",
    "namespaces",
    "split_tag",
    "LogETree",
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
namespaces.aioxmpp = "https://zombofant.net/xmlns/aioxmpp#library"

class LogETree:
    def __init__(self, subtree, **kwargs):
        self._kwargs = kwargs
        self._kwargs.setdefault("pretty_print", True)
        self._subtree = subtree

    def __str__(self):
        return etree.tostring(self._subtree, **self._kwargs)

def split_tag(tag):
    prefix, _, suffix = tag.partition("}")
    if not _:
        localname = prefix
        namespace = None
    else:
        localname = suffix
        namespace = prefix[1:]

    return namespace, localname
