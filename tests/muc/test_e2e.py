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

import aioxmpp.muc

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
    @require_feature(namespaces.xep0045_muc)
    @blocking
    @asyncio.coroutine
    def setUp(self, muc_provider):
        services = [aioxmpp.MUCClient]

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
        self.firstroom, fut = self.firstwitch.summon(
            aioxmpp.MUCClient
        ).join(
            self.mucjid,
            "firstwitch",
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

        self.assertDictEqual(
            subject,
            {
                None: "Wytches Brew!",
            }
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
        tracker = yield from self.firstroom.send_message_tracked(msg)
        tracker.on_state_changed.connect(onstatechange)
        yield from sent_future

        message, = yield from msg_future
        self.assertDictEqual(
            message.body,
            {
                None: "foo"
            }
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
        self.assertDictEqual(
            message.body,
            {
                None: "foo"
            }
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
