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
    @asyncio.coroutine
    def setUp(self):
        self.source, self.error_reflector, = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[aioxmpp.ping.PingService],
            ),
            self.provisioner.get_connected_client(),
        )

    @blocking_timed
    @asyncio.coroutine
    def test_ping_raises_error_condition(self):
        ping_svc = self.source.summon(aioxmpp.ping.PingService)

        with self.assertRaisesRegexp(aioxmpp.XMPPCancelError,
                                     "service-unavailable"):
            yield from ping_svc.ping(self.error_reflector.local_jid)

    @blocking_timed
    @asyncio.coroutine
    def test_ping_server(self):
        ping_svc = self.source.summon(aioxmpp.ping.PingService)

        yield from ping_svc.ping(self.error_reflector.local_jid.replace(
            localpart=None,
            resource=None,
        ))
