########################################################################
# File name: test_service.py
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
import asyncio
import contextlib
import functools
import unittest
import uuid

from datetime import datetime, timedelta

import aioxmpp.callbacks
import aioxmpp.errors
import aioxmpp.forms
import aioxmpp.im.conversation as im_conversation
import aioxmpp.im.dispatcher as im_dispatcher
import aioxmpp.im.service as im_service
import aioxmpp.im.p2p as im_p2p
import aioxmpp.misc
import aioxmpp.muc.service as muc_service
import aioxmpp.muc.xso as muc_xso
import aioxmpp.service as service
import aioxmpp.stanza
import aioxmpp.structs
import aioxmpp.tracking
import aioxmpp.utils as utils

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
    make_listener,
)


TEST_MUC_JID = aioxmpp.structs.JID.fromstr(
    "coven@chat.shakespeare.lit"
)

TEST_ENTITY_JID = aioxmpp.structs.JID.fromstr(
    "foo@bar.example/fnord"
)


class TestOccupant(unittest.TestCase):
    def test_init_mostly_default(self):
        occ = muc_service.Occupant(
            TEST_MUC_JID.replace(resource="firstwitch"),
            unittest.mock.sentinel.is_self,
        )
        self.assertEqual(occ.is_self, unittest.mock.sentinel.is_self)
        self.assertEqual(
            occ.conversation_jid,
            TEST_MUC_JID.replace(resource="firstwitch")
        )
        self.assertEqual(
            occ.nick,
            "firstwitch"
        )
        self.assertEqual(
            occ.presence_state,
            aioxmpp.structs.PresenceState(available=True)
        )
        self.assertDictEqual(occ.presence_status, {})
        self.assertIsInstance(occ.presence_status,
                              aioxmpp.structs.LanguageMap)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertEqual(occ.is_self, unittest.mock.sentinel.is_self)

    def test_init_full(self):
        status = {
            aioxmpp.structs.LanguageTag.fromstr("de-de"): "Hex-hex!",
            None: "Witchcraft!"
        }

        occ = muc_service.Occupant(
            TEST_MUC_JID.replace(resource="firstwitch"),
            unittest.mock.sentinel.is_self,
            presence_state=aioxmpp.structs.PresenceState(
                available=True,
                show=aioxmpp.PresenceShow.AWAY,
            ),
            presence_status=status,
            affiliation="admin",
            role="moderator",
            jid=TEST_ENTITY_JID
        )

        self.assertEqual(
            occ.presence_state,
            aioxmpp.structs.PresenceState(
                available=True,
                show=aioxmpp.PresenceShow.AWAY,
            )
        )

        self.assertDictEqual(
            occ.presence_status,
            status
        )
        self.assertIsNot(
            occ.presence_status,
            status
        )
        self.assertIsInstance(
            occ.presence_status,
            aioxmpp.structs.LanguageMap
        )

        self.assertEqual(
            occ.affiliation,
            "admin"
        )

        self.assertEqual(
            occ.role,
            "moderator"
        )

        self.assertEqual(
            occ.direct_jid,
            TEST_ENTITY_JID
        )

        self.assertEqual(
            occ.is_self,
            unittest.mock.sentinel.is_self,
        )

    def test_from_presence_can_deal_with_sparse_presence(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            show=aioxmpp.PresenceShow.DND,
        )

        presence.status[None] = "foo"

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self
        )
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertIsNone(occ.direct_jid)
        self.assertEqual(occ.is_self, unittest.mock.sentinel.is_self)

        presence.status[None] = "foo"
        presence.xep0045_muc_user = muc_xso.UserExt()

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertIsNone(occ.direct_jid)

    def test_from_presence_can_deal_with_sparse_presence(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            show=aioxmpp.PresenceShow.DND,
        )

        presence.status[None] = "foo"

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self
        )
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertIsNone(occ.affiliation)
        self.assertEqual(occ.role, "none")
        self.assertIsNone(occ.direct_jid)
        self.assertEqual(occ.is_self, unittest.mock.sentinel.is_self)

    def test_from_presence_extracts_what_it_can_get(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            show=aioxmpp.PresenceShow.DND,
        )

        presence.status[None] = "foo"

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID
                )
            ]
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self
        )
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertEqual(occ.affiliation, "owner")
        self.assertEqual(occ.role, "moderator")
        self.assertEqual(occ.direct_jid, TEST_ENTITY_JID)
        self.assertEqual(occ.is_self, unittest.mock.sentinel.is_self)

    def test_update_raises_for_different_occupantjids(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )

        with self.assertRaisesRegex(ValueError, "mismatch"):
            occ.update(muc_service.Occupant.from_presence(
                presence,
                unittest.mock.sentinel.is_self,
            ))

    def test_update_updates_all_the_fields(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            show=aioxmpp.PresenceShow.DND,
        )

        presence.status[None] = "foo"

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID
                )
            ]
        )

        old_status_dict = occ.presence_status

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))
        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertEqual(occ.affiliation, "owner")
        self.assertEqual(occ.role, "moderator")
        self.assertEqual(occ.direct_jid, TEST_ENTITY_JID)

        self.assertIs(occ.presence_status, old_status_dict)

    def test_update_does_not_copy_None(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID
                )
            ]
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
        )

        old_status_dict = occ.presence_status

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))
        self.assertEqual(occ.conversation_jid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertEqual(occ.affiliation, "owner")
        self.assertEqual(occ.role, "moderator")
        self.assertEqual(occ.direct_jid, TEST_ENTITY_JID)

        self.assertIs(occ.presence_status, old_status_dict)

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
        )

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))

        self.assertEqual(occ.role, "none")

    def test_random_uid_without_jid(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        uuid_sentinel = uuid.UUID(bytes=b"0123456789abcdef")

        with contextlib.ExitStack() as stack:
            uuid4 = stack.enter_context(unittest.mock.patch("uuid.uuid4"))
            uuid4.return_value = uuid_sentinel

            occ = muc_service.Occupant.from_presence(
                presence,
                unittest.mock.sentinel.is_self,
            )

        uuid4.assert_called_once_with()

        self.assertEqual(
            b"urn:uuid:" + uuid_sentinel.bytes,
            occ.uid,
        )

    def test_uid_from_jid_if_jid_is_known(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID.replace(resource="foo")
                )
            ]
        )

        with contextlib.ExitStack() as stack:
            uuid4 = stack.enter_context(unittest.mock.patch("uuid.uuid4"))

            occ = muc_service.Occupant.from_presence(
                presence,
                unittest.mock.sentinel.is_self,
            )

        uuid4.assert_not_called()

        self.assertEqual(
            b"xmpp:" + str(TEST_ENTITY_JID.bare()).encode("utf-8"),
            occ.uid,
        )

    def test_uid_stays_constant_over_updates(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                )
            ]
        )

        old_uid = occ.uid

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))

        self.assertEqual(old_uid, occ.uid)

    def test_uid_changes_if_jid_becomes_known(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID
                )
            ]
        )

        old_uid = occ.uid

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))

        self.assertEqual(
            b"xmpp:" + str(TEST_ENTITY_JID.bare()).encode("utf-8"),
            occ.uid,
        )

        self.assertNotEqual(old_uid, occ.uid)

    def test_uid_stays_intact_if_jid_becomes_unknown(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(
                    affiliation="owner",
                    role="moderator",
                    jid=TEST_ENTITY_JID
                )
            ]
        )

        occ = muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        )

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        old_uid = occ.uid

        occ.update(muc_service.Occupant.from_presence(
            presence,
            unittest.mock.sentinel.is_self,
        ))

        self.assertEqual(old_uid, occ.uid)


class TestServiceMember(unittest.TestCase):
    def setUp(self):
        self.mucjid = TEST_MUC_JID
        self.sm = muc_service.ServiceMember(self.mucjid)

    def test_defaults_for_Occupant_attributes(self):
        self.assertEqual(
            self.sm.presence_state,
            aioxmpp.structs.PresenceState(False),
        )

        self.assertDictEqual(
            self.sm.presence_status,
            {}
        )

        self.assertIsInstance(
            self.sm.presence_status,
            aioxmpp.structs.LanguageMap,
        )

        self.assertIs(self.sm.affiliation, None)
        self.assertIs(self.sm.role, None)

        self.assertEqual(self.sm.direct_jid, self.mucjid)
        self.assertEqual(self.sm.conversation_jid, self.mucjid)

        self.assertIsNone(self.sm.nick)

        self.assertEqual(self.sm.uid,
                         b"xmpp:" + str(self.mucjid).encode("utf-8"))

        self.assertFalse(self.sm.is_self)


