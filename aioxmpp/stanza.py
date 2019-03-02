########################################################################
# File name: stanza.py
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
:mod:`~aioxmpp.stanza` --- XSOs for dealing with stanzas
########################################################

This module provides :class:`~.xso.XSO` subclasses which provide access to
stanzas and their RFC6120-defined child elements.

Much of what you’ll read here makes much more sense if you have read
`RFC 6120 <https://tools.ietf.org/html/rfc6120#section-4.7.1>`_.

Top-level classes
=================

.. autoclass:: StanzaBase(*[, from_][, to][, id_])

.. currentmodule:: aioxmpp

.. autoclass:: Message(*[, from_][, to][, id_][, type_])

.. autoclass:: IQ(*[, from_][, to][, id_][, type_])

.. autoclass:: Presence(*[, from_][, to][, id_][, type_])

.. currentmodule:: aioxmpp.stanza

Payload classes
===============

For :class:`Presence` and :class:`Message` as well as :class:`IQ` errors, the
standardized payloads also have classes which are used as values for the
attributes:

.. autoclass:: Error(*[, condition][, type_][, text])

.. autofunction:: make_application_error

For messages
------------

.. autoclass:: Thread()

.. autoclass:: Subject()

.. autoclass:: Body()

For presence’
-------------

.. autoclass:: Status()

Exceptions
==========

.. autoclass:: PayloadError

.. autoclass:: PayloadParsingError

.. autoclass:: UnknownIQPayload

Module Level Constants
======================

