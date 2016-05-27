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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "get")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        payload = unittest.mock.sentinel.payload

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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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
        self.assertEqual(request_iq.type_, "set")
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


# foo
