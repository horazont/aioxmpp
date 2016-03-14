import asyncio
import contextlib
import functools
import unittest

from datetime import datetime, timedelta

import aioxmpp.callbacks
import aioxmpp.errors
import aioxmpp.muc.service as muc_service
import aioxmpp.muc.xso as muc_xso
import aioxmpp.service as service
import aioxmpp.stanza
import aioxmpp.structs
import aioxmpp.tracking as tracking
import aioxmpp.utils as utils

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
)


TEST_MUC_JID = aioxmpp.structs.JID.fromstr(
    "coven@chat.shakespeare.lit"
)

TEST_ENTITY_JID = aioxmpp.structs.JID.fromstr(
    "foo@bar.example/fnord"
)


class TestOccupant(unittest.TestCase):
    def test_init(self):
        occ = muc_service.Occupant(
            TEST_MUC_JID.replace(resource="firstwitch"),
        )
        self.assertEqual(occ.occupantjid,
                         TEST_MUC_JID.replace(resource="firstwitch"))
        self.assertEqual(occ.nick, "firstwitch")
        self.assertEqual(occ.presence_state,
                         aioxmpp.structs.PresenceState(available=True))
        self.assertDictEqual(occ.presence_status, {})
        self.assertIsInstance(occ.presence_status,
                              aioxmpp.structs.LanguageMap)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertFalse(occ.is_self)

        status = {
            aioxmpp.structs.LanguageTag.fromstr("de-de"): "Hex-hex!",
            None: "Witchcraft!"
        }

        occ = muc_service.Occupant(
            TEST_MUC_JID.replace(resource="firstwitch"),
            presence_state=aioxmpp.structs.PresenceState(
                available=True,
                show="away"
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
                show="away"
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
            occ.jid,
            TEST_ENTITY_JID
        )

        self.assertFalse(occ.is_self)

    def test_from_presence_can_deal_with_sparse_presence(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=None,
            show="dnd"
        )

        presence.status[None] = "foo"

        occ = muc_service.Occupant.from_presence(presence)
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.occupantjid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertIsNone(occ.jid)

        presence.status[None] = "foo"
        presence.xep0045_muc_user = muc_xso.UserExt()

        occ = muc_service.Occupant.from_presence(presence)
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.occupantjid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertIsNone(occ.affiliation)
        self.assertIsNone(occ.role)
        self.assertIsNone(occ.jid)

    def test_from_presence_extracts_what_it_can_get(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=None,
            show="dnd"
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

        occ = muc_service.Occupant.from_presence(presence)
        self.assertIsInstance(occ, muc_service.Occupant)

        self.assertEqual(occ.occupantjid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertEqual(occ.affiliation, "owner")
        self.assertEqual(occ.role, "moderator")
        self.assertEqual(occ.jid, TEST_ENTITY_JID)

    def test_update_raises_for_different_occupantjids(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(presence)

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )

        with self.assertRaisesRegex(ValueError, "mismatch"):
            occ.update(muc_service.Occupant.from_presence(presence))

    def test_update_updates_all_the_fields(self):
        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )

        occ = muc_service.Occupant.from_presence(presence)

        presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_=None,
            show="dnd"
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

        occ.update(muc_service.Occupant.from_presence(presence))
        self.assertEqual(occ.occupantjid, presence.from_)
        self.assertEqual(occ.nick, presence.from_.resource)
        self.assertDictEqual(occ.presence_status, presence.status)
        self.assertEqual(occ.affiliation, "owner")
        self.assertEqual(occ.role, "moderator")
        self.assertEqual(occ.jid, TEST_ENTITY_JID)

        self.assertIs(occ.presence_status, old_status_dict)


class TestRoom(unittest.TestCase):
    def setUp(self):
        self.mucjid = TEST_MUC_JID

        self.base = unittest.mock.Mock()

        self.jmuc = muc_service.Room(self.base.service, self.mucjid)

        # this occupant state events
        self.base.on_enter.return_value = None
        self.base.on_exit.return_value = None
        self.base.on_suspend.return_value = None
        self.base.on_resume.return_value = None

        self.jmuc.on_enter.connect(self.base.on_enter)
        self.jmuc.on_exit.connect(self.base.on_exit)
        self.jmuc.on_suspend.connect(self.base.on_suspend)
        self.jmuc.on_resume.connect(self.base.on_resume)

        # messaging events
        self.base.on_message.return_value = None

        self.jmuc.on_message.connect(self.base.on_message)

        # room meta events
        self.base.on_subject_change.return_value = None

        self.jmuc.on_subject_change.connect(self.base.on_subject_change)

        # other occupant presence/permission events
        self.base.on_join.return_value = None
        self.base.on_status_change.return_value = None
        self.base.on_nick_change.return_value = None
        self.base.on_role_change.return_value = None
        self.base.on_affiliation_change.return_value = None
        self.base.on_leave.return_value = None

        self.jmuc.on_join.connect(self.base.on_join)
        self.jmuc.on_status_change.connect(self.base.on_status_change)
        self.jmuc.on_nick_change.connect(self.base.on_nick_change)
        self.jmuc.on_role_change.connect(self.base.on_role_change)
        self.jmuc.on_affiliation_change.connect(
            self.base.on_affiliation_change)
        self.jmuc.on_leave.connect(self.base.on_leave)

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
            self.jmuc.on_status_change,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_affiliation_change,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_nick_change,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_role_change,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_subject_change,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_suspend,
            aioxmpp.callbacks.AdHocSignal
        )
        self.assertIsInstance(
            self.jmuc.on_resume,
            aioxmpp.callbacks.AdHocSignal
        )

    def test_init(self):
        self.assertIs(self.jmuc.service, self.base.service)
        self.assertEqual(self.jmuc.mucjid, self.mucjid)
        self.assertDictEqual(self.jmuc.subject, {})
        self.assertIsInstance(self.jmuc.subject, aioxmpp.structs.LanguageMap)
        self.assertFalse(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)
        self.assertIsNone(self.jmuc.subject_setter)
        self.assertIsNone(self.jmuc.this_occupant)
        self.assertFalse(self.jmuc.autorejoin)
        self.assertIsNone(self.jmuc.password)

    def test_service_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.service = self.base.service

    def test_mucjid_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.mucjid = self.mucjid

    def test_active_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.active = True

    def test_subject_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.subject = "foo"

    def test_subject_setter_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.subject_setter = "bar"

    def test_joined_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.joined = True

    def test_this_occupant_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.jmuc.this_occupant = muc_service.Occupant(
                TEST_MUC_JID.replace(resource="foo")
            )

    def test__suspend_with_autorejoin(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)

        self.jmuc.autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertTrue(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)
        self.assertIsNotNone(self.jmuc.this_occupant)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_suspend(),
            ]
        )

    def test__suspend_without_autorejoin(self):
        # this is identical to the above testcase, autorejoin should be handled
        # by the Service class

        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)

        self.jmuc.autorejoin = False
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertFalse(self.jmuc.active)
        self.assertTrue(self.jmuc.joined)
        self.assertIsNotNone(self.jmuc.this_occupant)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_suspend(),
            ]
        )

    def test__disconnect(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)

        self.jmuc.autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)
        self.assertIsNotNone(self.jmuc.this_occupant)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_exit(
                    None,
                    self.jmuc.this_occupant,
                    muc_service.LeaveMode.DISCONNECTED),
            ]
        )

    def test__disconnect_during_suspend(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)

        self.jmuc.autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)
        self.assertIsNotNone(self.jmuc.this_occupant)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_suspend(),
                unittest.mock.call.on_exit(
                    None,
                    self.jmuc.this_occupant,
                    muc_service.LeaveMode.DISCONNECTED),
            ]
        )

    def test__disconnect_is_noop_if_not_entered(self):
        self.assertFalse(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)

        self.jmuc.autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._disconnect()

        self.assertFalse(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
            ]
        )

    def test__suspend__resume_cycle(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)

        self.jmuc.autorejoin = True
        self.base.mock_calls.clear()

        self.jmuc._suspend()

        self.assertTrue(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)
        old_occupant = self.jmuc.this_occupant

        self.jmuc._resume()

        self.assertTrue(self.jmuc.joined)
        self.assertFalse(self.jmuc.active)

        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        self.assertTrue(self.jmuc.active)
        self.assertIsNot(old_occupant, self.jmuc.this_occupant)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_suspend(),
                unittest.mock.call.on_resume(),
                unittest.mock.call.on_enter(presence, self.jmuc.this_occupant)
            ]
        )

    def test__inbound_muc_user_presence_emits_on_join_for_new_users(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(
                        presence,
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

    def test__inbound_muc_user_presence_emits_on_leave_for_unavailable(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.NORMAL,
                        actor=None,
                        reason=None)
                ]
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_kick(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.update({307})
            presence.xep0045_muc_user.items[0].reason = "Avaunt, you cullion!"
            presence.xep0045_muc_user.items[0].role = "none"
            presence.xep0045_muc_user.items[0].actor = actor

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_role_change(
                        presence,
                        first,
                        actor=actor,
                        reason="Avaunt, you cullion!"),
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.KICKED,
                        actor=actor,
                        reason="Avaunt, you cullion!")
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

    def test__inbound_muc_user_presence_emits_on_leave_for_ban(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.update({301})
            presence.xep0045_muc_user.items[0].reason = "Treason"
            presence.xep0045_muc_user.items[0].affiliation = "outcast"
            presence.xep0045_muc_user.items[0].role = "none"
            presence.xep0045_muc_user.items[0].actor = actor

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_role_change(
                        presence,
                        first,
                        actor=actor,
                        reason="Treason",
                    ),
                    unittest.mock.call.on_affiliation_change(
                        presence,
                        first,
                        actor=actor,
                        reason="Treason"
                    ),
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.BANNED,
                        actor=actor,
                        reason="Treason")
                ]
            )
            self.assertEqual(
                first.affiliation,
                "outcast"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_affiliation_change(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.update({321})
            presence.xep0045_muc_user.items[0].reason = "foo"
            presence.xep0045_muc_user.items[0].actor = actor
            presence.xep0045_muc_user.items[0].affiliation = "none"
            presence.xep0045_muc_user.items[0].role = "none"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_role_change(
                        presence,
                        first,
                        actor=actor,
                        reason="foo",
                    ),
                    unittest.mock.call.on_affiliation_change(
                        presence,
                        first,
                        actor=actor,
                        reason="foo"
                    ),
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.AFFILIATION_CHANGE,
                        actor=actor,
                        reason="foo")
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
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.update({322})
            presence.xep0045_muc_user.items[0].reason = "foo"
            presence.xep0045_muc_user.items[0].actor = actor
            presence.xep0045_muc_user.items[0].affiliation = "none"
            presence.xep0045_muc_user.items[0].role = "none"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_role_change(
                        presence,
                        first,
                        actor=actor,
                        reason="foo",
                    ),
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.MODERATION_CHANGE,
                        actor=actor,
                        reason="foo")
                ]
            )
            self.assertEqual(
                first.affiliation,
                "none"
            )

    def test__inbound_muc_user_presence_emits_on_leave_for_system_shutdown(
            self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.update({332})
            presence.xep0045_muc_user.items[0].reason = "foo"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_leave(
                        presence,
                        first,
                        muc_service.LeaveMode.SYSTEM_SHUTDOWN,
                        actor=None,
                        reason="foo")
                ]
            )
            self.assertEqual(
                first.affiliation,
                "none"
            )

    def test__inbound_muc_user_presence_emits_on_status_change(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.show = "away"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_status_change(
                        presence,
                        first)
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

    def test__inbound_muc_user_presence_emits_on_nick_change(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.type_ = "unavailable"
            presence.xep0045_muc_user.status_codes.add(303)
            presence.xep0045_muc_user.items[0].nick = "oldhag"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_nick_change(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            self.assertEqual(
                first.occupantjid,
                TEST_MUC_JID.replace(resource="oldhag"),
            )

            presence = aioxmpp.stanza.Presence(
                type_=None,
                from_=TEST_MUC_JID.replace(resource="oldhag")
            )
            presence.xep0045_muc_user = muc_xso.UserExt(
                items=[
                    muc_xso.UserItem(affiliation="member",
                                     role="participant"),
                ]
            )

            third = original_Occupant.from_presence(presence)
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
            type_=None,
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
            first = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = first

            self.jmuc._inbound_muc_user_presence(presence)

            Occupant.from_presence.assert_called_with(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_join(presence, first)
                ]
            )
            self.base.mock_calls.clear()

            # update presence stanza
            presence.show = "away"
            presence.xep0045_muc_user.items[0].affiliation = "owner"
            presence.xep0045_muc_user.items[0].role = "moderator"
            presence.xep0045_muc_user.items[0].reason = "foobar"

            second = original_Occupant.from_presence(presence)
            Occupant.from_presence.return_value = second
            self.jmuc._inbound_muc_user_presence(presence)

            self.assertSequenceEqual(
                self.base.mock_calls,
                [
                    unittest.mock.call.on_status_change(presence, first),
                    unittest.mock.call.on_role_change(
                        presence, first,
                        actor=None,
                        reason="foobar"),
                    unittest.mock.call.on_affiliation_change(
                        presence, first,
                        actor=None,
                        reason="foobar"),
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

    def test__inbound_message_handles_subject_of_occupant(self):
        pres = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
        )
        pres.xep0045_muc_user = muc_xso.UserExt()

        self.jmuc._inbound_muc_user_presence(pres)

        _, (_, occupant), _ = self.base.on_join.mock_calls[-1]
        self.base.mock_calls.clear()

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_="groupchat"
        )
        msg.subject.update({
            None: "foo"
        })

        old_subject = self.jmuc.subject

        self.jmuc._inbound_message(msg)

        self.assertDictEqual(
            self.jmuc.subject,
            msg.subject
        )
        self.assertIsNot(self.jmuc.subject, msg.subject)
        self.assertIsNot(self.jmuc.subject, old_subject)
        self.assertEqual(self.jmuc.subject_setter, msg.from_.resource)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_subject_change(
                    msg,
                    self.jmuc.subject,
                    occupant=occupant
                )
            ]
        )

    def test__inbound_message_handles_subject_of_non_occupant(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_="groupchat"
        )
        msg.subject.update({
            None: "foo"
        })

        old_subject = self.jmuc.subject

        self.jmuc._inbound_message(msg)

        self.assertDictEqual(
            self.jmuc.subject,
            msg.subject
        )
        self.assertIsNot(self.jmuc.subject, msg.subject)
        self.assertIsNot(self.jmuc.subject, old_subject)
        self.assertEqual(self.jmuc.subject_setter, msg.from_.resource)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_subject_change(
                    msg,
                    self.jmuc.subject,
                    occupant=None
                )
            ]
        )

    def test__inbound_message_ignores_subject_if_body_is_present(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_="groupchat"
        )
        msg.subject.update({
            None: "foo"
        })
        msg.body.update({
            aioxmpp.structs.LanguageTag.fromstr("de"): "bar"
        })

        self.jmuc._inbound_message(msg)

        self.assertDictEqual(
            self.jmuc.subject,
            {}
        )
        self.assertIsNone(self.jmuc.subject_setter)

        self.assertFalse(self.base.on_subject_change.mock_calls)

    def test__inbound_message_does_not_reset_subject_if_no_subject_given(self):
        self.jmuc.subject[None] = "foo"

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_="groupchat"
        )

        self.jmuc._inbound_message(msg)

        self.assertDictEqual(
            self.jmuc.subject,
            {
                None: "foo"
            }
        )
        self.assertIsNone(self.jmuc.subject_setter)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
            ]
        )

    def test__inbound_groupchat_message_with_body_emits_on_message(self):
        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="secondwitch"),
            type_="groupchat"
        )
        msg.body[None] = "foo"

        self.jmuc._inbound_message(msg)

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.on_message(msg, occupant=None)
            ]
        )

    def test__inbound_muc_user_presence_emits_on_enter_and_on_exit(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
                unittest.mock.call.on_enter(presence,
                                            self.jmuc.this_occupant),
            ]
        )
        self.base.mock_calls.clear()

        self.assertTrue(self.jmuc.joined)
        self.assertTrue(self.jmuc.active)
        self.assertIsInstance(
            self.jmuc.this_occupant,
            muc_service.Occupant
        )
        self.assertEqual(
            self.jmuc.this_occupant.occupantjid,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertTrue(
            self.jmuc.this_occupant.is_self
        )

        presence = aioxmpp.stanza.Presence(
            type_="unavailable",
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
                    presence,
                    self.jmuc.this_occupant,
                    muc_service.LeaveMode.NORMAL,
                    actor=None,
                    reason=None
                )
            ]
        )
        self.assertFalse(self.jmuc.joined)
        self.assertIsInstance(
            self.jmuc.this_occupant,
            muc_service.Occupant
        )
        self.assertEqual(
            self.jmuc.this_occupant.occupantjid,
            TEST_MUC_JID.replace(resource="thirdwitch")
        )
        self.assertTrue(
            self.jmuc.this_occupant.is_self
        )
        self.assertFalse(self.jmuc.active)

    def test_set_role(self):
        new_role = "participant"

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "send_iq_and_wait_for_reply",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            run_coroutine(self.jmuc.set_role(
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
            "set"
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

    def test_set_role_rejects_None_nick(self):
        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "send_iq_and_wait_for_reply",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "nick must not be None"):
                run_coroutine(self.jmuc.set_role(
                    None,
                    "participant",
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_role_rejects_None_role(self):
        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "send_iq_and_wait_for_reply",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None

            with self.assertRaisesRegex(ValueError,
                                        "role must not be None"):
                run_coroutine(self.jmuc.set_role(
                    "thirdwitch",
                    None,
                    reason="foobar",
                ))

        self.assertFalse(send_iq.mock_calls)

    def test_set_role_fails(self):
        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "send_iq_and_wait_for_reply",
                new=CoroutineMock()) as send_iq:
            send_iq.return_value = None
            send_iq.side_effect = aioxmpp.errors.XMPPCancelError(
                condition=(utils.namespaces.stanzas, "forbidden")
            )

            with self.assertRaises(aioxmpp.errors.XMPPCancelError):
                run_coroutine(self.jmuc.set_role(
                    "thirdwitch",
                    "participant",
                    reason="foobar",
                ))

    def test_set_affiliation_delegates_to_service(self):
        with unittest.mock.patch.object(
                self.base.service,
                "set_affiliation",
                new=CoroutineMock()) as set_affiliation:
            jid, aff, reason = object(), object(), object()

            result = run_coroutine(self.jmuc.set_affiliation(
                jid, aff, reason=reason
            ))

        set_affiliation.assert_called_with(
            self.mucjid,
            jid,
            aff,
            reason=reason
        )
        self.assertEqual(result, run_coroutine(set_affiliation()))

    def test_set_subject(self):
        d = {
            None: "foobar"
        }

        result = self.jmuc.set_subject(d)

        _, (stanza,), _ = self.base.service.client.stream.\
            enqueue_stanza.mock_calls[-1]

        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Message
        )
        self.assertEqual(
            stanza.type_,
            "groupchat"
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

        self.assertEqual(
            result,
            self.base.service.client.stream.enqueue_stanza()
        )

    def test_leave(self):
        self.jmuc.leave()

        _, (stanza,), _ = self.base.service.client.stream.\
            enqueue_stanza.mock_calls[-1]

        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.type_,
            "unavailable"
        )
        self.assertEqual(
            stanza.to,
            self.mucjid
        )
        self.assertFalse(stanza.status)
        self.assertIsNone(stanza.show)

    def test_leave_and_wait(self):
        with unittest.mock.patch.object(
                self.jmuc,
                "leave") as leave:
            fut = asyncio.ensure_future(self.jmuc.leave_and_wait())
            run_coroutine(asyncio.sleep(0))
            self.assertFalse(fut.done())

            leave.assert_called_with()

            self.jmuc.on_exit(object(), object(), object())

            self.assertIsNone(run_coroutine(fut))

            self.jmuc.on_exit(object(), object(), object())


    def test_occupants(self):
        presence = aioxmpp.stanza.Presence(
            type_=None,
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
            type_=None,
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

        occupants = [
            occupant
            for _, (_, occupant, *_), _ in self.base.on_join.mock_calls
        ]

        self.assertSetEqual(
            set(occupants),
            set(self.jmuc.occupants)
        )

        presence = aioxmpp.stanza.Presence(
            type_=None,
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

        occupants += [
            occupant
            for _, (_, occupant, *_), _ in self.base.on_enter.mock_calls
        ]

        self.assertSetEqual(
            set(occupants),
            set(self.jmuc.occupants)
        )

        self.assertIs(self.jmuc.occupants[0], self.jmuc.this_occupant)

    def test_send_tracked_message_with_body(self):
        stanza = None
        set_on_state_change = None
        result = object()

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal stanza, set_on_state_change
            self.assertIsNone(stanza)
            stanza_to_send.autoset_id()
            stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        body = {
            None: "foo"
        }

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(body)

        self.assertIsNotNone(stanza)
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Message
        )
        self.assertEqual(
            stanza.type_,
            "groupchat"
        )
        self.assertEqual(
            stanza.to,
            self.mucjid
        )
        self.assertDictEqual(
            stanza.body,
            body
        )

        self.assertEqual(
            set_on_state_change,
            tracker.on_stanza_state_change
        )

        self.assertIsInstance(
            tracker,
            tracking.MessageTracker
        )
        self.assertEqual(
            tracker.token,
            result,
        )

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT
        )

        reflected = aioxmpp.stanza.Message(
            type_="groupchat",
            id_=stanza.id_
        )

        self.jmuc._inbound_message(reflected)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.DELIVERED_TO_RECIPIENT
        )

    def test_tracking_deals_with_invalid_state(self):
        stanza = None
        set_on_state_change = None
        result = object()

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal stanza, set_on_state_change
            self.assertIsNone(stanza)
            stanza_to_send.autoset_id()
            stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        body = {
            None: "foo"
        }

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(body)

        self.assertIsNotNone(stanza)
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Message
        )
        self.assertEqual(
            stanza.type_,
            "groupchat"
        )
        self.assertEqual(
            stanza.to,
            self.mucjid
        )
        self.assertDictEqual(
            stanza.body,
            body
        )

        self.assertEqual(
            set_on_state_change,
            tracker.on_stanza_state_change
        )

        self.assertIsInstance(
            tracker,
            tracking.MessageTracker
        )
        self.assertEqual(
            tracker.token,
            result,
        )

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT
        )

        tracker.state = tracking.MessageState.SEEN_BY_RECIPIENT

        reflected = aioxmpp.stanza.Message(
            type_="groupchat",
            id_=stanza.id_
        )

        self.jmuc._inbound_message(reflected)

    def test_send_tracked_message_with_timeout(self):
        stanza = None
        set_on_state_change = None
        result = object()

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal stanza, set_on_state_change
            self.assertIsNone(stanza)
            stanza_to_send.autoset_id()
            stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        body = {
            None: "foo"
        }

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(
                body,
                timeout=timedelta(seconds=0.05)
            )

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT
        )

        run_coroutine(asyncio.sleep(0.06))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.TIMED_OUT
        )

    def test_send_tracked_message_with_stanza(self):
        stanza = aioxmpp.stanza.Message(
            type_="chat",
            to=TEST_ENTITY_JID
        )

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal set_stanza, set_on_state_change
            self.assertIsNone(set_stanza)
            stanza_to_send.autoset_id()
            set_stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        set_stanza = None
        set_on_state_change = None
        result = object()

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(
                stanza,
            )

        self.assertIs(set_stanza, stanza)

        # assure that critical attributes are overriden
        self.assertEqual(stanza.type_, "groupchat")
        self.assertEqual(stanza.to, self.mucjid)

    def test_tracked_messages_are_set_to_unknown_on_exit(self):
        stanza = aioxmpp.stanza.Message(
            type_="chat",
            to=TEST_ENTITY_JID
        )

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal set_stanza, set_on_state_change
            self.assertIsNone(set_stanza)
            stanza_to_send.autoset_id()
            set_stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        set_stanza = None
        set_on_state_change = None
        result = object()

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(
                stanza,
            )

        self.assertIs(set_stanza, stanza)

        self.jmuc.on_exit(object(), object(), object())

        self.assertEqual(
            tracker.state,
            tracking.MessageState.UNKNOWN
        )

    def test_tracked_messages_are_set_to_unknown_on_resume(self):
        stanza = aioxmpp.stanza.Message(
            type_="chat",
            to=TEST_ENTITY_JID
        )

        def setup_stanza(stanza_to_send, *, on_state_change=None):
            nonlocal set_stanza, set_on_state_change
            self.assertIsNone(set_stanza)
            stanza_to_send.autoset_id()
            set_stanza = stanza_to_send
            set_on_state_change = on_state_change
            return result

        set_stanza = None
        set_on_state_change = None
        result = object()

        with unittest.mock.patch.object(
                self.base.service.client.stream,
                "enqueue_stanza",
                new=setup_stanza):
            tracker = self.jmuc.send_tracked_message(
                stanza,
            )

        self.assertIs(set_stanza, stanza)

        self.jmuc.on_resume()

        self.assertEqual(
            tracker.state,
            tracking.MessageState.UNKNOWN
        )

    def tearDown(self):
        del self.jmuc