.. autodata:: RANDOM_ID_BYTES
"""
import random
import warnings

from . import xso, errors, structs

from .utils import namespaces, to_nmtoken

#: The number of bytes of randomness used when generating stanza IDs.
RANDOM_ID_BYTES = 120 // 8


def _safe_format_attr(obj, attr_name):
    try:
        value = getattr(obj, attr_name)
    except AttributeError as exc:
        msg = str(exc)
        if msg.startswith("attribute value is incomplete"):
            return "<incomplete>"
        else:
            return "<unset>"
    if isinstance(value, structs.JID):
        return "'{!s}'".format(value)
    return repr(value)


class StanzaError(Exception):
    """
    Base class for exceptions raised when stanzas cannot be processed.

    .. attribute:: partial_obj

       The :class:`StanzaBase` instance which has not been parsed completely.
       There are no guarantees about any attributes. This is, if at all, only
       useful for logging.

    .. attribute:: ev_args

       The XSO parsing event arguments which caused the parsing to fail.

    .. attribute:: descriptor

       The descriptor whose parsing function raised the exception.
    """

    def __init__(self, msg, partial_obj, ev_args, descriptor):
        super().__init__(msg)
        self.ev_args = ev_args
        self.partial_obj = partial_obj
        self.descriptor = descriptor


class PayloadError(StanzaError):
    """
    Base class for exceptions raised when stanza payloads cannot be processed.

    This is a subclass of :class:`StanzaError`. :attr:`partial_obj` has the
    additional guarantee that the attributes :attr:`StanzaBase.from_`,
    :attr:`StanzaBase.to`, :attr:`StanzaBase.type_` and :attr:`StanzaBase.id_`
    are already parsed completely.
    """


class PayloadParsingError(PayloadError):
    """
    A constraint of a sub-object was not fulfilled and the stanza being
    processed is illegal. The partially parsed stanza object is provided in
    :attr:`~PayloadError.partial_obj`.

    This is a subclass of :class:`PayloadError`.
    """

    def __init__(self, partial_obj, ev_args, descriptor):
        super().__init__(
            "parsing of payload {} failed".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args,
            descriptor)


class UnknownIQPayload(PayloadError):
    """
    The payload of an IQ object is unknown. The partial object with attributes
    but without payload is available through :attr:`~PayloadError.partial_obj`.
    """

    def __init__(self, partial_obj, ev_args, descriptor):
        super().__init__(
            "unknown payload {} on iq".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args,
            descriptor
        )


class Error(xso.XSO):
    """
    An XMPP stanza error. The keyword arguments can be used to initialize the
    attributes of the :class:`Error`.

    :param condition: The error condition as enumeration member or XSO.
    :type condition: :class:`aioxmpp.ErrorCondition` or
        :class:`aioxmpp.xso.XSO`
    :param type_: The type of the error
    :type type_: :class:`aioxmpp.ErrorType`
    :param text: The optional error text
    :type text: :class:`str` or :data:`None`

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are enumerated in
       :class:`~.ErrorType`.

       .. versionchanged:: 0.7

          Starting with 0.7, the enumeration :class:`~.ErrorType` is
          used. Before, strings equal to the XML attribute value character data
          were used (``"cancel"``, ``"auth"``, and so on).

          As of 0.7, setting the string equivalents is still supported.
          However, reading from the attribute always returns the corresponding
          enumeration members (which still compare equal to their string
          equivalents).

       .. deprecated:: 0.7

          The use of the aforementioned string values is deprecated and will
          lead to :exc:`TypeError` and/or :exc:`ValueError` being raised when
          they are written to this attribute. See the Changelog for
          :ref:`api-changelog-0.7` for further details on how to upgrade your
          code efficiently.

    .. attribute:: condition

       The standard defined condition which triggered the error. Possible
       values can be determined by looking at the RFC or the source.

       This is a member of the :class:`aioxmpp.ErrorCondition` enumeration.

       .. versionchanged:: 0.10

          Starting with 0.10, the enumeration :class:`aioxmpp.ErrorCondition`
          is used. Before, tuples equal to the tags of the child elements were
          used (e.g. ``(namespaces.stanzas, "bad-request")``).

          As of 0.10, setting the tuple equivalents is still supported.
          However, reading from the attribute always returns the corresponding
          enumeration members (which still compare equal to their tuple
          equivalents).

       .. deprecated:: 0.10

          The use of the aforementioned tuple values is deprecated and will
          lead to :exc:`TypeError` and/or :exc:`ValueError` being raised when
          they are written to this attribute. See the changelog for notes on
          the transition.

    .. attribute:: condition_obj

        An XSO object representing the child element representing the
        :rfc:`6120` defined error condition.

        .. versionadded:: 0.10

    .. attribute:: text

       The descriptive error text which is part of the error stanza, if any
       (otherwise :data:`None`).

    Any child elements unknown to the XSO are dropped. This is to support
    application-specific conditions used by other applications. To register
    your own use :meth:`.xso.XSO.register_child` on
    :attr:`application_condition`:

    .. attribute:: application_condition

       Optional child :class:`~aioxmpp.xso.XSO` which describes the error
       condition in more application specific detail.

    To register a class as application condition, use:

    .. automethod:: as_application_condition

    Conversion to and from exceptions is supported with the following methods:

    .. automethod:: to_exception

    .. automethod:: from_exception

    """

    TAG = (namespaces.client, "error")

    DECLARE_NS = {}

    EXCEPTION_CLS_MAP = {
        structs.ErrorType.MODIFY: errors.XMPPModifyError,
        structs.ErrorType.CANCEL: errors.XMPPCancelError,
        structs.ErrorType.AUTH: errors.XMPPAuthError,
        structs.ErrorType.WAIT: errors.XMPPWaitError,
        structs.ErrorType.CONTINUE: errors.XMPPContinueError,
    }

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP

    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    type_ = xso.Attr(
        tag="type",
        type_=xso.EnumCDataType(
            structs.ErrorType,
            allow_coerce=True,
            deprecate_coerce=True,
        ),
    )

    text = xso.ChildText(
        tag=(namespaces.stanzas, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None
    )

    condition_obj = xso.Child(
        [member.xso_class for member in errors.ErrorCondition],
        required=True,
    )

    application_condition = xso.Child([], required=False)

    def __init__(self,
                 condition=errors.ErrorCondition.UNDEFINED_CONDITION,
                 type_=structs.ErrorType.CANCEL,
                 text=None):
        super().__init__()
        if not isinstance(condition, (errors.ErrorCondition, xso.XSO)):
            condition = errors.ErrorCondition(condition)
            warnings.warn(
                "as of aioxmpp 1.0, error conditions must be members of the "
                "aioxmpp.ErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        self.condition_obj = condition.to_xso()
        self.type_ = type_
        self.text = text

    @property
    def condition(self):
        return self.condition_obj.enum_member

    @condition.setter
    def condition(self, value):
        if not isinstance(value, errors.ErrorCondition):
            value = errors.ErrorCondition(value)
            warnings.warn(
                "as of aioxmpp 1.0, error conditions must be members of the "
                "aioxmpp.ErrorCondition enumeration",
                DeprecationWarning,
                stacklevel=2,
            )

        if self.condition == value:
            return

        self.condition_obj = value.xso_class()

    @classmethod
    def from_exception(cls, exc):
        """
        Construct a new :class:`Error` payload from the attributes of the
        exception.

        :param exc: The exception to convert
        :type exc: :class:`aioxmpp.errors.XMPPError`
        :result: Newly constructed error payload
        :rtype: :class:`Error`

        .. versionchanged:: 0.10

            The :attr:`aioxmpp.XMPPError.application_defined_condition` is now
            taken over into the result.
        """
        result = cls(
            condition=exc.condition,
            type_=exc.TYPE,
            text=exc.text
        )
        result.application_condition = exc.application_defined_condition
        return result

    def to_exception(self):
        """
        Convert the error payload to a :class:`~aioxmpp.errors.XMPPError`
        subclass.

        :result: Newly constructed exception
        :rtype: :class:`aioxmpp.errors.XMPPError`

        The exact type of the result depends on the :attr:`type_` (see
        :class:`~aioxmpp.errors.XMPPError` about the existing subclasses).

        The :attr:`condition_obj`, :attr:`text` and
        :attr:`application_condition` are transferred to the respective
        attributes of the :class:`~aioxmpp.errors.XMPPError`.
        """
        if hasattr(self.application_condition, "to_exception"):
            result = self.application_condition.to_exception(self.type_)
            if isinstance(result, Exception):
                return result

        return self.EXCEPTION_CLS_MAP[self.type_](
            condition=self.condition_obj,
            text=self.text,
            application_defined_condition=self.application_condition,
        )

    @classmethod
    def as_application_condition(cls, other_cls):
        """
        Register `other_cls` as child class for the
        :attr:`application_condition` attribute. Doing so will allows the class
        to be parsed instead of being discarded.


        .. seealso::

           :func:`make_application_error` --- creates and automatically
           registers a new application error condition.

        """
        cls.register_child(cls.application_condition, other_cls)
        return other_cls

    def __repr__(self):
        payload = ""
        if self.text:
            payload = " text={!r}".format(self.text)

        return "<{} type={!r}{}>".format(
            self.condition.value[1],
            self.type_,
            payload)


class StanzaBase(xso.XSO):
    """
    Base for all stanza classes. Usually, you will use the derived classes:

    .. autosummary::
       :nosignatures:

       Message
       Presence
       IQ

    However, some common attributes are defined in this base class:

    .. attribute:: from_

       The :class:`~aioxmpp.JID` of the sending entity.

    .. attribute:: to

       The :class:`~aioxmpp.JID` of the receiving entity.

    .. attribute:: lang

       The ``xml:lang`` value as :class:`~aioxmpp.structs.LanguageTag`.

    .. attribute:: error

       Either :data:`None` or a :class:`Error` instance.

    .. note::

       The :attr:`id_` attribute is not defined in :class:`StanzaBase` as
       different stanza classes have different requirements with respect to
       presence of that attribute.

    In addition to these attributes, common methods needed are also provided:

    .. automethod:: autoset_id

    .. automethod:: make_error

    """

    DECLARE_NS = {}

    from_ = xso.Attr(
        tag="from",
        type_=xso.JID(),
        default=None)
    to = xso.Attr(
        tag="to",
        type_=xso.JID(),
        default=None)

    lang = xso.LangAttr(
        tag=(namespaces.xml, "lang")
    )

    error = xso.Child([Error])

    def __init__(self, *, from_=None, to=None, id_=None):
        super().__init__()
        if from_ is not None:
            self.from_ = from_
        if to is not None:
            self.to = to
        if id_ is not None:
            self.id_ = id_

    def autoset_id(self):
        """
        If the :attr:`id_` already has a non-false (false is also the empty
        string!) value, this method is a no-op.

        Otherwise, the :attr:`id_` attribute is filled with
        :data:`RANDOM_ID_BYTES` of random data, encoded by
        :func:`aioxmpp.utils.to_nmtoken`.

        .. note::

           This method only works on subclasses of :class:`StanzaBase` which
           define the :attr:`id_` attribute.
        """
        try:
            self.id_
        except AttributeError:
            pass
        else:
            if self.id_:
                return

        self.id_ = to_nmtoken(random.getrandbits(8*RANDOM_ID_BYTES))

    def _make_reply(self, type_):
        obj = type(self)(type_)
        obj.from_ = self.to
        obj.to = self.from_
        obj.id_ = self.id_
        return obj

    def make_error(self, error):
        """
        Create a new instance of this stanza (this directly uses
        ``type(self)``, so also works for subclasses without extra care) which
        has the given `error` value set as :attr:`error`.

        In addition, the :attr:`id_`, :attr:`from_` and :attr:`to` values are
        transferred from the original (with from and to being swapped). Also,
        the :attr:`type_` is set to ``"error"``.
        """
        obj = type(self)(
            from_=self.to,
            to=self.from_,
            # because flat is better than nested (sarcasm)
            type_=type(self).type_.type_.enum_class.ERROR,
        )
        obj.id_ = self.id_
        obj.error = error
        return obj

    def xso_error_handler(self, descriptor, ev_args, exc_info):
        raise StanzaError(
            "failed to parse stanza",
            self,
            ev_args,
            descriptor
        )


class Thread(xso.XSO):
    """
    Threading information, consisting of a thread identifier and an optional
    parent thread identifier.

    .. attribute:: identifier

       Identifier of the thread

    .. attribute:: parent

       :data:`None` or the identifier of the parent thread.

    """
    TAG = (namespaces.client, "thread")

    identifier = xso.Text(
        validator=xso.Nmtoken(),
        validate=xso.ValidateMode.FROM_CODE)
    parent = xso.Attr(
        tag="parent",
        validator=xso.Nmtoken(),
        validate=xso.ValidateMode.FROM_CODE,
        default=None
    )


class Body(xso.AbstractTextChild):
    """
    The textual body of a :class:`Message` stanza.

    While it might seem intuitive to refer to the body using a
    :class:`~.xso.ChildText` descriptor, the fact that there might be multiple
    texts for different languages justifies the use of a separate class.

    .. attribute:: lang

       The ``xml:lang`` of this body part, as :class:`~.structs.LanguageTag`.

    .. attribute:: text

       The textual content of the body.

    """
    TAG = (namespaces.client, "body")


class Subject(xso.AbstractTextChild):
    """
    The subject of a :class:`Message` stanza.

    While it might seem intuitive to refer to the subject using a
    :class:`~.xso.ChildText` descriptor, the fact that there might be multiple
    texts for different languages justifies the use of a separate class.

    .. attribute:: lang

       The ``xml:lang`` of this subject part, as
       :class:`~.structs.LanguageTag`.

    .. attribute:: text

       The textual content of the subject

    """
    TAG = (namespaces.client, "subject")


class Message(StanzaBase):
    """
    An XMPP message stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`Message`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are enumerated in
       :class:`~.MessageType`.

       .. versionchanged:: 0.7

          Starting with 0.7, the enumeration :class:`~.MessageType` is
          used. Before, strings equal to the XML attribute value character data
          were used (``"chat"``, ``"headline"``, and so on).

          As of 0.7, setting the string equivalents is still supported.
          However, reading from the attribute always returns the corresponding
          enumeration members (which still compare equal to their string
          equivalents).

       .. deprecated:: 0.7

          The use of the aforementioned string values is deprecated and will
          lead to :exc:`TypeError` and/or :exc:`ValueError` being raised when
          they are written to this attribute. See the Changelog for
          :ref:`api-changelog-0.7` for further details on how to upgrade your
          code efficiently.

    .. attribute:: body

       A :class:`~.structs.LanguageMap` mapping the languages of the different
       body elements to their text.

       .. versionchanged:: 0.5

          Before 0.5, this was a :class:`~aioxmpp.xso.model.XSOList`.

    .. attribute:: subject

       A :class:`~.structs.LanguageMap` mapping the languages of the different
       subject elements to their text.

       .. versionchanged:: 0.5

          Before 0.5, this was a :class:`~aioxmpp.xso.model.XSOList`.

    .. attribute:: thread

       A :class:`Thread` instance representing the threading information
       attached to the message or :data:`None` if no threading information is
       attached.

    Note that some attributes are inherited from :class:`StanzaBase`:

    ========================= =======================================
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.lang`  ``xml:lang`` value
    :attr:`~StanzaBase.error` :class:`Error` instance
    ========================= =======================================

    .. automethod:: make_reply

    """

    TAG = (namespaces.client, "message")

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP

    id_ = xso.Attr(tag="id", default=None)
    type_ = xso.Attr(
        tag="type",
        type_=xso.EnumCDataType(
            structs.MessageType,
            allow_coerce=True,
            deprecate_coerce=True,
            # changing the following breaks stanza handling; StanzaStream
            # relies on the meta-properties of the enumerations (is_request and
            # such).
            allow_unknown=False,
            accept_unknown=False,
        ),
        default=structs.MessageType.NORMAL,
        erroneous_as_absent=True,
    )

    body = xso.ChildTextMap(Body)
    subject = xso.ChildTextMap(Subject)
    thread = xso.Child([Thread])

    def __init__(self, type_, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_

    def make_reply(self):
        """
        Create a reply for the message. The :attr:`id_` attribute is cleared in
        the reply. The :attr:`from_` and :attr:`to` are swapped and the
        :attr:`type_` attribute is the same as the one of the original
        message.

        The new :class:`Message` object is returned.
        """
        obj = super()._make_reply(self.type_)
        obj.id_ = None
        return obj

    def __repr__(self):
        return "<message from={} to={} id={} type={}>".format(
            _safe_format_attr(self, "from_"),
            _safe_format_attr(self, "to"),
            _safe_format_attr(self, "id_"),
            _safe_format_attr(self, "type_"),
        )


class Status(xso.AbstractTextChild):
    """
    The status of a :class:`Presence` stanza.

    While it might seem intuitive to refer to the status using a
    :class:`~.xso.ChildText` descriptor, the fact that there might be multiple
    texts for different languages justifies the use of a separate class.

    .. attribute:: lang

       The ``xml:lang`` of this status part, as :class:`~.structs.LanguageTag`.

    .. attribute:: text

       The textual content of the status

    """
    TAG = (namespaces.client, "status")


class Presence(StanzaBase):
    """
    An XMPP presence stanza. The keyword arguments can be used to initialize
    the attributes of the :class:`Presence`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are enumerated in
       :class:`~.PresenceType`.

       .. versionchanged:: 0.7

          Starting with 0.7, the enumeration :class:`~.PresenceType` is
          used. Before, strings equal to the XML attribute value character data
          were used (``"probe"``, ``"unavailable"``, and so on, as well as
          :data:`None` to indicate the absence of the attribute and thus
          "available" presence).

          As of 0.7, setting the string equivalents and :data:`None` is still
          supported. However, reading from the attribute always returns the
          corresponding enumeration members (which still compare equal to their
          string equivalents).

       .. deprecated:: 0.7

          The use of the aforementioned string values (and :data:`None`) is
          deprecated and will lead to :exc:`TypeError` and/or :exc:`ValueError`
          being raised when they are written to this attribute. See the
          Changelog for :ref:`api-changelog-0.7` for further details on how to
          upgrade your code efficiently.

    .. attribute:: show

       The ``show`` value of the stanza, or :data:`None` if no ``show`` element
       is present.

    .. attribute:: priority

       The ``priority`` value of the presence. The default here is ``0`` and
       corresponds to an absent ``priority`` element.

    .. attribute:: status

       A :class:`~.structs.LanguageMap` mapping the languages of the different
       status elements to their text.

       .. versionchanged:: 0.5

          Before 0.5, this was a :class:`~aioxmpp.xso.model.XSOList`.

    Note that some attributes are inherited from :class:`StanzaBase`:

    ========================= =======================================
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.lang`  ``xml:lang`` value
    :attr:`~StanzaBase.error` :class:`Error` instance
    ========================= =======================================

    """

    TAG = (namespaces.client, "presence")

    id_ = xso.Attr(tag="id", default=None)
    type_ = xso.Attr(
        tag="type",
        type_=xso.EnumCDataType(
            structs.PresenceType,
            allow_coerce=True,
            deprecate_coerce=True,
            # changing the following breaks stanza handling; StanzaStream
            # relies on the meta-properties of the enumerations (is_request and
            # such).
            allow_unknown=False,
            accept_unknown=False,
        ),
        default=structs.PresenceType.AVAILABLE,
    )

    show = xso.ChildText(
        tag=(namespaces.client, "show"),
        type_=xso.EnumCDataType(
            structs.PresenceShow,
            allow_coerce=True,
            deprecate_coerce=True,
            allow_unknown=False,
            accept_unknown=False,
        ),
        default=structs.PresenceShow.NONE,
        erroneous_as_absent=True,
    )

    status = xso.ChildTextMap(Status)

    priority = xso.ChildText(
        tag=(namespaces.client, "priority"),
        type_=xso.Integer(),
        default=0
    )

    unhandled_children = xso.Collector()

    def __init__(self, *,
                 type_=structs.PresenceType.AVAILABLE,
                 show=structs.PresenceShow.NONE, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.show = show

    def __repr__(self):
        return "<presence from={} to={} id={} type={}>".format(
            _safe_format_attr(self, "from_"),
            _safe_format_attr(self, "to"),
            _safe_format_attr(self, "id_"),
            _safe_format_attr(self, "type_"),
        )


class IQ(StanzaBase):
    """
    An XMPP IQ stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`IQ`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are enumerated in
       :class:`~.IQType`.

       .. versionchanged:: 0.7

          Starting with 0.7, the enumeration :class:`~.IQType` is used.
          Before, strings equal to the XML attribute value character data were
          used (``"get"``, ``"set"``, and so on).

          As of 0.7, setting the string equivalents is still supported.
          However, reading from the attribute always returns the corresponding
          enumeration members (which still compare equal to their string
          equivalents).

       .. deprecated:: 0.7

          The use of the aforementioned string values is deprecated and will
          lead to :exc:`TypeError` and/or :exc:`ValueError` being raised when
          they are written to this attribute. See the Changelog for
          :ref:`api-changelog-0.7` for further details on how to upgrade your
          code efficiently.

    .. attribute:: payload

       An XSO which forms the payload of the IQ stanza.

    Note that some attributes are inherited from :class:`StanzaBase`:

    ========================= =======================================
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.JID`
    :attr:`~StanzaBase.lang`  ``xml:lang`` value
    :attr:`~StanzaBase.error` :class:`Error` instance
    ========================= =======================================

    New payload classes can be registered using:

    .. automethod:: as_payload_class

    """
    TAG = (namespaces.client, "iq")

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.FAIL

    id_ = xso.Attr(tag="id")
    type_ = xso.Attr(
        tag="type",
        type_=xso.EnumCDataType(
            structs.IQType,
            allow_coerce=True,
            deprecate_coerce=True,
            # changing the following breaks stanza handling; StanzaStream
            # relies on the meta-properties of the enumerations (is_request and
            # such).
            allow_unknown=False,
            accept_unknown=False,
        )
    )
    payload = xso.Child([], strict=True)

    def __init__(self, type_, *, payload=None, error=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.payload = payload
        self.error = error

    def _validate(self):
        try:
            self.id_
        except AttributeError:
            raise ValueError("IQ requires ID") from None

        if self.type_ == structs.IQType.ERROR and self.error is None:
            raise ValueError("IQ with type='error' requires error payload")

        super().validate()

    def validate(self):
        try:
            self._validate()
        except Exception:
            raise StanzaError(
                "invalid IQ stanza",
                self,
                None,
                None,
            )

    def make_reply(self, type_):
        if not self.type_.is_request:
            raise ValueError("make_reply requires request IQ")
        obj = super()._make_reply(type_)
        return obj

    def xso_error_handler(self, descriptor, ev_args, exc_info):
        # raise a specific error if the payload failed to parse
        if descriptor == IQ.payload.xq_descriptor:
            raise PayloadParsingError(self, ev_args, descriptor)
        elif descriptor is None:
            raise UnknownIQPayload(self, ev_args, descriptor)
        return super().xso_error_handler(descriptor, ev_args, exc_info)

    def __repr__(self):
        payload = ""

        try:
            if self.type_.is_error:
                payload = " error={!r}".format(self.error)
            elif self.payload:
                payload = " data={!r}".format(self.payload)
        except AttributeError:
            payload = " error={!r} data={!r}".format(
                self.error,
                self.payload
            )

        return "<iq from={} to={} id={} type={}{}>".format(
            _safe_format_attr(self, "from_"),
            _safe_format_attr(self, "to"),
            _safe_format_attr(self, "id_"),
            _safe_format_attr(self, "type_"),
            payload)

    @classmethod
    def as_payload_class(cls, other_cls):
        """
        Register `other_cls` as possible :class:`IQ` :attr:`payload`. Doing so
        is required in order to receive IQs with such payload.
        """
        cls.register_child(cls.payload, other_cls)
        return other_cls


def make_application_error(name, tag):
    """
    Create and return a **class** inheriting from :class:`.xso.XSO`. The
    :attr:`.xso.XSO.TAG` is set to `tag` and the class’ name will be `name`.

    In addition, the class is automatically registered with
    :attr:`.Error.application_condition` using
    :meth:`~.Error.as_application_condition`.

    Keep in mind that if you subclass the class returned by this function, the
    subclass is not registered with :class:`.Error`. In addition, if you do not
    override the :attr:`~.xso.XSO.TAG`, you will not be able to register
    the subclass as application defined condition as it has the same tag as the
    class returned by this function, which has already been registered as
    application condition.
    """
    cls = type(xso.XSO)(name, (xso.XSO,), {
        "TAG": tag,
    })
    Error.as_application_condition(cls)
    return cls
