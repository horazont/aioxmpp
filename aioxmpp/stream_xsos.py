from . import xso, errors

from .utils import namespaces


class StreamError(xso.XSO):
    TAG = (namespaces.xmlstream, "error")

    text = xso.ChildText(
        tag=(namespaces.streams, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None)
    condition = xso.ChildTag(
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


class SMXSO(xso.XSO):
    DECLARE_NS = {
        None: namespaces.stream_management
    }


class SMRequest(SMXSO):
    TAG = (namespaces.stream_management, "r")


class SMAcknowledgement(SMXSO):
    TAG = (namespaces.stream_management, "a")

    counter = xso.Attr(
        "h",
        type_=xso.Integer(),
        required=True,
    )


class SMEnable(SMXSO):
    TAG = (namespaces.stream_management, "enable")

    resume = xso.Attr(
        "resume",
        type_=xso.Bool(),
        default=False
    )


class SMEnabled(SMXSO):
    TAG = (namespaces.stream_management, "enabled")

    resume = xso.Attr(
        "resume",
        type_=xso.Bool(),
        default=False
    )
    id_ = xso.Attr("id")
    location = xso.Attr(
        "location",
        default=None)


class SMResume(SMXSO):
    TAG = (namespaces.stream_management, "resume")

    counter = xso.Attr(
        "h",
        type_=xso.Integer(),
        required=True,
    )
    previd = xso.Attr(
        "previd",
        required=True)


class SMResumed(SMXSO):
    TAG = (namespaces.stream_management, "resumed")

    counter = xso.Attr(
        "h",
        type_=xso.Integer(),
        required=True)
    previd = xso.Attr(
        "previd",
        required=True)
