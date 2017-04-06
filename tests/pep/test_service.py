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
import gc
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.disco.xso as disco_xso
import aioxmpp.pep as pep
import aioxmpp.pep.service as pep_service

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
            aioxmpp.PubSubClient: self.pubsub,
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

        with unittest.mock.patch.object(
                self.disco_client, "query_info",
                new=CoroutineMock()) as query_info_mock:
            query_info_mock.return_value = disco_info
            run_coroutine(self.s._check_for_pep())
        query_info_mock.assert_called_once_with(
            TEST_FROM.bare()
        )

    def test_check_for_pep_failure(self):
        with unittest.mock.patch.object(
                self.disco_client, "query_info",
                new=CoroutineMock()) as query_info_mock:
            self.disco_client.query_info.return_value = disco_xso.InfoQuery()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s._check_for_pep())

        query_info_mock.assert_called_once_with(
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
            check_for_pep_mock = stack.enter_context(
                unittest.mock.patch.object(
                    self.s,
                    "_check_for_pep",
                    CoroutineMock(),
                )
            )

            publish_mock = stack.enter_context(
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

        check_for_pep_mock.assert_called_once_with()
        publish_mock.assert_called_once_with(
            None,
            "urn:example",
            unittest.mock.sentinel.data,
            id_="example-id",
        )

    def test_claim_pep_node_twice(self):
        handler1 = unittest.mock.Mock()
        handler2 = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature") as register_feature_mock:
            claim = self.s.claim_pep_node("urn:example")
            claim.on_item_publish.connect(handler1)
            register_feature_mock.assert_called_once_with("urn:example")
            with self.assertRaisesRegex(RuntimeError,
                    "^claiming already claimed node$"):
                claim2 = self.s.claim_pep_node("urn:example")
                claim2.on_item_publish.connect(handler2)
            # register feature mock was not called a second time
            register_feature_mock.assert_called_once()
        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature") as unregister_feature_mock:
            claim.close()
        unregister_feature_mock.assert_called_once_with("urn:example")

    def test_claim_pep_node_handle_event_unclaim_pep_node(self):
        handler = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature") as register_feature_mock:
            claim = self.s.claim_pep_node("urn:example")
            claim.on_item_publish.connect(handler)

        register_feature_mock.assert_called_once_with(
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
                "unregister_feature") as unregister_feature_mock:
            claim.close()

        unregister_feature_mock.assert_called_once_with(
            "urn:example"
        )

        handler.reset_mock()

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
                "register_feature") as register_feature_mock:
            claim = self.s.claim_pep_node("urn:example", notify=True)
            claim.on_item_publish.connect(handler)

        self.assertCountEqual(
            register_feature_mock.mock_calls,
            [unittest.mock.call("urn:example+notify"),
             unittest.mock.call("urn:example")]
        )

        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature") as unregister_feature_mock:
            claim.close()

        self.assertCountEqual(
            unregister_feature_mock.mock_calls,
            [unittest.mock.call("urn:example+notify"),
             unittest.mock.call("urn:example")]
        )

        handler.assert_not_called()

    def test_claim_pep_node_no_feature(self):
        handler = unittest.mock.Mock()
        with unittest.mock.patch.object(
                self.disco_server,
                "register_feature") as register_feature_mock:
            claim = self.s.claim_pep_node("urn:example",
                                          register_feature=False)
            claim.on_item_publish.connect(handler)
        register_feature_mock.assert_not_called()

        with unittest.mock.patch.object(
                self.disco_server,
                "unregister_feature") as unregister_feature_mock:
            claim.close()

        unregister_feature_mock.assert_not_called()
        handler.assert_not_called()

    def test_closed_claim(self):
        claim = self.s.claim_pep_node("urn:example")
        claim.close()

        with self.assertRaises(RuntimeError):
            claim.notify = True

        with self.assertRaises(RuntimeError):
            claim.feature_registered = True

    def test_claim_attributes(self):
        with contextlib.ExitStack() as stack:

            register_feature_mock = stack.enter_context(
                unittest.mock.patch.object(
                    self.disco_server, "register_feature"))

            unregister_feature_mock = stack.enter_context(
                unittest.mock.patch.object(
                    self.disco_server, "unregister_feature"))

            claim = self.s.claim_pep_node("urn:example")
            register_feature_mock.assert_called_once_with("urn:example")
            register_feature_mock.reset_mock()
            self.assertFalse(claim.notify)
            self.assertTrue(claim.feature_registered)
            claim.notify = True
            register_feature_mock.assert_called_once_with("urn:example+notify")
            register_feature_mock.reset_mock()
            self.assertTrue(claim.notify)
            claim.notify = True
            self.assertTrue(claim.notify)
            register_feature_mock.assert_not_called()
            register_feature_mock.reset_mock()
            claim.notify = False
            self.assertFalse(claim.notify)
            unregister_feature_mock.assert_called_once_with(
                "urn:example+notify"
            )
            unregister_feature_mock.reset_mock()
            claim.notify = False
            self.assertFalse(claim.notify)
            unregister_feature_mock.assert_not_called()
            unregister_feature_mock.reset_mock()

            self.assertTrue(claim.feature_registered)
            claim.feature_registered = True
            register_feature_mock.assert_not_called()
            register_feature_mock.reset_mock()
            self.assertTrue(claim.feature_registered)
            claim.feature_registered = False
            self.assertFalse(claim.feature_registered)
            unregister_feature_mock.assert_called_once_with("urn:example")
            unregister_feature_mock.reset_mock()
            claim.feature_registered = False
            self.assertFalse(claim.feature_registered)
            unregister_feature_mock.assert_not_called()
            unregister_feature_mock.reset_mock()
            claim.feature_registered = True
            self.assertTrue(claim.feature_registered)
            register_feature_mock.assert_called_once_with("urn:example")
            register_feature_mock.reset_mock()


    def test_close_is_idempotent(self):
        claim = self.s.claim_pep_node("urn:example")
        claim.close()
        self.assertTrue(claim._closed)

        class Token:
            _closed = True

            def __setattr__(myself, attr, value):
                self.fail("setting attr")

            def __getattr__(myself, attr, value):
                self.fail("getting attr")

        pep_service.RegisteredPEPNode.close(Token())

    def test_is_claimed(self):
        claim = self.s.claim_pep_node("urn:example")
        self.assertTrue(self.s.is_claimed("urn:example"))
        claim.close()
        self.assertFalse(self.s.is_claimed("urn:example"))

    def test_weakref_magic_works(self):
        self.s.claim_pep_node("urn:example")

        # trigger a garbage collection to ensure the pep node weakref
        # is reaped – while this is not necessary on CPython it might
        # be necessary on other implementations
        gc.collect()

        self.assertFalse(self.s.is_claimed("urn:example"))
