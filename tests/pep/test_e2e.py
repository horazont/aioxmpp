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
import unittest.mock

import aioxmpp.pep
import aioxmpp.xso as xso
import aioxmpp.pubsub.xso as pubsub_xso

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    TestCase
)

@pubsub_xso.as_payload_class
class ExamplePayload(xso.XSO):
    TAG = ("urn:example:payload", "payload")
    data = xso.Text()

EXAMPLE_TEXT = "Though this be madness, yet there is method in't"

class TestPEP(TestCase):

    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.client = yield from self.provisioner.get_connected_client(
            services=[
                aioxmpp.EntityCapsService,
                aioxmpp.PresenceServer,
                aioxmpp.PubSubClient,
                aioxmpp.pep.PEPClient
            ]
        )

    @blocking_timed
    @asyncio.coroutine
    def test_claim_node_and_get_notification(self):
        done = asyncio.Event()
        def handler(jid, node, item, *, message=None):
            self.assertEqual(jid, self.client.local_jid.bare())
            self.assertEqual(node, "urn:example:payload")
            self.assertEqual(item.payload.data, EXAMPLE_TEXT)
            done.set()

        p = self.client.summon(aioxmpp.pep.PEPClient)
        p.claim_pep_node("urn:example:payload", handler, notify=True)
        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT
        p.publish("urn:example:payload", payload)
        yield from done.wait()
        p.unclaim_pep_node("urn:example:payload")

    # TODO: test the same thing with test_claim_node
