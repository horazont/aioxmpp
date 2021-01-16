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
import logging
import unittest.mock

import aioxmpp

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    require_feature,
    TestCase,
)


TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")
TEST_JID3 = aioxmpp.structs.JID.fromstr("quux@bar.example/baz")


class TestBlocking(TestCase):

    @require_feature(namespaces.xep0191)
    def setUp(self, *features):
        pass

    async def make_client(self, run_before=None):
        return await self.provisioner.get_connected_client(
            services=[
                    aioxmpp.DiscoClient,
                    aioxmpp.BlockingClient,
            ],
            prepare=run_before,
        )

    @blocking_timed
    async def test_blocklist(self):

        initial_future = asyncio.Future()
        block_future = asyncio.Future()
        unblock_future = asyncio.Future()
        unblock_all_future = asyncio.Future()

        async def connect_initial_signal(client):
            blocking = client.summon(aioxmpp.BlockingClient)
            blocking.on_initial_blocklist_received.connect(
                initial_future,
                blocking.on_initial_blocklist_received.AUTO_FUTURE
            )

        client = await self.make_client(connect_initial_signal)

        blocking = client.summon(aioxmpp.BlockingClient)
        logging.info("waiting for initial blocklist")
        initial_blocklist = await initial_future
        self.assertEqual(initial_blocklist, frozenset())
        self.assertEqual(blocking.blocklist, frozenset())

        blocking.on_jids_blocked.connect(
            block_future,
            blocking.on_jids_blocked.AUTO_FUTURE
        )
        await blocking.block_jids([TEST_JID1, TEST_JID2, TEST_JID3])
        logging.info("waiting for update on block")
        blocked_jids = await block_future
        self.assertEqual(blocked_jids,
                         frozenset([TEST_JID1, TEST_JID2, TEST_JID3]))
        self.assertEqual(blocking.blocklist,
                         frozenset([TEST_JID1, TEST_JID2, TEST_JID3]))

        blocking.on_jids_unblocked.connect(
            unblock_future,
            blocking.on_jids_unblocked.AUTO_FUTURE
        )
        await blocking.unblock_jids([TEST_JID1])
        logging.info("waiting for update on unblock")
        unblocked_jids = await unblock_future
        self.assertEqual(unblocked_jids,
                         frozenset([TEST_JID1]))
        self.assertEqual(blocking.blocklist,
                         frozenset([TEST_JID2, TEST_JID3]))

        blocking.on_jids_unblocked.connect(
            unblock_all_future,
            blocking.on_jids_unblocked.AUTO_FUTURE
        )
        await blocking.unblock_all()
        logging.info("waiting for update on unblock all")
        unblocked_all_jids = await unblock_all_future
        self.assertEqual(unblocked_all_jids,
                         frozenset([TEST_JID2, TEST_JID3]))
        self.assertEqual(blocking.blocklist,
                         frozenset())
