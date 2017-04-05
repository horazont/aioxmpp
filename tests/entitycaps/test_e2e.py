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

from aioxmpp.e2etest import (
    blocking_timed,
    blocking,
    TestCase,
)


class TestEntityCapabilities(TestCase):
    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.source, self.sink = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[
                    aioxmpp.EntityCapsService,
                    aioxmpp.PresenceServer,
                    aioxmpp.PresenceClient,
                ]
            ),
            self.provisioner.get_connected_client(
                services=[
                    aioxmpp.EntityCapsService,
                    aioxmpp.PresenceServer,
                    aioxmpp.PresenceClient,
                ]
            )
        )

    @blocking_timed
    @asyncio.coroutine
    def test_caps_are_sent_with_presence(self):
        caps_server = self.source.summon(aioxmpp.EntityCapsService)
        disco_client = self.sink.summon(aioxmpp.DiscoClient)
        disco_server = self.source.summon(aioxmpp.DiscoServer)

        fut = asyncio.Future()

        def on_available(full_jid, stanza):
            if full_jid != self.source.local_jid:
                return False  # stay connected
            fut.set_result(stanza)
            return True  # disconnect

        self.sink.summon(aioxmpp.PresenceClient).on_available.connect(
            on_available
        )

        presence = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.AVAILABLE,
            to=self.sink.local_jid,
        )
        yield from self.source.stream.send(presence)

        presence = yield from fut

        self.assertIsNotNone(
            presence.xep0115_caps,
        )
        self.assertEqual(
            presence.xep0115_caps.ver,
            caps_server.ver,
        )

        info = yield from disco_client.query_info(
            self.source.local_jid,
            node="{}#{}".format(
                presence.xep0115_caps.node,
                presence.xep0115_caps.ver,
            )
        )
        self.assertSetEqual(
            info.features,
            set(disco_server.iter_features()),
        )
