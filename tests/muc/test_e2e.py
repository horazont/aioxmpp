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

        self.secondroom, fut = self.secondwitch.summon(
            aioxmpp.MUCClient
        ).join(
            self.mucjid,
            "secondwitch",
        )

        yield from fut

    @blocking_timed
    @asyncio.coroutine
    def test_join(self):
        service = self.thirdwitch.summon(aioxmpp.MUCClient)

        recvd_future = asyncio.Future()

        def onjoin(presence, occupant, **kwargs):
            if occupant.occupantjid.resource != "thirdwitch":
                return
            nonlocal recvd_future
            recvd_future.set_result((presence, occupant))
            # we do not want to be called again
            return True

        self.firstroom.on_join.connect(onjoin)

        thirdroom, fut = service.join(self.mucjid, "thirdwitch")
        yield from fut

        presence, occupant = yield from recvd_future
        self.assertEqual(
            occupant.occupantjid,
            self.mucjid.replace(resource="thirdwitch"),
        )

        self.assertEqual(
            presence.from_,
            occupant.occupantjid,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_kick(self):
        exit_fut = asyncio.Future()

        def onexit(presence, occupant, mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((presence, occupant, mode))
            return True

        self.secondroom.on_exit.connect(onexit)

        yield from self.firstroom.set_role(
            "secondwitch",
            "none",
            reason="Thou art no real witch")

        presence, occupant, mode = yield from exit_fut

        self.assertEqual(
            presence.type_,
            aioxmpp.PresenceType.UNAVAILABLE,
        )

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.KICKED,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_ban(self):
        exit_fut = asyncio.Future()

        def onexit(presence, occupant, mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((presence, occupant, mode))
            return True

        self.secondroom.on_exit.connect(onexit)

        yield from self.firstroom.set_affiliation(
            self.secondwitch.local_jid.bare(),
            "outcast",
            reason="Thou art no real witch")

        presence, occupant, mode = yield from exit_fut

        self.assertEqual(
            presence.type_,
            aioxmpp.PresenceType.UNAVAILABLE,
        )

        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.BANNED,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_leave(self):
        exit_fut = asyncio.Future()
        leave_fut = asyncio.Future()

        def onexit(presence, occupant, mode, **kwargs):
            nonlocal exit_fut
            exit_fut.set_result((presence, occupant, mode))
            return True

        def onleave(presence, occupant, mode, **kwargs):
            nonlocal leave_fut
            leave_fut.set_result((presence, occupant, mode))
            return True

        self.firstroom.on_leave.connect(onleave)
        self.secondroom.on_exit.connect(onexit)

        yield from self.secondroom.leave_and_wait()

        self.assertFalse(self.secondroom.active)
        self.assertFalse(self.secondroom.joined)

        presence, occupant, mode = yield from exit_fut
        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.NORMAL,
        )

        presence, occupant, mode = yield from leave_fut
        self.assertEqual(
            mode,
            aioxmpp.muc.LeaveMode.NORMAL,
        )

    @blocking_timed
    @asyncio.coroutine
    def test_set_subject(self):
        subject_fut = asyncio.Future()

        def onsubject(message, subject, **kwargs):
            nonlocal subject_fut
            subject_fut.set_result((message, subject))
            return True

        self.secondroom.on_subject_change.connect(onsubject)

        self.firstroom.set_subject({None: "Wytches Brew!"})

        message, subject = yield from subject_fut

        self.assertDictEqual(
            subject,
            {
                None: "Wytches Brew!",
            }
        )

        self.assertDictEqual(
            self.secondroom.subject,
            subject,
        )

        self.assertEqual(
            self.secondroom.subject_setter,
            "firstwitch",
        )

    @skip_with_quirk(Quirk.MUC_REWRITES_MESSAGE_ID)
    @blocking_timed
    @asyncio.coroutine
    def test_send_tracked_message(self):
        msg_future = asyncio.Future()
        sent_future = asyncio.Future()

        def onmessage(message, **kwargs):
            nonlocal msg_future
            msg_future.set_result((message,))
            return True

        def onstatechange(state):
            if state == aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT:
                sent_future.set_result(None)
                return True

        self.secondroom.on_message.connect(onmessage)

        tracker = self.firstroom.send_tracked_message({None: "foo"})
        tracker.on_state_change.connect(onstatechange)
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

        def onmessage(message, **kwargs):
            nonlocal msg_future
            msg_future.set_result((message,))
            return True

        self.secondroom.on_message.connect(onmessage)

        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
            to=self.mucjid
        )
        msg.body[None] = "foo"
        yield from self.firstwitch.stream.send(msg)

        message, = yield from msg_future
        self.assertDictEqual(
            message.body,
            {
                None: "foo"
            }
        )

    @blocking_timed
    @asyncio.coroutine
    def test_change_nick(self):
        self_future = asyncio.Future()
        foreign_future = asyncio.Future()

        def onnickchange(fut, presence, occupant, **kwargs):
            fut.set_result((presence, occupant,))
            return True

        self.secondroom.on_nick_change.connect(
            functools.partial(onnickchange, foreign_future),
        )

        self.firstroom.on_nick_change.connect(
            functools.partial(onnickchange, self_future),
        )

        yield from self.firstroom.change_nick("oldhag")

        presence, occupant = yield from self_future
        self.assertEqual(occupant, self.firstroom.this_occupant)
        self.assertEqual(occupant.occupantjid.resource, "oldhag")

        presence, occupant = yield from foreign_future
        self.assertEqual(occupant.occupantjid.resource, "oldhag")
