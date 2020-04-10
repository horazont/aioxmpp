########################################################################
# File name: nonza.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.nonza` --- Non-stanza stream-level XSOs (Nonzas)
###############################################################

This module contains XSO models for stream-level elements which are not
stanzas. Since :xep:`0360`, these are called "nonzas".

.. versionchanged:: 0.5

   Before version 0.5, this module was called :mod:`aioxmpp.stream_xsos`.

General XSOs
============

.. autoclass:: StreamError()

.. autoclass:: StreamFeatures()

StartTLS related XSOs
=====================

.. autoclass:: StartTLSXSO()

.. autoclass:: StartTLSFeature()

.. autoclass:: StartTLS()

.. autoclass:: StartTLSProceed()

.. autoclass:: StartTLSFailure()

SASL related XSOs
=================

.. autoclass:: SASLXSO

.. autoclass:: SASLAuth

.. autoclass:: SASLChallenge

.. autoclass:: SASLResponse

.. autoclass:: SASLFailure

.. autoclass:: SASLSuccess

.. autoclass:: SASLAbort

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
import warnings

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

    DECLARE_NS = {}

    text = xso.ChildText(
        tag=(namespaces.streams, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None
    )

    condition_obj = xso.Child(
        [member.xso_class for member in errors.StreamErrorCondition],
        required=True,
    )

    def __init__(self,
                 condition=errors.StreamErrorCondition.UNDEFINED_CONDITION,
                 text=None):
        super().__init__()
        if not isinstance(condition, errors.StreamErrorCondition):
            condition = errors.StreamErrorCondition(condition)
            warnings.warn(
                "as of aioxmpp 1.0, stream error conditions must be members "
                "of the aioxmpp.errors.StreamErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        self.condition_obj = condition.xso_class()
        self.text = text

    @property
    def condition(self):
        return self.condition_obj.enum_member

    @condition.setter
    def condition(self, value):
        if not isinstance(value, errors.StreamErrorCondition):
            value = errors.StreamErrorCondition(value)
            warnings.warn(
                "as of aioxmpp 1.0, stream error conditions must be members "
                "of the aioxmpp.errors.StreamErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        if self.condition == value:
            return
        self.condition_obj = value.xso_class()

    @classmethod
    def from_exception(cls, exc):
        instance = cls()
        instance.text = exc.text
        instance.condition = exc.condition
        return instance

    def to_exception(self):
        return errors.StreamError(
            condition=self.condition,
            text=self.text
        )


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

       Obtain the first feature XSO which matches the `FeatureClass`. If no
       such XSO is contained in the :class:`StreamFeatures` instance
       `stream_features`, :class:`KeyError` is raised.

    .. method:: stream_features[FeatureClass] = feature

       Replace the stream features belonging to the given `FeatureClass` with
       the `feature` XSO.

       If the `FeatureClass` does not match the type of the `feature` XSO, a
       :class:`TypeError` is raised.

       It is legal to leave the FeatureClass out by specifying ``...``
       instead. In that case, the class is auto-detected from the `feature`
       object assigned.

    .. method:: del stream_features[FeatureClass]

       If any feature of the given `FeatureClass` type is in the
       `stream_features`, they are all removed.

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
    cruft = xso.Collector()

    @classmethod
    def as_feature_class(cls, other_cls):
        cls.register_child(cls.features, other_cls)
        return other_cls

    @classmethod
    def is_feature(cls, other_cls):
        return (cls.CHILD_MAP.get(other_cls.TAG, None) is
                cls.features.xq_descriptor)

    def __getitem__(self, feature_cls):
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

    def __contains__(self, other):
        raise TypeError("membership test not supported")

    def has_feature(self, feature_cls):
        """
        Return :data:`True` if the stream features contain a feature of the
        given `feature_cls` type. :data:`False` is returned otherwise.
        """
        return feature_cls.TAG in self.features

    def get_feature(self, feature_cls, default=None):
        """
        If a feature of the given `feature_cls` type is contained in the
        current stream features set, the first such instance is returned.

        Otherwise, `default` is returned.
        """
        try:
            return self[feature_cls]
        except KeyError:
            return default

    def __iter__(self):
        return itertools.chain(*self.features.values())


class StartTLSXSO(xso.XSO):
    """
    Base class for starttls related XSOs.

    This base class merely defines the namespaces to declare when serialising
    the derived XSOs
    """

    DECLARE_NS = {None: namespaces.starttls}


@StreamFeatures.as_feature_class
class StartTLSFeature(StartTLSXSO):
    """
    Start TLS capability stream feature
    """

    TAG = (namespaces.starttls, "starttls")

    class Required(xso.XSO):
        TAG = (namespaces.starttls, "required")

    required = xso.Child([Required], required=False)


class StartTLS(StartTLSXSO):
    """
    XSO indicating that the client wants to start TLS now.
    """

    TAG = (namespaces.starttls, "starttls")


class StartTLSFailure(StartTLSXSO):
    """
    Server refusing to start TLS.
    """
    TAG = (namespaces.starttls, "failure")


class StartTLSProceed(StartTLSXSO):
    """
    Server allows start TLS.
    """
    TAG = (namespaces.starttls, "proceed")


class SASLXSO(xso.XSO):
    DECLARE_NS = {
        None: namespaces.sasl
    }


class SASLAuth(SASLXSO):
    """
    Start SASL authentication.

    .. attribute:: mechanism

       The mechanism to authenticate with.

    .. attribute:: payload

       For mechanisms which use an initial client-supplied payload, this can be
       a string. It is automatically encoded as base64 according to the XMPP
       SASL specification.

    """

    TAG = (namespaces.sasl, "auth")

    mechanism = xso.Attr("mechanism")
    payload = xso.Text(
        type_=xso.Base64Binary(empty_as_equal=True),
        default=None
    )

    def __init__(self, mechanism, payload=None):
        super().__init__()
        self.mechanism = mechanism
        self.payload = payload


class SASLChallenge(SASLXSO):
    """
    A SASL challenge.

    .. attribute:: payload

       The (decoded) SASL payload as :class:`bytes`. Base64 en/decoding is
       handled by the XSO stack.

    """

    TAG = (namespaces.sasl, "challenge")

    payload = xso.Text(
        type_=xso.Base64Binary(empty_as_equal=True),
    )

    def __init__(self, payload):
        super().__init__()
        self.payload = payload


class SASLResponse(SASLXSO):
    """
    A SASL response.

    .. attribute:: payload

       The (decoded) SASL payload as :class:`bytes`. Base64 en/decoding is
       handled by the XSO stack.

    """

    TAG = (namespaces.sasl, "response")

    payload = xso.Text(
        type_=xso.Base64Binary(empty_as_equal=True)
    )

    def __init__(self, payload):
        super().__init__()
        self.payload = payload


class SASLFailure(SASLXSO):
    """
    Indication of SASL failure.

    .. attribute:: condition

       The condition which caused the authentication to fail.

    .. attribute:: text

       Optional human-readable text.

    """

    TAG = (namespaces.sasl, "failure")

    condition = xso.ChildTag(
        tags=[
            "aborted",
            "account-disabled",
            "credentials-expired",
            "encryption-required",
            "incorrect-encoding",
            "invalid-authzid",
            "invalid-mechanism",
            "malformed-request",
            "mechanism-too-weak",
            "not-authorized",
            "temporary-auth-failure",
        ],
        default_ns=namespaces.sasl,
        allow_none=False,
        declare_prefix=None,
    )

    text = xso.ChildText(
        (namespaces.sasl, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None
    )

    def __init__(self, condition=(namespaces.sasl, "temporary-auth-failure")):
        super().__init__()
        self.condition = condition


class SASLSuccess(SASLXSO):
    """
    Indication of SASL success, with optional final payload supplied by the
    server.

    .. attribute:: payload

       The (decoded) SASL payload. Base64 en/decoding is handled by the XSO
       stack.

    """

    TAG = (namespaces.sasl, "success")

    payload = xso.Text(
        type_=xso.Base64Binary(empty_as_equal=True),
        default=None
    )


class SASLAbort(SASLXSO):
    """
    Request to abort the SASL authentication.
    """
    TAG = (namespaces.sasl, "abort")


class SMXSO(xso.XSO):
    """
    Base class for stream-management related XSOs.

    This base class merely defines the namespaces to declare when serializing
    the data.
    """

    DECLARE_NS = {
        None: namespaces.stream_management
    }


@StreamFeatures.as_feature_class
class StreamManagementFeature(SMXSO):
    """
    Stream management stream feature
    """
    TAG = (namespaces.stream_management, "sm")

    class Required(xso.XSO):
        TAG = (namespaces.stream_management, "required")

    class Optional(xso.XSO):
        TAG = (namespaces.stream_management, "optional")

    required = xso.Child([Required])
    optional = xso.Child([Optional])


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
        type_=xso.Integer()
    )

    def __init__(self, counter=0, **kwargs):
        super().__init__(**kwargs)
        self.counter = counter

    def __repr__(self):
        return "<{}.{} counter={} at 0x{:x}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.counter,
            id(self),
        )


class SMEnable(SMXSO):
    """
    Request to enable stream management.

    .. attribute:: resume

       Set this to :data:`True` to request the capability of resuming the
       stream later.

    .. attribute:: max_

        Maximum time, as integer in seconds, for which the stream should be
        resumable after the connection dropped. Only relevant if
        :attr:`resume` is true and may be overridden by the server.

        .. versionadded:: 0.9

    """

    TAG = (namespaces.stream_management, "enable")

    resume = xso.Attr(
        "resume",
        type_=xso.Bool(),
        default=False
    )

    max_ = xso.Attr(
        "max",
        type_=xso.Integer(),
        default=None,
        validate=xso.ValidateMode.ALWAYS,
        validator=xso.NumericRange(min_=0),
    )

    def __init__(self, resume=False, max_=None):
        super().__init__()
        self.resume = resume
        self.max_ = max_

    def __repr__(self):
        return "<{}.{} resume={} max={} at 0x{:x}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.resume,
            self.max_,
            id(self),
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

    .. attribute:: max_

        Maximum time, as integer in seconds, for which the stream will be
        resumable after the connection dropped. Only relevant if
        :attr:`resume` is true.

    """
    TAG = (namespaces.stream_management, "enabled")

    resume = xso.Attr(
        "resume",
        type_=xso.Bool(),
        default=False
    )

    id_ = xso.Attr("id", default=None)

    location = xso.Attr(
        "location",
        type_=xso.ConnectionLocation(),
        default=None
    )

    max_ = xso.Attr(
        "max",
        type_=xso.Integer(),
        default=None,
        validate=xso.ValidateMode.ALWAYS,
        validator=xso.NumericRange(min_=0),
    )

    def __init__(self,
                 resume=False,
                 id_=None,
                 location=None,
                 max_=None):
        super().__init__()
        self.resume = resume
        self.id_ = id_
        self.location = location
        self.max_ = max_

    def __repr__(self):
        return (
            "<{}.{} resume={} id={!r} location={!r} max={} at 0x{:x}>".format(
                type(self).__module__,
                type(self).__qualname__,
                self.resume,
                self.id_,
                self.location,
                self.max_,
                id(self),
            )
        )


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
        type_=xso.Integer()
    )
    previd = xso.Attr("previd")

    def __init__(self, counter, previd):
        super().__init__()
        self.counter = counter
        self.previd = previd

    def __repr__(self):
        return "<{}.{} counter={} previd={!r} at 0x{:x}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.counter,
            self.previd,
            id(self),
        )


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
        type_=xso.Integer())
    previd = xso.Attr("previd")

    def __init__(self, counter, previd):
        super().__init__()
        self.counter = counter
        self.previd = previd

    def __repr__(self):
        return "<{}.{} counter={} previd={!r} at 0x{:x}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.counter,
            self.previd,
            id(self),
        )


class SMFailed(SMXSO):
    """
    Server response to :class:`SMEnable` or :class:`SMResume` if stream
    management fails.
    """
    TAG = (namespaces.stream_management, "failed")

    condition = xso.Child(
        [member.xso_class for member in errors.ErrorCondition],
        required=True,
    )

    counter = xso.Attr(
        "h",
        default=None,
        type_=xso.Integer(),
    )

    def __init__(self,
                 condition=errors.ErrorCondition.UNDEFINED_CONDITION,
                 counter=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.condition = condition.to_xso()
        self.counter = counter

    def __repr__(self):
        return "<{}.{} condition={!r} at 0x{:x}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.condition,
            id(self),
        )
