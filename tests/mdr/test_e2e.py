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

import aioxmpp
import aioxmpp.mdr
import aioxmpp.tracking

from aioxmpp.e2etest import (
    blocking_timed,
    TestCase,
)


LANG = aioxmpp.structs.LanguageTag.fromstr("en-gb")


class TestMessaging(TestCase):
    @blocking_timed
    @asyncio.coroutine
    def setUp(self):
        self.a, self.b = yield from asyncio.gather(
            self.provisioner.get_connected_client(),
            self.provisioner.get_connected_client(),
        )
        self.a_mdr = self.a.summon(aioxmpp.DeliveryReceiptsService)
        self.b_mdr = self.b.summon(aioxmpp.DeliveryReceiptsService)
        self.b_recv = self.b.summon(
            aioxmpp.dispatcher.SimpleMessageDispatcher
        )

    @blocking_timed
    @asyncio.coroutine
    def test_send_with_attached_tracker(self):
        msg_delivered = asyncio.Event()

        def state_change_cb(new_state, *args):
            if (new_state ==
                    aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT):
                msg_delivered.set()

        msg = aioxmpp.Message(type_=aioxmpp.MessageType.CHAT,
                              to=self.b.local_jid)
        msg.body[LANG] = "This is a non-colourful test message!"

        tracker = self.a_mdr.attach_tracker(msg)
        tracker.on_state_changed.connect(state_change_cb)

        msg_recvd = asyncio.Future()

        def cb(message):
            msg_recvd.set_result(message)

        self.b_recv.register_callback(aioxmpp.MessageType.CHAT, None, cb)

        yield from self.a.send(msg)

        msg_b = yield from msg_recvd
        self.assertDictEqual(
            msg_b.body,
            {
                LANG: "This is a non-colourful test message!"
            }
        )
        self.assertTrue(msg_b.xep0184_request_receipt)

        self.assertFalse(msg_delivered.is_set())

        response = aioxmpp.mdr.compose_receipt(msg_b)
        yield from self.b.send(response)

        yield from msg_delivered.wait()
