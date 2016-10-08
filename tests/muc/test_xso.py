########################################################################
# File name: test_xso.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import unittest
import unittest.mock

from datetime import datetime

import aioxmpp.forms as forms
import aioxmpp.muc.xso as muc_xso
import aioxmpp.stanza as stanza
import aioxmpp.structs
import aioxmpp.stringprep
import aioxmpp.utils as utils
import aioxmpp.xso as xso


TEST_JID = aioxmpp.structs.JID.fromstr(
    "foo@bar.example/fnord"
)


class TestNamespaces(unittest.TestCase):
    def test_base_namespace(self):
        self.assertEqual(
            utils.namespaces.xep0045_muc,
            "http://jabber.org/protocol/muc"
        )

    def test_user_namespace(self):
        self.assertEqual(
            utils.namespaces.xep0045_muc_user,
            "http://jabber.org/protocol/muc#user"
        )

    def test_admin_namespace(self):
        self.assertEqual(
            utils.namespaces.xep0045_muc_admin,
            "http://jabber.org/protocol/muc#admin"
        )

    def test_owner_namespace(self):
        self.assertEqual(
            utils.namespaces.xep0045_muc_owner,
            "http://jabber.org/protocol/muc#owner"
        )


class TestHistory(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.History,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.History.TAG,
            (utils.namespaces.xep0045_muc, "history")
        )

    def test_maxchars(self):
        self.assertIsInstance(
            muc_xso.History.maxchars,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.History.maxchars.tag,
            (None, "maxchars")
        )
        self.assertIsInstance(
            muc_xso.History.maxchars.type_,
            xso.Integer
        )
        self.assertIs(
            muc_xso.History.maxchars.default,
            None
        )

    def test_maxstanzas(self):
        self.assertIsInstance(
            muc_xso.History.maxstanzas,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.History.maxstanzas.tag,
            (None, "maxstanzas")
        )
        self.assertIsInstance(
            muc_xso.History.maxstanzas.type_,
            xso.Integer
        )
        self.assertIs(
            muc_xso.History.maxstanzas.default,
            None
        )

    def test_seconds(self):
        self.assertIsInstance(
            muc_xso.History.seconds,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.History.seconds.tag,
            (None, "seconds")
        )
        self.assertIsInstance(
            muc_xso.History.seconds.type_,
            xso.Integer
        )
        self.assertIs(
            muc_xso.History.seconds.default,
            None
        )

    def test_since(self):
        self.assertIsInstance(
            muc_xso.History.since,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.History.since.tag,
            (None, "since")
        )
        self.assertIsInstance(
            muc_xso.History.since.type_,
            xso.DateTime
        )
        self.assertIs(
            muc_xso.History.since.default,
            None
        )

    def test_init(self):
        hist = muc_xso.History()
        self.assertIsNone(hist.seconds)
        self.assertIsNone(hist.since)
        self.assertIsNone(hist.maxstanzas)
        self.assertIsNone(hist.maxchars)

        now = datetime.utcnow()
        hist = muc_xso.History(
            since=now,
            seconds=123,
            maxstanzas=345,
            maxchars=456
        )
        self.assertEqual(hist.seconds, 123)
        self.assertEqual(hist.since, now)
        self.assertEqual(hist.maxchars, 456)
        self.assertEqual(hist.maxstanzas, 345)

        with self.assertRaisesRegex(TypeError, "positional argument"):
            hist = muc_xso.History(123)


class TestGenericExt(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.GenericExt,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.GenericExt.TAG,
            (utils.namespaces.xep0045_muc, "x")
        )

    def test_history(self):
        self.assertIsInstance(
            muc_xso.GenericExt.history,
            xso.Child
        )
        self.assertIn(
            muc_xso.History,
            muc_xso.GenericExt.history._classes
        )
        self.assertFalse(
            muc_xso.GenericExt.history.required
        )

    def test_password(self):
        self.assertIsInstance(
            muc_xso.GenericExt.password,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.GenericExt.password.tag,
            (utils.namespaces.xep0045_muc, "password")
        )
        self.assertIsNone(
            muc_xso.GenericExt.password.default
        )

    def test_Presence_attr(self):
        self.assertIsInstance(
            stanza.Presence.xep0045_muc,
            xso.Child
        )
        self.assertIn(
            muc_xso.GenericExt,
            stanza.Presence.xep0045_muc._classes
        )
        self.assertFalse(
            stanza.Presence.xep0045_muc.required
        )

    def test_Message_attr(self):
        self.assertIsInstance(
            stanza.Message.xep0045_muc,
            xso.Child
        )
        self.assertIn(
            muc_xso.GenericExt,
            stanza.Message.xep0045_muc._classes
        )
        self.assertFalse(
            stanza.Message.xep0045_muc.required
        )


