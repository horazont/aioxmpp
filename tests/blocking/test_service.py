########################################################################
# File name: test_service.py
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
import contextlib
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.service as service
import aioxmpp.disco.xso as disco_xso
import aioxmpp.blocking as blocking
import aioxmpp.blocking.xso as blocking_xso

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")
TEST_JID3 = aioxmpp.structs.JID.fromstr("quux@bar.example/baz")


class TestBlockingClient(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco = aioxmpp.DiscoClient(self.cc)
        self.s = blocking.BlockingClient(
            self.cc,
            dependencies={
                aioxmpp.DiscoClient: self.disco,
            }
        )

    def tearDown(self):
        del self.cc
        del self.disco
        del self.s

    def test_is_service(self):
        self.assertTrue(issubclass(
            blocking.BlockingClient,
            aioxmpp.service.Service
        ))

    def test_service_order(self):
        self.assertGreater(
            blocking.BlockingClient,
            aioxmpp.DiscoClient
        )

    def test_handle_stream_destroyed_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.stream.StanzaStream,
            "on_stream_destroyed",
            self.s.handle_stream_destroyed
        ))

    def test_check_for_blocking(self):
        disco_info = disco_xso.InfoQuery()
        disco_info.features.add(namespaces.xep0191)

        with unittest.mock.patch.object(self.disco, "query_info",
                                        new=CoroutineMock()):
            self.disco.query_info.return_value = disco_info

            run_coroutine(self.s._check_for_blocking())

            self.disco.query_info.assert_called_with(
                TEST_FROM.replace(localpart=None, resource=None)
            )

    def test_check_for_blocking_failure(self):
        disco_info = disco_xso.InfoQuery()
        with unittest.mock.patch.object(self.disco, "query_info",
                                        new=CoroutineMock()):
            self.disco.query_info.return_value = disco_info

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s._check_for_blocking())

            self.disco.query_info.assert_called_with(
                TEST_FROM.replace(localpart=None, resource=None)
            )

    def test_get_initial_blocklist(self):

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            handle_initial_blocklist_mock = unittest.mock.Mock()
            self.s.on_initial_blocklist_received.connect(
                handle_initial_blocklist_mock
            )

            BLOCKLIST = [TEST_JID1, TEST_JID2]
            blocklist = blocking_xso.BlockList()
            blocklist.items[:] = BLOCKLIST
            self.cc.stream.send.return_value = blocklist

            run_coroutine(self.s._get_initial_blocklist())

            self.assertCountEqual(
                self.s._blocklist,
                BLOCKLIST
            )

            self.assertEqual(len(self.cc.stream.send.mock_calls), 1)
            (_, (arg,), _), = self.cc.stream.send.mock_calls
            self.assertIsInstance(arg, aioxmpp.IQ)
            self.assertEqual(arg.type_, aioxmpp.IQType.GET)
            self.assertIsInstance(arg.payload, blocking_xso.BlockList)
            self.assertEqual(
                len(arg.payload.items),
                0
            )

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(
                handle_initial_blocklist_mock.mock_calls,
                [
                    unittest.mock.call(
                        frozenset(BLOCKLIST)
                    )
                ]
            )

    def test_block_jids(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            run_coroutine(self.s.block_jids([TEST_JID1]))

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

            self.assertEqual(len(self.cc.stream.send.mock_calls), 1)
            (_, (arg,), _), = self.cc.stream.send.mock_calls

            self.assertIsInstance(arg, aioxmpp.IQ)
            self.assertEqual(arg.type_, aioxmpp.IQType.SET)
            self.assertIsInstance(arg.payload, blocking_xso.BlockCommand)
            self.assertCountEqual(
                arg.payload.items,
                frozenset([TEST_JID1]),
            )

    def test_block_jids_ignore_empty(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            run_coroutine(self.s.block_jids([]))

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(self.cc.stream.send.mock_calls, [])

    def test_unblock_jids(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            run_coroutine(self.s.unblock_jids([TEST_JID2]))

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

            self.assertEqual(len(self.cc.stream.send.mock_calls), 1)
            (_, (arg,), _), = self.cc.stream.send.mock_calls

            self.assertIsInstance(arg, aioxmpp.IQ)
            self.assertEqual(arg.type_, aioxmpp.IQType.SET)
            self.assertIsInstance(arg.payload, blocking_xso.UnblockCommand)
            self.assertCountEqual(
                arg.payload.items,
                frozenset([TEST_JID2]),
            )

    def test_unblock_jids_ignore_empty(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            run_coroutine(self.s.unblock_jids([]))

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(self.cc.stream.send.mock_calls, [])

    def test_unblock_all(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s, "_check_for_blocking",
                    new=CoroutineMock()
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.cc.stream, "send",
                    new=CoroutineMock()
                )
            )

            run_coroutine(self.s.unblock_all())

            self.assertSequenceEqual(
                self.s._check_for_blocking.mock_calls,
                [unittest.mock.call()]
            )

    def test_handle_block_push_is_iq_handler(self):
        service.is_iq_handler(aioxmpp.IQType.SET,
                              blocking_xso.BlockCommand,
                              self.s.handle_block_push)

    def test_handle_block_push(self):
        handle_block = unittest.mock.Mock()
        handle_unblock = unittest.mock.Mock()

        self.s.on_jids_blocked.connect(
            handle_block
        )

        self.s.on_jids_unblocked.connect(
            handle_unblock
        )

        self.s._blocklist = frozenset([TEST_JID1])

        block = blocking_xso.BlockCommand()
        block.items[:] = [TEST_JID2]
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=block,
        )

        run_coroutine(self.s.handle_block_push(iq))

        self.assertEqual(
            self.s._blocklist,
            frozenset([TEST_JID1, TEST_JID2])
        )

        self.assertEqual(
            handle_block.mock_calls,
            [
                unittest.mock.call(
                    frozenset([TEST_JID2])
                )
            ]
        )

        handle_unblock.assert_not_called()

    def test_handle_unblock_push_is_iq_handler(self):
        service.is_iq_handler(aioxmpp.IQType.SET,
                              blocking_xso.UnblockCommand,
                              self.s.handle_unblock_push)

    def test_handle_unblock_push(self):
        handle_block = unittest.mock.Mock()
        handle_unblock = unittest.mock.Mock()

        self.s.on_jids_blocked.connect(
            handle_block
        )

        self.s.on_jids_unblocked.connect(
            handle_unblock
        )

        self.s._blocklist = frozenset([TEST_JID1, TEST_JID2])

        block = blocking_xso.UnblockCommand()
        block.items[:] = [TEST_JID2]
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=block,
        )

        run_coroutine(self.s.handle_unblock_push(iq))

        self.assertEqual(
            self.s._blocklist,
            frozenset([TEST_JID1])
        )

        self.assertEqual(
            handle_unblock.mock_calls,
            [
                unittest.mock.call(
                    frozenset([TEST_JID2])
                )
            ]
        )

        handle_block.assert_not_called()

    def test_handle_unblock_push_all(self):
        handle_block = unittest.mock.Mock()
        handle_unblock = unittest.mock.Mock()

        self.s.on_jids_blocked.connect(
            handle_block
        )

        self.s.on_jids_unblocked.connect(
            handle_unblock
        )

        self.s._blocklist = frozenset([TEST_JID1, TEST_JID2])

        block = blocking_xso.UnblockCommand()
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=block,
        )

        run_coroutine(self.s.handle_unblock_push(iq))

        self.assertEqual(
            handle_unblock.mock_calls,
            [
                unittest.mock.call(
                    frozenset([TEST_JID1, TEST_JID2])
                )
            ]
        )

        handle_block.assert_not_called()
