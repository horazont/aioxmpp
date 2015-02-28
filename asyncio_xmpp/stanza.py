import base64
import random

from . import stanza_model, stanza_types

from .utils import namespaces

RANDOM_ID_BYTES = (120//8)


class StanzaBase(stanza_model.StanzaObject):
    id_ = stanza_model.Attr(
        tag="id",
        required=True)
    from_ = stanza_model.Attr(
        tag="from",
        type_=stanza_types.JID())
    to = stanza_model.Attr(
        tag="to",
        type_=stanza_types.JID())

    def __init__(self, *, from_=None, to=None, id_=None):
        super().__init__()
        self.from_ = from_
        self.to = to
        self.id_ = id_

    def autoset_id(self):
        if self.id_:
            return

        self.id_ = base64.b64encode(random.getrandbits(
            RANDOM_ID_BYTES*8
        ).to_bytes(
            RANDOM_ID_BYTES, "little"
        )).decode("ascii")

    def _make_reply(self):
        obj = type(self)()
        obj.from_ = self.to
        obj.to = self.from_
        obj.id_ = self.id_
        return obj


class Thread(stanza_model.StanzaObject):
    TAG = (namespaces.client, "thread")

    identifier = stanza_model.Text(
        validator=stanza_types.Nmtoken(),
        validate=stanza_model.ValidateMode.FROM_CODE)
    parent = stanza_model.Attr(
        tag="parent",
        validator=stanza_types.Nmtoken(),
        validate=stanza_model.ValidateMode.FROM_CODE
    )

class Message(StanzaBase):
    TAG = (namespaces.client, "message")

    type_ = stanza_model.Attr(
        tag="type",
        validator=stanza_types.RestrictToSet({
            "chat",
            "groupchat",
            "error",
            "headline",
            "normal"}),
        required=True
    )

    body = stanza_model.ChildText(
        tag=(namespaces.client, "body"),
        attr_policy=stanza_model.UnknownAttrPolicy.DROP)
    subject = stanza_model.ChildText(
        tag=(namespaces.client, "subject"),
        attr_policy=stanza_model.UnknownAttrPolicy.DROP)
    thread = stanza_model.Child([Thread])
    ext = stanza_model.ChildMap([])

    def __init__(self, *, type_="chat", **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_

    def make_reply(self):
        obj = super()._make_reply()
        obj.type_ = self.type_
        obj.id_ = None
        return obj


class Presence(StanzaBase):
    TAG = (namespaces.client, "presence")

    type_ = stanza_model.Attr(
        tag="type",
        validator=stanza_types.RestrictToSet({
            "error",
            "probe",
            "subscribe",
            "subscribed",
            "unavailable",
            "unsubscribe",
            "unsubscribed"}),
        required=False,
    )
    ext = stanza_model.ChildMap([])

    def __init__(self, *, type_=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_


class Error(stanza_model.StanzaObject):
    TAG = (namespaces.client, "error")

    type_ = stanza_model.Attr(
        tag="type",
        validator=stanza_types.RestrictToSet({
            "auth",
            "cancel",
            "continue",
            "modify",
            "wait",
        }),
        required=True,
    )
    text = stanza_model.ChildText(
        tag=(namespaces.stanzas, "text"),
        attr_policy=stanza_model.UnknownAttrPolicy.DROP,
        default=None)
    condition = stanza_model.ChildTag(
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
        default=("urn:ietf:params:xml:ns:xmpp-stanzas", "undefined-condition")
    )


class IQ(StanzaBase):
    TAG = (namespaces.client, "iq")

    type_ = stanza_model.Attr(
        tag="type",
        validator=stanza_types.RestrictToSet({
            "get",
            "set",
            "result",
            "error"}),
        required=True,
    )
    payload = stanza_model.Child([])
    error = stanza_model.Child([Error])

    def __init__(self, *, type_=None, **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_

    def make_reply(self, type_):
        if self.type_ != "get" and self.type_ != "set":
            raise ValueError("make_reply requires request IQ")
        obj = super()._make_reply()
        obj.type_ = type_
        return obj
