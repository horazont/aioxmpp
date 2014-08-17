class XMPPError(Exception):
    @classmethod
    def format_text(cls,
                    error_tag,
                    text=None,
                    application_defined_condition=None):
        if application_defined_condition:
            error_tag += "/{}".format(application_defined_condition)
        if text:
            error_tag += " ({})".format(text)
        return error_tag

    def __init__(self,
                 error_tag,
                 text=None,
                 application_defined_condition=None):
        super().__init__(self.format_text(
            error_tag,
            text=text,
            application_defined_condition=application_defined_condition))
        self.error_tag = error_tag
        self.text = text
        self.application_defined_condition = application_defined_condition

class StreamError(XMPPError, ConnectionError):
    @classmethod
    def format_text(cls, *args, **kwargs):
        return "stream error: {}".format(
            super().format_text(*args, **kwargs)
        )
