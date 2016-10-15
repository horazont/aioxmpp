########################################################################
# File name: __init__.py
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

import aioxmpp.stream

from aioxmpp.e2etest import (  # NOQA
    setup_package,
    teardown_package,
    blocking,
    TestCase,
)


class TestConnect(TestCase):
    @blocking
    def test_provisioner_works_in_general(self):
        connected = yield from self.provisioner.get_connected_client()
        self.assertTrue(connected.running)
        self.assertTrue(connected.established)


class TestMessaging(TestCase):
    @blocking
    def test_message_from_a_to_b(self):
        a = yield from self.provisioner.get_connected_client()
        b = yield from self.provisioner.get_connected_client()

        fut = asyncio.Future()

        def cb(msg):
            fut.set_result(msg)

        with aioxmpp.stream.message_handler(
                b.stream,
                aioxmpp.MessageType.CHAT,
                a.local_jid,
                cb):

            msg_sent = aioxmpp.Message(
                to=b.local_jid,
                type_=aioxmpp.MessageType.CHAT,

            )
            msg_sent.body[None] = "Hello World!"

            yield from a.stream.send_and_wait_for_sent(msg_sent)

            msg_rcvd = yield from fut

        self.assertEqual(
            msg_rcvd.body[None],
            "Hello World!"
        )
