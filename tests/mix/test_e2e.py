import uuid

import aioxmpp
import aioxmpp.mix
import aioxmpp.mix.xso.pam0

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    TestCase,
    require_feature,
    blocking,
)


class TestMIX(TestCase):
    @require_feature(namespaces.xep0369_mix_core_0, argname="mix_service")
    @blocking
    async def setUp(self, mix_service):
        services = [
            aioxmpp.mix.MIXClient,
            aioxmpp.DiscoClient,
        ]

        self.firstwitch = await self.provisioner.get_connected_client(
            services=services,
        )
        self.firstmix = self.firstwitch.summon(aioxmpp.mix.MIXClient)
        self.test_channel = mix_service.replace(
            localpart=str(uuid.uuid4())
        )

    @blocking
    async def test_create_join_leave(self):
        await self.firstmix.create(self.test_channel)
        await self.firstmix.join(self.test_channel, [aioxmpp.mix.Node.MESSAGES])
        await self.firstmix.leave(self.test_channel)
