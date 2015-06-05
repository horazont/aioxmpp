"""
:mod:`~aioxmpp.stanza` --- XSOs for dealing with stanzas
########################################################

Top-level classes
=================

.. autoclass:: Message(*[, from_][, to][, id_][, type_])

.. autoclass:: IQ(*[, from_][, to][, id_][, type_])

.. autoclass:: Presence(*[, from_][, to][, id_][, type_])

Payload classes
===============

For :class:`Presence` and :class:`Message` as well as :class:`IQ` errors, the
standardized payloads also have classes which are used as values for the
attributes:

.. autoclass:: Error(*[, condition][, type_][, text])

.. autoclass:: Thread()

Base class for stanzas
======================

.. autoclass:: StanzaBase

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


class StanzaBase(xso.XSO):
    from_ = xso.Attr(
        tag="from",
        type_=xso.JID())
    to = xso.Attr(
        tag="to",
        type_=xso.JID())

    lang = xso.Attr(
        tag=(namespaces.xml, "lang")
    )

    def __init__(self, *, from_=None, to=None, id_=None):
        super().__init__()
        self.from_ = from_
        self.to = to
        self.id_ = id_

    def autoset_id(self):
        if self.id_:
            return

        self.id_ = base64.b64encode(random.getrandbits(
            RANDOM_ID_BYTES * 8
        ).to_bytes(
            RANDOM_ID_BYTES, "little"
        )).decode("ascii")

    def _make_reply(self):
        obj = type(self)()
        obj.from_ = self.to
        obj.to = self.from_
        obj.id_ = self.id_
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
        validate=xso.ValidateMode.FROM_CODE
    )


class Message(StanzaBase):
    """
    An XMPP message stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`Message`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are ``"chat"``,
       ``"groupchat"``, ``"error"``, ``"headline"`` and ``"normal"``.

    .. attribute:: from_

       The :class:`~aioxmpp.structs.JID` of the sending entity.

    .. attribute:: to

       The :class:`~aioxmpp.structs.JID` of the receiving entity.

    .. attribute:: body

       The string content of the ``body`` element, if any. This is :data:`None`
       if no body is attached to the message and the empty string if the
       attached body is empty.

    .. attribute:: subject

       The text content of the ``subject`` element, if any. This attribute is
       :data:`None` if the message has no subject and the empty string if the
       subject is empty.

    .. attribute:: thread

       A :class:`Thread` instance representing the threading information
       attached to the message or :data:`None` if no threading information is
       attached.

    .. automethod:: make_reply

    """

    TAG = (namespaces.client, "message")

    id_ = xso.Attr(tag="id")
    type_ = xso.Attr(
        tag="type",
        validator=xso.RestrictToSet({
            "chat",
            "groupchat",
            "error",
            "headline",
            "normal"}),
        required=True
    )

    body = xso.ChildText(
        tag=(namespaces.client, "body"),
        attr_policy=xso.UnknownAttrPolicy.DROP)
    subject = xso.ChildText(
        tag=(namespaces.client, "subject"),
        attr_policy=xso.UnknownAttrPolicy.DROP)
    thread = xso.Child([Thread])
    ext = xso.ChildMap([])

    def __init__(self, *, type_="chat", **kwargs):
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
        obj = super()._make_reply()
        obj.type_ = self.type_
        obj.id_ = None
        return obj

    def __repr__(self):
        return "<message from='{!s}' to='{!s}' id={!r} type={!r}>".format(
            self.from_,
            self.to,
            self.id_,
            self.type_)


class Presence(StanzaBase):
    """
    An XMPP presence stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`Presence`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are ``"error"``,
       ``"probe"``, ``"subscribe"``, ``"subscribed"``, ``"unavailable"``,
       ``"unsubscribe"``, ``"unsubscribed"`` and :data:`None`, where
       :data:`None` signifies the absence of the ``type`` attribute.

    .. attribute:: from_

       The :class:`~aioxmpp.structs.JID` of the sending entity.

    .. attribute:: to

       The :class:`~aioxmpp.structs.JID` of the receiving entity.
    """

    TAG = (namespaces.client, "presence")

    id_ = xso.Attr(tag="id")
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
        required=False,
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
        validate=xso.ValidateMode.ALWAYS
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

    """

    TAG = (namespaces.client, "error")

    EXCEPTION_CLS_MAP = {
        "modify": errors.XMPPModifyError,
        "cancel": errors.XMPPCancelError,
        "auth": errors.XMPPAuthError,
        "wait": errors.XMPPWaitError,
        "continue": errors.XMPPContinueError,
    }

    type_ = xso.Attr(
        tag="type",
        validator=xso.RestrictToSet({
            "auth",
            "cancel",
            "continue",
            "modify",
            "wait",
        }),
        required=True,
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
        default=("urn:ietf:params:xml:ns:xmpp-stanzas", "undefined-condition"),
        declare_prefix=None,
    )

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


class IQ(StanzaBase):
    """
    An XMPP IQ stanza. The keyword arguments can be used to initialize the
    attributes of the :class:`IQ`.

    .. attribute:: id_

       The optional ID of the stanza.

    .. attribute:: type_

       The type attribute of the stanza. The allowed values are ``"error"``,
       ``"result"``, ``"set"`` and ``"get"``.

    .. attribute:: from_

       The :class:`~aioxmpp.structs.JID` of the sending entity.

    .. attribute:: to

       The :class:`~aioxmpp.structs.JID` of the receiving entity.

    """
    TAG = (namespaces.client, "iq")

    id_ = xso.Attr(tag="id", required=True)
    type_ = xso.Attr(
        tag="type",
        validator=xso.RestrictToSet({
            "get",
            "set",
            "result",
            "error"}),
        required=True,
    )
    payload = xso.Child([])
    error = xso.Child([Error])

    def __init__(self, *, type_=None, payload=None, error=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.payload = payload
        self.error = error

    def make_reply(self, type_):
        if self.type_ != "get" and self.type_ != "set":
            raise ValueError("make_reply requires request IQ")
        obj = super()._make_reply()
        obj.type_ = type_
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
