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
import aioxmpp.errors
import aioxmpp.version

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    TestCase,
    require_feature,
)


class TestVersion(TestCase):
    @blocking
    @asyncio.coroutine
    def setUp(self):
        services = [
            aioxmpp.version.VersionServer,
        ]

        self.a, self.b = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=services,
            ),
            self.provisioner.get_connected_client(
                services=services,
            ),
        )

    @blocking_timed
    @asyncio.coroutine
    def test_version_query_returns_service_unavailable_if_unconfigured(self):
        b_version = self.b.summon(aioxmpp.version.VersionServer)

        with self.assertRaises(aioxmpp.XMPPCancelError) as ctx:
            yield from aioxmpp.version.query_version(
                self.a.stream,
                self.b.local_jid,
            )

        self.assertEqual(ctx.exception.condition,
                         aioxmpp.ErrorCondition.SERVICE_UNAVAILABLE)

    @blocking_timed
    @asyncio.coroutine
    def test_version_query_with_results(self):
        b_version = self.b.summon(aioxmpp.version.VersionServer)
        b_version.name = "aioxmpp"
        b_version.version = aioxmpp.__version__

        result = yield from aioxmpp.version.query_version(
            self.a.stream,
            self.b.local_jid,
        )

        self.assertEqual(
            result.name,
            "aioxmpp",
        )
        self.assertEqual(
            result.version,
            aioxmpp.__version__,
        )
        self.assertEqual(
            result.os,
            b_version.os,
        )

    @require_feature(namespaces.xep0092_version)
    @blocking_timed
    @asyncio.coroutine
    def test_version_query_against_server(self, peer):
        result = yield from aioxmpp.version.query_version(
            self.a.stream,
            peer,
        )

        self.assertIsNotNone(result)
