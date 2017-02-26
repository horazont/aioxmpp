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

Exception classes mapping to XMPP stanza errors
===============================================

.. autoclass:: StanzaError

.. autoclass:: XMPPError

.. currentmodule:: aioxmpp

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

"""
import gettext

from . import xso, i18n, structs


def format_error_text(
        condition,
        text=None,
        application_defined_condition=None):
    error_tag = xso.tag_to_str(condition)
    if application_defined_condition is not None:
        error_tag += "/{}".format(
            xso.tag_to_str(application_defined_condition.TAG)
        )
    if text:
        error_tag += " ({!r})".format(text)
    return error_tag


class StreamError(ConnectionError):
    def __init__(self, condition, text=None):
        super().__init__("stream error: {}".format(
            format_error_text(condition, text)))
        self.condition = condition
        self.text = text


class StanzaError(Exception):
    pass


class XMPPError(StanzaError):
    """
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
        super().__init__(format_error_text(
            condition,
            text=text,
            application_defined_condition=application_defined_condition))
        self.condition = condition
        self.text = text
        self.application_defined_condition = application_defined_condition


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
    # or that we could not agree on mechansims.
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
        consturctor. It is formatted using the `formatter` with the `args` and
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
