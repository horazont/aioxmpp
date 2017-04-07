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

    @asyncio.coroutine
    def make_client(self, run_before=None):
        return (yield from self.provisioner.get_connected_client(
            services=[
                    aioxmpp.DiscoClient,
                    aioxmpp.BlockingClient,
            ],
            prepare=run_before,
        ))

    @blocking_timed
    @asyncio.coroutine
    def test_blocklist(self):

        initial_future = asyncio.Future()
        def initial_handler(jids):
            initial_future.set_result(jids)
            return True

        block_future = asyncio.Future()
        def after_block_handler(jids):
            block_future.set_result(jids)
            return True

        unblock_future = asyncio.Future()
        def after_unblock_handler(jids):
            unblock_future.set_result(jids)
            return True

        unblock_all_future = asyncio.Future()
        def after_unblock_all_handler(jids):
            unblock_all_future.set_result(jids)
            return True

        @asyncio.coroutine
        def connect_initial_signal(client):
            blocking = client.summon(aioxmpp.BlockingClient)
            blocking.on_initial_blocklist_received.connect(
                initial_handler
            )

        client = yield from self.make_client(connect_initial_signal)

        blocking = client.summon(aioxmpp.BlockingClient)
        logging.info("waiting for initial blocklist")
        initial_blocklist = yield from initial_future
        self.assertEqual(initial_blocklist, frozenset())
        self.assertEqual(blocking.blocklist, frozenset())

        blocking.on_jids_blocked.connect(after_block_handler)
        yield from blocking.block_jids([TEST_JID1, TEST_JID2, TEST_JID3])
        logging.info("waiting for update on block")
        blocked_jids = yield from block_future
        self.assertEqual(blocked_jids,
                         frozenset([TEST_JID1, TEST_JID2, TEST_JID3]))
        self.assertEqual(blocking.blocklist,
                         frozenset([TEST_JID1, TEST_JID2, TEST_JID3]))

        blocking.on_jids_unblocked.connect(after_unblock_handler)
        yield from blocking.unblock_jids([TEST_JID1])
        logging.info("waiting for update on unblock")
        unblocked_jids = yield from unblock_future
        self.assertEqual(unblocked_jids,
                         frozenset([TEST_JID1]))
        self.assertEqual(blocking.blocklist,
                         frozenset([TEST_JID2, TEST_JID3]))

        blocking.on_jids_unblocked.connect(after_unblock_all_handler)
        yield from blocking.unblock_all()
        logging.info("waiting for update on unblock all")
        unblocked_all_jids = yield from unblock_all_future
        self.assertEqual(unblocked_all_jids,
                         frozenset([TEST_JID2, TEST_JID3]))
        self.assertEqual(blocking.blocklist,
                         frozenset())