class TestStatus(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.Status,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.Status.TAG,
            (utils.namespaces.xep0045_muc_user, "status")
        )

    def test_code(self):
        self.assertIsInstance(
            muc_xso.Status.code,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Status.code.tag,
            (None, "code")
        )
        self.assertIsInstance(
            muc_xso.Status.code.type_,
            xso.Integer
        )
        self.assertEqual(
            muc_xso.Status.code.default,
            xso.NO_DEFAULT
        )

    def test_init(self):
        item = muc_xso.Status(200)
        self.assertEqual(item.code, 200)


class TestStatusCodeList(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertTrue(issubclass(
            muc_xso.StatusCodeList,
            xso.AbstractType
        ))

    def setUp(self):
        self.type_ = muc_xso.StatusCodeList()

    def test_parse(self):
        item = muc_xso.Status(123)

        self.assertEqual(
            self.type_.parse(item),
            123
        )

    def test_format(self):
        item = self.type_.format(123)
        self.assertIsInstance(
            item,
            muc_xso.Status
        )
        self.assertEqual(item.code, 123)

    def test_get_formatted_type(self):
        self.assertIs(self.type_.get_formatted_type(), muc_xso.Status)

    def tearDown(self):
        del self.type_


class TestDestroyNotification(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.DestroyNotification,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.DestroyNotification.TAG,
            (utils.namespaces.xep0045_muc_user, "destroy")
        )

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.DestroyNotification.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.DestroyNotification.reason.tag,
            (utils.namespaces.xep0045_muc_user, "reason")
        )
        self.assertIsNone(
            muc_xso.DestroyNotification.reason.default
        )

    def test_jid(self):
        self.assertIsInstance(
            muc_xso.DestroyNotification.jid,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.DestroyNotification.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            muc_xso.DestroyNotification.jid.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.DestroyNotification.jid.default)


class TestDecline(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.Decline,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.Decline.TAG,
            (utils.namespaces.xep0045_muc_user, "decline")
        )

    def test_from_(self):
        self.assertIsInstance(
            muc_xso.Decline.from_,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Decline.from_.tag,
            (None, "from")
        )
        self.assertIsInstance(
            muc_xso.Decline.from_.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.Decline.from_.default)

    def test_to(self):
        self.assertIsInstance(
            muc_xso.Decline.to,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Decline.to.tag,
            (None, "to")
        )
        self.assertIsInstance(
            muc_xso.Decline.to.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.Decline.to.default)

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.Decline.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.Decline.reason.tag,
            (utils.namespaces.xep0045_muc_user, "reason")
        )
        self.assertIsNone(
            muc_xso.Decline.reason.default
        )


class TestInvite(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.Invite,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.Invite.TAG,
            (utils.namespaces.xep0045_muc_user, "invite")
        )

    def test_from_(self):
        self.assertIsInstance(
            muc_xso.Invite.from_,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Invite.from_.tag,
            (None, "from")
        )
        self.assertIsInstance(
            muc_xso.Invite.from_.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.Invite.from_.default)

    def test_to(self):
        self.assertIsInstance(
            muc_xso.Invite.to,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Invite.to.tag,
            (None, "to")
        )
        self.assertIsInstance(
            muc_xso.Invite.to.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.Invite.to.default)

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.Invite.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.Invite.reason.tag,
            (utils.namespaces.xep0045_muc_user, "reason")
        )
        self.assertIsNone(
            muc_xso.Invite.reason.default
        )


class TestActorBase(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.ActorBase,
            xso.XSO
        ))

    def test_jid(self):
        self.assertIsInstance(
            muc_xso.ActorBase.jid,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ActorBase.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            muc_xso.ActorBase.jid.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.ActorBase.jid.default)

    def test_nick(self):
        self.assertIsInstance(
            muc_xso.ActorBase.nick,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ActorBase.nick.tag,
            (None, "nick")
        )
        self.assertIsInstance(
            muc_xso.ActorBase.nick.type_,
            xso.String
        )
        self.assertEqual(
            muc_xso.ActorBase.nick.type_.prepfunc,
            aioxmpp.stringprep.resourceprep
        )


