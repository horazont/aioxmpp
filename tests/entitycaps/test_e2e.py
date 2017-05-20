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
import base64

import aioxmpp.stream
import aioxmpp.entitycaps as caps
import aioxmpp.disco as disco

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

        self.assertIsNotNone(
            presence.xep0390_caps,
        )
        self.assertTrue(presence.xep0390_caps.digests)

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

        for algo, digest in presence.xep0390_caps.digests.items():
            info = yield from disco_client.query_info(
                self.source.local_jid,
                node="urn:xmpp:caps#{}.{}".format(
                    algo,
                    base64.b64encode(digest).decode("ascii")
                )
            )
            self.assertSetEqual(
                info.features,
                set(disco_server.iter_features()),
                (algo, digest)
            )

    @blocking_timed
    @asyncio.coroutine
    def test_caps115_are_cached(self):
        info = disco.xso.InfoQuery()
        info.features.add("http://feature.test/feature")
        info.features.add("http://feature.test/another-feature")

        info_hash = caps.caps115.hash_query(info, "sha1")

        disco_iq = None
        disco_called_again = False

        @asyncio.coroutine
        def fake_disco_handler(iq):
            nonlocal disco_called_again, disco_iq
            if disco_iq is None:
                disco_iq = iq
            else:
                disco_called_again = True
            return info

        self.source, self.sink = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[
                    aioxmpp.PresenceServer,
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

        self.source.stream.register_iq_request_coro(
            aioxmpp.IQType.GET,
            disco.xso.InfoQuery,
            fake_disco_handler,
        )

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
        presence.xep0115_caps = caps.xso.Caps115(
            "http://test",
            info_hash,
            "sha-1",
        )

        yield from self.source.stream.send(presence)

        yield from fut

        disco_client = self.sink.summon(aioxmpp.DiscoClient)

        info_direct = yield from disco_client.query_info(
            self.source.local_jid,
        )
        self.assertEqual(info_direct.features, info.features)

        self.assertIsNotNone(disco_iq)

        self.assertEqual(
            disco_iq.payload.node,
            "http://test#{}".format(info_hash)
        )

        self.assertFalse(disco_called_again)

    @blocking_timed
    @asyncio.coroutine
    def test_caps390_are_cached(self):
        info = disco.xso.InfoQuery()
        info.features.add("http://feature.test/feature")
        info.features.add("http://feature.test/another-feature")

        info_hash = caps.caps390._calculate_hash(
            "sha-256",
            caps.caps390._get_hash_input(info)
        )
        info_hash_b64 = base64.b64encode(info_hash).decode("ascii")

        disco_iq = None
        disco_called_again = False

        @asyncio.coroutine
        def fake_disco_handler(iq):
            nonlocal disco_called_again, disco_iq
            if disco_iq is None:
                disco_iq = iq
            else:
                disco_called_again = True
            return info

        self.source, self.sink = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[
                    aioxmpp.PresenceServer,
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

        self.source.stream.register_iq_request_coro(
            aioxmpp.IQType.GET,
            disco.xso.InfoQuery,
            fake_disco_handler,
        )

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
        presence.xep0390_caps = caps.xso.Caps390()
        presence.xep0390_caps.digests["sha-256"] = info_hash

        yield from self.source.stream.send(presence)

        yield from fut

        disco_client = self.sink.summon(aioxmpp.DiscoClient)

        info_direct = yield from disco_client.query_info(
            self.source.local_jid,
        )
        self.assertEqual(info_direct.features, info.features)

        self.assertIsNotNone(disco_iq)

        self.assertEqual(
            disco_iq.payload.node,
            "urn:xmpp:caps#sha-256.{}".format(info_hash_b64)
        )

        self.assertFalse(disco_called_again)
