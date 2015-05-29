"""
:mod:`~aioxmpp.stream_xsos` --- Non-stanza stream-level XSOs
############################################################

This module contains XSO models for stream-level elements which are not
stanzas.

General XSOs
============

.. autoclass:: StreamError()

.. autoclass:: StreamFeatures()

Stream management related XSOs
==============================

.. autoclass:: SMXSO()

.. autoclass:: SMRequest()

.. autoclass:: SMAcknowledgement()

.. autoclass:: SMEnable()

.. autoclass:: SMEnabled()

.. autoclass:: SMResume()

.. autoclass:: SMResumed()

"""
import itertools

from . import xso, errors

from .utils import namespaces


class StreamError(xso.XSO):
    """
    XSO representing a stream error.

    .. attribute:: text

       The text content of the stream error.

    .. attribute:: condition

       The RFC 6120 stream error condition.

    """

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
    use the :meth:`as_feature_class` classmethod as decorator for your feature
    XSO class.

    Adding new feature classes:

    .. automethod:: as_feature_class

    Querying features:

    .. method:: stream_features[FeatureClass]

       Obtain the first feature XSO which matches the *FeatureClass*. If no
       such XSO is contained in the :class:`StreamFeatures` instance
       *stream_features*, :class:`KeyError` is raised.

    .. method:: stream_features[FeatureClass] = feature

       Replace the stream features belonging to the given *FeatureClass* with
       the *feature* XSO.

       If the *FeatureClass* does not match the type of the *feature* XSO, a
       :class:`TypeError` is raised.

       It is legal to leave the FeatureClass out by specifying ``...``
       instead. In that case, the class is auto-detected from the *feature*
       object assigned.

    .. method:: del stream_features[FeatureClass]

       If any feature of the given *FeatureClass* type is in the
       *stream_features*, they are all removed.

       Otherwise, :class:`KeyError` is raised, to stay consistent with other
       mapping-like types.

    .. automethod:: get_feature

    .. automethod:: has_feature

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

    def __setitem__(self, feature_cls, feature):
        if feature_cls is Ellipsis:
            feature_cls = type(feature)
        if not isinstance(feature, feature_cls):
            raise ValueError("incorrect XSO class supplied")
        self.features[feature_cls.TAG][:] = [feature]

    def __delitem__(self, feature_cls):
        items = self.features[feature_cls.TAG]
        if not items:
            raise KeyError(feature_cls)
        items.clear()

    def has_feature(self, feature_cls):
        """
        Return :data:`True` if the stream features contain a feature of the
        given *feature_cls* type. :data:`False` is returned otherwise.
        """
        return feature_cls.TAG in self.features

    def get_feature(self, feature_cls, default=None):
        """
        If a feature of the given *feature_cls* type is contained in the
        current stream features set, the first such instance is returned.

        Otherwise, *default* is returned.
        """
        try:
            return self[feature_cls]
        except KeyError:
            return default

    def __iter__(self):
        return itertools.chain(*self.features.values())


class SMXSO(xso.XSO):
    """
    Base class for stream-management related XSOs.

    This base class merely defines the namespaces to declare when serializing
    the data.
    """

    DECLARE_NS = {
        None: namespaces.stream_management
    }


class SMRequest(SMXSO):
    """
    A request for an SM acknowledgement (see :class:`SMAcknowledgement`).
    """
    TAG = (namespaces.stream_management, "r")


class SMAcknowledgement(SMXSO):
    """
    Response to a :class:`SMRequest`.

    .. attribute:: counter

       The counter as received by the remote side.

    """

    TAG = (namespaces.stream_management, "a")

    counter = xso.Attr(
        "h",
        type_=xso.Integer(),
        required=True,
    )


class SMEnable(SMXSO):
    """
    Request to enable stream management.

    .. attribute:: resume

       Set this to :data:`True` to request the capability of resuming the
       stream later.

    """

    TAG = (namespaces.stream_management, "enable")

    resume = xso.Attr(
        "resume",
        type_=xso.Bool(),
        default=False
    )


class SMEnabled(SMXSO):
    """
    Response to a :class:`SMEnable` request.

    .. attribute:: resume

       If :data:`True`, the peer allows resumption of the stream.

    .. attribute:: id_

       The SM-ID of the stream. This is required to resume later.

    .. attribute:: location

       A hostname-port pair which defines to which host the client shall
       connect to resume the stream.

    """
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
    """
    Request resumption of a previously interrupted SM stream.

    .. attribute:: counter

       Set this to the value of the local incoming stanza counter.

    .. attribute:: previd

       Set this to the SM-ID, as received in :class:`SMEnabled`.

    """

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
    """
    Notification that SM resumption was successful, in response to
    :class:`SMResume`.

    .. attribute:: counter

       The stanza counter of the remote side.

    .. attribute:: previd

       The SM-ID of the stream.

    """

    TAG = (namespaces.stream_management, "resumed")

    counter = xso.Attr(
        "h",
        type_=xso.Integer(),
        required=True)
    previd = xso.Attr(
        "previd",
        required=True)
