"""
:mod:`~aioxmpp.errors` --- Exception classes
############################################

Exception classes mapping to XMPP stream errors
===============================================

.. autoclass:: StreamError

Exception classes mapping to XMPP stanza errors
===============================================

.. autoclass:: XMPPError

.. autoclass:: XMPPAuthError

.. autoclass:: XMPPModifyError

.. autoclass:: XMPPCancelError

.. autoclass:: XMPPWaitError

.. autoclass:: XMPPContinueError

Stream negotiation exceptions
=============================

.. autoclass:: StreamNegotiationFailure

.. autoclass:: SecurityNegotiationFailure

.. autoclass:: SASLFailure

.. autoclass:: SASLUnavailable

.. autoclass:: TLSFailure

.. autoclass:: TLSUnavailable

.. autoclass:: AuthenticationFailure

I18N exception mixins
=====================

.. autoclass:: UserError

Other exceptions
================

.. autoclass:: MultiOSError

"""
import gettext

from . import xso, i18n


def format_error_text(
        condition,
        text=None,
        application_defined_condition=None):
    error_tag = xso.tag_to_str(condition)
    if application_defined_condition is not None:
        error_tag += "/{}".format(application_defined_condition.tag)
    if text:
        error_tag += " ({!r})".format(text)
    return error_tag


class StreamError(ConnectionError):
    def __init__(self, condition, text=None):
        super().__init__("stream error: {}".format(
            format_error_text(condition, text)))
        self.condition = condition
        self.text = text


class XMPPError(Exception):
    TYPE = "cancel"

    def __init__(self,
                 condition,
                 text=None,
                 application_defined_condition=None):
        super().__init__(format_error_text(
            condition,
            text=text,
            application_defined_condition=application_defined_condition))
        self.condition = condition
        self.text = text
        self.application_defined_condition = application_defined_condition


class XMPPWarning(XMPPError, UserWarning):
    TYPE = "continue"


class XMPPAuthError(XMPPError, PermissionError):
    TYPE = "auth"


class XMPPModifyError(XMPPError, ValueError):
    TYPE = "modify"


class XMPPCancelError(XMPPError):
    TYPE = "cancel"


class XMPPWaitError(XMPPError):
    TYPE = "wait"


class XMPPContinueError(XMPPWarning):
    TYPE = "continue"


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


class SASLFailure(SecurityNegotiationFailure):
    def __init__(self, xmpp_error, text=None):
        super().__init__(xmpp_error, text=text, kind="SASL failure")

    def promote_to_authentication_failure(self):
        return AuthenticationFailure(
            xmpp_error=self.xmpp_error,
            text=self.text)


class SASLUnavailable(SASLFailure):
    # we use this to tell the Client that SASL has not been available at all,
    # or that we could not agree on mechansims.
    # it might be helpful to notify the peer about this before dying.
    pass


class TLSFailure(SecurityNegotiationFailure):
    def __init__(self, xmpp_error, text=None):
        super().__init__(xmpp_error, text=text, kind="TLS failure")


class TLSUnavailable(TLSFailure):
    pass


class AuthenticationFailure(SecurityNegotiationFailure):
    def __init__(self, xmpp_error, text=None):
        super().__init__(xmpp_error, text=text, kind="Authentication failure")


error_type_map = {
    "auth": XMPPAuthError,
    "modify": XMPPModifyError,
    "cancel": XMPPCancelError,
    "wait": XMPPWaitError,
    "continue": XMPPContinueError,
}


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
        consturctor. It is formatted using the `formatter` with the `args` and
        `kwargs` passed to the constructor of :class:`UserError`.
        """
        return self.localizable_string.localize(
            formatter,
            translator,
            *self.args,
            **self.kwargs
        )


class MultiOSError(OSError):
    """
    Describe an error situation which has been caused by the sequential
    occurence of multiple other `exceptions`.

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
