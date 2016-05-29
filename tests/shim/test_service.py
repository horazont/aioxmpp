import unittest

import aioxmpp.disco
import aioxmpp.shim.service as shim_service

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")


class TestService(unittest.TestCase):
    def setUp(self):
        self.disco = unittest.mock.Mock()
        self.node = unittest.mock.Mock()
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.cc.query_info = CoroutineMock()
        self.cc.query_info.side_effect = AssertionError
        self.cc.query_items = CoroutineMock()
        self.cc.query_items.side_effect = AssertionError
        self.cc.mock_services[aioxmpp.disco.Service] = self.disco

        with unittest.mock.patch("aioxmpp.disco.StaticNode") as Node:
            Node.return_value = self.node
            self.s = shim_service.Service(self.cc)

        self.disco.mock_calls.clear()
        self.cc.mock_calls.clear()

    def tearDown(self):
        del self.s
        del self.cc
        del self.disco

    def test_orders_before_disco_service(self):
        self.assertLess(
            aioxmpp.disco.Service,
            shim_service.Service,
        )

    def test_init(self):
        self.disco = unittest.mock.Mock()
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.cc.query_info = CoroutineMock()
        self.cc.query_info.side_effect = AssertionError
        self.cc.query_items = CoroutineMock()
        self.cc.query_items.side_effect = AssertionError
        self.cc.mock_services[aioxmpp.disco.Service] = self.disco

        with unittest.mock.patch("aioxmpp.disco.StaticNode") as Node:
            self.s = shim_service.Service(self.cc)

        self.disco.register_feature.assert_called_with(
            "http://jabber.org/protocol/shim"
        )

        self.disco.mount_node.assert_called_with(
            "http://jabber.org/protocol/shim",
            Node()
        )

    def test_shutdown(self):
        run_coroutine(self.s.shutdown())
        self.disco.unregister_feature.assert_called_with(
            "http://jabber.org/protocol/shim"
        )

        self.disco.unmount_node.assert_called_with(
            "http://jabber.org/protocol/shim",
        )

    def test_register_header(self):
        self.s.register_header(
            "Foo"
        )

        self.node.register_feature.assert_called_with(
            "http://jabber.org/protocol/shim#Foo"
        )

    def test_unregister_header(self):
        self.s.unregister_header(
            "Foo"
        )

        self.node.unregister_feature.assert_called_with(
            "http://jabber.org/protocol/shim#Foo"
        )