class TestItemBase(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.ItemBase,
            xso.XSO
        ))

    def test_affiliation(self):
        self.assertIsInstance(
            muc_xso.ItemBase.affiliation,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ItemBase.affiliation.tag,
            (None, "affiliation")
        )
        self.assertIsInstance(
            muc_xso.ItemBase.affiliation.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            muc_xso.ItemBase.affiliation.validator.values,
            {
                "admin",
                "member",
                "none",
                "outcast",
                "owner",
                None,
            }
        )
        self.assertEqual(
            muc_xso.ItemBase.affiliation.validate,
            xso.ValidateMode.ALWAYS
        )
        self.assertEqual(
            muc_xso.ItemBase.affiliation.default,
            None
        )

    def test_jid(self):
        self.assertIsInstance(
            muc_xso.ItemBase.jid,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ItemBase.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            muc_xso.ItemBase.jid.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.ItemBase.jid.default)

    def test_nick(self):
        self.assertIsInstance(
            muc_xso.ItemBase.nick,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ItemBase.nick.tag,
            (None, "nick")
        )
        self.assertIsInstance(
            muc_xso.ItemBase.nick.type_,
            xso.String
        )
        self.assertEqual(
            muc_xso.ItemBase.nick.type_.prepfunc,
            aioxmpp.stringprep.resourceprep
        )

    def test_role(self):
        self.assertIsInstance(
            muc_xso.ItemBase.role,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.ItemBase.role.tag,
            (None, "role")
        )
        self.assertIsInstance(
            muc_xso.ItemBase.role.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            muc_xso.ItemBase.role.validator.values,
            {
                "moderator",
                "none",
                "participant",
                "visitor",
                None,
            }
        )
        self.assertEqual(
            muc_xso.ItemBase.role.validate,
            xso.ValidateMode.ALWAYS
        )
        self.assertEqual(
            muc_xso.ItemBase.role.default,
            None
        )


