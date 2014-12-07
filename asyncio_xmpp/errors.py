def format_error_text(
        error_tag,
        text=None,
        application_defined_condition=None):
    if application_defined_condition is not None:
        error_tag += "/{}".format(application_defined_condition.tag)
    if text:
        error_tag += " ({})".format(text)
    return error_tag

class XMPPWarning(UserWarning):
    def __init__(self,
                 error_tag,
                 text=None,
                 application_defined_condition=None):
        super().__init__(format_error_text(
            error_tag, text, application_defined_condition))
        self.error_tag = error_tag
        self.text = text
        self.application_defined_condition = application_defined_condition

class SendStreamError(Exception):
    def __init__(self, error_tag, text=None):
        super().__init__("Going to send a stream:error (seeing this exception is"
                         " a bug)")
        self.error_tag = error_tag
        self.text = text

class XMPPError(Exception):
    TYPE = "cancel"

    def __init__(self,
                 error_tag,
                 text=None,
                 application_defined_condition=None):
        super().__init__(format_error_text(
            error_tag,
            text=text,
            application_defined_condition=application_defined_condition))
        self.error_tag = error_tag
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

class StreamError(XMPPError, ConnectionError):
    @classmethod
    def format_text(cls, *args, **kwargs):
        return "stream error: {}".format(
            super().format_text(*args, **kwargs)
        )

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
    # we use this to tell the Client that SASL has not been available at all, or
    # that we could not agree on mechansims.
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
