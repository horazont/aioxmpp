from . import stanza_model, stanza_types, errors

from .utils import namespaces


class StreamError(stanza_model.StanzaObject):
    TAG = (namespaces.xmlstream, "error")

    text = stanza_model.ChildText(
        tag=(namespaces.streams, "text"),
        attr_policy=stanza_model.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None)
    condition = stanza_model.ChildTag(
        tags=[
            "bad-format",
            "bad-namespace-prefix",
            "conflict",
            "connection-timeout",
            "host-gone",
            "host-unknown",
            "improper-addressing",
            "internal-server-error",
            "invalid-from",
            "invalid-namespace",
            "invalid-xml",
            "not-authorized",
            "not-well-formed",
            "policy-violation",
            "remote-connection-failed",
            "reset",
            "resource-constraint",
            "restricted-xml",
            "see-other-host",
            "system-shutdown",
            "undefined-condition",
            "unsupported-encoding",
            "unsupported-feature",
            "unsupported-stanza-type",
            "unsupported-version",
        ],
        default_ns=namespaces.streams,
        allow_none=False,
        default=(namespaces.streams, "undefined-condition"),
        declare_prefix=None,
    )

    @classmethod
    def from_exception(cls, exc):
        instance = cls()
        instance.text = exc.text
        instance.condition = exc.condition
        return instance

    def to_exception(self):
        return errors.StreamError(
            condition=self.condition,
            text=self.text)
