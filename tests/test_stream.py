import asyncio
import unittest

import aioxmpp.jid as jid
import aioxmpp.stanza_model as stanza_model
import aioxmpp.stanza as stanza
import aioxmpp.stream as stream
import aioxmpp.stream_elements as stream_elements
import aioxmpp.errors as errors

from datetime import datetime, timedelta

from aioxmpp.utils import namespaces
from aioxmpp.plugins import xep0199

from .testutils import run_coroutine


TEST_FROM = jid.JID.fromstr("foo@example.test/r1")
TEST_TO = jid.JID.fromstr("bar@example.test/r1")

class FancyTestIQ(stanza_model.StanzaObject):
    TAG = ("uri:tests:test_stream.py", "foo")

stanza.IQ.register_child(stanza.IQ.payload, FancyTestIQ)


def make_test_iq(from_=TEST_FROM, to=TEST_TO, type_="get"):
    iq = stanza.IQ(type_=type_, from_=from_, to=to)
    iq.payload = FancyTestIQ()
    return iq


def make_test_message(from_=TEST_FROM, to=TEST_TO, type_="chat"):
    msg = stanza.Message(type_=type_, from_=from_, to=to)
    return msg


def make_test_presence(from_=TEST_FROM, to=TEST_TO, type_=None):
    pres = stanza.Presence(type_=type_, from_=from_, to=to)
    return pres


class StanzaStreamTestBase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.sent_stanzas = asyncio.Queue()
        self.xmlstream = unittest.mock.MagicMock()
        self.xmlstream.send_stanza = self._on_send_stanza
        self.xmlstream.stanza_parser = unittest.mock.MagicMock()
        self.stream = stream.StanzaStream(loop=self.loop)

    def _on_send_stanza(self, obj):
        self.sent_stanzas.put_nowait(obj)

    def tearDown(self):
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        assert not self.stream.running()
        del self.stream
        del self.xmlstream
        del self.sent_stanzas

