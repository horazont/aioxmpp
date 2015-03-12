import asyncio
import unittest

import asyncio_xmpp.jid as jid
import asyncio_xmpp.stanza_model as stanza_model
import asyncio_xmpp.stanza as stanza
import asyncio_xmpp.stream_worker as stream_worker
import asyncio_xmpp.errors as errors

from asyncio_xmpp.utils import namespaces

from .testutils import run_coroutine


TEST_FROM = jid.JID.fromstr("foo@example.test/r1")
TEST_TO = jid.JID.fromstr("bar@example.test/r1")

class FancyTestIQ(stanza_model.StanzaObject):
    TAG = ("uri:tests:test_stream_worker.py", "foo")

stanza.IQ.register_child(stanza.IQ.payload, FancyTestIQ)

def make_test_iq(from_=TEST_FROM, to=TEST_TO, type_="get"):
    iq = stanza.IQ(type_=type_, from_=from_, to=to)
    iq.payload = FancyTestIQ()
    return iq

class TestStanzaBroker(unittest.TestCase):
    def setUp(self):
        self.sent_stanzas = asyncio.Queue()
        self.broker = stream_worker.StanzaBroker(self._on_send_stanza)

    def _on_send_stanza(self, obj):
        self.sent_stanzas.put_nowait(obj)

    def test_broker_iq_response(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.broker.register_iq_response_callback(
            TEST_FROM,
            iq.id_,
            fut.set_result)
        self.broker.start()
        self.broker.recv_stanza(iq)

        run_coroutine(fut)

        self.broker.stop()

    def test_queue_stanza(self):
        iq = make_test_iq(type_="get")

        self.broker.start()
        self.broker.enqueue_stanza(iq)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIs(obj, iq)

        self.broker.stop()

    def test_run_iq_request_coro_with_result(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_put, response_got = None, None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal response_put
            response_put = stanza.make_reply(type_="result")
            return response_put

        self.broker.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.broker.start()
        self.broker.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertIs(response_got, response_put)

        self.broker.stop()

    def test_run_iq_request_without_handler(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        self.broker.start()
        self.broker.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            "error",
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "feature-not-implemented"),
            response_got.error.condition
        )

        self.broker.stop()

    def test_run_iq_request_coro_with_generic_exception(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_got = None

        @asyncio.coroutine
        def handle_request(stanza):
            raise Exception("foo")

        self.broker.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.broker.start()
        self.broker.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            "error",
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            response_got.error.condition
        )

        self.broker.stop()

    def test_run_iq_request_coro_with_xmpp_exception(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_got = None

        @asyncio.coroutine
        def handle_request(stanza):
            raise errors.XMPPWaitError(
                condition=(namespaces.stanzas, "gone"),
                text="foobarbaz",
            )

        self.broker.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.broker.start()
        self.broker.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            "error",
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "gone"),
            response_got.error.condition
        )
        self.assertEqual(
            "foobarbaz",
            response_got.error.text
        )

        self.broker.stop()

    def tearDown(self):
        del self.broker
