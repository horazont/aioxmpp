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

.. autoclass:: Message(*[, from_][, to][, id_][, type_])

.. autoclass:: IQ(*[, from_][, to][, id_][, type_])

.. autoclass:: Presence(*[, from_][, to][, id_][, type_])

Payload classes
===============

For :class:`Presence` and :class:`Message` as well as :class:`IQ` errors, the
standardized payloads also have classes which are used as values for the
attributes:

.. autoclass:: Error(*[, condition][, type_][, text])

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

"""
import base64
import random

from . import xso, errors

from .utils import namespaces

RANDOM_ID_BYTES = 120 // 8

STANZA_ERROR_TAGS = (
    "bad-request",
    "conflict",
    "feature-not-implemented",
    "forbidden",
    "gone",
    "internal-server-error",
    "item-not-found",
    "jid-malformed",
    "not-acceptable",
    "not-allowed",
    "not-authorized",
    "policy-violation",
    "recipient-unavailable",
    "redirect",
    "registration-required",
    "remote-server-not-found",
    "remote-server-timeout",
    "resource-constraint",
    "service-unavailable",
    "subscription-required",
    "undefined-condition",
    "unexpected-request",
)


class PayloadError(Exception):
    """
    Base class for exceptions raised when stanza payloads cannot be processed.

    .. attribute:: partial_obj

       The :class:`IQ` instance which has not been parsed completely. The
       attributes of the instance are already there, everything else is not
       guaranteed to be there.

    .. attribute:: ev_args

       The XSO parsing event arguments which caused the parsing to fail.

    """

    def __init__(self, msg, partial_obj, ev_args):
        super().__init__(msg)
        self.ev_args = ev_args
        self.partial_obj = partial_obj


class PayloadParsingError(PayloadError):
    """
    A constraint of a sub-object was not fulfilled and the stanza being
    processed is illegal. The partially parsed stanza object is provided in
    :attr:`~PayloadError.partial_obj`.
    """

    def __init__(self, partial_obj, ev_args):
        super().__init__(
            "parsing of payload {} failed".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args)


class UnknownIQPayload(PayloadError):
    """
    The payload of an IQ object is unknown. The partial object with attributes
    but without payload is available through :attr:`~PayloadError.partial_obj`.
    """

    def __init__(self, partial_obj, ev_args):
        super().__init__(
            "unknown payload {} on iq".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args)


class Error(xso.XSO):
    """
    An XMPP stanza error. The keyword arguments can be used to initialize the
    attributes of the :class:`Error`.

    .. attribute:: type_

       The type of the error. Valid values are ``"auth"``, ``"cancel"``,
       ``"continue"``, ``"modify"`` and ``"wait"``.

    .. attribute:: condition

       The standard defined condition which triggered the error. Possible
       values can be determined by looking at the RFC or the source.

    .. attribute:: text

       The descriptive error text which is part of the error stanza, if any
       (otherwise :data:`None`).

    Any child elements unknown to the XSO are dropped. This is to support
    application-specific conditions used by other applications. To register
    your own use :meth:`.xso.XSO.register_child` on
    :attr:`application_condition`:

    .. attribute:: application_condition

       A :class:`.xso.XSO.Child` which can be used to register support for
       application-specific errors.

    """

    TAG = (namespaces.client, "error")

    DECLARE_NS = {}

    EXCEPTION_CLS_MAP = {
        "modify": errors.XMPPModifyError,
        "cancel": errors.XMPPCancelError,
        "auth": errors.XMPPAuthError,
        "wait": errors.XMPPWaitError,
        "continue": errors.XMPPContinueError,
    }

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP

    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    type_ = xso.Attr(
        tag="type",
        validator=xso.RestrictToSet({
            "auth",
            "cancel",
            "continue",
            "modify",
            "wait",
        })
    )

    text = xso.ChildText(
        tag=(namespaces.stanzas, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None)

    condition = xso.ChildTag(
        tags=STANZA_ERROR_TAGS,
        default_ns="urn:ietf:params:xml:ns:xmpp-stanzas",
        allow_none=False,
        declare_prefix=None,
    )

    application_condition = xso.Child([], required=False)

    def __init__(self,
                 condition=(namespaces.stanzas, "undefined-condition"),
                 type_="cancel",
                 text=None):
        super().__init__()
        self.condition = condition
        self.type_ = type_
        self.text = text

    @classmethod
    def from_exception(cls, exc):
        return cls(condition=exc.condition,
                   type_=exc.TYPE,
                   text=exc.text)

    def to_exception(self):
        if hasattr(self.application_condition, "to_exception"):
            result = self.application_condition.to_exception(self.type_)
            if isinstance(result, Exception):
                return result
        return self.EXCEPTION_CLS_MAP[self.type_](
            condition=self.condition,
            text=self.text
        )

    def __repr__(self):
        payload = ""
        if self.text:
            payload = " text={!r}".format(self.text)

        return "<{} type={!r}{}>".format(
            self.condition[1],
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

       The :class:`~aioxmpp.structs.JID` of the sending entity.

    .. attribute:: to

       The :class:`~aioxmpp.structs.JID` of the receiving entity.

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

        Otherwise, the :attr:`id_` attribute is filled with eight bytes of
        random data, encoded as base64.

        .. note::

           This method only works on subclasses of :class:`StanzaBase` which
           define the :attr:`id_` attribute.

        """
        try:
            self.id_
        except AttributeError:
            pass
        else:
            return

        self.id_ = "x"+base64.b64encode(random.getrandbits(
            RANDOM_ID_BYTES * 8
        ).to_bytes(
            RANDOM_ID_BYTES, "little"
        )).decode("ascii")

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
        obj = type(self)(from_=self.to,
                         to=self.from_,
                         type_="error")
        obj.id_ = self.id_
        obj.error = error
        return obj


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

       The type attribute of the stanza. The allowed values are ``"chat"``,
       ``"groupchat"``, ``"error"``, ``"headline"`` and ``"normal"``.

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
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.structs.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.structs.JID`
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
        validator=xso.RestrictToSet({
            "chat",
            "groupchat",
            "error",
            "headline",
            "normal"}),
        default="normal",
    )

    body = xso.ChildTextMap(Body)
    subject = xso.ChildTextMap(Subject)
    thread = xso.Child([Thread])
    ext = xso.ChildMap([])

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
        return "<message from='{!s}' to='{!s}' id={!r} type={!r}>".format(
            self.from_,
            self.to,
            self.id_,
            self.type_)


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

       The type attribute of the stanza. The allowed values are ``"error"``,
       ``"probe"``, ``"subscribe"``, ``"subscribed"``, ``"unavailable"``,
       ``"unsubscribe"``, ``"unsubscribed"`` and :data:`None`, where
       :data:`None` signifies the absence of the ``type`` attribute.

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
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.structs.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.structs.JID`
    :attr:`~StanzaBase.lang`  ``xml:lang`` value
    :attr:`~StanzaBase.error` :class:`Error` instance
    ========================= =======================================

    """

    TAG = (namespaces.client, "presence")

    id_ = xso.Attr(tag="id", default=None)
    type_ = xso.Attr(
        tag="type",
        validator=xso.RestrictToSet({
            "error",
            "probe",
            "subscribe",
            "subscribed",
            "unavailable",
            "unsubscribe",
            "unsubscribed"}),
        default=None,
    )

    show = xso.ChildText(
        tag=(namespaces.client, "show"),
        validator=xso.RestrictToSet({
            "dnd",
            "xa",
            "away",
            None,
            "chat",
        }),
        validate=xso.ValidateMode.ALWAYS,
        default=None,
    )

    status = xso.ChildTextMap(Status)

    priority = xso.ChildText(
        tag=(namespaces.client, "priority"),
        type_=xso.Integer(),
        default=0
    )

    ext = xso.ChildMap([])
    unhandled_children = xso.Collector()

    def __init__(self, *, type_=None, show=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.show = show

    def __repr__(self):
        return "<presence from='{!s}' to='{!s}' id={!r} type={!r}>".format(
            self.from_,
            self.to,
            self.id_,
            self.type_)


class IQ(StanzaBase):
    """
    An XMPP IQ stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`IQ`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are ``"error"``,
       ``"result"``, ``"set"`` and ``"get"``.

    .. attribute:: payload

       An XSO which forms the payload of the IQ stanza.

    Note that some attributes are inherited from :class:`StanzaBase`:

    ========================= =======================================
    :attr:`~StanzaBase.from_` sender :class:`~aioxmpp.structs.JID`
    :attr:`~StanzaBase.to`    recipient :class:`~aioxmpp.structs.JID`
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
        validator=xso.RestrictToSet({
            "get",
            "set",
            "result",
            "error"})
    )
    payload = xso.Child([])

    def __init__(self, type_, *, payload=None, error=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.payload = payload
        self.error = error

    def validate(self):
        try:
            self.id_
        except AttributeError:
            raise ValueError("IQ requires ID") from None
        super().validate()

    def make_reply(self, type_):
        if self.type_ != "get" and self.type_ != "set":
            raise ValueError("make_reply requires request IQ")
        obj = super()._make_reply(type_)
        return obj

    def xso_error_handler(self, descriptor, ev_args, exc_info):
        # raise a specific error if the payload failed to parse
        if descriptor == IQ.payload:
            raise PayloadParsingError(self, ev_args)
        elif descriptor is None:
            raise UnknownIQPayload(self, ev_args)

    def __repr__(self):
        payload = ""
        if self.type_ == "error":
            payload = " error={!r}".format(self.error)
        elif self.payload:
            payload = " data={!r}".format(self.payload)
        return "<iq from='{!s}' to='{!s}' id={!r} type={!r}{}>".format(
            self.from_,
            self.to,
            self.id_,
            self.type_,
            payload)

    @classmethod
    def as_payload_class(cls, other_cls):
        cls.register_child(cls.payload, other_cls)
        return other_cls
