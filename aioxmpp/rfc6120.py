from . import xso, stanza, stream_xsos
from .utils import namespaces

namespaces.rfc6120_bind = "urn:ietf:params:xml:ns:xmpp-bind"


@stream_xsos.StreamFeatures.as_feature_class
class BindFeature(xso.XSO):
    TAG = (namespaces.rfc6120_bind, "bind")

    class Required(xso.XSO):
        TAG = (namespaces.rfc6120_bind, "required")

    required = xso.Child([Required])

class Bind(xso.XSO):
    TAG = (namespaces.rfc6120_bind, "bind")

    jid = xso.ChildText(
        (namespaces.rfc6120_bind, "jid"),
        type_=xso.JID()
    )
    resource = xso.ChildText(
        (namespaces.rfc6120_bind, "resource"),
    )

    def __init__(self, jid=None, resource=None):
        super().__init__()
        self.jid = jid
        self.resource = resource


stanza.IQ.register_child(stanza.IQ.payload, Bind)
