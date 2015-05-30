import base64
import random

from . import xso, errors

from .utils import namespaces

RANDOM_ID_BYTES = 120 // 8


class PayloadError(Exception):
    def __init__(self, msg, partial_obj, ev_args):
        super().__init__(msg)
        self.ev_args = ev_args
        self.partial_obj = partial_obj


class PayloadParsingError(PayloadError):
    def __init__(self, partial_obj, ev_args):
        super().__init__(
            "parsing of payload {} failed".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args)


class UnknownIQPayload(PayloadError):
    def __init__(self, partial_obj, ev_args):
        super().__init__(
            "unknown payload {} on iq".format(
                xso.tag_to_str((ev_args[0], ev_args[1]))),
            partial_obj,
            ev_args)


class StanzaBase(xso.XSO):
    id_ = xso.Attr(
        tag="id",
        required=True)
    from_ = xso.Attr(
        tag="from",
        type_=xso.JID())
    to = xso.Attr(
        tag="to",
        type_=xso.JID())

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
    TAG = (namespaces.client, "message")

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
    TAG = (namespaces.client, "presence")

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

    def __init__(self, *, type_=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_

    def __repr__(self):
        return "<presence from='{!s}' to='{!s}' id={!r} type={!r}>".format(
            self.from_,
            self.to,
            self.id_,
            self.type_)


class Error(xso.XSO):
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
        tags=[
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
        ],
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
    TAG = (namespaces.client, "iq")

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