class TestRoom(unittest.TestCase):
    def setUp(self):
        self.mucjid = TEST_MUC_JID

        self.base = unittest.mock.Mock()
        self.base.service.logger = unittest.mock.Mock(name="logger")
        self.base.service.client.send = \
            CoroutineMock()
        self.base.service.dependencies = {}
        self.base.service.dependencies[
            aioxmpp.tracking.BasicTrackingService
        ] = self.base.tracking_service

        self.jmuc = muc_service.Room(self.base.service, self.mucjid)

        for ev in ["on_enter", "on_exit", "on_muc_suspend", "on_muc_resume",
                   "on_message", "on_topic_changed",
                   "on_join", "on_presence_changed", "on_nick_changed",
                   "on_muc_role_changed", "on_muc_affiliation_changed",
                   "on_leave", "on_muc_enter"]:
            cb = getattr(self.base, ev)
            cb.return_value = None
            getattr(self.jmuc, ev).connect(cb)

        self.listener = make_listener(self.jmuc)

        self.msg_end_of_history = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        self.msg_end_of_history.subject.update({None: None})
        self.msg_end_of_history.xep0045_muc_user = muc_xso.UserExt()

    def tearDown(self):
        del self.jmuc

    def test_event_attributes(self):
        self.assertIsInstance(
            self.jmuc.on_message,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertFalse(hasattr(
            self.jmuc,
            "on_private_message"
        ))
        self.assertIsInstance(
            self.jmuc.on_join,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_leave,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_presence_changed,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_muc_affiliation_changed,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_nick_changed,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_muc_role_changed,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_topic_changed,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_muc_suspend,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_muc_resume,
            aioxmpp.callbacks.AdHocSignal
        )

    def test_init(self):
        self.assertIs(self.jmuc.service, self.base.service)
        self.assertEqual(self.jmuc.jid, self.mucjid)
        self.assertDictEqual(self.jmuc.muc_subject, {})
        self.assertIsInstance(self.jmuc.muc_subject, aioxmpp.structs.LanguageMap)
        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        self.assertIsNone(self.jmuc.muc_subject_setter)
        self.assertIsNone(self.jmuc.me)
        self.assertFalse(self.jmuc.muc_autorejoin)
        self.assertIsNone(self.jmuc.muc_password)

    def test_service_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.service = self.base.service

    def test_jid_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.jid = self.mucjid

    def test_active_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.muc_active = True

    def test_subject_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.muc_subject = "foo"

    def test_subject_setter_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.muc_subject_setter = "bar"

    def test_joined_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.muc_joined = True

    def test_me_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.me = muc_service.Occupant(
                TEST_MUC_JID.replace(resource="foo"),
                True,
            )

    def test_service_member_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.service_member = self.jmuc.service_member

    def test_service_member_attribute(self):
        self.assertIsInstance(
            self.jmuc.service_member,
            muc_service.ServiceMember,
        )

        self.assertEqual(
            self.jmuc.service_member.conversation_jid,
            self.jmuc.jid,
        )

    def test__suspend_with_autorejoin(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertTrue(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        self.assertIsNotNone(self.jmuc.me)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_suspend(),
            ]
        )

    def test__suspend_without_autorejoin(self):
        # this is identical to the above testcase, autorejoin should be handled
        # by the Service class

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = False
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertFalse(self.jmuc.muc_active)
        self.assertTrue(self.jmuc.muc_joined)
        self.assertIsNotNone(self.jmuc.me)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_suspend(),
            ]
        )

    def test__disconnect(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        self.assertIsNotNone(self.jmuc.me)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_exit(
                    muc_leave_mode=muc_service.LeaveMode.DISCONNECTED,
                ),
            ]
        )

    def test__disconnect_during_suspend(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        self.assertIsNotNone(self.jmuc.me)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_suspend(),
                unittest.mock.call.on_exit(
                    muc_leave_mode=muc_service.LeaveMode.DISCONNECTED
                ),
            ]
        )

    def test__disconnect_is_noop_if_not_entered(self):
        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
            ]
        )

    def test__suspend__resume_cycle(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)

        self.jmuc.muc_autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertTrue(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        old_occupant = self.jmuc.me

        self.jmuc._resume()

        self.assertTrue(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        self.assertTrue(self.jmuc.muc_active)
        self.assertIsNot(old_occupant, self.jmuc.me)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_suspend(),
                unittest.mock.call.on_muc_resume(),
                unittest.mock.call.on_muc_enter(
                    presence, self.jmuc.me,
                    muc_status_codes={110},
                ),
                unittest.mock.call.on_enter(),
            ]
        )

    def test__inbound_muc_user_presence_emits_on_join_for_new_users(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(
                        Occupant.from_presence()
                    )
                ]
            )
            self.base.mock_calls.clear()

            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                ]
            )

    def test__inbound_muc_user_presence_ignored_from_bare_jid(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource=None)
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            self.jmuc._inbound_muc_user_presence(presence)

        Occupant.from_presence.assert_not_called()

        self.base.on_join.assert_not_called()

    def test__inbound_muc_user_presence_emits_on_leave_for_unavailable(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE

            second = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.NORMAL,
                        muc_actor=None,
                        muc_reason=None,
                        muc_status_codes=set(),
                    )
                ]
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_kick(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        actor = object()

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({307})
            presence.xep0045_muc_user.items[0].reason = "Avaunt, you cullion!"
            presence.xep0045_muc_user.items[0].role = "none"
            presence.xep0045_muc_user.items[0].actor = actor

            second = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="Avaunt, you cullion!",
                        status_codes={307},
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.KICKED,
                        muc_actor=actor,
                        muc_reason="Avaunt, you cullion!",
                        muc_status_codes={307},
                    )
                ]
            )

            self.assertEqual(
                first.role,
                "none"
            )
            self.assertEqual(
                first.affiliation,
                "member"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_error_kick(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        actor = object()

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({307, 333})
            presence.xep0045_muc_user.items[0].reason = "Error"
            presence.xep0045_muc_user.items[0].role = "none"
            presence.xep0045_muc_user.items[0].actor = actor

            second = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="Error",
                        status_codes={307, 333},
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.ERROR,
                        muc_actor=actor,
                        muc_reason="Error",
                        muc_status_codes={307, 333},
                    )
                ]
            )

            self.assertEqual(
                first.role,
                "none"
            )
            self.assertEqual(
                first.affiliation,
                "member"
            )

    def test__inbound_muc_user_presence_handles_itemless_role_change(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        actor = object()

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.clear()
            del presence.xep0045_muc_user.items[0]

            second = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=None,
                        reason=None,
                        status_codes=set(),
                    ),
                    unittest.mock.call.on_muc_affiliation_changed(
                        presence,
                        first,
                        actor=None,
                        reason=None,
                        status_codes=set(),
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.NORMAL,
                        muc_actor=None,
                        muc_reason=None,
                        muc_status_codes=set(),
                    )
                ]
            )

            self.assertEqual(
                first.role,
                "none",
            )
            self.assertEqual(
                first.affiliation,
                "member",
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_ban(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        actor = object()
        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(
                presence,
                False,
            )

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({301})
            presence.xep0045_muc_user.items[0].reason = "Treason"
            presence.xep0045_muc_user.items[0].affiliation = "outcast"
            presence.xep0045_muc_user.items[0].role = "none"
            presence.xep0045_muc_user.items[0].actor = actor

            second = original_Occupant.from_presence(
                presence,
                False,
            )
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="Treason",
                        status_codes={301},
                    ),
                    unittest.mock.call.on_muc_affiliation_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="Treason",
                        status_codes={301},
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.BANNED,
                        muc_actor=actor,
                        muc_reason="Treason",
                        muc_status_codes={301},
                    )
                ]
            )
            self.assertEqual(
                first.affiliation,
                "outcast"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_affiliation_change(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        actor = object()
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({321})
            presence.xep0045_muc_user.items[0].reason = "foo"
            presence.xep0045_muc_user.items[0].actor = actor
            presence.xep0045_muc_user.items[0].affiliation = "none"
            presence.xep0045_muc_user.items[0].role = "none"

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="foo",
                        status_codes={321},
                    ),
                    unittest.mock.call.on_muc_affiliation_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="foo",
                        status_codes={321},
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.AFFILIATION_CHANGE,
                        muc_actor=actor,
                        muc_reason="foo",
                        muc_status_codes={321},
                    )
                ]
            )
            self.assertEqual(
                first.affiliation,
                "none"
            )
            self.assertEqual(
                first.role,
                "none"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_moderation_change(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="none",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        actor = object()
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({322})
            presence.xep0045_muc_user.items[0].reason = "foo"
            presence.xep0045_muc_user.items[0].actor = actor
            presence.xep0045_muc_user.items[0].affiliation = "none"
            presence.xep0045_muc_user.items[0].role = "none"

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_role_changed(
                        presence,
                        first,
                        actor=actor,
                        reason="foo",
                        status_codes={322},
                    ),
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.MODERATION_CHANGE,
                        muc_actor=actor,
                        muc_reason="foo",
                        muc_status_codes={322},
                    )
                ]
            )
            self.assertEqual(
                first.affiliation,
                "none"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_system_shutdown(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="none",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.update({332})
            presence.xep0045_muc_user.items[0].reason = "foo"

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_leave(
                        first,
                        muc_leave_mode=muc_service.LeaveMode.SYSTEM_SHUTDOWN,
                        muc_actor=None,
                        muc_reason="foo",
                        muc_status_codes={332},
                    )
                ]
            )
            self.assertEqual(
                first.affiliation,
                "none"
            )

    def test__inbound_muc_user_presence_emits_on_presence_changed(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.show = aioxmpp.PresenceShow.AWAY

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_presence_changed(
                        first,
                        None,
                        presence,
                    )
                ]
            )

            self.assertEqual(
                first.presence_state,
                aioxmpp.structs.PresenceState.from_stanza(presence)
            )
            self.assertDictEqual(
                first.presence_status,
                presence.status
            )

    def test__inbound_muc_user_presence_emits_on_nick_changed(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ]
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.add(303)
            presence.xep0045_muc_user.items[0].nick = "oldhag"

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_nick_changed(
                        first,
                        "thirdwitch",
                        "oldhag",
                    )
                ]
            )
            self.base.mock_calls.clear()

            self.assertEqual(
                first.conversation_jid,
                TEST_MUC_JID.replace(resource="oldhag"),
            )

            presence = aioxmpp.stanza.Presence(
                type_=aioxmpp.structs.PresenceType.AVAILABLE,
                from_=TEST_MUC_JID.replace(resource="oldhag")
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                items=[
                    muc_xso.UserItem(affiliation="member",
                                     role="participant"),
                ]
            )

            third = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = third
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                ]
            )
            self.base.mock_calls.clear()

    def test__inbound_muc_self_presence_emits_on_nick_changed(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, True)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, True)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_muc_enter(
                        presence, first,
                        muc_status_codes={110},
                    ),
                    unittest.mock.call.on_enter(),
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
            presence.xep0045_muc_user.status_codes.add(303)
            presence.xep0045_muc_user.status_codes.add(110)
            presence.xep0045_muc_user.items[0].nick = "oldhag"

            second = original_Occupant.from_presence(presence, True)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_nick_changed(
                        first,
                        "thirdwitch",
                        "oldhag",
                    )
                ]
            )
            self.base.mock_calls.clear()

            self.assertEqual(
                first.conversation_jid,
                TEST_MUC_JID.replace(resource="oldhag"),
            )

            presence = aioxmpp.stanza.Presence(
                type_=aioxmpp.structs.PresenceType.AVAILABLE,
                from_=TEST_MUC_JID.replace(resource="oldhag")
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                items=[
                    muc_xso.UserItem(affiliation="member",
                                     role="participant"),
                ]
            )
            presence.xep0045_muc_user.status_codes.add(110)

            third = original_Occupant.from_presence(presence, True)
            Occupant.from_presence.return_value = third
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                ]
            )
            self.base.mock_calls.clear()

    def test__inbound_muc_user_presence_emits_on_various_changes(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant")
            ]
        )

        original_Occupant = muc_service.Occupant
        with unittest.mock.patch("aioxmpp.muc.service.Occupant") as Occupant:
            first = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence, False)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.show = aioxmpp.PresenceShow.AWAY
            presence.xep0045_muc_user.items[0].affiliation = "owner"
            presence.xep0045_muc_user.items[0].role = "moderator"
            presence.xep0045_muc_user.items[0].reason = "foobar"

            second = original_Occupant.from_presence(presence, False)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_presence_changed(
                        first,
                        None,
                        presence,
                    ),
                    unittest.mock.call.on_muc_role_changed(
                        presence, first,
                        actor=None,
                        reason="foobar",
                        status_codes=set(),
                    ),
                    unittest.mock.call.on_muc_affiliation_changed(
                        presence, first,
                        actor=None,
                        reason="foobar",
                        status_codes=set(),
                    ),
                ]
            )

            self.assertEqual(
                first.presence_state,
                aioxmpp.structs.PresenceState.from_stanza(presence)
            )
            self.assertDictEqual(
                first.presence_status,
                presence.status
            )
            self.assertEqual(
                first.affiliation,
                "owner"
            )
            self.assertEqual(
                first.role,
                "moderator"
            )

    def test_handle_message_handles_subject_of_occupant(self):
        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt()

        self.jmuc._inbound_muc_user_presence(pres)

        _, (occupant, ), _ = self.base.on_join.mock_calls[-1]
        self.base.mock_calls.clear()

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.subject.update({
            None: "foo"
        })

        old_subject = self.jmuc.muc_subject

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.assertDictEqual(
            self.jmuc.muc_subject,
            msg.subject
        )
        self.assertIsNot(self.jmuc.muc_subject, msg.subject)
        self.assertIsNot(self.jmuc.muc_subject, old_subject)
        self.assertEqual(self.jmuc.muc_subject_setter, msg.from_.resource)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_topic_changed(
                    occupant,
                    {
                        None: "foo",
                    },
                    muc_nick=occupant.nick,
                )
            ]
        )

    def test_handle_message_handles_subject_of_non_occupant(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.subject.update({
            None: "foo"
        })

        old_subject = self.jmuc.muc_subject

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.assertDictEqual(
            self.jmuc.muc_subject,
            msg.subject
        )
        self.assertIsNot(self.jmuc.muc_subject, msg.subject)
        self.assertIsNot(self.jmuc.muc_subject, old_subject)
        self.assertEqual(self.jmuc.muc_subject_setter, msg.from_.resource)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_topic_changed(
                    unittest.mock.ANY,
                    msg.subject,
                    muc_nick=msg.from_.resource,
                )
            ]
        )

    def test_handle_message_handles_subject_from_service(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource=None),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.subject.update({
            None: "foo"
        })

        old_subject = self.jmuc.muc_subject

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.assertDictEqual(
            self.jmuc.muc_subject,
            msg.subject
        )
        self.assertIsNot(self.jmuc.muc_subject, msg.subject)
        self.assertIsNot(self.jmuc.muc_subject, old_subject)
        self.assertEqual(self.jmuc.muc_subject_setter, msg.from_.resource)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_topic_changed(
                    self.jmuc.service_member,
                    msg.subject,
                    muc_nick=msg.from_.resource,
                )
            ]
        )

    def test_handle_message_ignores_subject_if_body_is_present(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.subject.update({
            None: "foo"
        })
        msg.body.update({
            aioxmpp.structs.LanguageTag.fromstr("de"): "bar"
        })

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source
        )

        self.assertDictEqual(
            self.jmuc.muc_subject,
            {}
        )
        self.assertIsNone(self.jmuc.muc_subject_setter)

        self.base.on_topic_changed.assert_not_called()

    def test_handle_message_does_not_reset_subject_if_no_subject_given(self):
        self.jmuc.muc_subject[None] = "foo"

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source
        )

        self.assertDictEqual(
            self.jmuc.muc_subject,
            {
                None: "foo"
            }
        )
        self.assertIsNone(self.jmuc.muc_subject_setter)

        self.base.on_topic_changed.assert_not_called()

    def test_inbound_groupchat_message_with_body_emits_on_message(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.body[None] = "foo"

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.base.on_message.assert_called_once_with(
            msg,
            unittest.mock.ANY,
            unittest.mock.sentinel.source,
            tracker=None,
        )

    def test_inbound_groupchat_message_with_body_emits_on_message_from_service(self):  # NOQA
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource=None),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.body[None] = "foo"

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.base.on_message.assert_called_once_with(
            msg,
            self.jmuc.service_member,
            unittest.mock.sentinel.source,
            tracker=None,
        )

    def test_inbound_groupchat_message_with_body_emits_on_message_with_me(self):
        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt(status_codes={110})

        self.jmuc._inbound_muc_user_presence(pres)

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.body[None] = "foo"

        with contextlib.ExitStack() as stack:
            MessageTracker = stack.enter_context(
                unittest.mock.patch("aioxmpp.tracking.MessageTracker")
            )

            self.jmuc._handle_message(
                msg,
                msg.from_,
                False,
                unittest.mock.sentinel.source,
            )

        MessageTracker.assert_called_once_with()

        MessageTracker()._set_state.assert_called_once_with(
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        MessageTracker().close.assert_called_once_with()

        self.base.on_message.assert_called_once_with(
            msg,
            self.jmuc.me,
            unittest.mock.sentinel.source,
            tracker=MessageTracker(),
        )

    def test_inbound_groupchat_message_with_body_emits_on_message_other_member(
            self):
        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt(status_codes={})

        self.jmuc._inbound_muc_user_presence(pres)

        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt(status_codes={110})

        self.jmuc._inbound_muc_user_presence(pres)

        _, (occupant, ), _ = self.base.on_join.mock_calls[-1]
        self.base.mock_calls.clear()

        self.base.on_muc_enter.assert_called_once_with(
            pres,
            self.jmuc.me,
            muc_status_codes=unittest.mock.ANY,
        )
        self.base.on_enter.assert_called_once_with()
        self.base.mock_calls.clear()

        # end of history replay
        self.jmuc._handle_message(self.msg_end_of_history,
                                  self.msg_end_of_history.from_,
                                  False,
                                  im_dispatcher.MessageSource.STREAM)

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.body[None] = "foo"

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.base.on_message.assert_called_once_with(
            msg,
            occupant,
            unittest.mock.sentinel.source,
            tracker=None,
        )

    def test_invent_temporary_member_for_message_from_non_occupant(self):
        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt(status_codes={})

        self.jmuc._inbound_muc_user_presence(pres)

        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt(status_codes={110})

        self.jmuc._inbound_muc_user_presence(pres)

        self.base.on_muc_enter.assert_called_once_with(
            pres,
            self.jmuc.me,
            muc_status_codes=unittest.mock.ANY,
        )
        self.base.on_enter.assert_called_once_with()
        self.base.mock_calls.clear()

        # end of history replay
        self.jmuc._handle_message(self.msg_end_of_history,
                                  self.msg_end_of_history.from_,
                                  False,
                                  im_dispatcher.MessageSource.STREAM)

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="interloper"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        msg.body[None] = "foo"

        self.jmuc._handle_message(
            msg,
            msg.from_,
            False,
            unittest.mock.sentinel.source,
        )

        self.base.on_message.assert_called_once_with(
            msg,
            unittest.mock.ANY,
            unittest.mock.sentinel.source,
            tracker=None,
        )

        _, (_, occupant, *_), _ = self.base.on_message.mock_calls[0]

        self.assertIsInstance(occupant, muc_service.Occupant)
        self.assertEqual(occupant.nick, "interloper")
        self.assertIsNone(occupant.direct_jid)
        self.assertFalse(occupant.is_self)
        self.assertEqual(occupant.presence_state,
                         aioxmpp.structs.PresenceState(available=False))

        self.assertNotIn(occupant, self.jmuc.members)

    def test__inbound_muc_user_presence_emits_on_enter_and_on_exit(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_enter(
                    presence,
                    self.jmuc.me,
                    muc_status_codes={110},
                ),
                unittest.mock.call.on_enter(),
            ]
        )
        self.base.mock_calls.clear()

        self.assertTrue(self.jmuc.muc_joined)
        self.assertTrue(self.jmuc.muc_active)
        self.assertIsInstance(
            self.jmuc.me,
            muc_service.Occupant
        )
        self.assertEqual(
            self.jmuc.me.conversation_jid,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertTrue(
            self.jmuc.me.is_self
        )

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_exit(
                    muc_leave_mode=muc_service.LeaveMode.NORMAL,
                    muc_actor=None,
                    muc_reason=None,
                    muc_status_codes={110}
                )
            ]
        )
        self.assertFalse(self.jmuc.muc_joined)
        self.assertIsInstance(
            self.jmuc.me,
            muc_service.Occupant
        )
        self.assertEqual(
            self.jmuc.me.conversation_jid,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertTrue(
            self.jmuc.me.is_self
        )
        self.assertFalse(self.jmuc.muc_active)

    def test_on_muc_enter_forwards_status_codes(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110, 1234, 375},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_enter(
                    presence,
                    self.jmuc.me,
                    muc_status_codes={
                        110,
                        375,
                        1234,
                    }
                ),
                unittest.mock.call.on_enter(),
            ]
        )

    def test_detect_self_presence_from_jid_if_status_is_missing(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_enter(
                    presence,
                    self.jmuc.me,
                    muc_status_codes={110},
                ),
                unittest.mock.call.on_enter(),
            ]
        )
        self.base.mock_calls.clear()

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={307},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_exit(
                    muc_leave_mode=muc_service.LeaveMode.KICKED,
                    muc_actor=None,
                    muc_reason=None,
                    muc_status_codes={307},
                )
            ]
        )
        self.assertFalse(self.jmuc.muc_joined)
        self.assertIsInstance(
            self.jmuc.me,
            muc_service.Occupant
        )
        self.assertEqual(
            self.jmuc.me.conversation_jid,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertTrue(
            self.jmuc.me.is_self
        )
        self.assertFalse(self.jmuc.muc_active)

    def test_do_not_treat_unavailable_stanzas_as_join(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_muc_enter(
                    presence,
                    self.jmuc.me,
                    muc_status_codes={110},
                ),
                unittest.mock.call.on_enter(),
            ]
        )
        self.base.mock_calls.clear()

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            from_=TEST_MUC_JID.replace(resource="foo")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
            ]
        )

    def test__inbound_muc_user_presence_ignores_self_leave_if_inactive(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch"),
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
            ]
        )
        self.base.mock_calls.clear()

        self.assertFalse(self.jmuc.muc_joined)
        self.assertFalse(self.jmuc.muc_active)
        self.assertIsNone(self.jmuc.me)

    def test_muc_set_role(self):
        new_role = "participant"

        with unittest.mock.patch.object(
                self.base.service.client,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            run_coroutine(self.jmuc.muc_set_role(
                "thirdwitch",
                new_role,
                reason="foobar",
            ))

        _, (iq,), _ = send_iq.mock_calls[-1]

        self.assertIsInstance(
            iq,
            aioxmpp.stanza.IQ
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.structs.IQType.SET,
        )
        self.assertEqual(
            iq.to,
            self.mucjid
        )

        self.assertIsInstance(
            iq.payload,
            muc_xso.AdminQuery
        )

        self.assertEqual(
            len(iq.payload.items),
            1
        )
        item = iq.payload.items[0]
        self.assertIsInstance(
            item,
            muc_xso.AdminItem
        )
        self.assertEqual(
            item.nick,
            "thirdwitch"
        )
        self.assertEqual(
            item.reason,
            "foobar"
        )
        self.assertEqual(
            item.role,
            new_role
        )

    def test_muc_set_role_rejects_None_nick(self):
        with unittest.mock.patch.object(
                self.base.service.client,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "nick must not be None"):
                run_coroutine(self.jmuc.muc_set_role(
                    None,
                    "participant",
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_muc_set_role_rejects_None_role(self):
        with unittest.mock.patch.object(
                self.base.service.client,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "role must not be None"):
                run_coroutine(self.jmuc.muc_set_role(
                    "thirdwitch",
                    None,
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_muc_set_role_fails(self):
        with unittest.mock.patch.object(
                self.base.service.client,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None
            send_iq.side_effect = aioxmpp.errors.XMPPCancelError(
                condition=(utils.namespaces.stanzas, "forbidden")
            )

            with self.assertRaises(aioxmpp.errors.XMPPCancelError):
                run_coroutine(self.jmuc.muc_set_role(
                    "thirdwitch",
                    "participant",
                    reason="foobar",
                ))

    def test_set_nick(self):
        with unittest.mock.patch.object(
                self.base.service.client,
                "send",
                new=CoroutineMock()) as send_stanza:
            send_stanza.return_value = None

            run_coroutine(self.jmuc.set_nick(
                "oldhag",
            ))

        _, (pres,), _ = send_stanza.mock_calls[-1]

        self.assertIsInstance(
            pres,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            pres.type_,
            aioxmpp.structs.PresenceType.AVAILABLE,
        )
        self.assertEqual(
            pres.to,
            self.mucjid.replace(resource="oldhag"),
        )

    def test_muc_set_affiliation_delegates_to_service(self):
        with unittest.mock.patch.object(
                self.base.service,
                "set_affiliation",
                new=CoroutineMock()) as set_affiliation:
            jid, aff, reason = object(), object(), object()

            result = run_coroutine(self.jmuc.muc_set_affiliation(
                jid, aff, reason=reason
            ))

        set_affiliation.assert_called_with(
            self.mucjid,
            jid,
            aff,
            reason=reason
        )
        self.assertEqual(result, run_coroutine(set_affiliation()))

    def test_set_topic(self):
        d = {
            None: "foobar"
        }

        result = run_coroutine(self.jmuc.set_topic(d))

        _, (stanza,), _ = self.base.service.client.\
            send.mock_calls[-1]

        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Message
        )
        self.assertEqual(
            stanza.type_,
            aioxmpp.structs.MessageType.GROUPCHAT,
        )
        self.assertEqual(
            stanza.to,
            self.mucjid
        )

        self.assertDictEqual(
            stanza.subject,
            d
        )
        self.assertFalse(stanza.body)

    def test_leave(self):
        fut = asyncio.ensure_future(self.jmuc.leave())
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(fut.done(), fut.done() and fut.result())

        _, (stanza,), _ = self.base.service.client.\
            send.mock_calls[-1]

        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.type_,
            aioxmpp.structs.PresenceType.UNAVAILABLE
        )
        self.assertEqual(
            stanza.to,
            self.mucjid
        )
        self.assertFalse(stanza.status)
        self.assertEqual(stanza.show, aioxmpp.PresenceShow.NONE)

        self.jmuc.on_exit(muc_leave_mode=object(),
                          muc_actor=object(),
                          muc_reason=object())

        self.assertIsNone(run_coroutine(fut))

        self.jmuc.on_exit(muc_leave_mode=object(),
                          muc_actor=object(),
                          muc_reason=object())

    def test_members(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={},
            items=[
                muc_xso.UserItem(affiliation="owner",
                                 role="participant"),
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="secondwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={},
            items=[
                muc_xso.UserItem(affiliation="admin",
                                 role="participant"),
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        members = [
            occupant
            for _, (occupant, *_), _ in self.base.on_join.mock_calls
        ]

        self.assertSetEqual(
            set(members),
            set(self.jmuc.members)
        )

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="visitor"),
            ]
        )
        self.jmuc._inbound_muc_user_presence(presence)

        members += [
            occupant
            for _, (_, occupant, *_), _ in self.base.on_muc_enter.mock_calls
        ]

        self.assertSetEqual(
            set(members),
            set(self.jmuc.members)
        )

        self.assertIs(self.jmuc.members[0], self.jmuc.me)

    def test_muc_request_voice(self):
        run_coroutine(self.jmuc.muc_request_voice())

        self.assertEqual(
            len(self.base.service.client.send.mock_calls),
            1,
        )

        _, (msg, ), _ = \
            self.base.service.client.send.mock_calls[0]

        self.assertIsInstance(
            msg,
            aioxmpp.Message,
        )

        self.assertEqual(
            msg.type_,
            aioxmpp.MessageType.NORMAL,
        )

        self.assertEqual(
            msg.to,
            TEST_MUC_JID,
        )

        self.assertEqual(
            len(msg.xep0004_data),
            1
        )

        data, = msg.xep0004_data

        self.assertIsInstance(
            data,
            aioxmpp.forms.Data,
        )

        self.assertEqual(
            data.type_,
            aioxmpp.forms.DataType.SUBMIT,
        )

        self.assertEqual(
            len(data.fields),
            2
        )

        field = data.fields[0]
        self.assertIsInstance(
            field,
            aioxmpp.forms.Field,
        )

        self.assertEqual(
            field.type_,
            aioxmpp.forms.FieldType.HIDDEN,
        )

        self.assertEqual(
            field.var,
            "FORM_TYPE",
        )

        self.assertSequenceEqual(
            field.values,
            ["http://jabber.org/protocol/muc#request"]
        )

        field = data.fields[1]
        self.assertIsInstance(
            field,
            aioxmpp.forms.Field,
        )

        self.assertEqual(
            field.type_,
            aioxmpp.forms.FieldType.LIST_SINGLE,
        )

        self.assertEqual(
            field.var,
            "muc#role",
        )

        self.assertSequenceEqual(
            field.values,
            ["participant"]
        )

    def test_send_message(self):
        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        token = self.jmuc.send_message(msg)

        self.base.service.client.enqueue.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (msg, ), _ = self.base.service.client.enqueue.mock_calls[0]

        self.assertEqual(token, self.base.service.client.enqueue())

        self.assertIsInstance(
            msg,
            aioxmpp.Message,
        )

        self.assertEqual(
            msg.type_,
            aioxmpp.MessageType.GROUPCHAT,
        )

        self.assertEqual(
            msg.to,
            self.jmuc.jid,
        )

        self.assertDictEqual(
            msg.body,
            {None: "some text"},
        )

        self.assertIsInstance(
            msg.xep0045_muc_user,
            muc_xso.UserExt,
        )

        # on_message should not be called for untracked messages because it will
        # be called once the reflection has been received!
        self.base.on_message.assert_not_called()

    def test_send_message_with_reflection(self):
        # we need to be in the MUC for the tracking argument to be working
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="none"),
            ]
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.GROUPCHAT)
        msg.body.update({None: "some text"})

        self.jmuc.send_message(msg)

        self.base.service.client.enqueue.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (msg, ), _ = self.base.service.client.enqueue.mock_calls[0]

        reply = msg.make_reply()
        reply.body.update(msg.body)
        reply.from_ = reply.from_.replace(resource=self.jmuc.me.nick)
        msg.xep0045_muc_user = muc_xso.UserExt()

        self.jmuc._handle_message(reply, reply.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.base.on_message.assert_called_once_with(
            reply,
            self.jmuc.me,
            im_dispatcher.MessageSource.STREAM,
            tracker=unittest.mock.ANY,
        )

        tracker = self.base.on_message.mock_calls[0][2]["tracker"]
        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT
        )

    def test_send_message_tracked_uses_basic_tracking_service(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        with contextlib.ExitStack() as stack:
            MessageTracker = stack.enter_context(
                unittest.mock.patch("aioxmpp.tracking.MessageTracker")
            )

            self.base.tracking_service.send_tracked.return_value = \
                unittest.mock.sentinel.token

            result = self.jmuc.send_message_tracked(msg)

        self.assertIsNotNone(msg.id_)

        MessageTracker.assert_called_once_with()

        self.base.tracking_service.send_tracked.assert_called_once_with(
            msg,
            MessageTracker()
        )

        self.assertEqual(
            result,
            (unittest.mock.sentinel.token,
             MessageTracker(),)
        )

        self.assertIsInstance(
            msg,
            aioxmpp.Message,
        )

        self.assertEqual(
            msg.type_,
            aioxmpp.MessageType.GROUPCHAT,
        )

        self.assertEqual(
            msg.to,
            self.jmuc.jid,
        )

        self.assertDictEqual(
            msg.body,
            {None: "some text"},
        )

        self.assertIsInstance(
            msg.xep0045_muc_user,
            muc_xso.UserExt,
        )

    def test_send_message_tracked_emits_on_message_tracked_with_tracker(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        with contextlib.ExitStack() as stack:
            MessageTracker = stack.enter_context(
                unittest.mock.patch("aioxmpp.tracking.MessageTracker")
            )

            self.base.tracking_service.send_tracked.return_value = \
                unittest.mock.sentinel.token

            result = self.jmuc.send_message_tracked(msg)

        self.assertIsNotNone(msg.id_)

        MessageTracker.assert_called_once_with()

        self.base.on_message.assert_called_once_with(
            msg,
            self.jmuc.me,
            im_dispatcher.MessageSource.STREAM,
            tracker=MessageTracker(),
        )

    def test_tracker_changes_state_on_reflection(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_=msg.id_,
        )
        reflected.body[None] = "other text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertEqual(tracker.response, reflected)

        self.base.on_message.assert_not_called()

    def test_tracker_matches_on_body_and_from_too(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected.body[None] = "some text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertEqual(tracker.response, reflected)

        self.base.on_message.assert_not_called()

    def test_tracker_matches_on_relanguaged_from(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected.body[aioxmpp.structs.LanguageTag.fromstr("de")] = "some text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertEqual(tracker.response, reflected)

        self.base.on_message.assert_not_called()

    def test_tracker_does_not_match_for_different_from(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)
        self.jmuc._handle_message(self.msg_end_of_history,
                                  self.msg_end_of_history.from_,
                                  False,
                                  im_dispatcher.MessageSource.STREAM)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid.replace(resource="fnord"),
            id_="#notmyid",
        )
        reflected.body[None] = "some text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        self.assertIsNone(tracker.response)

        self.base.on_message.assert_called_once_with(
            reflected,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

    def test_tracker_does_not_match_for_different_body(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected.body[None] = "some other text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        self.assertIsNone(tracker.response)

        self.base.on_message.assert_called_once_with(
            reflected,
            self.jmuc.me,
            im_dispatcher.MessageSource.STREAM,
            tracker=unittest.mock.ANY,
        )

    def test_tracker_follows_concurrent_nickchange(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        presence.type_ = aioxmpp.structs.PresenceType.UNAVAILABLE
        presence.xep0045_muc_user.status_codes.add(303)
        presence.xep0045_muc_user.status_codes.add(110)
        presence.xep0045_muc_user.items[0].nick = "oldhag"

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(
            self.jmuc.me.conversation_jid,
            TEST_MUC_JID.replace(resource="oldhag")
        )

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=TEST_MUC_JID.replace(resource="oldhag"),
            id_="#notmyid",
        )
        reflected.body[None] = "some text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertIs(tracker.response, reflected)

        self.base.on_message.assert_not_called()

    def test_tracker_can_deal_with_localised_messages(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update(
            {aioxmpp.structs.LanguageTag.fromstr("de"): "ein Text"}
        )

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        other_message = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        other_message.body[aioxmpp.structs.LanguageTag.fromstr("de")] = "ein anderer Text"

        self.jmuc._handle_message(
            other_message,
            other_message.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        self.assertIsNone(tracker.response)

        self.base.on_message.assert_called_once_with(
            other_message,
            self.jmuc.me,
            im_dispatcher.MessageSource.STREAM,
            tracker=unittest.mock.ANY,
        )
        self.base.on_message.reset_mock()
        self.base.on_message.return_value = None

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected.body[aioxmpp.structs.LanguageTag.fromstr("de")] = "ein Text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertIs(tracker.response, reflected)

        self.base.on_message.assert_not_called()

    def test_tracker_body_from_match_works_with_multiple_identical_messages(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg1 = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg1.body.update({None: "some text"})

        msg2 = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg2.body.update({None: "some text"})

        _, tracker1 = self.jmuc.send_message_tracked(msg1)

        _, tracker2 = self.jmuc.send_message_tracked(msg2)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker1.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        self.assertEqual(
            tracker2.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected1 = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected1.body[None] = "some text"

        self.jmuc._handle_message(
            reflected1,
            reflected1.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker1.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertIs(tracker1.response, reflected1)

        self.assertEqual(
            tracker2.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        reflected2 = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_="#notmyid",
        )
        reflected2.body[None] = "some text"

        self.jmuc._handle_message(
            reflected2,
            reflected2.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker2.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

        self.assertIs(
            tracker2.response,
            reflected2,
        )

    def test_tracking_does_not_fail_on_race(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        tracker._set_state(aioxmpp.tracking.MessageState.SEEN_BY_RECIPIENT)

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_=msg.id_,
        )
        reflected.body[None] = "some text"

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.base.on_message.assert_not_called()

    def test_tracking_state_cleanup_on_close(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body.update({None: "some text"})

        _, tracker = self.jmuc.send_message_tracked(msg)

        self.base.on_message.reset_mock()

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

        tracker.close()

        reflected = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=self.jmuc.me.conversation_jid,
            id_=msg.id_,
        )

        self.jmuc._handle_message(
            reflected,
            reflected.from_,
            False,
            im_dispatcher.MessageSource.STREAM,
        )

        self.assertEqual(
            tracker.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

    def test_ban_uses_set_affiliation(self):
        member = unittest.mock.Mock(spec=muc_service.Occupant)
        with unittest.mock.patch.object(
                self.jmuc,
                "muc_set_affiliation",
                CoroutineMock()) as muc_set_affiliation:
            run_coroutine(self.jmuc.ban(
                member,
                reason=unittest.mock.sentinel.reason
            ))

            muc_set_affiliation.assert_called_once_with(
                member.direct_jid,
                "outcast",
                reason=unittest.mock.sentinel.reason,
            )

    def test_ban_accepts_request_kick_argument(self):
        member = unittest.mock.Mock(spec=muc_service.Occupant)
        with unittest.mock.patch.object(
                self.jmuc,
                "muc_set_affiliation",
                CoroutineMock()) as muc_set_affiliation:
            run_coroutine(self.jmuc.ban(
                member,
                reason=unittest.mock.sentinel.reason,
                request_kick=unittest.mock.sentinel.request_kick,
            ))

            muc_set_affiliation.assert_called_once_with(
                member.direct_jid,
                "outcast",
                reason=unittest.mock.sentinel.reason,
            )

    def test_ban_raises_ValueError_if_direct_jid_not_known(self):
        member = unittest.mock.Mock(spec=muc_service.Occupant)
        member.direct_jid = None
        with unittest.mock.patch.object(
                self.jmuc,
                "muc_set_affiliation",
                CoroutineMock()) as muc_set_affiliation:
            with self.assertRaisesRegex(
                ValueError,
                "cannot ban members whose direct JID is not known"):
                run_coroutine(self.jmuc.ban(
                    member,
                    reason=unittest.mock.sentinel.reason
                ))

            muc_set_affiliation.assert_not_called()

    def test_kick_uses_muc_set_role(self):
        member = unittest.mock.Mock(spec=muc_service.Occupant)
        with unittest.mock.patch.object(
                self.jmuc,
                "muc_set_role",
                CoroutineMock()) as muc_set_role:
            run_coroutine(self.jmuc.kick(
                member,
                reason=unittest.mock.sentinel.reason
            ))

            muc_set_role.assert_called_once_with(
                member.nick,
                "none",
                reason=unittest.mock.sentinel.reason,
            )

    def test_features(self):
        Feature = im_conversation.ConversationFeature

        self.assertLessEqual(
            {
                Feature.SET_NICK,
                Feature.SET_TOPIC,
                Feature.KICK,
                Feature.BAN,
                Feature.BAN_WITH_KICK,
                Feature.SEND_MESSAGE,
                Feature.SEND_MESSAGE_TRACKED,
            },
            self.jmuc.features,
        )

    def test_state(self):
        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.JOIN_PRESENCE)

    def test_state_during_presence_state_transfer(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes=set(),
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.JOIN_PRESENCE)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

    def test_state_during_history_replay(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt()

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt()

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        self.jmuc._handle_message(self.msg_end_of_history,
                                  self.msg_end_of_history.from_,
                                  False,
                                  im_dispatcher.MessageSource.STREAM)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.ACTIVE)

    def test_state_disconnect(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.subject.update({None: None})
        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0203_delay.append(aioxmpp.misc.Delay())

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.ACTIVE)

        self.jmuc._disconnect()

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.DISCONNECTED)

    def test_state_suspend(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.subject.update({None: None})
        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0203_delay.append(aioxmpp.misc.Delay())

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.ACTIVE)

        self.jmuc._suspend()

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.DISCONNECTED)

    def test_state_suspend_resume_cycle(self):
        self.jmuc._suspend()

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.DISCONNECTED)

        self.jmuc._resume()

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.JOIN_PRESENCE)

    def test_generate_transitional_occupant_objects_for_history(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0203_delay.append(aioxmpp.misc.Delay())

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]

        self.assertIsNotNone(occupant)
        self.assertEqual(occupant.nick, "firstwitch")
        self.assertIsNone(occupant.direct_jid)

    def test_do_not_generate_transitional_occupant_object_for_service_during_history(self):  # NOQA
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource=None),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0203_delay.append(aioxmpp.misc.Delay())

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]

        self.assertIs(occupant, self.jmuc.service_member)

    def test_include_real_jid_in_transitional_occupant_objects_if_available(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID),
            ],
        )

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]

        self.assertIsNotNone(occupant)
        self.assertEqual(occupant.nick, "firstwitch")
        self.assertEqual(occupant.direct_jid, TEST_ENTITY_JID)

    def test_require_jid_match_to_reuse_current_occupants_object(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant",
                                 jid=TEST_ENTITY_JID.replace(
                                     localpart="firstwitch"
                                 )),
            ],
            status_codes=set(),
        )

        self.jmuc._inbound_muc_user_presence(presence)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="mallory"
                )),
            ],
        )

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

        self.assertTrue(any(occupant.nick == "firstwitch"
                            for occupant in self.jmuc.members))

        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]

        self.assertIsNotNone(occupant)

        self.assertNotIn(occupant, self.jmuc.members)

        self.assertEqual(occupant.nick, "firstwitch")
        self.assertEqual(
            occupant.direct_jid,
            TEST_ENTITY_JID.replace(localpart="mallory")
        )

    def test_re_use_actual_occupant_if_jid_matches(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant",
                                 jid=TEST_ENTITY_JID.replace(
                                     localpart="firstwitch"
                                 )),
            ],
            status_codes=set(),
        )

        self.jmuc._inbound_muc_user_presence(presence)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )

        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )

        firstwitch, = (
            occupant for occupant in self.jmuc.members
            if occupant.nick == "firstwitch"
        )

        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]

        self.assertIsNotNone(occupant)
        self.assertIs(firstwitch, occupant)

    def test_re_use_transient_occupant_if_jid_matches(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant1, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.body[None] = "something"
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant2, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        self.assertIsNotNone(occupant1)
        self.assertIs(occupant1, occupant2)

    def test_do_not_reuse_after_suspend_resume(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant1, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant2, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        self.jmuc._suspend()
        self.jmuc._resume()

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(jid=TEST_ENTITY_JID.replace(
                    localpart="firstwitch"
                )),
            ],
        )
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant3, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        self.assertIsNotNone(occupant3)
        self.assertIsNot(occupant3, occupant1)

    def test_presence_reception_after_join_presence_enters_active_state(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.ACTIVE)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.xep0203_delay.append(aioxmpp.misc.Delay())
        message.body[None] = "something"
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        self.assertIn(occupant, self.jmuc.members)

    def test_non_delayed_message_reception_forces_active_state(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="firstwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            items=[
                muc_xso.UserItem(affiliation="member",
                                 role="participant"),
            ],
            status_codes={110},
        )

        self.jmuc._inbound_muc_user_presence(presence)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.HISTORY)

        message = aioxmpp.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        message.body[None] = "something"
        self.jmuc._handle_message(message, message.from_, False,
                                  im_dispatcher.MessageSource.STREAM)

        self.listener.on_message.assert_called_once_with(
            message,
            unittest.mock.ANY,
            im_dispatcher.MessageSource.STREAM,
            tracker=None,
        )
        _, (_, occupant, _), _ = self.listener.on_message.mock_calls[0]
        self.listener.on_message.reset_mock()

        self.assertIn(occupant, self.jmuc.members)

        self.assertEqual(self.jmuc.muc_state,
                         muc_service.RoomState.ACTIVE)

    def test__handle_voice_request_forwards_to_event(self):
        form = unittest.mock.sentinel.form

        self.jmuc._handle_role_request(form)

        self.listener.on_muc_role_request.assert_called_once_with(
            form,
            unittest.mock.ANY,
        )

    def test__handle_voice_request_passes_future_and_emits_reply_on_future(
            self):
        form = unittest.mock.sentinel.form
        reply_form = aioxmpp.forms.Data(aioxmpp.forms.DataType.SUBMIT)

        exc = None

        def handler(form, fut):
            nonlocal exc
            try:
                self.assertFalse(fut.done())
                fut.set_result(reply_form)
            except Exception as cexc:
                exc = cexc

        self.jmuc.on_muc_role_request.connect(handler)

        self.jmuc._handle_role_request(form)

        self.listener.on_muc_role_request.assert_called_once_with(
            form,
            unittest.mock.ANY,
        )

        if exc is not None:
            raise exc

        run_coroutine(asyncio.sleep(0))

        _, (_, fut), _ = self.listener.on_muc_role_request.mock_calls[0]

        self.base.service.client.enqueue.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (msg,), _ = self.base.service.client.enqueue.mock_calls[0]

        self.assertIsInstance(msg, aioxmpp.Message)
        self.assertEqual(msg.type_, aioxmpp.MessageType.NORMAL)
        self.assertFalse(msg.body)
        self.assertEqual(msg.to, self.jmuc.jid)
        self.assertTrue(msg.xep0004_data)

        self.assertCountEqual(msg.xep0004_data, [reply_form])

    def test_expose_invite_features(self):
        self.assertIn(
            im_conversation.ConversationFeature.INVITE,
            self.jmuc.features,
        )

        self.assertIn(
            im_conversation.ConversationFeature.INVITE_DIRECT,
            self.jmuc.features,
        )

    def test_direct_invite(self):
        self.base.service.client.enqueue.return_value = \
            unittest.mock.sentinel.token

        result = run_coroutine(
            self.jmuc.invite(
                TEST_ENTITY_JID,
                mode=im_conversation.InviteMode.DIRECT,
                text="some text",
            )
        )

        self.assertEqual(
            result,
            (unittest.mock.sentinel.token, self.jmuc),
        )

        self.base.service.client.enqueue.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (msg, ), _ = self.base.service.client.enqueue.mock_calls[-1]

        self.assertIsInstance(msg, aioxmpp.Message)
        self.assertEqual(msg.to, TEST_ENTITY_JID.bare())
        self.assertEqual(msg.type_, aioxmpp.MessageType.NORMAL)
        self.assertIsInstance(msg.xep0249_direct_invite, muc_xso.DirectInvite)
        self.assertEqual(
            msg.xep0249_direct_invite.jid,
            self.jmuc.jid,
        )
        self.assertEqual(
            msg.xep0249_direct_invite.reason,
            "some text",
        )

    def test_mediated_invite(self):
        self.base.service.client.enqueue.return_value = \
            unittest.mock.sentinel.token

        result = run_coroutine(
            self.jmuc.invite(
                TEST_ENTITY_JID,
                mode=im_conversation.InviteMode.MEDIATED,
                text="some text",
            )
        )

        self.assertEqual(
            result,
            (unittest.mock.sentinel.token, self.jmuc),
        )

        self.base.service.client.enqueue.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (msg, ), _ = self.base.service.client.enqueue.mock_calls[-1]

        self.assertIsInstance(msg, aioxmpp.Message)
        self.assertEqual(msg.to, self.jmuc.jid)
        self.assertEqual(msg.type_, aioxmpp.MessageType.NORMAL)
        self.assertIsInstance(msg.xep0045_muc_user, muc_xso.UserExt)

        invite, = msg.xep0045_muc_user.invites

        self.assertEqual(invite.to, TEST_ENTITY_JID)
        self.assertEqual(invite.reason, "some text")


