import contextlib
import unittest

import aioxmpp.disco
import aioxmpp.service
import aioxmpp.stanza
import aioxmpp.structs
import aioxmpp.pubsub.service as pubsub_service
import aioxmpp.pubsub.xso as pubsub_xso

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")
TEST_JID3 = aioxmpp.structs.JID.fromstr("fnord@bar.example/baz")
TEST_TO = aioxmpp.structs.JID.fromstr("pubsub.example")


class TestService(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            pubsub_service.Service,
            aioxmpp.service.Service
        ))

    def test_orders_behind_disco(self):
        self.assertGreater(
            pubsub_service.Service,
            aioxmpp.disco.Service
        )

    def setUp(self):
        self.disco = unittest.mock.Mock()
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.cc.query_info = CoroutineMock()
        self.cc.query_info.side_effect = AssertionError
        self.cc.query_items = CoroutineMock()
        self.cc.query_items.side_effect = AssertionError
        self.cc.mock_services[aioxmpp.disco.Service] = self.disco
        self.s = pubsub_service.Service(self.cc)

        self.disco.mock_calls.clear()
        self.cc.mock_calls.clear()

    def tearDown(self):
        del self.s
        del self.cc
        del self.disco

    def test_filter_inbound_message_passes_chat(self):
        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.CHAT
        )
        self.assertIs(
            self.s.filter_inbound_message(msg),
            msg,
        )

    def test_filter_inbound_message_passes_headline(self):
        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.HEADLINE
        )
        self.assertIs(
            self.s.filter_inbound_message(msg),
            msg,
        )

    def test_filter_inbound_message_passes_error(self):
        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.ERROR,
        )
        self.assertIs(
            self.s.filter_inbound_message(msg),
            msg,
        )

    def test_filter_inbound_message_passes_groupchat(self):
        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
        )
        self.assertIs(
            self.s.filter_inbound_message(msg),
            msg,
        )

    def test_filter_inbound_message_passes_normal(self):
        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
        )
        self.assertIs(
            self.s.filter_inbound_message(msg),
            msg,
        )

    def test_filter_inbound_message_publish_emits_events(self):
        item1 = unittest.mock.sentinel.item1
        item2 = unittest.mock.sentinel.item2

        items = [
            pubsub_xso.EventItem(item1, id_="foo"),
            pubsub_xso.EventItem(item2, id_="bar"),
        ]

        ev = pubsub_xso.Event(
            pubsub_xso.EventItems(
                items=items,
                node="some-node",
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
            from_=TEST_TO,
        )
        msg.xep0060_event = ev

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_item_published.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "some-node",
                    item,
                    message=msg,
                )
                for item in items
            ]
        )

    def test_filter_inbound_message_headline_publish_emits_events(self):
        item1 = unittest.mock.sentinel.item1
        item2 = unittest.mock.sentinel.item2

        items = [
            pubsub_xso.EventItem(item1, id_="foo"),
            pubsub_xso.EventItem(item2, id_="bar"),
        ]

        ev = pubsub_xso.Event(
            pubsub_xso.EventItems(
                items=items,
                node="some-node",
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.HEADLINE,
            from_=TEST_TO,
        )
        msg.xep0060_event = ev

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_item_published.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "some-node",
                    item,
                    message=msg,
                )
                for item in items
            ]
        )

    def test_filter_inbound_message_retract_emits_events(self):
        ids = ["foo-id", "bar-id"]

        retracts = [
            pubsub_xso.EventRetract(id_)
            for id_ in ids
        ]

        ev = pubsub_xso.Event(
            pubsub_xso.EventItems(
                retracts=retracts,
                node="some-node",
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
            from_=TEST_TO,
        )
        msg.xep0060_event = ev

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_item_retracted.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "some-node",
                    id_,
                    message=msg,
                )
                for id_ in ids
            ]
        )

    def test_filter_inbound_message_headline_retract_emits_events(self):
        ids = ["foo-id", "bar-id"]

        retracts = [
            pubsub_xso.EventRetract(id_)
            for id_ in ids
        ]

        ev = pubsub_xso.Event(
            pubsub_xso.EventItems(
                retracts=retracts,
                node="some-node",
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.HEADLINE,
            from_=TEST_TO,
        )
        msg.xep0060_event = ev

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_item_retracted.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "some-node",
                    id_,
                    message=msg,
                )
                for id_ in ids
            ]
        )

    def test_filter_inbound_message_affiliation_change_emits_event(self):
        req = pubsub_xso.Request(
            payload=pubsub_xso.Affiliations(
                affiliations=[
                    pubsub_xso.Affiliation(
                        "member",
                        node="foobar",
                    )
                ]
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
            from_=TEST_TO,
        )
        msg.xep0060_request = req

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_affiliation_update.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "foobar",
                    "member",
                    message=msg,
                )
            ]
        )

    def test_filter_inbound_message_subscription_change_emits_event(self):
        req = pubsub_xso.Request(
            payload=pubsub_xso.Subscriptions(
                subscriptions=[
                    pubsub_xso.Subscription(
                        TEST_FROM,
                        node="foobar",
                        subid="some-subid",
                        subscription="subscribed",
                    ),
                    pubsub_xso.Subscription(
                        TEST_FROM,
                        node="baz",
                        subid="some-other-subid",
                        subscription="unconfigured",
                    )
                ]
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
            from_=TEST_TO,
        )
        msg.xep0060_request = req

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_subscription_update.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "foobar",
                    "subscribed",
                    subid="some-subid",
                    message=msg,
                ),
                unittest.mock.call(
                    TEST_TO,
                    "baz",
                    "unconfigured",
                    subid="some-other-subid",
                    message=msg,
                )
            ]
        )

    def test_filter_inbound_message_node_deletion_emits_event(self):
        ev = pubsub_xso.Event(
            payload=pubsub_xso.EventDelete(
                "node",
                redirect_uri="some-uri",
            )
        )

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.NORMAL,
            from_=TEST_TO,
        )
        msg.xep0060_event = ev

        m = unittest.mock.Mock()
        m.return_value = None

        self.s.on_node_deleted.connect(m)

        self.assertIsNone(self.s.filter_inbound_message(msg))

        self.assertSequenceEqual(
            m.mock_calls,
            [
                unittest.mock.call(
                    TEST_TO,
                    "node",
                    redirect_uri="some-uri",
                    message=msg,
                )
            ]
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
        self.s = pubsub_service.Service(self.cc)

        self.cc.stream.service_inbound_message_filter.register.\
            assert_called_with(
                self.s.filter_inbound_message,
                pubsub_service.Service
            )

    def test_subscribe(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Subscription(
            TEST_FROM.bare(),
            node="foo",
            subid="bar",
            subscription="subscribed",
        )
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.s.subscribe(TEST_TO, node="foo"))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Subscribe)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.jid, TEST_FROM.bare())

        self.assertIsNone(request.options)

    def test_subscribe_with_explicit_jid(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Subscription(
            TEST_FROM.replace(resource="fnord"),
            node="foo",
            subid="bar",
            subscription="subscribed",
        )
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.s.subscribe(
            TEST_TO,
            node="foo",
            subscription_jid=TEST_FROM.replace(resource="fnord")
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Subscribe)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.jid,
                         TEST_FROM.replace(resource="fnord"))

        self.assertIsNone(request.options)

    def test_subscribe_with_options(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Subscription(
            TEST_FROM.replace(resource="fnord"),
            node="foo",
            subid="bar",
            subscription="subscribed",
        )
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        data = unittest.mock.Mock()

        run_coroutine(self.s.subscribe(
            TEST_TO,
            node="foo",
            subscription_jid=TEST_FROM.replace(resource="fnord"),
            config=data,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Subscribe)
        self.assertEqual(request.payload.jid,
                         TEST_FROM.replace(resource="fnord"))
        self.assertEqual(request.payload.node, "foo")

        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.jid,
                         TEST_FROM.replace(resource="fnord"))
        self.assertEqual(request.options.node, "foo")
        self.assertIsNone(request.options.subid)
        self.assertIs(request.options.data, data)

    def test_subscribe_returns_full_response(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.subscribe(
            TEST_TO,
            node="foo",
            subscription_jid=TEST_FROM.replace(resource="fnord")
        ))

        self.assertEqual(
            result,
            response
        )

    def test_unsubscribe(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.s.unsubscribe(
            TEST_TO,
            node="foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Unsubscribe)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.jid,
                         TEST_FROM.bare())
        self.assertIsNone(request.payload.subid)

    def test_unsubscribe_with_subscription_jid(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.s.unsubscribe(
            TEST_TO,
            node="foo",
            subscription_jid=TEST_FROM.replace(resource="fnord")
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Unsubscribe)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.jid,
                         TEST_FROM.replace(resource="fnord"))
        self.assertIsNone(request.payload.subid)

    def test_unsubscribe_with_subid(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.s.unsubscribe(
            TEST_TO,
            node="foo",
            subid="bar",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Unsubscribe)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.jid, TEST_FROM.bare())
        self.assertEqual(request.payload.subid, "bar")

    def test_get_subscription_config(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_subscription_config(
            TEST_TO,
            node="foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid, TEST_FROM.bare())
        self.assertIsNone(request.options.subid)

        self.assertEqual(result, response.options.data)

    def test_get_subscription_config_with_subid(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_subscription_config(
            TEST_TO,
            node="foo",
            subid="bar",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid, TEST_FROM.bare())
        self.assertEqual(request.options.subid, "bar")

        self.assertEqual(result, response.options.data)

    def test_get_subscription_config_with_subscription_jid(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_subscription_config(
            TEST_TO,
            node="foo",
            subscription_jid=TEST_FROM.replace(resource="fnord"),
            subid="bar",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid,
                         TEST_FROM.replace(resource="fnord"))
        self.assertEqual(request.options.subid, "bar")

        self.assertEqual(result, response.options.data)

    def test_set_subscription_config(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        data = unittest.mock.Mock()

        run_coroutine(self.s.set_subscription_config(
            TEST_TO,
            data,
            node="foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid, TEST_FROM.bare())
        self.assertIsNone(request.options.subid)
        self.assertIs(request.options.data, data)

    def test_set_subscription_config_with_subid(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        data = unittest.mock.Mock()

        run_coroutine(self.s.set_subscription_config(
            TEST_TO,
            data,
            node="foo",
            subid="bar"
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid, TEST_FROM.bare())
        self.assertEqual(request.options.subid, "bar")
        self.assertIs(request.options.data, data)

    def test_set_subscription_config_with_subscription_jid_and_subid(self):
        response = pubsub_xso.Request()
        response.options = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        data = unittest.mock.Mock()

        run_coroutine(self.s.set_subscription_config(
            TEST_TO,
            data,
            node="foo",
            subid="bar",
            subscription_jid=TEST_FROM.replace(resource="fnord"),
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsNone(request.payload)
        self.assertIsInstance(request.options, pubsub_xso.Options)
        self.assertEqual(request.options.node, "foo")
        self.assertEqual(request.options.jid,
                         TEST_FROM.replace(resource="fnord"))
        self.assertEqual(request.options.subid, "bar")
        self.assertIs(request.options.data, data)

    def test_get_default_config(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_default_config(
            TEST_TO,
            node="foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Default)
        self.assertEqual(request.payload.node, "foo")

        self.assertEqual(result, response.payload.data)

    def test_get_items(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_items(
            TEST_TO,
            node="foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Items)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsNone(request.payload.max_items)

        self.assertEqual(result, response)

    def test_get_items_max_items(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_items(
            TEST_TO,
            node="foo",
            max_items=2,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Items)
        self.assertEqual(request.payload.node, "foo")
        self.assertEqual(request.payload.max_items, 2)

        self.assertEqual(result, response)

    def test_get_items_by_id(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        ids = [
            "abc",
            "def",
            "ghi",
        ]

        result = run_coroutine(self.s.get_items_by_id(
            TEST_TO,
            node="foo",
            ids=ids,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        request_iq, = call[1]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Items)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsNone(request.payload.max_items)

        self.assertEqual(len(ids), len(request.payload.items))
        for item, id_ in zip(request.payload.items, ids):
            self.assertIsInstance(item, pubsub_xso.Item, id_)
            self.assertEqual(item.id_, id_, id_)
            self.assertFalse(item.registered_payload)
            self.assertFalse(item.unregistered_payload)

        self.assertEqual(result, response)

    def test_get_items_by_id_rejects_empty_iterable(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        ids = []

        with self.assertRaisesRegex(ValueError, "ids must not be empty"):
            run_coroutine(self.s.get_items_by_id(
                TEST_TO,
                node="foo",
                ids=ids,
            ))

        self.assertEqual(
            0,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

    def test_get_subscriptions(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_subscriptions(
            TEST_TO,
            "node",
        ))

        self.assertEqual(result, response.payload)

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Subscriptions)
        self.assertEqual(request.payload.node, "node")

    def test_get_subscriptions_node_defaults_to_None(self):
        response = pubsub_xso.Request()
        response.payload = unittest.mock.Mock()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.get_subscriptions(
            TEST_TO,
        ))

        self.assertEqual(result, response.payload)

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Subscriptions)
        self.assertIsNone(request.payload.node)

    def test_publish_with_id(self):
        payload = unittest.mock.sentinel.payload

        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Publish()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.publish(
            TEST_TO,
            "foo",
            payload,
            id_="some-id",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Publish)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsInstance(request.payload.item, pubsub_xso.Item)

        item = request.payload.item
        self.assertIs(item.registered_payload, payload)
        self.assertEqual(item.id_, "some-id")

        self.assertEqual(result, "some-id")

    def test_publish_with_returned_id(self):
        payload = unittest.mock.sentinel.payload

        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Publish()
        response.payload.item = pubsub_xso.Item()
        response.payload.item.id_ = "some-other-id"

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.publish(
            TEST_TO,
            "foo",
            payload,
            id_="some-id",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Publish)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsInstance(request.payload.item, pubsub_xso.Item)

        item = request.payload.item
        self.assertIs(item.registered_payload, payload)
        self.assertEqual(item.id_, "some-id")

        self.assertEqual(result, "some-other-id")

    def test_publish_without_given_id_and_with_returned_id(self):
        payload = unittest.mock.sentinel.payload

        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Publish()
        response.payload.item = pubsub_xso.Item()
        response.payload.item.id_ = "generated-id"

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.publish(
            TEST_TO,
            "foo",
            payload,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Publish)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsInstance(request.payload.item, pubsub_xso.Item)

        item = request.payload.item
        self.assertIs(item.registered_payload, payload)
        self.assertIsNone(item.id_)

        self.assertEqual(result, "generated-id")

    def test_publish_without_payload(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Publish()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.publish(
            TEST_TO,
            "foo",
            None,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Publish)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsNone(request.payload.item)

        self.assertIsNone(result)

    def test_notify_uses_publish_with_None_payload(self):
        with contextlib.ExitStack() as stack:
            publish = stack.enter_context(
                unittest.mock.patch.object(
                    self.s,
                    "publish",
                    new=CoroutineMock()
                )
            )

            publish.return_value = None

            run_coroutine(
                self.s.notify(
                    unittest.mock.sentinel.jid,
                    unittest.mock.sentinel.node,
                )
            )

        publish.assert_called_with(
            unittest.mock.sentinel.jid,
            unittest.mock.sentinel.node,
            None,
        )

    def test_retract(self):
        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(self.s.retract(
            TEST_TO,
            "foo",
            "some-id",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Retract)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsInstance(request.payload.item, pubsub_xso.Item)
        self.assertFalse(request.payload.notify)

        item = request.payload.item
        self.assertIs(item.id_, "some-id")

    def test_retract_with_notify(self):
        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(self.s.retract(
            TEST_TO,
            "foo",
            "some-id",
            notify=True,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Retract)
        self.assertEqual(request.payload.node, "foo")
        self.assertIsInstance(request.payload.item, pubsub_xso.Item)
        self.assertTrue(request.payload.notify)

        item = request.payload.item
        self.assertIs(item.id_, "some-id")

    def test_get_features_uses_disco(self):
        response = aioxmpp.disco.xso.InfoQuery()
        response.features.update({
            "some-non-feature",
            pubsub_xso.Feature.GET_PENDING.value,
            pubsub_xso.Feature.ACCESS_AUTHORIZE.value,
        })

        self.disco.query_info = CoroutineMock()
        self.disco.query_info.return_value = response

        result = run_coroutine(
            self.s.get_features(TEST_TO),
        )

        self.assertSetEqual(
            result,
            {
                pubsub_xso.Feature.GET_PENDING,
                pubsub_xso.Feature.ACCESS_AUTHORIZE,
            }
        )

    def test_create_with_node(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Create()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.create(
            TEST_TO,
            "foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Create)
        self.assertEqual(request.payload.node, "foo")

        self.assertEqual(result, "foo")

    def test_create_with_node_copes_with_empty_reply(self):
        response = None

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.create(
            TEST_TO,
            "foo",
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Create)
        self.assertEqual(request.payload.node, "foo")

        self.assertEqual(result, "foo")

    def test_create_instant_node(self):
        response = pubsub_xso.Request()
        response.payload = pubsub_xso.Create()
        response.payload.node = "autogen-id"

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(self.s.create(
            TEST_TO,
        ))

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.Request)

        request = request_iq.payload
        self.assertIsInstance(request.payload, pubsub_xso.Create)
        self.assertIsNone(request.payload.node)

        self.assertEqual(result, "autogen-id")

    def test_get_nodes_uses_disco(self):
        response = aioxmpp.disco.xso.ItemsQuery()
        response.items[:] = [
            aioxmpp.disco.xso.Item(
                TEST_TO,
                node="foo",
                name="foo name",
            ),
            aioxmpp.disco.xso.Item(
                TEST_TO,
                node="bar",
            ),
            aioxmpp.disco.xso.Item(
                TEST_TO.replace(localpart="xyz"),
                node="fnord",
                name="fnord name",
            ),
        ]

        self.disco.query_items = CoroutineMock()
        self.disco.query_items.return_value = response

        result = run_coroutine(
            self.s.get_nodes(TEST_TO),
        )

        self.assertSequenceEqual(
            result,
            [
                ("foo", "foo name"),
                ("bar", None),
            ]
        )

    def test_delete_without_redirect_uri(self):
        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(
            self.s.delete(TEST_TO, "node"),
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        payload = request_iq.payload.payload
        self.assertIsInstance(payload, pubsub_xso.OwnerDelete)
        self.assertEqual(payload.node, "node")
        self.assertIsNone(payload.redirect_uri)

    def test_delete_with_redirect_uri(self):
        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(
            self.s.delete(TEST_TO, "node", redirect_uri="fnord"),
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        payload = request_iq.payload.payload
        self.assertIsInstance(payload, pubsub_xso.OwnerDelete)
        self.assertEqual(payload.node, "node")
        self.assertEqual(payload.redirect_uri, "fnord")

    def test_get_node_affiliations(self):
        response = pubsub_xso.OwnerRequest(
            pubsub_xso.OwnerAffiliations(node="fnord")
        )

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(
            self.s.get_node_affiliations(TEST_TO, "node"),
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        self.assertIsInstance(request_iq.payload.payload,
                              pubsub_xso.OwnerAffiliations)
        self.assertEqual(request_iq.payload.payload.node,
                         "node")

        self.assertIs(result, response)

    def test_get_node_subscriptions(self):
        response = pubsub_xso.OwnerRequest(
            pubsub_xso.OwnerSubscriptions(node="fnord")
        )

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(
            self.s.get_node_subscriptions(TEST_TO, "node"),
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.GET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        self.assertIsInstance(request_iq.payload.payload,
                              pubsub_xso.OwnerSubscriptions)
        self.assertEqual(request_iq.payload.payload.node,
                         "node")

        self.assertIs(result, response)

    def test_change_node_affiliations(self):
        affiliations_to_set = [
            (TEST_JID1, "owner"),
            (TEST_JID2, "outcast"),
            (TEST_JID3, "none"),
        ]

        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(
            self.s.change_node_affiliations(
                TEST_TO,
                "node",
                affiliations_to_set,
            )
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        payload = request_iq.payload.payload
        self.assertIsInstance(payload, pubsub_xso.OwnerAffiliations)
        self.assertEqual(payload.node, "node")

        self.assertSequenceEqual(
            affiliations_to_set,
            [
                (item.jid, item.affiliation)
                for item in payload.affiliations
            ]
        )

    def test_change_node_subscriptions(self):
        subscriptions_to_set = [
            (TEST_JID1, "subscribed"),
            (TEST_JID2, "unconfigured"),
            (TEST_JID3, "none"),
        ]

        self.cc.stream.send_iq_and_wait_for_reply.return_value = None

        run_coroutine(
            self.s.change_node_subscriptions(
                TEST_TO,
                "node",
                subscriptions_to_set,
            )
        )

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        _, (request_iq, ), _ = \
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO)
        self.assertIsInstance(request_iq.payload, pubsub_xso.OwnerRequest)

        payload = request_iq.payload.payload
        self.assertIsInstance(payload, pubsub_xso.OwnerSubscriptions)
        self.assertEqual(payload.node, "node")

        self.assertSequenceEqual(
            subscriptions_to_set,
            [
                (item.jid, item.subscription)
                for item in payload.subscriptions
            ]
        )


# foo
