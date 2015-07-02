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

Other exceptions
================

.. autoclass:: MultiOSError

"""

from . import xso


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
