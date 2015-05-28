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


class StreamFeatures(xso.XSO):
    """
    XSO for collecting the supported stream features the remote advertises.

    To register a stream feature, use :meth:`register_child` with the
    :attr:`features` descriptor. A more fancy way to do the same thing is to
    """

    TAG = (namespaces.xmlstream, "features")
    DECLARE_NS = {
        None: namespaces.xmlstream
    }

    # we drop unknown children
    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP

    features = xso.ChildMap([])

    @classmethod
    def as_feature_class(cls, other_cls):
        cls.register_child(cls.features, other_cls)
        return other_cls

    def __getitem__(self, feature_cls):
        tag = feature_cls.TAG
        try:
            return self.features[feature_cls.TAG][0]
        except IndexError:
            raise KeyError(feature_cls) from None

    def has_feature(self, feature_cls):
        return feature_cls.TAG in self.features

    def get_feature(self, feature_cls):
        try:
            return self[feature_cls]
        except KeyError:
            return None


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
