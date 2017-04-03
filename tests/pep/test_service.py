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
import aioxmpp.disco.xso as disco_xso
import aioxmpp.pep as pep

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")


class TestPEPClient(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco_client = aioxmpp.DiscoClient(self.cc)
        self.disco_server = aioxmpp.DiscoServer(self.cc)
        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client
        })

        self.s = pep.PEPClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client,
            aioxmpp.DiscoServer: self.disco_server,
            aioxmpp.PubSubClient: self.pubsub
        })

    def tearDown(self):
        del self.cc
        del self.disco_client
        del self.disco_server
        del self.pubsub
        del self.s

    def test_is_service(self):
        self.assertTrue(issubclass(pep.PEPClient, aioxmpp.service.Service))

    def test_check_for_pep(self):
        disco_info = disco_xso.InfoQuery()
        disco_info.identities.append(
            disco_xso.Identity(type_="pep", category="pubsub")
        )

        with unittest.mock.patch.object(self.disco_client, "query_info",
                                        new=CoroutineMock()):
            self.disco_client.query_info.return_value = disco_info
            run_coroutine(self.s._check_for_pep())
            self.disco_client.query_info.assert_called_once_with(
                TEST_FROM.bare()
            )

    def test_check_for_pep_failure(self):

        with unittest.mock.patch.object(self.disco_client, "query_info",
                                        new=CoroutineMock()):
            self.disco_client.query_info.return_value = disco_xso.InfoQuery()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s._check_for_pep())

            self.disco_client.query_info.assert_called_once_with(
                TEST_FROM.bare()
            )

    def test_handle_pubsub_publish_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.PubSubClient,
            "on_item_published",
            self.s._handle_pubsub_publish
        ))

    def test_publish(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.s,
                    "_check_for_pep",
                    CoroutineMock(),
                )
            )

            stack.enter_context(
                unittest.mock.patch.object(
                    self.pubsub,
                    "publish",
                    CoroutineMock(),
                )
            )

            run_coroutine(self.s.publish(
                "urn:example",
                unittest.mock.sentinel.data,
                id_="example-id",
            ))

            self.s._check_for_pep.assert_called_once_with()
            self.pubsub.publish.assert_called_once_with(
                None,
                "urn:example",
                unittest.mock.sentinel.data,
                id_="example-id",
            )

    def test_subscribe(self):
        with unittest.mock.patch.object(self.pubsub,
                                        "subscribe",
                                        CoroutineMock()):
            run_coroutine(self.s.subscribe(TEST_JID1, "urn:example"))
            self.pubsub.subscribe.assert_called_once_with(
                TEST_JID1,
                "urn:example"
            )

    def test_claim_pep_node_handle_event_unclaim_pep_node(self):
        handler = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature"):
            self.s.claim_pep_node("urn:example", handler)

            self.disco_server.register_feature.assert_called_once_with(
                "urn:example"
            )

        self.s._handle_pubsub_publish(
            TEST_JID1,
            "urn:example",
            unittest.mock.sentinel.payload,
            message=None
        )

        handler.assert_called_once_with(
            TEST_JID1,
            "urn:example",
            unittest.mock.sentinel.payload,
            message=None
        )

        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature"):
            self.s.unclaim_pep_node("urn:example")

            self.disco_server.unregister_feature.assert_called_once_with(
                "urn:example"
            )

        handler.mock_calls.clear()

        self.s._handle_pubsub_publish(
            TEST_JID1,
            "urn:example",
            unittest.mock.sentinel.payload,
            message=None
        )

        handler.assert_not_called()

    def test_claim_pep_node_with_notify(self):
        handler = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature"):
            self.s.claim_pep_node("urn:example", handler, notify=True)

            self.assertCountEqual(
                self.disco_server.register_feature.mock_calls,
                [unittest.mock.call("urn:example+notify"),
                 unittest.mock.call("urn:example")]
            )

        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature"):
            self.s.unclaim_pep_node("urn:example")

            self.assertCountEqual(
                self.disco_server.unregister_feature.mock_calls,
                [unittest.mock.call("urn:example+notify"),
                 unittest.mock.call("urn:example")]
            )

        handler.assert_not_called()

    def test_claim_pep_node_no_feature(self):
        handler = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature"):
            self.s.claim_pep_node("urn:example", handler,
                                  register_feature=False)
            self.disco_server.register_feature.assert_not_called()

        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature"):
            self.s.unclaim_pep_node("urn:example")
            self.disco_server.unregister_feature.assert_not_called()

        handler.assert_not_called()
