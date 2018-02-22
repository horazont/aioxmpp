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

import aioxmpp.stream
import aioxmpp.xso

from aioxmpp.e2etest import (
    blocking_timed,
    TestCase,
)


@aioxmpp.IQ.as_payload_class
class MadeUpIQPayload(aioxmpp.xso.XSO):
    TAG = "made-up", "made-up"


class TestConnect(TestCase):
    @blocking_timed
    @asyncio.coroutine
    def test_provisioner_works_in_general(self):
        connected = yield from self.provisioner.get_connected_client()
        self.assertTrue(connected.running)
        self.assertTrue(connected.established)


class TestMessaging(TestCase):
    @blocking_timed
    @asyncio.coroutine
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
            msg_sent.body[aioxmpp.structs.LanguageTag.fromstr("en")] = \
                "Hello World!"

            yield from a.send(msg_sent)

            msg_rcvd = yield from fut

        self.assertEqual(
            msg_rcvd.body[aioxmpp.structs.LanguageTag.fromstr("en")],
            "Hello World!"
        )


class TestMisc(TestCase):
    @blocking_timed
    @asyncio.coroutine
    def test_receive_response_from_iq_to_bare_explicit_self(self):
        c = yield from self.provisioner.get_connected_client()

        iq = aioxmpp.IQ(
            to=c.local_jid.bare(),
            type_=aioxmpp.IQType.GET,
            payload=MadeUpIQPayload()
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError):
            yield from c.send(iq)

    @blocking_timed
    @asyncio.coroutine
    def test_receive_response_from_iq_to_bare_self_using_None(self):
        c = yield from self.provisioner.get_connected_client()

        iq = aioxmpp.IQ(
            to=None,
            type_=aioxmpp.IQType.GET,
            payload=MadeUpIQPayload()
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError):
            yield from c.send(iq)

    @blocking_timed
    @asyncio.coroutine
    def test_exception_from_non_wellformed(self):
        c = yield from self.provisioner.get_connected_client()

        msg = aioxmpp.Message(
            to=c.local_jid,
            type_=aioxmpp.MessageType.NORMAL,
        )
        msg.body[None] = "foo\u0000"

        with self.assertRaisesRegex(ValueError, "not allowed"):
            yield from c.send(msg)

        msg.body[None] = "foo"

        yield from c.send(msg)
