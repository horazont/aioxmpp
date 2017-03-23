import unittest
import unittest.mock

import aioxmpp
import aioxmpp.service
import aioxmpp.stream

import aioxmpp.dispatcher as dispatcher

from aioxmpp.testutils import (
    make_connected_client,
)


TEST_JID = aioxmpp.JID.fromstr("foo@bar.example/baz")
TEST_LOCAL_JID = aioxmpp.JID.fromstr("foo@local.example")


class FooStanza:
    def __init__(self, from_, type_):
        self.from_ = from_
        self.type_ = type_


class FooDispatcher(dispatcher.SimpleStanzaDispatcher):
    @property
    def local_jid(self):
        return TEST_LOCAL_JID


class TestSimpleStanzaDispatcher(unittest.TestCase):
    def setUp(self):
        self.d = FooDispatcher()

        self.handlers = unittest.mock.Mock()

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            self.handlers.type_fulljid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            self.handlers.type_barejid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            self.handlers.type_barejid_wildcard,
            wildcard_resource=True,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            self.handlers.type_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID,
            self.handlers.wildcard_fulljid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID.bare(),
            self.handlers.wildcard_barejid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID.bare(),
            self.handlers.wildcard_barejid_wildcard,
            wildcard_resource=True,
        )

        self.d.register_callback(
            None,
            None,
            self.handlers.wildcard_wildcard,
            wildcard_resource=False,
        )

    def tearDown(self):
        del self.d

    def test_register_callback_rejects_dups(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                TEST_JID,
                unittest.mock.sentinel.cb2,
            )

    def test_register_callback_flattens_wildcard_resource_for_fulljid(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                TEST_JID,
                unittest.mock.sentinel.cb,
            )

    def test_register_callback_flattens_wildcard_resource_for_None(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                None,
                unittest.mock.sentinel.cb,
            )

    def test_register_callback_honors_wildcard_resource_for_bare(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=True,
        )

    def test_unregister_removes_callback(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            wildcard_resource=False,
        )

        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

    def test_unregister_flattens_wildcard_resource_for_fulljid(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False,
        )

        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=True,
        )

    def test_unregister_flattens_wildcard_resource_for_None(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            None,
            wildcard_resource=False,
        )

        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            None,
            wildcard_resource=True,
        )

    def test_unregister_raises_KeyError_if_unregistered(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=True,
        )

        with self.assertRaises(KeyError):
            d.unregister_callback(
                unittest.mock.sentinel.type_,
                TEST_JID.bare(),
                wildcard_resource=False,
            )

    def test_dispatch_converts_None_to_local_jid(self):
        self.d.register_callback(
            unittest.mock.sentinel.footype,
            TEST_LOCAL_JID,
            self.handlers.local,
        )

        stanza = FooStanza(None, unittest.mock.sentinel.footype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.local(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid(self):
        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_fulljid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid_via_wildcard_to_bare(self):
        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_barejid_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid_via_wildcard_to_none(self):
        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False
        )

        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            wildcard_resource=True,
        )

        self.d.unregister_callback(
            None,
            TEST_JID.bare(),
            wildcard_resource=True,
        )

        self.d.unregister_callback(
            None,
            TEST_JID,
            wildcard_resource=False,
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_full_wildcard(self):
        stanza = FooStanza(TEST_JID.replace(localpart="fnord"),
                           unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_barejid_no_wildcard(self):
        stanza = FooStanza(TEST_JID.bare(), unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_barejid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_mistype_fulljid(self):
        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_fulljid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_mistype_fulljid_wildcard(self):
        self.d.unregister_callback(
            None,
            TEST_JID,
            wildcard_resource=False,
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_barejid_wildcard(stanza),
            ]
        )

    def test_does_not_connect_to_on_message_received(self):
        self.assertFalse(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_message_received",
                self.d._feed,
            )
        )

    def test_does_not_connect_to_on_presence_received(self):
        self.assertFalse(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_presence_received",
                self.d._feed,
            )
        )


class TestSimpleMessageDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.d = dispatcher.SimpleMessageDispatcher(self.cc)

    def tearDown(self):
        del self.d
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            dispatcher.SimpleMessageDispatcher,
            aioxmpp.service.Service,
        ))

    def test_is_SimpleStanzaDispatcher(self):
        self.assertTrue(issubclass(
            dispatcher.SimpleMessageDispatcher,
            dispatcher.SimpleStanzaDispatcher,
        ))

    def test_local_jid_uses_local_jid_from_client(self):
        self.assertEqual(
            self.d.local_jid,
            self.cc.local_jid,
        )

    def test_connects_to_on_message_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_message_received",
                self.d._feed,
            )
        )


class TestSimplePresenceDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.d = dispatcher.SimplePresenceDispatcher(self.cc)

    def tearDown(self):
        del self.d
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            dispatcher.SimplePresenceDispatcher,
            aioxmpp.service.Service,
        ))

    def test_is_SimpleStanzaDispatcher(self):
        self.assertTrue(issubclass(
            dispatcher.SimplePresenceDispatcher,
            dispatcher.SimpleStanzaDispatcher,
        ))

    def test_local_jid_uses_local_jid_from_client(self):
        self.assertEqual(
            self.d.local_jid,
            self.cc.local_jid,
        )

    def test_connects_to_on_presence_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_presence_received",
                self.d._feed,
            )
        )
