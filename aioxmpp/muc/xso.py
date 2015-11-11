import aioxmpp.forms
import aioxmpp.stanza
import aioxmpp.stringprep
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0045_muc = "http://jabber.org/protocol/muc"
namespaces.xep0045_muc_user = "http://jabber.org/protocol/muc#user"
namespaces.xep0045_muc_admin = "http://jabber.org/protocol/muc#admin"
namespaces.xep0045_muc_owner = "http://jabber.org/protocol/muc#owner"


class History(xso.XSO):
    TAG = (namespaces.xep0045_muc, "history")

    maxchars = xso.Attr(
        "maxchars",
        type_=xso.Integer(),
        default=None,
    )

    maxstanzas = xso.Attr(
        "maxstanzas",
        type_=xso.Integer(),
        default=None,
    )

    seconds = xso.Attr(
        "seconds",
        type_=xso.Integer(),
        default=None,
    )

    since = xso.Attr(
        "since",
        type_=xso.DateTime(),
        default=None,
    )

    def __init__(self, *,
                 maxchars=None, maxstanzas=None, seconds=None, since=None):
        super().__init__()
        self.maxchars = maxchars
        self.maxstanzas = maxstanzas
        self.seconds = seconds
        self.since = since


class GenericExt(xso.XSO):
    TAG = (namespaces.xep0045_muc, "x")

    history = xso.Child([History])

    password = xso.ChildText(
        (namespaces.xep0045_muc, "password"),
        default=None
    )


aioxmpp.stanza.Presence.xep0045_muc = xso.Child([
    GenericExt
])

aioxmpp.stanza.Message.xep0045_muc = xso.Child([
    GenericExt
])


class Status(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "status")

    code = xso.Attr(
        "code",
        type_=xso.Integer()
    )

    def __init__(self, code):
        super().__init__()
        self.code = code


class StatusCodeList(xso.AbstractType):
    def parse(self, item):
        return item.code

    def format(self, code):
        item = Status(code)
        return item

    def get_formatted_type(self):
        return Status


class DestroyNotification(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "destroy")

    reason = xso.ChildText(
        (namespaces.xep0045_muc_user, "reason"),
        default=None
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
        default=None
    )


class Decline(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "decline")

    from_ = xso.Attr(
        "from",
        type_=xso.JID(),
        default=None
    )

    to = xso.Attr(
        "to",
        type_=xso.JID(),
        default=None
    )

    reason = xso.ChildText(
        (namespaces.xep0045_muc_user, "reason"),
        default=None
    )


class Invite(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "invite")

    from_ = xso.Attr(
        "from",
        type_=xso.JID(),
        default=None
    )

    to = xso.Attr(
        "to",
        type_=xso.JID(),
        default=None
    )

    reason = xso.ChildText(
        (namespaces.xep0045_muc_user, "reason"),
        default=None
    )


class ActorBase(xso.XSO):
    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
        default=None,
    )

    nick = xso.Attr(
        "nick",
        type_=xso.String(aioxmpp.stringprep.resourceprep),
        default=None
    )


class ItemBase(xso.XSO):
    affiliation = xso.Attr(
        "affiliation",
        validator=xso.RestrictToSet({
            "admin",
            "member",
            "none",
            "outcast",
            "owner",
            None,
        }),
        validate=xso.ValidateMode.ALWAYS,
        default=None,
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
        default=None,
    )

    nick = xso.Attr(
        "nick",
        type_=xso.String(aioxmpp.stringprep.resourceprep),
        default=None
    )

    role = xso.Attr(
        "role",
        validator=xso.RestrictToSet({
            "moderator",
            "none",
            "participant",
            "visitor",
            None,
        }),
        validate=xso.ValidateMode.ALWAYS,
        default=None,
    )

    def __init__(self,
                 affiliation=None,
                 jid=None,
                 nick=None,
                 role=None,
                 reason=None):
        super().__init__()
        self.affiliation = affiliation
        self.jid = jid
        self.nick = nick
        self.role = role
        self.reason = reason


class UserActor(ActorBase):
    TAG = (namespaces.xep0045_muc_user, "actor")


class Continue(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "continue")

    thread = xso.Attr(
        "thread",
        type_=aioxmpp.stanza.Thread.identifier.type_,
        default=None,
    )


class UserItem(ItemBase):
    TAG = (namespaces.xep0045_muc_user, "item")

    actor = xso.Child([UserActor])

    continue_ = xso.Child([Continue])

    reason = xso.ChildText(
        (namespaces.xep0045_muc_user, "reason"),
        default=None
    )


class UserExt(xso.XSO):
    TAG = (namespaces.xep0045_muc_user, "x")

    status_codes = xso.ChildValueList(
        StatusCodeList(),
        container_type=set
    )

    destroy = xso.Child([DestroyNotification])

    decline = xso.Child([Decline])

    invites = xso.ChildList([Invite])

    items = xso.ChildList([UserItem])

    password = xso.ChildText(
        (namespaces.xep0045_muc_user, "password"),
        default=None
    )

    def __init__(self,
                 status_codes=[],
                 destroy=None,
                 decline=None,
                 invites=[],
                 items=[],
                 password=None):
        super().__init__()
        self.status_codes.update(status_codes)
        self.destroy = destroy
        self.decline = decline
        self.invites.extend(invites)
        self.items.extend(items)
        self.password = password


aioxmpp.stanza.Presence.xep0045_muc_user = xso.Child([
    UserExt
])

aioxmpp.stanza.Message.xep0045_muc_user = xso.Child([
    UserExt
])


class AdminActor(ActorBase):
    TAG = (namespaces.xep0045_muc_admin, "actor")


class AdminItem(ItemBase):
    TAG = (namespaces.xep0045_muc_admin, "item")

    actor = xso.Child([AdminActor])

    continue_ = xso.Child([Continue])

    reason = xso.ChildText(
        (namespaces.xep0045_muc_admin, "reason"),
        default=None
    )


@aioxmpp.stanza.IQ.as_payload_class
class AdminQuery(xso.XSO):
    TAG = (namespaces.xep0045_muc_admin, "query")

    items = xso.ChildList([AdminItem])

    def __init__(self, *, items=[]):
        super().__init__()
        self.items[:] = items


class DestroyRequest(xso.XSO):
    TAG = (namespaces.xep0045_muc_owner, "destroy")

    reason = xso.ChildText(
        (namespaces.xep0045_muc_owner, "reason"),
        default=None
    )

    password = xso.ChildText(
        (namespaces.xep0045_muc_owner, "password"),
        default=None
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
        default=None
    )


@aioxmpp.stanza.IQ.as_payload_class
class OwnerQuery(xso.XSO):
    TAG = (namespaces.xep0045_muc_owner, "query")

    destroy = xso.Child([DestroyRequest])

    form = xso.Child([aioxmpp.forms.Data])
