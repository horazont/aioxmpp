########################################################################
# File name: errors.py
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
:mod:`~aioxmpp.errors` --- Exception classes
############################################

Exception classes mapping to XMPP stream errors
===============================================

.. autoclass:: StreamError

.. autoclass:: StreamErrorCondition

Exception classes mapping to XMPP stanza errors
===============================================

.. autoclass:: StanzaError

.. autoclass:: XMPPError

.. currentmodule:: aioxmpp

.. autoclass:: ErrorCondition

.. autoclass:: XMPPAuthError

.. autoclass:: XMPPModifyError

.. autoclass:: XMPPCancelError

.. autoclass:: XMPPWaitError

.. autoclass:: XMPPContinueError

.. currentmodule:: aioxmpp.errors

.. autoclass:: ErroneousStanza

Stream negotiation exceptions
=============================

.. autoclass:: StreamNegotiationFailure

.. autoclass:: SecurityNegotiationFailure

.. autoclass:: SASLUnavailable

.. autoclass:: TLSFailure

.. autoclass:: TLSUnavailable

I18N exceptions
===============

.. autoclass:: UserError

.. autoclass:: UserValueError

Other exceptions
================

.. autoclass:: MultiOSError

.. autoclass:: GatherError

"""
import enum
import gettext
import warnings

from . import xso, i18n, structs

from .utils import namespaces


def format_error_text(
        condition,
        text=None,
        application_defined_condition=None):
    error_tag = xso.tag_to_str(condition.value)
    if application_defined_condition is not None:
        error_tag += "/{}".format(
            xso.tag_to_str(application_defined_condition.TAG)
        )
    if text:
        error_tag += " ({!r})".format(text)
    return error_tag


class ErrorCondition(structs.CompatibilityMixin, xso.XSOEnumMixin, enum.Enum):
    """
    Enumeration to represent a :rfc:`6120` stanza error condition. Please
    see :rfc:`6120`, section 8.3.3, for the semantics of the individual
    conditions.

    .. versionadded:: 0.10

    .. attribute:: BAD_REQUEST
        :annotation: = namespaces.stanzas, "bad-request"

    .. attribute:: CONFLICT
        :annotation: = namespaces.stanzas, "conflict"

    .. attribute:: FEATURE_NOT_IMPLEMENTED
        :annotation: = namespaces.stanzas, "feature-not-implemented"

    .. attribute:: FORBIDDEN
        :annotation: = namespaces.stanzas, "forbidden"

    .. attribute:: GONE
        :annotation: = namespaces.stanzas, "gone"

        .. attribute:: xso_class

            .. attribute:: new_address

                The text content of the ``<gone/>`` element represtenting the
                URI at which the entity can now be found.

                May be :data:`None` if there is no such URI.

    .. attribute:: INTERNAL_SERVER_ERROR
        :annotation: = namespaces.stanzas, "internal-server-error"

    .. attribute:: ITEM_NOT_FOUND
        :annotation: = namespaces.stanzas, "item-not-found"

    .. attribute:: JID_MALFORMED
        :annotation: = namespaces.stanzas, "jid-malformed"

    .. attribute:: NOT_ACCEPTABLE
        :annotation: = namespaces.stanzas, "not-acceptable"

    .. attribute:: NOT_ALLOWED
        :annotation: = namespaces.stanzas, "not-allowed"

    .. attribute:: NOT_AUTHORIZED
        :annotation: = namespaces.stanzas, "not-authorized"

    .. attribute:: POLICY_VIOLATION
        :annotation: = namespaces.stanzas, "policy-violation"

    .. attribute:: RECIPIENT_UNAVAILABLE
        :annotation: = namespaces.stanzas, "recipient-unavailable"

    .. attribute:: REDIRECT
        :annotation: = namespaces.stanzas, "redirect"

        .. attribute:: xso_class

            .. attribute:: new_address

                The text content of the ``<redirect/>`` element represtenting
                the URI at which the entity can currently be found.

                May be :data:`None` if there is no such URI.

    .. attribute:: REGISTRATION_REQUIRED
        :annotation: = namespaces.stanzas, "registration-required"

    .. attribute:: REMOTE_SERVER_NOT_FOUND
        :annotation: = namespaces.stanzas, "remote-server-not-found"

    .. attribute:: REMOTE_SERVER_TIMEOUT
        :annotation: = namespaces.stanzas, "remote-server-timeout"

    .. attribute:: RESOURCE_CONSTRAINT
        :annotation: = namespaces.stanzas, "resource-constraint"

    .. attribute:: SERVICE_UNAVAILABLE
        :annotation: = namespaces.stanzas, "service-unavailable"

    .. attribute:: SUBSCRIPTION_REQUIRED
        :annotation: = namespaces.stanzas, "subscription-required"

    .. attribute:: UNDEFINED_CONDITION
        :annotation: = namespaces.stanzas, "undefined-condition"

    .. attribute:: UNEXPECTED_REQUEST
        :annotation: = namespaces.stanzas, "unexpected-request"

    """

    BAD_REQUEST = (namespaces.stanzas, "bad-request")
    CONFLICT = (namespaces.stanzas, "conflict")
    FEATURE_NOT_IMPLEMENTED = (namespaces.stanzas, "feature-not-implemented")
    FORBIDDEN = (namespaces.stanzas, "forbidden")
    GONE = (namespaces.stanzas, "gone")
    INTERNAL_SERVER_ERROR = (namespaces.stanzas, "internal-server-error")
    ITEM_NOT_FOUND = (namespaces.stanzas, "item-not-found")
    JID_MALFORMED = (namespaces.stanzas, "jid-malformed")
    NOT_ACCEPTABLE = (namespaces.stanzas, "not-acceptable")
    NOT_ALLOWED = (namespaces.stanzas, "not-allowed")
    NOT_AUTHORIZED = (namespaces.stanzas, "not-authorized")
    POLICY_VIOLATION = (namespaces.stanzas, "policy-violation")
    RECIPIENT_UNAVAILABLE = (namespaces.stanzas, "recipient-unavailable")
    REDIRECT = (namespaces.stanzas, "redirect")
    REGISTRATION_REQUIRED = (namespaces.stanzas, "registration-required")
    REMOTE_SERVER_NOT_FOUND = (namespaces.stanzas, "remote-server-not-found")
    REMOTE_SERVER_TIMEOUT = (namespaces.stanzas, "remote-server-timeout")
    RESOURCE_CONSTRAINT = (namespaces.stanzas, "resource-constraint")
    SERVICE_UNAVAILABLE = (namespaces.stanzas, "service-unavailable")
    SUBSCRIPTION_REQUIRED = (namespaces.stanzas, "subscription-required")
    UNDEFINED_CONDITION = (namespaces.stanzas, "undefined-condition")
    UNEXPECTED_REQUEST = (namespaces.stanzas, "unexpected-request")


ErrorCondition.GONE.xso_class.new_address = xso.Text()
ErrorCondition.REDIRECT.xso_class.new_address = xso.Text()


class StreamErrorCondition(structs.CompatibilityMixin,
                           xso.XSOEnumMixin,
                           enum.Enum):
    """
    Enumeration to represent a :rfc:`6120` stream  error condition. Please
    see :rfc:`6120`, section 4.9.3, for the semantics of the individual
    conditions.

    .. versionadded:: 0.10

    .. attribute:: BAD_FORMAT
        :annotation: = (namespaces.streams, "bad-format")

    .. attribute:: BAD_NAMESPACE_PREFIX
        :annotation: = (namespaces.streams, "bad-namespace-prefix")

    .. attribute:: CONFLICT
        :annotation: = (namespaces.streams, "conflict")

    .. attribute:: CONNECTION_TIMEOUT
        :annotation: = (namespaces.streams, "connection-timeout")

    .. attribute:: HOST_GONE
        :annotation: = (namespaces.streams, "host-gone")

    .. attribute:: HOST_UNKNOWN
        :annotation: = (namespaces.streams, "host-unknown")

    .. attribute:: IMPROPER_ADDRESSING
        :annotation: = (namespaces.streams, "improper-addressing")

    .. attribute:: INTERNAL_SERVER_ERROR
        :annotation: = (namespaces.streams, "internal-server-error")

    .. attribute:: INVALID_FROM
        :annotation: = (namespaces.streams, "invalid-from")

    .. attribute:: INVALID_NAMESPACE
        :annotation: = (namespaces.streams, "invalid-namespace")

    .. attribute:: INVALID_XML
        :annotation: = (namespaces.streams, "invalid-xml")

    .. attribute:: NOT_AUTHORIZED
        :annotation: = (namespaces.streams, "not-authorized")

    .. attribute:: NOT_WELL_FORMED
        :annotation: = (namespaces.streams, "not-well-formed")

    .. attribute:: POLICY_VIOLATION
        :annotation: = (namespaces.streams, "policy-violation")

    .. attribute:: REMOTE_CONNECTION_FAILED
        :annotation: = (namespaces.streams, "remote-connection-failed")

    .. attribute:: RESET
        :annotation: = (namespaces.streams, "reset")

    .. attribute:: RESOURCE_CONSTRAINT
        :annotation: = (namespaces.streams, "resource-constraint")

    .. attribute:: RESTRICTED_XML
        :annotation: = (namespaces.streams, "restricted-xml")

    .. attribute:: SEE_OTHER_HOST
        :annotation: = (namespaces.streams, "see-other-host")

    .. attribute:: SYSTEM_SHUTDOWN
        :annotation: = (namespaces.streams, "system-shutdown")

    .. attribute:: UNDEFINED_CONDITION
        :annotation: = (namespaces.streams, "undefined-condition")

    .. attribute:: UNSUPPORTED_ENCODING
        :annotation: = (namespaces.streams, "unsupported-encoding")

    .. attribute:: UNSUPPORTED_FEATURE
        :annotation: = (namespaces.streams, "unsupported-feature")

    .. attribute:: UNSUPPORTED_STANZA_TYPE
        :annotation: = (namespaces.streams, "unsupported-stanza-type")

    .. attribute:: UNSUPPORTED_VERSION
        :annotation: = (namespaces.streams, "unsupported-version")

    """

    BAD_FORMAT = (namespaces.streams, "bad-format")
    BAD_NAMESPACE_PREFIX = (namespaces.streams, "bad-namespace-prefix")
    CONFLICT = (namespaces.streams, "conflict")
    CONNECTION_TIMEOUT = (namespaces.streams, "connection-timeout")
    HOST_GONE = (namespaces.streams, "host-gone")
    HOST_UNKNOWN = (namespaces.streams, "host-unknown")
    IMPROPER_ADDRESSING = (namespaces.streams, "improper-addressing")
    INTERNAL_SERVER_ERROR = (namespaces.streams, "internal-server-error")
    INVALID_FROM = (namespaces.streams, "invalid-from")
    INVALID_NAMESPACE = (namespaces.streams, "invalid-namespace")
    INVALID_XML = (namespaces.streams, "invalid-xml")
    NOT_AUTHORIZED = (namespaces.streams, "not-authorized")
    NOT_WELL_FORMED = (namespaces.streams, "not-well-formed")
    POLICY_VIOLATION = (namespaces.streams, "policy-violation")
    REMOTE_CONNECTION_FAILED = (namespaces.streams, "remote-connection-failed")
    RESET = (namespaces.streams, "reset")
    RESOURCE_CONSTRAINT = (namespaces.streams, "resource-constraint")
    RESTRICTED_XML = (namespaces.streams, "restricted-xml")
    SEE_OTHER_HOST = (namespaces.streams, "see-other-host")
    SYSTEM_SHUTDOWN = (namespaces.streams, "system-shutdown")
    UNDEFINED_CONDITION = (namespaces.streams, "undefined-condition")
    UNSUPPORTED_ENCODING = (namespaces.streams, "unsupported-encoding")
    UNSUPPORTED_FEATURE = (namespaces.streams, "unsupported-feature")
    UNSUPPORTED_STANZA_TYPE = (namespaces.streams, "unsupported-stanza-type")
    UNSUPPORTED_VERSION = (namespaces.streams, "unsupported-version")


StreamErrorCondition.SEE_OTHER_HOST.xso_class.new_address = xso.Text()


class StreamError(ConnectionError):
    def __init__(self, condition, text=None):
        if not isinstance(condition, StreamErrorCondition):
            condition = StreamErrorCondition(condition)
            warnings.warn(
                "as of aioxmpp 1.0, stream error conditions must be members "
                "of the aioxmpp.errors.StreamErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        super().__init__("stream error: {}".format(
            format_error_text(condition, text))
        )
        self.condition = condition
        self.text = text


class StanzaError(Exception):
    pass


class XMPPError(StanzaError):
    """
    Exception representing an error defined in the XMPP protocol.

    :param condition: The :rfc:`6120` defined error condition as enumeration
        member or :class:`aioxmpp.xso.XSO`
    :type condition: :class:`aioxmpp.ErrorCondition` or
        :class:`aioxmpp.xso.XSO`
    :param text: Optional human-readable text explaining the error
    :type text: :class:`str`
    :param application_defined_condition: Object describing the error in more
        detail
    :type application_defined_condition: :class:`aioxmpp.xso.XSO`

    .. versionchanged:: 0.10

        As of 0.10, `condition` should either be a
        :class:`aioxmpp.ErrorCondition` enumeration member or an XSO
        representing one of the error conditions.

        For compatibility, namespace-localpart tuples indicating the tag of
        the defined error condition are still accepted.

    .. deprecated:: 0.10

        Starting with aioxmpp 1.0, namespace-localpart tuples will not be
        accepted anymore. See the changelog for notes on the transition.

    .. attribute:: condition_obj

        The :class:`aioxmpp.XSO` which represents the error condition.

        .. versionadded:: 0.10

    .. autoattribute:: condition

    .. attribute:: text

        Optional human-readable text describing the error further.

        This is :data:`None` if the text is omitted.

    .. attribute:: application_defined_condition

        Optional :class:`aioxmpp.XSO` which further defines the error
        condition.

    Relevant subclasses:

    .. autosummary::

       aioxmpp.XMPPAuthError
       aioxmpp.XMPPModifyError
       aioxmpp.XMPPCancelError
       aioxmpp.XMPPContinueError
       aioxmpp.XMPPWaitError

    """

    TYPE = structs.ErrorType.CANCEL

    def __init__(self,
                 condition,
                 text=None,
                 application_defined_condition=None):
        if not isinstance(condition, (ErrorCondition, xso.XSO)):
            condition = ErrorCondition(condition)
            warnings.warn(
                "as of aioxmpp 1.0, error conditions must be members of the "
                "aioxmpp.ErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        super().__init__(format_error_text(
            condition.enum_member,
            text=text,
            application_defined_condition=application_defined_condition))
        self.condition_obj = condition.to_xso()
        self.text = text
        self.application_defined_condition = application_defined_condition

    @property
    def condition(self):
        """
        :class:`aioxmpp.ErrorCondition` enumeration member representing the
        error condition.
        """

        return self.condition_obj.enum_member


class XMPPWarning(XMPPError, UserWarning):
    TYPE = structs.ErrorType.CONTINUE


class XMPPAuthError(XMPPError, PermissionError):
    TYPE = structs.ErrorType.AUTH


class XMPPModifyError(XMPPError, ValueError):
    TYPE = structs.ErrorType.MODIFY


class XMPPCancelError(XMPPError):
    TYPE = structs.ErrorType.CANCEL


class XMPPWaitError(XMPPError):
    TYPE = structs.ErrorType.WAIT


class XMPPContinueError(XMPPWarning):
    TYPE = structs.ErrorType.CONTINUE


class ErroneousStanza(StanzaError):
    """
    This exception is thrown into listeners for IQ responses by
    :class:`aioxmpp.stream.StanzaStream` if a response for an IQ was received,
    but could not be decoded (due to malformed or unsupported payload).

    .. attribute:: partial_obj

       Contains the partially decoded stanza XSO. Do not rely on any members
       except those representing XML attributes (:attr:`~.StanzaBase.to`,
       :attr:`~.StanzaBase.from_`, :attr:`~.StanzaBase.type_`).

    """

    def __init__(self, partial_obj):
        super().__init__("erroneous stanza received: {!r}".format(
            partial_obj))
        self.partial_obj = partial_obj


class StreamNegotiationFailure(ConnectionError):
    pass


class SecurityNegotiationFailure(StreamNegotiationFailure):
    def __init__(self, xmpp_error,
                 kind="Security negotiation failure",
                 text=None):
        msg = "{}: {}".format(kind, xmpp_error)
        if text:
            msg += " ('{}')".format(text)
        super().__init__(msg)
        self.xmpp_error = xmpp_error
        self.text = text


class SASLUnavailable(SecurityNegotiationFailure):
    # we use this to tell the Client that SASL has not been available at all,
    # or that we could not agree on mechanisms.
    # it might be helpful to notify the peer about this before dying.
    pass


class TLSFailure(SecurityNegotiationFailure):
    def __init__(self, xmpp_error, text=None):
        super().__init__(xmpp_error, text=text, kind="TLS failure")


class TLSUnavailable(TLSFailure):
    pass


class UserError(Exception):
    """
    An exception subclass, which should be used as a mix-in.

    It is intended to be used for exceptions which may be user-facing, such as
    connection errors, value validation issues and the like.

    `localizable_string` must be a :class:`.i18n.LocalizableString`
    instance. The `args` and `kwargs` will be passed to
    :class:`.LocalizableString.localize` when either :func:`str` is called on
    the :class:`UserError` or :meth:`localize` is called.

    The :func:`str` is created using the default
    :class:`~.i18n.LocalizingFormatter` and a :class:`gettext.NullTranslations`
    instance. The point in time at which the default localizing formatter is
    created is unspecified.

    .. automethod:: localize

    """

    DEFAULT_FORMATTER = i18n.LocalizingFormatter()
    DEFAULT_TRANSLATIONS = gettext.NullTranslations()

    def __init__(self, localizable_string, *args, **kwargs):
        super().__init__()
        self._str = localizable_string.localize(
            self.DEFAULT_FORMATTER,
            self.DEFAULT_TRANSLATIONS,
            *args, **kwargs)
        self.localizable_string = localizable_string
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return str(self._str)

    def localize(self, formatter, translator):
        """
        Return a localized version of the `localizable_string` passed to the
        constructor. It is formatted using the `formatter` with the `args` and
        `kwargs` passed to the constructor of :class:`UserError`.
        """
        return self.localizable_string.localize(
            formatter,
            translator,
            *self.args,
            **self.kwargs
        )


class UserValueError(UserError, ValueError):
    """
    This is a :class:`ValueError` with :class:`UserError` mixed in.
    """


class MultiOSError(OSError):
    """
    Describe an error situation which has been caused by the sequential
    occurrence of multiple other `exceptions`.

    The `message` shall be descriptive and will be prepended to a concatenation
    of the error messages of the given `exceptions`.
    """

    def __init__(self, message, exceptions):
        flattened_exceptions = []
        for exc in exceptions:
            if hasattr(exc, "exceptions"):
                flattened_exceptions.extend(exc.exceptions)
            else:
                flattened_exceptions.append(exc)

        super().__init__(
            "{}: multiple errors: {}".format(
                message,
                ", ".join(map(str, flattened_exceptions))
            )
        )
        self.exceptions = flattened_exceptions


class GatherError(RuntimeError):
    """
    Describe an error situation which has been caused by the occurrence
    of multiple other `exceptions`.

    The `message` shall be descriptive and will be prepended to a concatenation
    of the error messages of the given `exceptions`.
    """

    def __init__(self, message, exceptions):
        flattened_exceptions = []
        for exc in exceptions:
            if hasattr(exc, "exceptions"):
                flattened_exceptions.extend(exc.exceptions)
            else:
                flattened_exceptions.append(exc)

        super().__init__(
            "{}: multiple errors: {}".format(
                message,
                ", ".join(map(str, flattened_exceptions))
            )
        )
        self.exceptions = flattened_exceptions