class TestUserActor(unittest.TestCase):
    def test_is_actor_base(self):
        self.assertTrue(issubclass(
            muc_xso.UserActor,
            muc_xso.ActorBase
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.UserActor.TAG,
            (utils.namespaces.xep0045_muc_user, "actor")
        )


class TestContinue(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.Continue,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.Continue.TAG,
            (utils.namespaces.xep0045_muc_user, "continue")
        )

    def test_thread(self):
        self.assertIsInstance(
            muc_xso.Continue.thread,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.Continue.thread.tag,
            (None, "thread")
        )
        self.assertEqual(
            muc_xso.Continue.thread.type_,
            stanza.Thread.identifier.type_
        )
        self.assertIsNone(
            muc_xso.Continue.thread.default,
        )


class TestUserItem(unittest.TestCase):
    def test_is_item_base(self):
        self.assertTrue(issubclass(
            muc_xso.UserItem,
            muc_xso.ItemBase
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.UserItem.TAG,
            (utils.namespaces.xep0045_muc_user, "item")
        )

    def test_actor(self):
        self.assertIsInstance(
            muc_xso.UserItem.actor,
            xso.Child
        )
        self.assertSetEqual(
            muc_xso.UserItem.actor._classes,
            {muc_xso.UserActor}
        )

    def test_continue_(self):
        self.assertIsInstance(
            muc_xso.UserItem.continue_,
            xso.Child
        )
        self.assertSetEqual(
            muc_xso.UserItem.continue_._classes,
            {muc_xso.Continue}
        )

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.UserItem.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.UserItem.reason.tag,
            (utils.namespaces.xep0045_muc_user, "reason")
        )
        self.assertIsNone(
            muc_xso.UserItem.reason.default
        )

    def test_init(self):
        item = muc_xso.UserItem()
        self.assertIsNone(item.affiliation)
        self.assertIsNone(item.jid)
        self.assertIsNone(item.nick)
        self.assertIsNone(item.role)
        self.assertIsNone(item.actor)
        self.assertIsNone(item.continue_)
        self.assertIsNone(item.reason)

        item = muc_xso.UserItem(
            affiliation="admin",
            role="moderator",
            jid=TEST_JID,
            nick="foo",
            reason="fnord"
        )

        self.assertEqual(
            item.affiliation,
            "admin"
        )
        self.assertEqual(
            item.jid,
            TEST_JID
        )
        self.assertEqual(
            item.nick,
            "foo"
        )
        self.assertEqual(
            item.role,
            "moderator",
        )
        self.assertEqual(
            item.reason,
            "fnord"
        )


class TestUserExt(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.UserExt,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.UserExt.TAG,
            (utils.namespaces.xep0045_muc_user, "x")
        )

    def test_status_codes(self):
        self.assertIsInstance(
            muc_xso.UserExt.status_codes,
            xso.ChildValueList
        )
        self.assertIs(
            muc_xso.UserExt.status_codes.container_type,
            set
        )
        self.assertIsInstance(
            muc_xso.UserExt.status_codes.type_,
            muc_xso.StatusCodeList
        )

    def test_destroy(self):
        self.assertIsInstance(
            muc_xso.UserExt.destroy,
            xso.Child,
        )
        self.assertSetEqual(
            muc_xso.UserExt.destroy._classes,
            {muc_xso.DestroyNotification}
        )

    def test_decline(self):
        self.assertIsInstance(
            muc_xso.UserExt.decline,
            xso.Child,
        )
        self.assertSetEqual(
            muc_xso.UserExt.decline._classes,
            {muc_xso.Decline}
        )

    def test_invites(self):
        self.assertIsInstance(
            muc_xso.UserExt.invites,
            xso.ChildList,
        )
        self.assertSetEqual(
            muc_xso.UserExt.invites._classes,
            {muc_xso.Invite}
        )

    def test_items(self):
        self.assertIsInstance(
            muc_xso.UserExt.items,
            xso.ChildList,
        )
        self.assertSetEqual(
            muc_xso.UserExt.items._classes,
            {muc_xso.UserItem}
        )

    def test_password(self):
        self.assertIsInstance(
            muc_xso.UserExt.password,
            xso.ChildText,
        )
        self.assertEqual(
            muc_xso.UserExt.password.tag,
            (utils.namespaces.xep0045_muc_user, "password")
        )
        self.assertIsNone(muc_xso.UserExt.password.default)

    def test_Presence_attr(self):
        self.assertIsInstance(
            stanza.Presence.xep0045_muc_user,
            xso.Child
        )
        self.assertIn(
            muc_xso.UserExt,
            stanza.Presence.xep0045_muc_user._classes
        )
        self.assertFalse(
            stanza.Presence.xep0045_muc_user.required
        )

    def test_Message_attr(self):
        self.assertIsInstance(
            stanza.Message.xep0045_muc_user,
            xso.Child
        )
        self.assertIn(
            muc_xso.UserExt,
            stanza.Message.xep0045_muc_user._classes
        )
        self.assertFalse(
            stanza.Message.xep0045_muc_user.required
        )

    def test_init(self):
        user_ext = muc_xso.UserExt()
        self.assertSetEqual(user_ext.status_codes, set())
        self.assertIsNone(user_ext.destroy)
        self.assertIsNone(user_ext.decline)
        self.assertFalse(user_ext.invites)
        self.assertFalse(user_ext.items)
        self.assertIsNone(user_ext.password)

        items = [
            muc_xso.UserItem(),
            muc_xso.UserItem(),
        ]

        invites = [
            muc_xso.Invite(),
            muc_xso.Invite(),
        ]

        destroy = muc_xso.DestroyNotification()

        decline = muc_xso.Decline()

        user_ext = muc_xso.UserExt(
            status_codes=[110, 110, 200],
            destroy=destroy,
            decline=decline,
            invites=invites,
            items=items,
            password="foobar",
        )
        self.assertSetEqual(user_ext.status_codes, {110, 110, 200})
        self.assertIs(user_ext.destroy, destroy)
        self.assertIs(user_ext.decline, decline)
        self.assertSequenceEqual(user_ext.invites, invites)
        self.assertSequenceEqual(user_ext.items, items)
        self.assertEqual(user_ext.password, "foobar")


class TestAdminActor(unittest.TestCase):
    def test_is_actor_base(self):
        self.assertTrue(issubclass(
            muc_xso.AdminActor,
            muc_xso.ActorBase
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.AdminActor.TAG,
            (utils.namespaces.xep0045_muc_admin, "actor")
        )


class TestAdminItem(unittest.TestCase):
    def test_is_item_base(self):
        self.assertTrue(issubclass(
            muc_xso.AdminItem,
            muc_xso.ItemBase
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.AdminItem.TAG,
            (utils.namespaces.xep0045_muc_admin, "item")
        )

    def test_actor(self):
        self.assertIsInstance(
            muc_xso.AdminItem.actor,
            xso.Child
        )
        self.assertSetEqual(
            muc_xso.AdminItem.actor._classes,
            {muc_xso.AdminActor}
        )

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.AdminItem.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.AdminItem.reason.tag,
            (utils.namespaces.xep0045_muc_admin, "reason")
        )
        self.assertIsNone(
            muc_xso.AdminItem.reason.default
        )

    def test_init(self):
        item = muc_xso.AdminItem()
        self.assertIsNone(item.affiliation)
        self.assertIsNone(item.jid)
        self.assertIsNone(item.nick)
        self.assertIsNone(item.role)
        self.assertIsNone(item.actor)
        self.assertIsNone(item.reason)

        item = muc_xso.AdminItem(
            affiliation="admin",
            role="moderator",
            jid=TEST_JID,
            nick="foo",
            reason="foobar",
        )

        self.assertEqual(
            item.affiliation,
            "admin"
        )
        self.assertEqual(
            item.jid,
            TEST_JID
        )
        self.assertEqual(
            item.nick,
            "foo"
        )
        self.assertEqual(
            item.role,
            "moderator",
        )
        self.assertEqual(
            item.reason,
            "foobar"
        )


class TestAdminQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.AdminQuery,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.AdminQuery.TAG,
            (utils.namespaces.xep0045_muc_admin, "query")
        )

    def test_items(self):
        self.assertIsInstance(
            muc_xso.AdminQuery.items,
            xso.ChildList
        )
        self.assertSetEqual(
            muc_xso.AdminQuery.items._classes,
            {muc_xso.AdminItem}
        )

    def test_is_iq_payload(self):
        self.assertIn(
            muc_xso.AdminQuery.TAG,
            stanza.IQ.CHILD_MAP
        )
        self.assertIs(
            stanza.IQ.CHILD_MAP[muc_xso.AdminQuery.TAG],
            stanza.IQ.payload.xq_descriptor
        )

    def test_init(self):
        query = muc_xso.AdminQuery()
        self.assertFalse(query.items)

        item = muc_xso.AdminItem()
        query = muc_xso.AdminQuery(
            items=[
                item
            ]
        )

        self.assertEqual(query.items[0], item)

        with self.assertRaisesRegex(TypeError, "positional argument"):
            muc_xso.AdminQuery([])


class TestDestroyRequest(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.DestroyRequest,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.DestroyRequest.TAG,
            (utils.namespaces.xep0045_muc_owner, "destroy")
        )

    def test_reason(self):
        self.assertIsInstance(
            muc_xso.DestroyRequest.reason,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.DestroyRequest.reason.tag,
            (utils.namespaces.xep0045_muc_owner, "reason")
        )
        self.assertIsNone(
            muc_xso.DestroyRequest.reason.default
        )

    def test_password(self):
        self.assertIsInstance(
            muc_xso.DestroyRequest.password,
            xso.ChildText
        )
        self.assertEqual(
            muc_xso.DestroyRequest.password.tag,
            (utils.namespaces.xep0045_muc_owner, "password")
        )
        self.assertIsNone(
            muc_xso.DestroyRequest.password.default
        )

    def test_jid(self):
        self.assertIsInstance(
            muc_xso.DestroyRequest.jid,
            xso.Attr
        )
        self.assertEqual(
            muc_xso.DestroyRequest.jid.tag,
            (None, "jid")
        )
        self.assertIsInstance(
            muc_xso.DestroyRequest.jid.type_,
            xso.JID
        )
        self.assertIsNone(muc_xso.DestroyRequest.jid.default)


class TestOwnerQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            muc_xso.OwnerQuery,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            muc_xso.OwnerQuery.TAG,
            (utils.namespaces.xep0045_muc_owner, "query")
        )

    def test_destroy(self):
        self.assertIsInstance(
            muc_xso.OwnerQuery.destroy,
            xso.Child
        )
        self.assertSetEqual(
            muc_xso.OwnerQuery.destroy._classes,
            {muc_xso.DestroyRequest}
        )

    def test_form(self):
        self.assertIsInstance(
            muc_xso.OwnerQuery.form,
            xso.Child
        )
        self.assertSetEqual(
            muc_xso.OwnerQuery.form._classes,
            {forms.Data}
        )

    def test_is_iq_payload(self):
        self.assertIn(
            muc_xso.OwnerQuery.TAG,
            stanza.IQ.CHILD_MAP
        )
        self.assertIs(
            stanza.IQ.CHILD_MAP[muc_xso.OwnerQuery.TAG],
            stanza.IQ.payload.xq_descriptor
        )

    def test_init(self):
        oq = muc_xso.OwnerQuery()
        self.assertIsNone(oq.destroy)
        self.assertIsNone(oq.form)

    def test_init_form(self):
        oq = muc_xso.OwnerQuery(form=unittest.mock.sentinel.form)
        self.assertEqual(
            oq.form,
            unittest.mock.sentinel.form,
        )

    def test_init_destroy(self):
        oq = muc_xso.OwnerQuery(destroy=unittest.mock.sentinel.destroy)
        self.assertEqual(
            oq.destroy,
            unittest.mock.sentinel.destroy,
        )
