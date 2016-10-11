########################################################################
# File name: xso.py
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

    def __init__(self, *, form=None, destroy=None):
        super().__init__()
        self.form = form
        self.destroy = destroy


class ConfigurationForm(aioxmpp.forms.Form):
    """
    This is a :xep:`4` form template (see :mod:`aioxmpp.forms`) for MUC
    configuration forms.

    The attribute documentation is auto-generated from :xep:`45`; see there for
    details on the semantics of each field.

    .. versionadded:: 0.7
    """

    FORM_TYPE = 'http://jabber.org/protocol/muc#roomconfig'

    maxhistoryfetch = aioxmpp.forms.TextSingle(
        var='muc#maxhistoryfetch',
        label='Maximum Number of History Messages Returned by Room'
    )

    allowpm = aioxmpp.forms.ListSingle(
        var='muc#roomconfig_allowpm',
        label='Roles that May Send Private Messages'
    )

    allowinvites = aioxmpp.forms.Boolean(
        var='muc#roomconfig_allowinvites',
        label='Whether to Allow Occupants to Invite Others'
    )

    changesubject = aioxmpp.forms.Boolean(
        var='muc#roomconfig_changesubject',
        label='Whether to Allow Occupants to Change Subject'
    )

    enablelogging = aioxmpp.forms.Boolean(
        var='muc#roomconfig_enablelogging',
        label='Whether to Enable Public Logging of Room Conversations'
    )

    getmemberlist = aioxmpp.forms.ListMulti(
        var='muc#roomconfig_getmemberlist',
        label='Roles and Affiliations that May Retrieve Member List'
    )

    lang = aioxmpp.forms.TextSingle(
        var='muc#roomconfig_lang',
        label='Natural Language for Room Discussions'
    )

    pubsub = aioxmpp.forms.TextSingle(
        var='muc#roomconfig_pubsub',
        label='XMPP URI of Associated Publish-Subscribe Node'
    )

    maxusers = aioxmpp.forms.ListSingle(
        var='muc#roomconfig_maxusers',
        label='Maximum Number of Room Occupants'
    )

    membersonly = aioxmpp.forms.Boolean(
        var='muc#roomconfig_membersonly',
        label='Whether to Make Room Members-Only'
    )

    moderatedroom = aioxmpp.forms.Boolean(
        var='muc#roomconfig_moderatedroom',
        label='Whether to Make Room Moderated'
    )

    passwordprotectedroom = aioxmpp.forms.Boolean(
        var='muc#roomconfig_passwordprotectedroom',
        label='Whether a Password is Required to Enter'
    )

    persistentroom = aioxmpp.forms.Boolean(
        var='muc#roomconfig_persistentroom',
        label='Whether to Make Room Persistent'
    )

    presencebroadcast = aioxmpp.forms.ListMulti(
        var='muc#roomconfig_presencebroadcast',
        label='Roles for which Presence is Broadcasted'
    )

    publicroom = aioxmpp.forms.Boolean(
        var='muc#roomconfig_publicroom',
        label='Whether to Allow Public Searching for Room'
    )

    roomadmins = aioxmpp.forms.JIDMulti(
        var='muc#roomconfig_roomadmins',
        label='Full List of Room Admins'
    )

    roomdesc = aioxmpp.forms.TextSingle(
        var='muc#roomconfig_roomdesc',
        label='Short Description of Room'
    )

    roomname = aioxmpp.forms.TextSingle(
        var='muc#roomconfig_roomname',
        label='Natural-Language Room Name'
    )

    roomowners = aioxmpp.forms.JIDMulti(
        var='muc#roomconfig_roomowners',
        label='Full List of Room Owners'
    )

    roomsecret = aioxmpp.forms.TextPrivate(
        var='muc#roomconfig_roomsecret',
        label='The Room Password'
    )

    whois = aioxmpp.forms.ListSingle(
        var='muc#roomconfig_whois',
        label='Affiliations that May Discover Real JIDs of Occupants'
    )
