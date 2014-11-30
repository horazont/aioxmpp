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

class XMPPError(Exception):
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
    pass

class XMPPAuthError(XMPPError, PermissionError):
    pass

class XMPPModifyError(XMPPError, ValueError):
    pass

class XMPPCancelError(XMPPError):
    pass

class XMPPWaitError(XMPPError):
    pass

class XMPPContinueError(XMPPWarning):
    pass

class StreamError(XMPPError, ConnectionError):
    @classmethod
    def format_text(cls, *args, **kwargs):
        return "stream error: {}".format(
            super().format_text(*args, **kwargs)
        )

error_type_map = {
    "auth": XMPPAuthError,
    "modify": XMPPModifyError,
    "cancel": XMPPCancelError,
    "wait": XMPPWaitError,
    "continue": XMPPContinueError,
}
