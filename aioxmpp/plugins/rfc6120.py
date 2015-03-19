import aioxmpp.stanza as stanza
import aioxmpp.jid as jid
import aioxmpp.xml as xml

from aioxmpp.utils import namespaces

namespaces.bind = "urn:ietf:params:xml:ns:xmpp-bind"


class Bind(stanza.StanzaElementBase):
    TAG = "{{{}}}bind".format(namespaces.bind)
    _JID_TAG = "{{{}}}jid".format(namespaces.bind)
    _RESOURCE_TAG = "{{{}}}resource".format(namespaces.bind)

    def __init__(self, *args, nsmap={}, **kwargs):
        nsmap = dict(nsmap)
        nsmap[None] = namespaces.bind
        super().__init__(*args, nsmap=nsmap, **kwargs)

    @property
    def jid(self):
        el = self.find(self._JID_TAG)
        if el is None or el.text is None:
            return None
        return jid.JID.fromstr(el.text)

    @jid.setter
    def jid(self, value):
        el = self.find(self._JID_TAG)
        if el is None:
            el = self.makeelement(self._JID_TAG)
            self.insert(0, el)
        el.text = str(value)

    @jid.deleter
    def jid(self):
        el = self.find(self._JID_TAG)
        self.remove(el)

    @property
    def resource(self):
        el = self.find(self._RESOURCE_TAG)
        if el is None:
            return None
        return el.text

    @resource.setter
    def resource(self, value):
        el = self.find(self._RESOURCE_TAG)
        if el is None:
            el = self.makeelement(self._RESOURCE_TAG)
            self.insert(0, el)
        el.text = str(value)

    @resource.deleter
    def resource(self):
        el = self.find(self._RESOURCE_TAG)
        self.remove(el)


def register(lookup):
    ns = lookup.get_namespace(namespaces.bind)
    ns["bind"] = Bind

register(xml.lookup)