class TestService(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            muc_service.Service,
            service.Service
        ))

    def setUp(self):
        self.cc = make_connected_client()
        self.s = muc_service.Service(self.cc)

    def test_event_attributes(self):
        self.assertIsInstance(
            self.s.on_muc_joined,
            aioxmpp.callbacks.AdHocSignal
        )

    def test_init_and_shutdown(self):
        cc = make_connected_client()
        s = muc_service.Service(cc)

        calls = list(cc.mock_calls)

        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.
                stream.service_inbound_presence_filter.register(
                    s._inbound_presence_filter,
                    muc_service.Service
                ),
            ]
        )
        cc.mock_calls.clear()

        run_coroutine(s.shutdown())

        calls = list(cc.mock_calls)

        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.
                stream.service_inbound_presence_filter.unregister(
                    cc.stream.service_inbound_presence_filter.register()
                )
            ]
        )

    def test__inbound_presence_filter_passes_ordinary_presence(self):
        presence = aioxmpp.stanza.Presence()
        self.assertIs(
            presence,
            self.s._inbound_presence_filter(presence)
        )

    def test__inbound_presence_filter_catches_presence_with_muc_user(self):
        presence = aioxmpp.stanza.Presence()
        presence.xep0045_muc_user = muc_xso.UserExt()

        with unittest.mock.patch.object(
                self.s,
                "_inbound_muc_user_presence") as handler:
            handler.return_value = 123
            self.assertIsNone(
                self.s._inbound_presence_filter(presence)
            )

        handler.assert_called_with(presence)

    def test__inbound_presence_filter_catches_presence_with_muc(self):
        presence = aioxmpp.stanza.Presence()
        presence.xep0045_muc = muc_xso.GenericExt()
        with unittest.mock.patch.object(
                self.s,
                "_inbound_muc_presence") as handler:
            handler.return_value = 123
            self.assertIsNone(
                self.s._inbound_presence_filter(presence)
            )

        handler.assert_called_with(presence)

    def test_join_without_password_or_history(self):
        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")
        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )
        self.assertTrue(room.autorejoin)
        self.assertIsNone(room.password)

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
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

        self.cc.stream.register_message_callback.assert_called_with(
            "groupchat",
            TEST_MUC_JID,
            self.s._inbound_message
        )

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
        self.assertTrue(room.autorejoin)
        self.assertEqual(room.password, "foobar")

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
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
        self.assertFalse(room.autorejoin)
        self.assertEqual(room.password, "foobar")

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
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

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
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
        self.s.join(TEST_MUC_JID, "firstwitch")
        with self.assertRaisesRegex(
                ValueError,
                "already joined"):
            self.s.join(
                TEST_MUC_JID,
                "thirdwitch",
            )

    def test_join_rejects_non_bare_muc_jid(self):
        with self.assertRaisesRegex(
                ValueError,
                "MUC JID must be bare"):
            self.s.join(
                TEST_MUC_JID.replace(resource="firstwitch"),
                "firstwitch"
            )

    def test_join_raises_if_message_callback_is_in_use(self):
        self.cc.stream.register_message_callback.side_effect = ValueError()

        with self.assertRaisesRegex(
                RuntimeError,
                "message callback for MUC already in use"):
            self.s.join(
                TEST_MUC_JID,
                "firstwitch"
            )

    def test_future_receives_exception_on_join_error(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        response = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID,
            type_="error")
        response.xep0045_muc = muc_xso.GenericExt()
        response.error = aioxmpp.stanza.Error()
        self.s._inbound_presence_filter(response)

        self.assertTrue(future.done())
        self.assertIsInstance(
            future.exception(),
            aioxmpp.errors.XMPPCancelError
        )

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

    def test_pending_muc_removed_and_unavailable_presence_emitted_on_cancel(
            self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        self.cc.stream.enqueue_stanza.mock_calls.clear()

        future.cancel()

        run_coroutine(asyncio.sleep(0))

        with self.assertRaises(KeyError):
            self.s.get_muc(TEST_MUC_JID)

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
        self.assertIsInstance(
            stanza,
            aioxmpp.stanza.Presence
        )
        self.assertEqual(
            stanza.type_,
            "unavailable"
        )
        self.assertIsInstance(
            stanza.xep0045_muc,
            muc_xso.GenericExt
        )

    def test_join_completed_on_occupant_presence(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        occupant_presence = aioxmpp.stanza.Presence(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
        )
        occupant_presence.xep0045_muc_user = muc_xso.UserExt()

        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                room,
                "_inbound_muc_user_presence",
                new=base.inbound_muc_user_presence
            ))

            self.s._inbound_presence_filter(occupant_presence)

        self.assertTrue(future.done())
        self.assertIsNone(future.result())

        self.assertIs(
            self.s.get_muc(TEST_MUC_JID),
            room
        )

        base.inbound_muc_user_presence.assert_called_with(
            occupant_presence
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
                self.s._inbound_presence_filter(presence)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.inbound_muc_user_presence(
                    presence
                )
                for presence in occupant_presences
            ]
        )

    def test_forward_messages_to_joined_mucs(self):
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

        msg = aioxmpp.stanza.Message(
            from_=TEST_MUC_JID.replace(resource="firstwitch"),
            type_="groupchat",
        )

        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                room,
                "_inbound_muc_user_presence",
                new=base.inbound_muc_user_presence
            ))
            stack.enter_context(unittest.mock.patch.object(
                room,
                "_inbound_message",
                new=base.inbound_message
            ))

            for presence in occupant_presences:
                self.s._inbound_presence_filter(presence)

            self.s._inbound_message(msg)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.inbound_muc_user_presence(
                    presence
                )
                for presence in occupant_presences
            ]+[
                unittest.mock.call.inbound_message(msg)
            ]
        )

    def test_muc_is_untracked_when_user_leaves(self):
        room, future = self.s.join(TEST_MUC_JID, "thirdwitch")

        presence = aioxmpp.stanza.Presence(
            type_=None,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt()
        presence.xep0045_muc_user.status_codes.add(110)

        self.s._inbound_presence_filter(presence)
        run_coroutine(asyncio.sleep(0))

        self.assertTrue(future.done())

        presence = aioxmpp.stanza.Presence(
            type_="unavailable",
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt()
        presence.xep0045_muc_user.status_codes.add(110)

        self.s._inbound_presence_filter(presence)
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
            self.cc.stream.enqueue_stanza.mock_calls,
            []
        )

        self.cc.on_stream_established()

        run_coroutine(asyncio.sleep(0))

        _, (stanza,), _ = self.cc.stream.enqueue_stanza.mock_calls[-1]
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

        room1.on_enter.connect(base.enter1)
        room2.on_enter.connect(base.enter2)

        room1.on_suspend.connect(base.suspend1)
        room2.on_suspend.connect(base.suspend2)

        room1.on_resume.connect(base.resume1)
        room2.on_resume.connect(base.resume2)

        room1.on_exit.connect(base.exit1)
        room2.on_exit.connect(base.exit2)

        # test one which is joined and one which is not joined

        presence = aioxmpp.stanza.Presence(
            type_=None,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )

        self.s._inbound_presence_filter(presence)
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
                                          unittest.mock.ANY),
                unittest.mock.call.suspend1(),
            ]
        )
        base.mock_calls.clear()
        self.cc.stream.enqueue_stanza.mock_calls.clear()

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
            len(self.cc.stream.enqueue_stanza.mock_calls),
            2,
        )

        self.assertSetEqual(
            extract(
                self.cc.stream.enqueue_stanza.mock_calls,
                lambda stanza: (stanza.to.bare(),)
            ),
            {
                (TEST_MUC_JID,),
                (TEST_MUC_JID.replace(localpart="foo"),)
            }
        )

        self.assertSetEqual(
            extract(
                self.cc.stream.enqueue_stanza.mock_calls,
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

        self.assertFalse(room1.active)
        self.assertFalse(room2.active)

        # now let both be joined
        presence = aioxmpp.stanza.Presence(
            type_=None,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )
        self.s._inbound_presence_filter(presence)

        presence = aioxmpp.stanza.Presence(
            type_=None,
            from_=TEST_MUC_JID.replace(localpart="foo",
                                       resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )
        self.s._inbound_presence_filter(presence)

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(fut1.done())
        self.assertTrue(fut2.done())

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.enter1(unittest.mock.ANY,
                                          unittest.mock.ANY),
                unittest.mock.call.enter2(unittest.mock.ANY,
                                          unittest.mock.ANY),
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

        room1.on_enter.connect(base.enter1)
        room2.on_enter.connect(base.enter2)

        room1.on_suspend.connect(base.suspend1)
        room2.on_suspend.connect(base.suspend2)

        room1.on_resume.connect(base.resume1)
        room2.on_resume.connect(base.resume2)

        room1.on_exit.connect(base.exit1)
        room2.on_exit.connect(base.exit2)

        # test one which is joined and one which is not joined

        presence = aioxmpp.stanza.Presence(
            type_=None,
            from_=TEST_MUC_JID.replace(resource="thirdwitch")
        )
        presence.xep0045_muc_user = muc_xso.UserExt(
            status_codes={110}
        )

        self.s._inbound_presence_filter(presence)
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
                                          unittest.mock.ANY),
                unittest.mock.call.exit1(None,
                                         room1.this_occupant,
                                         muc_service.LeaveMode.DISCONNECTED),
            ]
        )
        base.mock_calls.clear()
        self.cc.stream.enqueue_stanza.mock_calls.clear()

        self.cc.on_stream_established()
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            len(self.cc.stream.enqueue_stanza.mock_calls),
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
            type_=None,
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

        self.s._inbound_presence_filter(presence)

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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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
            "set"
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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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
                self.cc.stream,
                "send_iq_and_wait_for_reply",
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

    def tearDow(self):
        del self.s
        del self.cc