class TestStanzaStream(StanzaStreamTestBase):
    def test_init(self):
        self.assertEqual(
            timedelta(seconds=15),
            self.stream.ping_interval
        )
        self.assertEqual(
            timedelta(seconds=15),
            self.stream.ping_opportunistic_interval
        )

    def test_broker_iq_response(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_callback(
            TEST_FROM,
            iq.id_,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(iq, fut.result())

    def test_queue_stanza(self):
        iq = make_test_iq(type_="get")

        self.stream.start(self.xmlstream)
        self.stream.enqueue_stanza(iq)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIs(obj, iq)

        self.stream.stop()

    def test_start_stop(self):
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.stream.recv_stanza),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.stream.recv_stanza),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.stream.recv_stanza),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )
        self.xmlstream.stanza_parser.mock_calls.clear()

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.remove_class(stanza.IQ),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

    def test_run_iq_request_coro_with_result(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_put, response_got = None, None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal response_put
            response_put = stanza.make_reply(type_="result")
            return response_put

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertIs(response_got, response_put)

        self.stream.stop()

    def test_run_iq_request_without_handler(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            "error",
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "feature-not-implemented"),
            response_got.error.condition
        )

        self.stream.stop()

    def test_run_iq_request_coro_with_generic_exception(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_got = None

        @asyncio.coroutine
        def handle_request(stanza):
            raise Exception("foo")

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            "error",
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            response_got.error.condition
        )

        self.stream.stop()

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

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

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

        self.stream.stop()

    def test_run_message_callback(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.stream.register_message_callback(
            "chat",
            TEST_FROM,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    def test_run_message_callback_from_wildcard(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.stream.register_message_callback(
            "chat",
            None,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    def test_run_message_callback_full_wildcard(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.stream.register_message_callback(
            None,
            None,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    def test_run_presence_callback_from_wildcard(self):
        pres = make_test_presence()

        fut = asyncio.Future()

        self.stream.register_presence_callback(
            None,  # note that None is a valid type value for presence
            None,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(pres)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(pres, fut.result())

    def test_rescue_unprocessed_incoming_stanza_on_stop(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.stream.recv_stanza(pres)
        self.stream.stop()

        self.assertIs(
            pres,
            run_coroutine(self.stream._incoming_queue.get())
        )

    def test_rescue_unprocessed_outgoing_stanza_on_stop(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.stream.enqueue_stanza(pres)
        self.stream.stop()

        self.assertIs(
            pres,
            run_coroutine(self.stream._active_queue.get()).stanza
        )

    def test_unprocessed_incoming_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.stream.stop()

        self.stream.recv_stanza(pres)

        self.assertIs(
            pres,
            run_coroutine(self.stream._incoming_queue.get())
        )

    def test_unprocessed_outgoing_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.stream.stop()

        self.stream.enqueue_stanza(pres)

        self.assertIs(
            pres,
            run_coroutine(self.stream._active_queue.get()).stanza
        )

    def test_fail_on_unknown_stanza_class(self):
        caught_exc = None
        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.on_failure = failure_handler

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(object())

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.stream.running())
        self.assertIsInstance(
            caught_exc,
            RuntimeError
        )


    def test_stopping_after_unassigning_stanza_sender_induces_clean_shutdown(self):
        caught_exc = None
        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        iq = make_test_iq()
        self.stream.on_failure = failure_handler

        self.stream.start(self.xmlstream)
        self.stream.enqueue_stanza(iq)

        iq_sent = run_coroutine(self.sent_stanzas.get())
        self.assertIs(iq, iq_sent)

        self.stream.on_send_stanza = None
        self.stream.enqueue_stanza(iq)
        self.stream.recv_stanza(iq)
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_send_bulk(self):
        state_change_handler = unittest.mock.MagicMock()
        iqs = [make_test_iq() for i in range(3)]

        def send_handler(stanza_obj):
            # we send a cancel right when the stanza is enqueued for
            # sending.
            # by that, we ensure that the broker does not yield and sends
            # multiple stanzas if it can, optimizing the opportunistic send
            self.stream.stop()
            self._on_send_stanza(stanza_obj)

        self.xmlstream.send_stanza = send_handler

        tokens = [
            self.stream.enqueue_stanza(
                iq,
                on_state_change=state_change_handler)
            for iq in iqs
        ]

        self.stream.start(self.xmlstream)

        for iq in iqs:
            self.assertIs(
                iq,
                run_coroutine(self.sent_stanzas.get()),
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call(token, stream.StanzaState.SENT_WITHOUT_SM)
                for token in tokens
            ],
            state_change_handler.mock_calls
        )


    def test_running(self):
        self.assertFalse(self.stream.running())
        self.stream.start(self.xmlstream)
        self.assertTrue(self.stream.running())
        self.stream.stop()
        # the task does not immediately terminate, it requires one cycle through
        # the event loop to do so
        self.assertTrue(self.stream.running())
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running())

    def test_forbid_starting_twice(self):
        self.stream.start(self.xmlstream)
        with self.assertRaises(RuntimeError):
            self.stream.start(self.xmlstream)

    def test_allow_stopping_twice(self):
        self.stream.start(self.xmlstream)
        self.stream.stop()
        self.stream.stop()

    def test_sm_initialization_only_in_stopped_state(self):
        self.stream.start(self.xmlstream)
        with self.assertRaises(RuntimeError):
            self.stream.start_sm()

    def test_start_sm(self):
        self.assertFalse(self.stream.sm_enabled)
        self.stream.start_sm()
        self.assertTrue(self.stream.sm_enabled)

        self.assertEqual(
            0,
            self.stream.sm_outbound_base
        )
        self.assertEqual(
            0,
            self.stream.sm_inbound_ctr
        )
        self.assertSequenceEqual(
            [],
            self.stream.sm_unacked_list
        )

        self.stream.start(self.xmlstream)
        self.assertSequenceEqual(
            [
                unittest.mock.call.add_class(stream_elements.SMAcknowledgement,
                                             self.stream.recv_stanza),
                unittest.mock.call.add_class(stream_elements.SMRequest,
                                             self.stream.recv_stanza),
            ],
            self.xmlstream.stanza_parser.mock_calls[-2:]
        )
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(
                    stream_elements.SMRequest),
                unittest.mock.call.remove_class(
                    stream_elements.SMAcknowledgement),
            ],
            self.xmlstream.stanza_parser.mock_calls[-2:]
        )

    def test_sm_ack_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError, "is not enabled"):
            self.stream.sm_ack(0)

    def test_sm_outbound(self):
        state_change_handler = unittest.mock.MagicMock()
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start_sm()
        self.stream.start(self.xmlstream)

        tokens = [
            self.stream.enqueue_stanza(
                iq, on_state_change=state_change_handler)
            for iq in iqs]

        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            0,
            self.stream.sm_outbound_base
        )
        self.assertSequenceEqual(
            tokens,
            self.stream.sm_unacked_list
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call(token, stream.StanzaState.SENT)
                for token in tokens
            ],
            state_change_handler.mock_calls
        )
        del state_change_handler.mock_calls[:]
        self.assertSequenceEqual(
            [stream.StanzaState.SENT]*3,
            [token.state for token in tokens]
        )

        self.stream.sm_ack(1)
        self.assertEqual(
            1,
            self.stream.sm_outbound_base
        )
        self.assertSequenceEqual(
            tokens[1:],
            self.stream.sm_unacked_list
        )
        self.assertSequenceEqual(
            [
                stream.StanzaState.ACKED,
                stream.StanzaState.SENT,
                stream.StanzaState.SENT
            ],
            [token.state for token in tokens]
        )

        # idempotence with same number

        self.stream.sm_ack(1)
        self.assertEqual(
            1,
            self.stream.sm_outbound_base
        )
        self.assertSequenceEqual(
            tokens[1:],
            self.stream.sm_unacked_list
        )
        self.assertSequenceEqual(
            [
                stream.StanzaState.ACKED,
                stream.StanzaState.SENT,
                stream.StanzaState.SENT
            ],
            [token.state for token in tokens]
        )

        self.stream.sm_ack(3)
        self.assertEqual(
            3,
            self.stream.sm_outbound_base
        )
        self.assertSequenceEqual(
            [],
            self.stream.sm_unacked_list
        )
        self.assertSequenceEqual(
            [
                stream.StanzaState.ACKED,
                stream.StanzaState.ACKED,
                stream.StanzaState.ACKED
            ],
            [token.state for token in tokens]
        )

    def test_sm_inbound(self):
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start_sm()
        self.stream.start(self.xmlstream)

        self.stream.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            1,
            self.stream.sm_inbound_ctr
        )

        self.stream.recv_stanza(iqs.pop())
        self.stream.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            3,
            self.stream.sm_inbound_ctr
        )

    def test_sm_resume(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        for iq in iqs:
            self.stream.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))

        self.stream.sm_ack(1)
        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        # enqueue a stanza before resumption and check that the sequence is
        # correct (resumption-generated stanzas before new stanzas)
        self.stream.enqueue_stanza(additional_iq)

        self.stream.resume_sm(2)
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        for iq in iqs:
            self.assertIs(
                iq,
                self.sent_stanzas.get_nowait()
            )
        self.assertIsInstance(
            self.sent_stanzas.get_nowait(),
            stream_elements.SMRequest
        )
        for iq in iqs[2:] + [additional_iq]:
            self.assertIs(
                iq,
                self.sent_stanzas.get_nowait()
            )
        self.assertIsInstance(
            self.sent_stanzas.get_nowait(),
            stream_elements.SMRequest
        )

    def test_stop_sm(self):
        self.stream.start_sm()
        self.stream.stop_sm()

        self.assertFalse(self.stream.sm_enabled)
        self.assertFalse(hasattr(self.stream, "sm_outbound_base"))
        self.assertFalse(hasattr(self.stream, "sm_inbound_ctr"))
        self.assertFalse(hasattr(self.stream, "sm_unacked_list"))

    def test_sm_ping_automatic(self):
        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)
        self.stream.start_sm()
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.005))
        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()
        run_coroutine(asyncio.sleep(0.009))
        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()
        run_coroutine(asyncio.sleep(0.005))

        request = self.sent_stanzas.get_nowait()
        self.assertIsInstance(request, stream_elements.SMRequest)

    def test_sm_ping_opportunistic(self):
        # sm ping is always opportunistic: it also allows the server to ACK our
        # stanzas, which is great.

        self.stream.start_sm()
        self.stream.start(self.xmlstream)

        iq = make_test_iq()
        self.stream.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))
        self.assertIs(
            iq,
            self.sent_stanzas.get_nowait()
        )
        self.assertIsInstance(
            self.sent_stanzas.get_nowait(),
            stream_elements.SMRequest
        )

    def test_sm_ping_timeout(self):
        exc = None
        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.on_failure = failure_handler

        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.enqueue_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0.005))
        self.stream.enqueue_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0.006))
        # at this point, the first ping must have timed out, and failure should
        # be reported
        self.assertIsInstance(
            exc,
            ConnectionError
        )

    def test_sm_ping_ack(self):
        exc = None
        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.on_failure = failure_handler

        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.enqueue_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0.005))
        self.stream.enqueue_stanza(make_test_iq())
        ack = stream_elements.SMAcknowledgement()
        ack.counter = 1
        self.stream.recv_stanza(ack)
        run_coroutine(asyncio.sleep(0.006))
        self.assertIsNone(exc)
        self.assertEqual(
            1,
            self.stream.sm_outbound_base
        )

    def test_sm_handle_req(self):
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.recv_stanza(stream_elements.SMRequest())
        run_coroutine(asyncio.sleep(0))
        response = self.sent_stanzas.get_nowait()
        self.assertIsInstance(
            response,
            stream_elements.SMAcknowledgement
        )
        self.assertEqual(
            response.counter,
            self.stream.sm_inbound_ctr
        )

        # no opportunistic send after SMAck
        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_nonsm_ping(self):
        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0.02))

        request = self.sent_stanzas.get_nowait()
        self.assertIsInstance(
            request,
            stanza.IQ)
        self.assertIsInstance(
            request.payload,
            xep0199.Ping)
        self.assertEqual(
            "get",
            request.type_)

    def test_nonsm_ping_timeout(self):
        exc = None
        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)
        self.stream.on_failure = failure_handler

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0.02))

        request = self.sent_stanzas.get_nowait()
        run_coroutine(asyncio.sleep(0.011))

        self.assertIsInstance(
            exc,
            ConnectionError
        )

    def test_nonsm_ping_pong(self):
        exc = None
        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)
        self.stream.on_failure = failure_handler

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0.02))

        request = self.sent_stanzas.get_nowait()
        response = request.make_reply(type_="result")
        self.stream.recv_stanza(response)
        run_coroutine(asyncio.sleep(0.011))

        self.assertIsNone(exc)

    def test_enqueue_stanza_returns_token(self):
        token = self.stream.enqueue_stanza(make_test_iq())
        self.assertIsInstance(
            token,
            stream.StanzaToken)

    def test_set_stanzas_to_sent_without_sm_when_sm_is_turned_off(self):
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        tokens = [self.stream.enqueue_stanza(iq) for iq in iqs]
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()
        self.stream.stop_sm()

        self.assertSequenceEqual(
            [
                stream.StanzaState.SENT_WITHOUT_SM,
                stream.StanzaState.SENT_WITHOUT_SM,
                stream.StanzaState.SENT_WITHOUT_SM,
            ],
            [token.state for token in tokens]
        )

    def test_abort_stanza(self):
        iqs = [make_test_iq() for i in range(3)]
        self.stream.start(self.xmlstream)
        tokens = [self.stream.enqueue_stanza(iq) for iq in iqs]
        tokens[1].abort()
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                stream.StanzaState.SENT_WITHOUT_SM,
                stream.StanzaState.ABORTED,
                stream.StanzaState.SENT_WITHOUT_SM,
            ],
            [token.state for token in tokens]
        )

        for iq in iqs[:1] + iqs[2:]:
            self.assertIs(
                iq,
                self.sent_stanzas.get_nowait()
            )
        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()


