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
import unittest

import aioxmpp
import aioxmpp.ibb

from aioxmpp.testutils import get_timeout

from aioxmpp.e2etest import (
    blocking_timed,
    TestCase,
)


class TestProtocol(asyncio.Protocol):

    def __init__(self):
        self.data = b""
        self._transport = None
        self.connection_lost_fut = asyncio.Future()

    def connection_made(self, transport):
        self._transport = transport

    def connection_lost(self, e):
        self.connection_lost_fut.set_result(e)

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def data_received(self, data):
        self.data += data


class TestIBB(TestCase):
    async def make_client(self, run_before=None):
        return await self.provisioner.get_connected_client(
            services=[
                aioxmpp.ibb.IBBService,
            ],
            prepare=run_before,
        )

    @blocking_timed
    async def test_ibb(self):
        client1 = await self.make_client()
        client2 = await self.make_client()

        s1 = client1.summon(aioxmpp.ibb.IBBService)
        s2 = client2.summon(aioxmpp.ibb.IBBService)

        # set-up the session
        handle2_fut = s2.expect_session(
            TestProtocol, client1.local_jid, "fnord")
        transport1, proto1 = await s1.open_session(
            TestProtocol, client2.local_jid, sid="fnord")
        transport2, proto2 = await handle2_fut

        # transfer data
        transport2.write(b"this")
        transport2.write(b"is")
        transport2.write(b"data")
        transport2.close()

        # assert that both protocols get notified (otherwise time out)
        e1 = await proto1.connection_lost_fut
        self.assertIsNone(e1)
        e2 = await proto2.connection_lost_fut
        self.assertIsNone(e2)

        self.assertEqual(proto1.data, b"thisisdata")

    @blocking_timed
    async def test_ibb_message(self):
        client1 = await self.make_client()
        client2 = await self.make_client()

        s1 = client1.summon(aioxmpp.ibb.IBBService)
        s2 = client2.summon(aioxmpp.ibb.IBBService)

        # set-up the session
        handle2_fut = s2.expect_session(
            TestProtocol, client1.local_jid, "fnord")
        transport1, proto1 = await s1.open_session(
            TestProtocol, client2.local_jid, sid="fnord",
            stanza_type=aioxmpp.ibb.IBBStanzaType.MESSAGE
        )
        transport2, proto2 = await handle2_fut

        # transfer data
        transport2.write(b"this")
        transport2.write(b"is")
        transport2.write(b"data")
        transport2.close()

        # assert that both protocols get notified (otherwise time out)
        e1 = await proto1.connection_lost_fut
        self.assertIsNone(e1)
        e2 = await proto2.connection_lost_fut
        self.assertIsNone(e2)

        self.assertEqual(proto1.data, b"thisisdata")

    @blocking_timed
    async def test_ibb_client_disconnects(self):
        client1 = await self.make_client()
        client2 = await self.make_client()

        s1 = client1.summon(aioxmpp.ibb.IBBService)
        s2 = client2.summon(aioxmpp.ibb.IBBService)

        # set-up the session
        handle2_fut = s2.expect_session(
            TestProtocol, client1.local_jid, "fnord")
        transport1, proto1 = await s1.open_session(
            TestProtocol, client2.local_jid, sid="fnord")
        transport2, proto2 = await handle2_fut

        # transfer data
        transport2.write(b"this")
        transport1.abort()
        transport2.write(b"is")

        # assert that both protocols get notified (otherwise time out)
        e1 = await proto1.connection_lost_fut
        self.assertIsNone(e1)
        e2 = await proto2.connection_lost_fut
        self.assertIsInstance(e2, aioxmpp.errors.XMPPCancelError)
