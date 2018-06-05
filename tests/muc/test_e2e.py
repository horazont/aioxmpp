########################################################################
# File name: test_e2e.py
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
import functools
import logging
import unittest

import aioxmpp.muc
import aioxmpp.im.p2p
import aioxmpp.im.service

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    require_feature,
    blocking,
    blocking_timed,
    TestCase,
    skip_with_quirk,
    Quirk,
)


class TestMuc(TestCase):
    @skip_with_quirk(Quirk.BROKEN_MUC)
    @require_feature(namespaces.xep0045_muc)
    @blocking
    @asyncio.coroutine
    def setUp(self, muc_provider):
        services = [
            aioxmpp.MUCClient,
            aioxmpp.im.p2p.Service,
            aioxmpp.im.service.ConversationService,
        ]

        self.peer = muc_provider
        self.mucjid = self.peer.replace(localpart="coven")

        self.firstwitch, self.secondwitch, self.thirdwitch = \
            yield from asyncio.gather(
                self.provisioner.get_connected_client(
                    services=services
                ),
                self.provisioner.get_connected_client(
                    services=services
                ),
                self.provisioner.get_connected_client(
                    services=services
                ),
            )

        logging.debug("firstwitch is %s", self.firstwitch.local_jid)
        logging.debug("secondwitch is %s", self.secondwitch.local_jid)
        logging.debug("thirdwitch is %s", self.thirdwitch.local_jid)

        # make firstwitch and secondwitch join
        firstmuc = self.firstwitch.summon(aioxmpp.MUCClient)
        self.firstroom, fut = firstmuc.join(
            self.mucjid,
            "firstwitch",
        )

        # configure room to be open (this also alleviates any locking)
        try:
            form = aioxmpp.muc.xso.ConfigurationForm.from_xso(
                (yield from firstmuc.get_room_config(self.firstroom.jid))
            )
            form.membersonly.value = False
            yield from firstmuc.set_room_config(self.firstroom.jid,
                                                form.render_reply())
        except aioxmpp.errors.XMPPError:
            logging.warning(
                "failed to configure room for the tests",
                exc_info=True,
            )

        # we want firstwitch to join first so that we have a deterministic
        # owner of the muc
        yield from fut

        secondwitch_fut = asyncio.Future()
        def cb(member, **kwargs):
            secondwitch_fut.set_result(member)
            return True

        self.firstroom.on_join.connect(cb)

        self.secondroom, fut = self.secondwitch.summon(
            aioxmpp.MUCClient
        ).join(
            self.mucjid,
            "secondwitch",
        )

        yield from fut

        # we also want to wait until firstwitch sees secondwitch

        member = yield from secondwitch_fut
        self.assertIn(member, self.firstroom.members)

    @blocking_timed
    @asyncio.coroutine
    def test_join(self):
        service = self.thirdwitch.summon(aioxmpp.MUCClient)

        recvd_future = asyncio.Future()

        def onjoin(occupant, **kwargs):
            if occupant.nick != "thirdwitch":
                return
            nonlocal recvd_future
            recvd_future.set_result((occupant, ))
            # we do not want to be called again
            return True

        self.firstroom.on_join.connect(onjoin)

        thirdroom, fut = service.join(self.mucjid, "thirdwitch")
        yield from fut

        occupant, = yield from recvd_future
        self.assertEqual(
            occupant.conversation_jid,
            self.mucjid.replace(resource="thirdwitch"),
        )

        self.assertIn(occupant, self.firstroom.members)

    @blocking_timed
    @asyncio.coroutine
    def test_join_history(self):
        service = self.thirdwitch.summon(aioxmpp.MUCClient)

        recvd_future = asyncio.Future()

        def onjoin(occupant, **kwargs):
            if occupant.nick != "thirdwitch":
                return
            nonlocal recvd_future
            recvd_future.set_result((occupant, ))
            # we do not want to be called again
            return True

        self.firstroom.on_join.connect(onjoin)

        msg = aioxmpp.Message(type_=aioxmpp.MessageType.GROUPCHAT)
        msg.body[None] = "test"
        yield from self.firstroom.send_message(msg)

        thirdroom, fut = service.join(
            self.mucjid,
            "thirdwitch",
            history=aioxmpp.muc.xso.History(seconds=10)
        )
        yield from fut

        occupant, = yield from recvd_future
        self.assertEqual(
            occupant.conversation_jid,
            self.mucjid.replace(resource="thirdwitch"),
        )

        yield from asyncio.sleep(0.2)

        if thirdroom.muc_state != aioxmpp.muc.RoomState.ACTIVE:
            logging.warning(
                "this seems to be a broken server implementation. MUC is in"
                " history state after join seems to be over. Maybe it doesn’t"
                " send <subject/>? Trying to send a message to bust this..."
            )

            message_fut = asyncio.Future()

            def onmessage(*args, **kwargs):
                nonlocal message_fut
                message_fut.set_result(None)
                return True

            thirdroom.on_message.connect(onmessage)

            self.firstroom.send_message(msg)

            yield from message_fut

        self.assertEqual(thirdroom.muc_state,
                         aioxmpp.muc.RoomState.ACTIVE)

        self.assertIn(occupant, self.firstroom.members)

    @blocking_timed
    @asyncio.coroutine
    def test_kick(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode, muc_reason))
            return True

        def onleave(occupant, muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode, muc_reason))
            return True

        self.secondroom.on_exit.connect(onexit)
        self.firstroom.on_leave.connect(onleave)

        for witch in self.firstroom.members:
            if witch.nick == "secondwitch":
                yield from self.firstroom.kick(witch, "Thou art no real witch")
                break
        else:
            self.assertFalse(True, "secondwitch not found in members")

        mode, reason = yield from exit_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.KICKED,
        )

        self.assertEqual(
            reason,
            "Thou art no real witch",
        )

        occupant, mode, reason = yield from leave_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.KICKED,
        )

        self.assertEqual(
            reason,
            "Thou art no real witch",
        )

    @blocking_timed
    @asyncio.coroutine
    def test_kick_using_set_role(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode,))
            return True

        def onleave(occupant, muc_leave_mode, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode))
            return True

        self.secondroom.on_exit.connect(onexit)
        self.firstroom.on_leave.connect(onleave)

        yield from self.firstroom.muc_set_role(
            "secondwitch",
            "none",
            reason="Thou art no real witch")

        mode, = yield from exit_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.KICKED,
        )

        occupant, mode = yield from leave_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.KICKED,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_ban(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode, muc_reason))
            return True

        def onleave(occupant, muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode, muc_reason))
            return True

        self.secondroom.on_exit.connect(onexit)
        self.firstroom.on_leave.connect(onleave)

        for witch in self.firstroom.members:
            if witch.nick == "secondwitch":
                yield from self.firstroom.ban(witch, "Treason!")
                break
        else:
            self.assertFalse(True, "secondwitch not found in members")

        mode, reason = yield from exit_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.BANNED,
        )

        self.assertEqual(
            reason,
            "Treason!",
        )

        occupant, mode, reason = yield from leave_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.BANNED,
        )

        self.assertEqual(
            reason,
            "Treason!",
        )

    @blocking_timed
    @asyncio.coroutine
    def test_ban_using_set_affiliation(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode,))
            return True

        def onleave(occupant, muc_leave_mode, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode))
            return True

        self.secondroom.on_exit.connect(onexit)
        self.firstroom.on_leave.connect(onleave)

        yield from self.firstroom.muc_set_affiliation(
            self.secondwitch.local_jid.bare(),
            "outcast",
            reason="Thou art no real witch")

        mode, = yield from exit_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.BANNED,
        )

        occupant, mode = yield from leave_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.BANNED,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_leave(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode,))
            return True

        def onleave(occupant, muc_leave_mode, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode))
            return True

        self.firstroom.on_leave.connect(onleave)
        self.secondroom.on_exit.connect(onexit)

        yield from self.secondroom.leave()

        self.assertFalse(self.secondroom.muc_active)
        self.assertFalse(self.secondroom.muc_joined)

        mode, = yield from exit_fut
        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.NORMAL,
        )

        occupant, mode = yield from leave_fut
        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.NORMAL,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_set_topic(self):
        subject_fut = asyncio.Future()

        def onsubject(member, subject, **kwargs):
            nonlocal subject_fut
            subject_fut.set_result((member, subject))
            return True

        self.secondroom.on_topic_changed.connect(onsubject)

        yield from self.firstroom.set_topic({None: "Wytches Brew!"})

        member, subject = yield from subject_fut

        self.assertEqual(
            subject.any(),
            "Wytches Brew!",
            subject,
        )

        self.assertDictEqual(
            self.secondroom.muc_subject,
            subject,
        )

        self.assertEqual(
            self.secondroom.muc_subject_setter,
            "firstwitch",
        )

    @blocking_timed
    @asyncio.coroutine
    def test_send_tracked_message(self):
        msg_future = asyncio.Future()
        sent_future = asyncio.Future()

        def onmessage(message, member, source, **kwargs):
            nonlocal msg_future
            msg_future.set_result((message,))
            return True

        def onstatechange(state, response=None):
            if state == aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT:
                sent_future.set_result(None)
                return True

        self.secondroom.on_message.connect(onmessage)

        msg = aioxmpp.Message(aioxmpp.MessageType.NORMAL)
        msg.body[None] = "foo"
        token, tracker = self.firstroom.send_message_tracked(msg)
        tracker.on_state_changed.connect(onstatechange)
        yield from sent_future

        message, = yield from msg_future
        self.assertEqual(
            message.body.any(),
            "foo",
        )

    @blocking_timed
    @asyncio.coroutine
    def test_send_message(self):
        msg_future = asyncio.Future()

        def onmessage(message, member, source, **kwargs):
            nonlocal msg_future
            msg_future.set_result((message, member,))
            return True

        self.secondroom.on_message.connect(onmessage)

        msg = aioxmpp.Message(type_=aioxmpp.MessageType.CHAT)
        msg.body.update({None: "foo"})
        yield from self.firstroom.send_message(msg)

        message, member, = yield from msg_future
        self.assertEqual(
            message.body.any(),
            "foo",
        )
        self.assertEqual(
            message.type_,
            aioxmpp.MessageType.GROUPCHAT,
        )
        self.assertEqual(
            msg.type_,
            aioxmpp.MessageType.GROUPCHAT,
        )

        self.assertCountEqual(
            [member],
            [member
             for member in self.secondroom.members
             if member.nick == "firstwitch"],
        )

    @blocking_timed
    @asyncio.coroutine
    def test_muc_pms(self):
        firstwitch_convs = self.firstwitch.summon(
            aioxmpp.im.service.ConversationService
        )

        firstconv_future = asyncio.Future()
        first_msgs = asyncio.Queue()

        def conv_added(conversation):
            firstconv_future.set_result(conversation)

            def message(message, member, source, **kwargs):
                first_msgs.put_nowait((message, member, source))

            conversation.on_message.connect(message)
            return True

        firstwitch_convs.on_conversation_added.connect(conv_added)

        secondwitch_p2p = self.secondwitch.summon(
            aioxmpp.im.p2p.Service,
        )
        secondconv = secondwitch_p2p.get_conversation(
            self.secondroom.members[1].conversation_jid
        )

        msg = aioxmpp.Message(type_=aioxmpp.MessageType.CHAT)
        msg.body[None] = "I'll give thee a wind."

        yield from secondconv.send_message(msg)
        firstconv = yield from firstconv_future

        self.assertEqual(firstconv.members[1].conversation_jid,
                         self.firstroom.members[1].conversation_jid)

        message, member, *_ = yield from first_msgs.get()
        self.assertIsInstance(message, aioxmpp.Message)
        self.assertEqual(
            message.body.any(),
            msg.body.any(),
        )
        self.assertEqual(member, firstconv.members[1])

    @blocking_timed
    @asyncio.coroutine
    def test_set_nick(self):
        self_future = asyncio.Future()
        foreign_future = asyncio.Future()

        def onnickchange(fut, occupant, old_nick, new_nick, **kwargs):
            fut.set_result((occupant, old_nick, new_nick))
            return True

        self.secondroom.on_nick_changed.connect(
            functools.partial(onnickchange, foreign_future),
        )

        self.firstroom.on_nick_changed.connect(
            functools.partial(onnickchange, self_future),
        )

        yield from self.firstroom.set_nick("oldhag")

        occupant, old_nick, new_nick = yield from self_future
        self.assertEqual(occupant, self.firstroom.me)
        self.assertEqual(old_nick, "firstwitch")
        self.assertEqual(occupant.nick, "oldhag")
        self.assertEqual(new_nick, occupant.nick)

        occupant, old_nick, new_nick = yield from foreign_future
        self.assertEqual(occupant.nick, "oldhag")
        self.assertEqual(old_nick, "firstwitch")
        self.assertEqual(new_nick, occupant.nick)

    @skip_with_quirk(Quirk.MUC_NO_333)
    @blocking_timed
    @asyncio.coroutine
    def test_kick_due_to_error(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((muc_leave_mode, muc_reason))
            return True

        def onleave(occupant, muc_leave_mode, muc_reason=None, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((occupant, muc_leave_mode, muc_reason))
            return True

        self.secondroom.on_exit.connect(onexit)
        self.firstroom.on_leave.connect(onleave)

        error_presence = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.ERROR,
            to=self.secondroom.me.conversation_jid,
        )
        error_presence.status.update({None: "Client exited"})
        yield from self.secondwitch.send(
            error_presence,
        )

        mode, reason = yield from exit_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.ERROR,
        )

        occupant, mode, reason = yield from leave_fut

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.ERROR,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_voice_request_handling(self):
        info = yield from self.firstwitch.summon(
            aioxmpp.DiscoClient
        ).query_info(
            self.firstroom.jid
        )

        if aioxmpp.muc.xso.VoiceRequestForm.FORM_TYPE not in info.features:
            raise unittest.SkipTest(
                "voice request not supported"
            )

        role_future = asyncio.Future()
        request_future = asyncio.Future()

        def secondwitch_role_changed(presence, member, *,
                                     actor=None, reason=None,
                                     **kwargs):
            print("role changed")
            role_future.set_result((presence, member, actor, reason))

        def firstwitch_role_request(form, submission_future):
            request_future.set_result(form)
            form.request_allow.value = True
            submission_future.set_result(form.render_reply())

        self.secondroom.on_muc_role_changed.connect(secondwitch_role_changed)
        self.firstroom.on_muc_role_request.connect(firstwitch_role_request)

        firstmuc = self.firstwitch.summon(aioxmpp.MUCClient)

        form = aioxmpp.muc.xso.ConfigurationForm.from_xso(
            (yield from firstmuc.get_room_config(self.firstroom.jid))
        )
        form.moderatedroom.value = True
        yield from firstmuc.set_room_config(self.firstroom.jid,
                                            form.render_reply())

        # ensure that secondwitch has no voice
        yield from self.firstroom.muc_set_role("secondwitch", "visitor")

        # wait until demotion has passed
        _, member, _, _ = yield from role_future
        self.assertEqual(member.role, "visitor")

        role_future = asyncio.Future()

        yield from self.secondroom.muc_request_voice()

        yield from request_future

        _, member, _, _ = yield from role_future
        self.assertEqual(member.role, "participant")
        self.assertEqual(self.secondroom.me.role, "participant")