class TestStanzaToken(unittest.TestCase):
    def test_init(self):
        stanza = make_test_iq()
        token = stream.StanzaToken(stanza)
        self.assertIs(
            stanza,
            token.stanza
        )
        self.assertEqual(
            stream.StanzaState.ACTIVE,
            token.state
        )

    def test_state_not_writable(self):
        stanza = make_test_iq()
        token = stream.StanzaToken(stanza)
        with self.assertRaises(AttributeError):
            token.state = stream.StanzaState.ACKED

    def test_state_change_callback(self):
        state_change_handler = unittest.mock.MagicMock()

        stanza = make_test_iq()
        token = stream.StanzaToken(stanza,
                                   on_state_change=state_change_handler)

        states = [
            stream.StanzaState.SENT,
            stream.StanzaState.ACKED,
            stream.StanzaState.SENT_WITHOUT_SM,
            stream.StanzaState.ACTIVE,
            stream.StanzaState.ABORTED,
        ]

        for state in states:
            token._set_state(state)
            self.assertEqual(
                state,
                token.state
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call(token, state)
                for state in states
            ],
            state_change_handler.mock_calls
        )

    def test_abort_while_active(self):
        stanza = make_test_iq()
        token = stream.StanzaToken(stanza)
        token.abort()
        self.assertEqual(
            stream.StanzaState.ABORTED,
            token.state
        )

    def test_abort_while_sent(self):
        stanza = make_test_iq()
        token = stream.StanzaToken(stanza)
        for state in set(stream.StanzaState) - {stream.StanzaState.ACTIVE,
                                                stream.StanzaState.ABORTED}:
            token._set_state(stream.StanzaState.SENT)
            with self.assertRaisesRegexp(RuntimeError, "already sent"):
                token.abort()

    def test_abort_while_aborted(self):
        stanza = make_test_iq()
        token = stream.StanzaToken(stanza)
        token.abort()
        token.abort()
