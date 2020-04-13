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

from aioxmpp.utils import namespaces

import aioxmpp.ping

from aioxmpp.e2etest import (
    TestCase,
    blocking,
    blocking_timed,
)


class TestPing(TestCase):
    @blocking
    async def setUp(self):
        self.source, self.unimplemented, self.implemented = await asyncio.gather(
            self.provisioner.get_connected_client(
                services=[aioxmpp.ping.PingService],
            ),
            self.provisioner.get_connected_client(
                services=[aioxmpp.DiscoClient],
            ),
            self.provisioner.get_connected_client(
                services=[aioxmpp.ping.PingService],
            ),
        )

    @blocking_timed
    async def test_ping_raises_error_condition(self):
        ping_svc = self.source.summon(aioxmpp.ping.PingService)

        with self.assertRaisesRegexp(aioxmpp.XMPPCancelError,
                                     "service-unavailable"):
            await ping_svc.ping(self.unimplemented.local_jid)

    @blocking_timed
    async def test_ping_server(self):
        ping_svc = self.source.summon(aioxmpp.ping.PingService)

        await ping_svc.ping(self.unimplemented.local_jid.replace(
            localpart=None,
            resource=None,
        ))

    @blocking_timed
    async def test_ping_works_with_peer_with_ping_implementation(self):
        ping_svc = self.source.summon(aioxmpp.ping.PingService)

        self.assertIsNone(await ping_svc.ping(self.implemented.local_jid))

    @blocking_timed
    async def test_ping_service_exports_feature(self):
        info = await self.unimplemented.summon(
            aioxmpp.DiscoClient
        ).query_info(
            self.source.local_jid,
        )

        self.assertIn(
            namespaces.xep0199_ping,
            info.features,
        )

    @blocking_timed
    async def test_ping_service_replies_to_ping(self):
        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.GET,
            to=self.source.local_jid,
            payload=aioxmpp.ping.Ping(),
        )

        resp = await self.unimplemented.send(req)

        self.assertIsInstance(resp, aioxmpp.ping.Ping)
