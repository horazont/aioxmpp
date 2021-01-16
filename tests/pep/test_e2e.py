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

import aioxmpp.pep
import aioxmpp.xso as xso
import aioxmpp.pubsub.xso as pubsub_xso

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    require_pep,
    TestCase
)


@pubsub_xso.as_payload_class
class ExamplePayload(xso.XSO):
    TAG = ("urn:example:payload", "payload")
    data = xso.Text()


EXAMPLE_TEXT = "Though this be madness, yet there is method in't"


class TestPEP(TestCase):
    @require_pep
    @blocking
    async def setUp(self):
        self.client = await self.provisioner.get_connected_client(
            services=[
                aioxmpp.PresenceServer,
                aioxmpp.pep.PEPClient
            ]
        )
        self._pep = self.client.summon(aioxmpp.pep.PEPClient)
        self._pubsub = self.client.summon(aioxmpp.PubSubClient)

    async def _require_pep_features(self, features):
        pep_features = await self._pubsub.get_features(
            self.client.local_jid.bare()
        )

        if features & pep_features != features:
            raise unittest.SkipTest("missing required PEP features: {}".format(
                features - pep_features
            ))

    @blocking_timed
    async def test_claim_node_and_get_notification(self):
        done = asyncio.Future()

        def handler(jid, node, item, *, message=None):
            done.set_result((jid, node, item))

        presence = self.client.summon(aioxmpp.PresenceServer)
        claim = self._pep.claim_pep_node("urn:example:payload", notify=True)
        claim.on_item_publish.connect(handler)
        # this is necessary, otherwise the +notify feature will not be
        # sent to the server.
        await presence.resend_presence()
        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT
        await self._pep.publish("urn:example:payload", payload)
        jid, node, item = await done
        self.assertEqual(jid, self.client.local_jid.bare())
        self.assertEqual(node, "urn:example:payload")
        self.assertEqual(item.registered_payload.data, EXAMPLE_TEXT)
        claim.close()

    @blocking_timed
    async def test_publish_with_whitelist_access_model(self):
        await self._require_pep_features({
            aioxmpp.pubsub.xso.Feature.PUBLISH_OPTIONS
        })

        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT

        await self._pep.publish("urn:example:payload", payload,
                                access_model="whitelist")

        config_form_raw = await self._pubsub.get_node_config(
            self.client.local_jid.bare(),
            node="urn:example:payload",
        )

        config_form = pubsub_xso.NodeConfigForm.from_xso(config_form_raw)
        self.assertEqual(config_form.access_model.value, "whitelist")

    @blocking_timed
    async def test_publish_passes_with_subsequent_equal_access_models(self):
        await self._require_pep_features({
            aioxmpp.pubsub.xso.Feature.PUBLISH_OPTIONS
        })

        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT

        await self._pep.publish("urn:example:payload", payload,
                                access_model="whitelist")

        await self._pep.publish("urn:example:payload", payload,
                                access_model="whitelist")

    @blocking_timed
    async def test_publish_fails_with_subsequent_conflicting_access_models(self):
        await self._require_pep_features({
            aioxmpp.pubsub.xso.Feature.PUBLISH_OPTIONS
        })

        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT

        await self._pep.publish("urn:example:payload", payload,
                                access_model="whitelist")

        with self.assertRaises(aioxmpp.errors.XMPPError) as exc:
            await self._pep.publish("urn:example:payload", payload,
                                    access_model="presence")

        self.assertEqual(
            exc.exception.condition,
            aioxmpp.errors.ErrorCondition.CONFLICT,
        )


class ExampleService(aioxmpp.service.Service):
    ORDER_AFTER = [aioxmpp.pep.PEPClient]

    payload = aioxmpp.pep.register_pep_node("urn:example:payload", notify=True)

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

    def register_handler(self, handler):
        self.payload.on_item_publish.connect(handler)


class Test_register_pep_node_Descriptor(TestCase):

    @require_pep
    @blocking
    async def setUp(self):
        self.client = await self.provisioner.get_connected_client(
            services=[
                aioxmpp.PresenceServer,
                aioxmpp.pep.PEPClient,
                ExampleService,
            ]
        )

    @blocking_timed
    async def test_get_notification(self):
        done = asyncio.Future()

        def handler(jid, node, item, *, message=None):
            done.set_result((jid, node, item))

        example = self.client.summon(ExampleService)
        example.register_handler(handler)
        p = self.client.summon(aioxmpp.pep.PEPClient)
        payload = ExamplePayload()
        payload.data = EXAMPLE_TEXT
        await p.publish("urn:example:payload", payload)
        jid, node, item = await done
        self.assertEqual(jid, self.client.local_jid.bare())
        self.assertEqual(node, "urn:example:payload")
        self.assertEqual(item.registered_payload.data, EXAMPLE_TEXT)