class TestService(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            muc_service.MUCClient,
            service.Service
        ))

    def test_is_conversation_service(self):
        self.assertTrue(issubclass(
            muc_service.MUCClient,
            im_conversation.AbstractConversationService,
        ))

    def setUp(self):
        self.cc = make_connected_client()
        self.im_dispatcher = im_dispatcher.IMDispatcher(self.cc)
        self.im_service = unittest.mock.Mock(
            spec=im_service.ConversationService
        )
        self.tracking_service = unittest.mock.Mock(
            spec=aioxmpp.tracking.BasicTrackingService
        )
        self.disco_server_service = unittest.mock.Mock(
            spec=aioxmpp.DiscoServer
        )
        self.s = muc_service.MUCClient(self.cc, dependencies={
            im_dispatcher.IMDispatcher: self.im_dispatcher,
            im_service.ConversationService: self.im_service,
            aioxmpp.tracking.BasicTrackingService: self.tracking_service,
            aioxmpp.DiscoServer: self.disco_server_service,
        })
        self.listener = make_listener(self.s)

    def tearDown(self):
        del self.s
        del self.cc

    def test_depends_on_IMDispatcher(self):
        self.assertIn(
            im_dispatcher.IMDispatcher,
            muc_service.MUCClient.ORDER_AFTER,
        )

    def test_depends_on_ConversationService(self):
        self.assertIn(
            im_service.ConversationService,
            muc_service.MUCClient.ORDER_AFTER,
        )

    def test_depends_on_BasicTrackingService(self):
        self.assertIn(
            aioxmpp.tracking.BasicTrackingService,
            muc_service.MUCClient.ORDER_AFTER,
        )

    def test_orders_before_P2P_Service(self):
        self.assertIn(
            im_p2p.Service,
            muc_service.MUCClient.ORDER_BEFORE,
        )

    def test_handle_presence_is_decorated(self):
        self.assertTrue(
            aioxmpp.service.is_depfilter_handler(
                im_dispatcher.IMDispatcher,
                "presence_filter",
                muc_service.MUCClient._handle_presence,
            )
        )

    def test_handle_message_is_decorated(self):
        self.assertTrue(
            aioxmpp.service.is_depfilter_handler(
                im_dispatcher.IMDispatcher,
                "message_filter",
                muc_service.MUCClient._handle_message,
            )
        )

    def test_handle_message_ignores_unknown_groupchat_stanza(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        msg.xep0045_muc_user = muc_xso.UserExt()
        self.assertIs(
            msg,
            self.s._handle_message(
                msg,
                msg.from_,
                False,
                unittest.mock.sentinel.source,
            )
        )

    def test_handle_message_ignores_nonmuc_ccd_message(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        self.assertIs(
            msg,
            self.s._handle_message(
                msg,
                msg.from_,
                False,
                im_dispatcher.MessageSource.CARBONS,
            )
        )
        self.assertIsNone(msg.xep0045_muc_user)

    def test_handle_message_ignores_nonmuc_chat_message(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        self.assertIs(
            msg,
            self.s._handle_message(
                msg,
                msg.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            )
        )
        self.assertIsNone(msg.xep0045_muc_user)

    def test_handle_message_drops_received_carbon_of_pm(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        msg.xep0045_muc_user = muc_xso.UserExt()
        self.assertIsNone(
            self.s._handle_message(
                msg,
                msg.from_,
                False,
                im_dispatcher.MessageSource.CARBONS,
            )
        )

    def test__stream_established_is_decorated(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.Client,
                "on_stream_established",
                muc_service.MUCClient._stream_established,
            )
        )

    def test__stream_destroyed_is_decorated(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.Client,
                "on_stream_destroyed",
                muc_service.MUCClient._stream_destroyed,
            )
        )

    def test__handle_presence_passes_ordinary_presence(self):
        presence = aioxmpp.stanza.Presence()
        self.assertIs(
            presence,
            self.s._handle_presence(
                presence, presence.from_, False
            )
        )

    def test__handle_presence_catches_presence_with_muc_user(self):
        presence = aioxmpp.stanza.Presence()
        presence.xep0045_muc_user = muc_xso.UserExt()

        with unittest.mock.patch.object(
                self.s,
                "_inbound_muc_user_presence") as handler:
            handler.return_value = 123
            self.assertIsNone(
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )
            )

        handler.assert_called_with(presence)

    def test__handle_presence_ignores_presence_with_muc_user_if_sent(self):
        presence = aioxmpp.stanza.Presence()
        presence.xep0045_muc_user = muc_xso.UserExt()

        with unittest.mock.patch.object(
                self.s,
                "_inbound_muc_user_presence") as handler:
            handler.return_value = 123
            self.assertIs(
                presence,
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    True,
                )
            )

        handler.assert_not_called()

    def test_join_without_password_or_history(self):
        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        self.im_service._add_conversation.assert_called_once_with(room)
        self.listener.on_conversation_new.assert_called_once_with(room)

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )
        self.assertTrue(room.muc_autorejoin)
        self.assertIsNone(room.muc_password)

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.to,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )
        self.assertIsNone(
            stanza.xep0045_muc.password
        )
        self.assertIsNone(
            stanza.xep0045_muc.history
        )

        self.cc.stream.register_message_callback.assert_not_called()

        self.assertFalse(future.done())

    def test_join_with_password(self):
        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        room, future = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            password="foobar",
        )
        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )
        self.assertTrue(room.muc_autorejoin)
        self.assertEqual(room.muc_password, "foobar")

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.to,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )
        self.assertEqual(
            stanza.xep0045_muc.password,
            "foobar",
        )
        self.assertIsNone(
            stanza.xep0045_muc.history
        )

        self.assertFalse(future.done())

    def test_join_without_autorejoin_with_password(self):
        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        room, future = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            password="foobar",
            autorejoin=False
        )
        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )
        self.assertFalse(room.muc_autorejoin)
        self.assertEqual(room.muc_password, "foobar")

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.to,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )
        self.assertEqual(
            stanza.xep0045_muc.password,
            "foobar",
        )
        self.assertIsNone(
            stanza.xep0045_muc.history
        )

        self.assertFalse(future.done())

    def test_join_with_history(self):
        history = muc_xso.History()

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        room, future = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            history=history
        )

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.to,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )
        self.assertIsNone(
            stanza.xep0045_muc.password,
        )
        self.assertIs(
            stanza.xep0045_muc.history,
            history,
        )

        self.assertFalse(future.done())

    def test_join_rejects_incorrect_history_object(self):
        with self.assertRaises(TypeError):
            self.s.join(
                TEST_MUC_JID,
                "thirdwitch",
                history="fnord"
            )

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

    def test_join_rejects_joining_a_pending_muc(self):
        room, fut = self.s.join(TEST_MUC_JID, "firstwitch")
        room2, fut2 = self.s.join(TEST_MUC_JID, "thirdwitch")

        self.assertIs(room, room2)
        self.assertIs(fut, fut2)

    def test_join_rejects_non_bare_muc_jid(self):
        with self.assertRaisesRegex(
                ValueError,
                "MUC JID must be bare"):
            self.s.join(
                TEST_MUC_JID.replace(resource="firstwitch"),
                "firstwitch"
            )

    def test_future_receives_exception_on_join_error(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        response = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID,
            type_=aioxmpp.structs.PresenceType.ERROR)
        response.error = aioxmpp.stanza.Error()
        self.s._handle_presence(
            response,
            response.from_,
            False,
        )

        self.assertTrue(future.done())
        self.assertIsInstance(
            future.exception(),
            aioxmpp.errors.XMPPCancelError
        )

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

    def test_on_failure_is_emitted_on_join_error(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")
        listener = make_listener(room)

        response = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID,
            type_=aioxmpp.structs.PresenceType.ERROR)
        response.error = aioxmpp.stanza.Error()
        self.s._handle_presence(
            response,
            response.from_,
            False,
        )

        run_coroutine(asyncio.sleep(0))

        listener.on_enter.assert_not_called()
        listener.on_muc_enter.assert_not_called()
        listener.on_failure.assert_called_once_with(
            future.exception(),
        )

    def test_on_failure_is_emitted_on_stream_destruction_without_autorejoin(
            self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch",
                                   autorejoin=False)
        listener = make_listener(room)

        self.s._stream_destroyed()

        run_coroutine(asyncio.sleep(0))

        listener.on_enter.assert_not_called()
        listener.on_muc_enter.assert_not_called()
        listener.on_failure.assert_called_once_with(
            future.exception(),
        )

    def test_pending_muc_removed_and_unavailable_presence_emitted_on_cancel(
            self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")
        listener = make_listener(room)

        self.cc.enqueue.mock_calls.clear()

        future.cancel()

        run_coroutine(asyncio.sleep(0))

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.type_,
            aioxmpp.structs.PresenceType.UNAVAILABLE,
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )

        listener.on_failure.assert_called_once_with(unittest.mock.ANY)

        _, (exc,), _ = listener.on_failure.mock_calls[-1]

        self.assertIsInstance(exc, asyncio.CancelledError)

    def test_join_completed_on_self_presence(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        occupant_presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="thirdwitch"),
        )
        occupant_presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
        )

        self.s._handle_presence(
            occupant_presence,
            occupant_presence.from_,
            False,
        )

        self.assertTrue(future.done())
        self.assertIsNone(future.result())

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

    def test_join_returns_existing_muc_and_done_future_if_joined(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        occupant_presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="thirdwitch"),
        )
        occupant_presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110},
        )

        self.s._handle_presence(
            occupant_presence,
            occupant_presence.from_,
            False,
        )

        self.assertTrue(future.done())
        self.assertIsNone(future.result())

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        room2, future2 = self.s.join(TEST_MUC_JID, "thirdwitch")
        self.assertIs(room, room2)
        self.assertTrue(future2.done())

    def test_join_not_completed_on_occupant_presence(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        occupant_presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        occupant_presence.xep0045_muc_user = muc_xso.UserExt()

        self.s._handle_presence(
            occupant_presence,
            occupant_presence.from_,
            False,
        )

        self.assertFalse(future.done())

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

    def test_forward_muc_user_presence_to_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt()
            return presence

        occupant_presences = [
            mkpresence(nick)
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                room,
                "_inbound_muc_user_presence",
                new=base.inbound_muc_user_presence
            ))

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.inbound_muc_user_presence(
                    presence
                )
                for presence in occupant_presences
            ]
        )

    def test_forward_groupchat_messages_to_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )

        with contextlib.ExitStack() as stack:
            _handle_message = stack.enter_context(unittest.mock.patch.object(
                room,
                "_handle_message",
            ))

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIsNone(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    unittest.mock.sentinel.sent,
                    unittest.mock.sentinel.source,
                )
            )

        _handle_message.assert_called_once_with(
            msg,
            msg.from_,
            unittest.mock.sentinel.sent,
            unittest.mock.sentinel.source,
        )

    def test_forward_groupchat_messages_from_service_to_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource=None),
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )

        with contextlib.ExitStack() as stack:
            _handle_message = stack.enter_context(unittest.mock.patch.object(
                room,
                "_handle_message",
            ))

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIsNone(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    unittest.mock.sentinel.sent,
                    unittest.mock.sentinel.source,
                )
            )

        _handle_message.assert_called_once_with(
            msg,
            msg.from_,
            unittest.mock.sentinel.sent,
            unittest.mock.sentinel.source,
        )

    def test_forward_voice_requests_to_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.bare(),
            type_=aioxmpp.structs.MessageType.NORMAL,
        )

        form = muc_xso.VoiceRequestForm()
        form.roomnick.value = "secondwitch"
        form.role.options = {
            "participant": "participant",
        }
        form.role.value = "participant"

        data_xso = form.render_request()

        msg.xep0004_data.append(data_xso)

        with contextlib.ExitStack() as stack:
            _handle_role_request = stack.enter_context(
                unittest.mock.patch.object(
                    room,
                    "_handle_role_request",
                )
            )

            from_xso = stack.enter_context(unittest.mock.patch.object(
                muc_xso.VoiceRequestForm,
                "from_xso",
            ))
            from_xso.return_value = unittest.mock.sentinel.form_obj

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIsNone(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    False,
                    unittest.mock.sentinel.source,
                )
            )

        from_xso.assert_called_once_with(
            data_xso,
        )

        _handle_role_request.assert_called_once_with(
            unittest.mock.sentinel.form_obj,
        )

    def test_does_not_forward_voice_requests_from_users(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.NORMAL,
        )

        form = muc_xso.VoiceRequestForm()
        form.roomnick.value = "secondwitch"
        form.role.options = {
            "participant": "participant",
        }
        form.role.value = "participant"

        msg.xep0004_data.append(form.render_request())

        with contextlib.ExitStack() as stack:
            _handle_role_request = stack.enter_context(
                unittest.mock.patch.object(
                    room,
                    "_handle_role_request",
                )
            )

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIs(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    False,
                    unittest.mock.sentinel.source,
                ),
                msg
            )

        _handle_role_request.assert_not_called()

    def test_does_not_forward_sent_voice_request(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.NORMAL,
        )

        form = muc_xso.VoiceRequestForm()
        form.roomnick.value = "secondwitch"
        form.role.options = {
            "participant": "participant",
        }
        form.role.value = "participant"

        msg.xep0004_data.append(form.render_request())

        with contextlib.ExitStack() as stack:
            _handle_role_request = stack.enter_context(
                unittest.mock.patch.object(
                    room,
                    "_handle_role_request",
                )
            )

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIs(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    True,
                    unittest.mock.sentinel.source,
                ),
                msg
            )

        _handle_role_request.assert_not_called()

    def test_does_not_forward_unrelated_data_forms(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.NORMAL,
        )

        class RandomForm(aioxmpp.forms.Form):
            FORM_TYPE = "foo"

        msg.xep0004_data.append(RandomForm().render_request())

        with contextlib.ExitStack() as stack:
            _handle_role_request = stack.enter_context(
                unittest.mock.patch.object(
                    room,
                    "_handle_role_request",
                )
            )

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIs(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    False,
                    unittest.mock.sentinel.source,
                ),
                msg,
            )

        _handle_role_request.assert_not_called()

    def test_tags_chat_messages_from_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.CHAT,
        )

        with contextlib.ExitStack() as stack:
            _handle_message = stack.enter_context(unittest.mock.patch.object(
                room,
                "_handle_message",
            ))

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIs(
                msg,
                self.s._handle_message(
                    msg,
                    msg.from_,
                    unittest.mock.sentinel.sent,
                    unittest.mock.sentinel.source,
                )
            )

            self.assertIsInstance(
                msg.xep0045_muc_user,
                muc_xso.UserExt,
            )

        _handle_message.assert_not_called()

    def test_drop_untagged_pm_carbons_from_joined_mucs(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        def mkpresence(nick, is_self=False):
            presence = aioxmpp.stanza.Presence(
                from_=TEST_MUC_JID.replace(resource=nick)
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                status_codes={110} if is_self else set()
            )
            return presence

        occupant_presences = [
            mkpresence(nick, is_self=(nick == "thirdwitch"))
            for nick in [
                "firstwitch",
                "secondwitch",
                "thirdwitch",
            ]
        ]

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_=aioxmpp.structs.MessageType.CHAT,
        )

        with contextlib.ExitStack() as stack:
            _handle_message = stack.enter_context(unittest.mock.patch.object(
                room,
                "_handle_message",
            ))

            for presence in occupant_presences:
                self.s._handle_presence(
                    presence,
                    presence.from_,
                    False,
                )

            self.assertIsNone(
                self.s._handle_message(
                    msg,
                    msg.from_,
                    unittest.mock.sentinel.sent,
                    im_dispatcher.MessageSource.CARBONS,
                )
            )

        _handle_message.assert_not_called()

    def test_muc_is_untracked_when_user_leaves(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt()
        presence.xep0045_muc_user.status_codes.add(110)

        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )
        run_coroutine(asyncio.sleep(0))

        self.assertTrue(future.done())

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt()
        presence.xep0045_muc_user.status_codes.add(110)

        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )
        run_coroutine(asyncio.sleep(0))

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

    def test_join_is_deferred_until_stream_is_established(self):
        self.cc.established = False

        history = muc_xso.History()
        password = "foobar"
        room, future = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            history=history,
            password=password)

        run_coroutine(asyncio.sleep(0))

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        self.assertSequenceEqual(
            self.cc.enqueue.mock_calls,
            []
        )

        self.cc.on_stream_established()

        run_coroutine(asyncio.sleep(0))

        _, (stanza,), _ = self.cc.enqueue.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.to,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )
        self.assertEqual(
            stanza.xep0045_muc.password,
            password,
        )
        self.assertIs(
            stanza.xep0045_muc.history,
            history,
        )

    def test_stream_destruction_with_autorejoin(self):
        base = unittest.mock.Mock()
        base.enter1.return_value = None
        base.enter2.return_value = None
        base.suspend1.return_value = None
        base.suspend2.return_value = None
        base.resume1.return_value = None
        base.resume2.return_value = None
        base.exit1.return_value = None
        base.exit2.return_value = None

        room1, fut1 = self.s.join(
            TEST_MUC_JID,
            "thirdwitch")

        room2, fut2 = self.s.join(
            TEST_MUC_JID.replace(localpart="foo"),
            "thirdwitch")

        room1.on_muc_enter.connect(base.enter1)
        room2.on_muc_enter.connect(base.enter2)

        room1.on_muc_suspend.connect(base.suspend1)
        room2.on_muc_suspend.connect(base.suspend2)

        room1.on_muc_resume.connect(base.resume1)
        room2.on_muc_resume.connect(base.resume2)

        room1.on_exit.connect(base.exit1)
        room2.on_exit.connect(base.exit2)

        # test one which is joined and one which is not joined

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )

        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )
        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertFalse(fut2.done())

        now = datetime.utcnow()
        with unittest.mock.patch(
                "aioxmpp.muc.service.datetime"
        ) as mock_datetime:
            mock_datetime.utcnow.return_value = now
            self.cc.on_stream_destroyed()

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertFalse(fut2.done())

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.enter1(unittest.mock.ANY,
                                          unittest.mock.ANY,
                                          muc_status_codes=unittest.mock.ANY),
                unittest.mock.call.suspend1(),
            ]
        )
        base.mock_calls.clear()
        self.cc.enqueue.mock_calls.clear()

        self.cc.on_stream_established()
        run_coroutine(asyncio.sleep(0))

        def extract(items, op):
            result = set()
            for _, (stanza,), _ in items:
                try:
                    data = op(stanza)
                except AttributeError:
                    continue
                result.add(data)
            return result

        self.assertEqual(
            len(self.cc.enqueue.mock_calls),
            2,
        )

        self.assertSetEqual(
            extract(
                self.cc.enqueue.mock_calls,
                lambda stanza: (stanza.to.bare(),)
            ),
            {
                (TEST_MUC_JID,),
                (TEST_MUC_JID.replace(localpart="foo"),)
            }
        )

        self.assertSetEqual(
            extract(
                self.cc.enqueue.mock_calls,
                lambda stanza: (stanza.to.bare(),
                                stanza.xep0045_muc.history.since)
            ),
            {
                (TEST_MUC_JID, now)
            }
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.resume1(),
            ]
        )
        base.mock_calls.clear()

        self.assertFalse(room1.muc_active)
        self.assertFalse(room2.muc_active)

        # now let both be joined
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )
        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(localpart="foo",
                                       resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )
        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertTrue(fut2.done())

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.enter1(unittest.mock.ANY,
                                          unittest.mock.ANY,
                                          muc_status_codes=unittest.mock.ANY),
                unittest.mock.call.enter2(unittest.mock.ANY,
                                          unittest.mock.ANY,
                                          muc_status_codes=unittest.mock.ANY),
            ]
        )

    def test_stream_destruction_without_autorejoin(self):
        base = unittest.mock.Mock()
        base.enter1.return_value = None
        base.enter2.return_value = None
        base.suspend1.return_value = None
        base.suspend2.return_value = None
        base.resume1.return_value = None
        base.resume2.return_value = None
        base.exit1.return_value = None
        base.exit2.return_value = None

        room1, fut1 = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            autorejoin=False)

        room2, fut2 = self.s.join(
            TEST_MUC_JID.replace(localpart="foo"),
            "thirdwitch",
            autorejoin=False)

        room1.on_muc_enter.connect(base.enter1)
        room2.on_muc_enter.connect(base.enter2)

        room1.on_muc_suspend.connect(base.suspend1)
        room2.on_muc_suspend.connect(base.suspend2)

        room1.on_muc_resume.connect(base.resume1)
        room2.on_muc_resume.connect(base.resume2)

        room1.on_exit.connect(base.exit1)
        room2.on_exit.connect(base.exit2)

        # test one which is joined and one which is not joined

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )

        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )
        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertFalse(fut2.done())

        now = datetime.utcnow()
        with unittest.mock.patch(
                "aioxmpp.muc.service.datetime"
        ) as mock_datetime:
            mock_datetime.utcnow.return_value = now
            self.cc.on_stream_destroyed()

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertTrue(fut2.done())
        self.assertIsInstance(fut2.exception(), ConnectionError)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.enter1(unittest.mock.ANY,
                                          unittest.mock.ANY,
                                          muc_status_codes=unittest.mock.ANY),
                unittest.mock.call.exit1(
                    muc_leave_mode=muc_service.LeaveMode.DISCONNECTED
                ),
            ]
        )
        base.mock_calls.clear()
        self.cc.enqueue.mock_calls.clear()

        self.cc.on_stream_established()
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            len(self.cc.enqueue.mock_calls),
            0,
        )

    def test_hard_against_on_exit_while_pending(self):
        room1, fut1 = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            autorejoin=False)
        room1.on_exit(None)
        self.assertTrue(fut1.done())
        self.assertIsNone(fut1.result())

    def test_hard_against_on_exit_while_pending_with_fulfilled_future(self):
        room1, fut1 = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            autorejoin=False)
        fut1.set_result(1)
        room1.on_exit(None)
        self.assertTrue(fut1.done())
        self.assertEqual(fut1.result(), 1)

    def test_disconnect_all_mucs_on_shutdown(self):
        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.AVAILABLE,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )

        room1, fut1 = self.s.join(
            TEST_MUC_JID,
            "thirdwitch",
            autorejoin=False)

        room2, fut2 = self.s.join(
            TEST_MUC_JID.replace(localpart="foo"),
            "thirdwitch")

        room3, fut3 = self.s.join(
            TEST_MUC_JID.replace(localpart="bar"),
            "thirdwitch")

        self.s._handle_presence(
            presence,
            presence.from_,
            False,
        )

        base = unittest.mock.Mock()

        def disconnect_wrap(mock_dest, actual_dest, *args, **kwargs):
            mock_dest(*args, **kwargs)
            actual_dest(*args, **kwargs)

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                room1,
                "_disconnect",
                new=functools.partial(
                    disconnect_wrap,
                    base.disconnect1,
                    room1._disconnect
                )
            ))

            stack.enter_context(unittest.mock.patch.object(
                room2,
                "_disconnect",
                new=functools.partial(
                    disconnect_wrap,
                    base.disconnect2,
                    room2._disconnect
                )
            ))

            stack.enter_context(unittest.mock.patch.object(
                room3,
                "_disconnect",
                new=functools.partial(
                    disconnect_wrap,
                    base.disconnect3,
                    room3._disconnect
                )
            ))

            run_coroutine(self.s.shutdown())

        self.assertTrue(fut1.done())
        self.assertTrue(fut2.done())
        self.assertTrue(fut3.done())

        self.assertIsInstance(fut2.exception(), ConnectionError)
        self.assertIsInstance(fut3.exception(), ConnectionError)

        self.assertIn(
            unittest.mock.call.disconnect1(),
            base.mock_calls
        )

        self.assertIn(
            unittest.mock.call.disconnect2(),
            base.mock_calls
        )

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID.replace(localpart="foo"))

    def test_set_affiliation(self):
        new_affiliation = "owner"

        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            run_coroutine(self.s.set_affiliation(
                TEST_MUC_JID,
                TEST_ENTITY_JID,
                new_affiliation,
                reason="foobar",
            ))

        _, (iq,), _ = send_iq.mock_calls[-1]

        self.assertIsInstance(
            iq,
            aioxmpp.stanza.IQ
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.structs.IQType.SET
        )
        self.assertEqual(
            iq.to,
            TEST_MUC_JID,
        )

        self.assertIsInstance(
            iq.payload,
            muc_xso.AdminQuery
        )

        self.assertEqual(
            len(iq.payload.items),
            1
        )
        item = iq.payload.items[0]
        self.assertIsInstance(
            item,
            muc_xso.AdminItem
        )
        self.assertIsNone(item.nick)
        self.assertEqual(
            item.reason,
            "foobar"
        )
        self.assertEqual(
            item.affiliation,
            new_affiliation
        )
        self.assertEqual(
            item.jid,
            TEST_ENTITY_JID
        )

    def test_set_affiliation_rejects_None_affiliation(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "affiliation must not be None"):
                run_coroutine(self.s.set_affiliation(
                    TEST_MUC_JID,
                    TEST_ENTITY_JID,
                    None,
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_affiliation_rejects_None_jid(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "jid must not be None"):
                run_coroutine(self.s.set_affiliation(
                    TEST_MUC_JID,
                    None,
                    "outcast",
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_affiliation_rejects_None_mucjid(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "mucjid must be bare JID"):
                run_coroutine(self.s.set_affiliation(
                    None,
                    TEST_ENTITY_JID,
                    "outcast",
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_affiliation_rejects_full_mucjid(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "mucjid must be bare JID"):
                run_coroutine(self.s.set_affiliation(
                    TEST_MUC_JID.replace(resource="thirdwitch"),
                    TEST_ENTITY_JID,
                    "outcast",
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_affiliation_fails(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None
            send_iq.side_effect = aioxmpp.errors.XMPPCancelError(
                condition=(utils.namespaces.stanzas, "forbidden")
            )

            with self.assertRaises(aioxmpp.errors.XMPPCancelError):
                run_coroutine(self.s.set_affiliation(
                    TEST_MUC_JID,
                    TEST_ENTITY_JID,
                    "owner",
                    reason="foobar",
                ))

    def test_get_room_config(self):
        reply = muc_xso.OwnerQuery()
        reply.form = unittest.mock.sentinel.form

        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = reply

            result = run_coroutine(self.s.get_room_config(
                TEST_MUC_JID,
            ))

        self.assertEqual(
            result,
            reply.form,
        )

        _, (iq,), _ = send_iq.mock_calls[-1]

        self.assertIsInstance(
            iq,
            aioxmpp.stanza.IQ
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.structs.IQType.GET
        )
        self.assertEqual(
            iq.to,
            TEST_MUC_JID,
        )

        self.assertIsInstance(
            iq.payload,
            muc_xso.OwnerQuery
        )

        self.assertIsNone(
            iq.payload.form,
        )

        self.assertIsNone(
            iq.payload.destroy,
        )

    def test_get_room_config_rejects_full_mucjid(self):
        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            with self.assertRaisesRegex(ValueError,
                                        "mucjid must be bare JID"):
                run_coroutine(self.s.get_room_config(
                    TEST_MUC_JID.replace(resource="thirdwitch"),
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_room_config(self):
        data = unittest.mock.sentinel.data

        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            result = run_coroutine(self.s.set_room_config(
                TEST_MUC_JID,
                data,
            ))

        _, (iq,), _ = send_iq.mock_calls[-1]

        self.assertIsInstance(
            iq,
            aioxmpp.stanza.IQ
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.structs.IQType.SET
        )
        self.assertEqual(
            iq.to,
            TEST_MUC_JID,
        )

        self.assertIsInstance(
            iq.payload,
            muc_xso.OwnerQuery
        )

        self.assertEqual(
            iq.payload.form,
            data,
        )

        self.assertIsNone(
            iq.payload.destroy,
        )

    def test_emit_on_muc_invitation_on_mediated_invite(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.from_ = aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop")
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            invite.from_,
            im_conversation.InviteMode.MEDIATED,
            password="cauldronburn",
            reason="Hey Hecate, this is the place for all good witches!",
        )

    def test_emit_on_muc_invitation_on_mediated_invite_from_carbons(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.from_ = aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop")
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.CARBONS,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            invite.from_,
            im_conversation.InviteMode.MEDIATED,
            password="cauldronburn",
            reason="Hey Hecate, this is the place for all good witches!",
        )

    def test_emit_on_muc_invitation_on_mediated_without_from(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            None,
            im_conversation.InviteMode.MEDIATED,
            password="cauldronburn",
            reason="Hey Hecate, this is the place for all good witches!",
        )

    def test_on_muc_invitation_degrades_nicely_with_fewer_info(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            None,
            im_conversation.InviteMode.MEDIATED,
            password=None,
            reason=None,
        )

    def test_announces_support_for_direct_invites(self):
        self.assertIsInstance(
            muc_service.MUCClient.direct_invite_feature,
            aioxmpp.disco.register_feature,
        )
        self.assertEqual(
            muc_service.MUCClient.direct_invite_feature.feature,
            "jabber:x:conference"
        )

        self.assertIsInstance(
            self.s.direct_invite_feature,
            aioxmpp.disco.service.RegisteredFeature,
        )
        self.assertEqual(
            self.s.direct_invite_feature.feature,
            "jabber:x:conference"
        )
        self.assertTrue(
            self.s.direct_invite_feature.enabled,
        )

    def test_emit_on_muc_invitation_on_direct_invite(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop"),
        )

        message.xep0249_direct_invite = muc_xso.DirectInvite(TEST_MUC_JID)
        message.xep0249_direct_invite.password = "cauldronburn"
        message.xep0249_direct_invite.reason = \
            "Hey Hecate, this is the place for all good witches!"

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            message.from_,
            im_conversation.InviteMode.DIRECT,
            password="cauldronburn",
            reason="Hey Hecate, this is the place for all good witches!",
        )

    def test_handles_missing_jid_on_direct_invite(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop"),
        )

        # we can’t use init here because we need to trick the required JID
        # argument
        message.xep0249_direct_invite = \
            muc_xso.DirectInvite.__new__(muc_xso.DirectInvite)
        message.xep0249_direct_invite.password = "cauldronburn"
        message.xep0249_direct_invite.reason = \
            "Hey Hecate, this is the place for all good witches!"

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_not_called()

    def test_emit_on_muc_invitation_on_carbon_copied_direct_invite(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop"),
        )

        message.xep0249_direct_invite = muc_xso.DirectInvite(TEST_MUC_JID)
        message.xep0249_direct_invite.password = "cauldronburn"
        message.xep0249_direct_invite.reason = \
            "Hey Hecate, this is the place for all good witches!"

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.CARBONS,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_called_once_with(
            message,
            TEST_MUC_JID,
            message.from_,
            im_conversation.InviteMode.DIRECT,
            password="cauldronburn",
            reason="Hey Hecate, this is the place for all good witches!",
        )

    def test_on_muc_invitation_not_emitted_for_direct_sent(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=aioxmpp.JID.fromstr("crone1@shakespeare.lit/desktop"),
        )

        message.xep0249_direct_invite = muc_xso.DirectInvite(TEST_MUC_JID)
        message.xep0249_direct_invite.password = "cauldronburn"
        message.xep0249_direct_invite.reason = \
            "Hey Hecate, this is the place for all good witches!"

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                True,
                im_dispatcher.MessageSource.STREAM,
            ),
            None,
        )

        self.listener.on_muc_invitation.assert_not_called()

    def test_on_muc_invitation_not_emitted_for_mediated_sent(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.from_ = TEST_ENTITY_JID
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                True,
                im_dispatcher.MessageSource.STREAM,
            ),
            None
        )

        self.listener.on_muc_invitation.assert_not_called()

    def test_on_muc_invitation_not_emitted_for_outbound_mediated(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.to = TEST_ENTITY_JID
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                False,
                im_dispatcher.MessageSource.STREAM,
            ),
            None
        )

        self.listener.on_muc_invitation.assert_not_called()

    def test_on_muc_invitation_not_emitted_for_outbound_mediated_sent(self):
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL,
            from_=TEST_MUC_JID,
        )

        invite = muc_xso.Invite()
        invite.to = TEST_ENTITY_JID
        invite.reason = "Hey Hecate, this is the place for all good witches!"
        invite.password = "cauldronburn"

        message.xep0045_muc_user = muc_xso.UserExt()
        message.xep0045_muc_user.invites.append(invite)

        self.assertIsNone(
            self.s._handle_message(
                message,
                message.from_,
                True,
                im_dispatcher.MessageSource.STREAM,
            ),
            None
        )

        self.listener.on_muc_invitation.assert_not_called()
