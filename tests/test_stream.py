import asyncio
import time
import unittest

import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.stanza as stanza
import aioxmpp.stream as stream
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.errors as errors
import aioxmpp.callbacks as callbacks

from datetime import timedelta

from aioxmpp.utils import namespaces
from aioxmpp.plugins import xep0199

from .testutils import run_coroutine


TEST_FROM = structs.JID.fromstr("foo@example.test/r1")
TEST_TO = structs.JID.fromstr("bar@example.test/r1")


class FancyTestIQ(xso.XSO):
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


def make_mocked_streams(loop):
    def _on_send_xso(obj):
        nonlocal sent_stanzas
        sent_stanzas.put_nowait(obj)

    sent_stanzas = asyncio.Queue()
    xmlstream = unittest.mock.MagicMock()
    xmlstream.send_xso = _on_send_xso
    xmlstream.stanza_parser = unittest.mock.MagicMock()
    xmlstream.on_failure = callbacks.AdHocSignal()
    stanzastream = stream.StanzaStream(loop=loop)

    return sent_stanzas, xmlstream, stanzastream


class StanzaStreamTestBase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.sent_stanzas, self.xmlstream, self.stream = \
            make_mocked_streams(self.loop)

    def tearDown(self):
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        assert not self.stream.running
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

    def test_broker_iq_response_to_future(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_future(
            TEST_FROM,
            iq.id_,
            fut)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(iq, fut.result())

    def test_broker_iq_response_to_future_with_error(self):
        iq = make_test_iq(type_="error")
        iq.autoset_id()
        iq.payload = None
        iq.error = stanza.Error(
            type_="modify",
            condition=(namespaces.stanzas, "bad-request"),
        )

        fut = asyncio.Future()

        self.stream.register_iq_response_future(
            TEST_FROM,
            iq.id_,
            fut)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        with self.assertRaises(errors.XMPPModifyError) as cm:
            run_coroutine(fut)
        self.assertEqual(
            (namespaces.stanzas, "bad-request"),
            cm.exception.condition
        )

        self.stream.stop()

    def test_ignore_unexpected_iq_result(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        iq = make_test_iq(type_="error")
        iq.autoset_id()
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_ignore_unexpected_message(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        msg = make_test_message()
        msg.autoset_id()
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_ignore_unexpected_presence(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        pres = make_test_presence()
        pres.autoset_id()
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(pres)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

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

        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(object())

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.stream.running)
        self.assertIsInstance(
            caught_exc,
            RuntimeError
        )

    def test_induces_clean_shutdown_and_no_call_to_transport(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        iq = make_test_iq()
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        self.stream.enqueue_stanza(iq)

        iq_sent = run_coroutine(self.sent_stanzas.get())
        self.assertIs(iq, iq_sent)

        self.xmlstream.send_xso = unittest.mock.MagicMock(
            side_effect=RuntimeError())
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
            self.sent_stanzas.put_nowait(stanza_obj)

        self.xmlstream.send_xso = send_handler

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
        self.assertFalse(self.stream.running)
        self.stream.start(self.xmlstream)
        self.assertTrue(self.stream.running)
        self.stream.stop()
        # the task does not immediately terminate, it requires one cycle
        # through the event loop to do so
        self.assertTrue(self.stream.running)
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

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
                unittest.mock.call.add_class(stream_xsos.SMAcknowledgement,
                                             self.stream.recv_stanza),
                unittest.mock.call.add_class(stream_xsos.SMRequest,
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
                    stream_xsos.SMRequest),
                unittest.mock.call.remove_class(
                    stream_xsos.SMAcknowledgement),
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
            stream_xsos.SMRequest
        )
        for iq in iqs[2:] + [additional_iq]:
            self.assertIs(
                iq,
                self.sent_stanzas.get_nowait()
            )
        self.assertIsInstance(
            self.sent_stanzas.get_nowait(),
            stream_xsos.SMRequest
        )

    def test_sm_resume_requires_stopped_stream(self):
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        with self.assertRaises(RuntimeError):
            self.stream.resume_sm(0)

    def test_sm_stop_requires_stopped_stream(self):
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        with self.assertRaisesRegexp(RuntimeError,
                                     "is running"):
            self.stream.stop_sm()

    def test_sm_stop_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     "not enabled"):
            self.stream.stop_sm()

    def test_sm_start_requires_disabled_sm(self):
        self.stream.start_sm()
        with self.assertRaisesRegexp(RuntimeError,
                                     "Stream Management already enabled"):
            self.stream.start_sm()

    def test_sm_resume_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     "Stream Management is not enabled"):
            self.stream.resume_sm(0)

    def test_stop_sm(self):
        self.stream.start_sm()
        self.stream.stop_sm()

        self.assertFalse(self.stream.sm_enabled)
        with self.assertRaises(RuntimeError):
            self.stream.sm_outbound_base
        with self.assertRaises(RuntimeError):
            self.stream.sm_inbound_ctr
        with self.assertRaises(RuntimeError):
            self.stream.sm_unacked_list

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
        self.assertIsInstance(request, stream_xsos.SMRequest)

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
            stream_xsos.SMRequest
        )

    def test_sm_ping_timeout(self):
        exc = None

        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.on_failure.connect(failure_handler)

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
        self.stream.on_failure.connect(failure_handler)

        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.enqueue_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0.005))
        self.stream.enqueue_stanza(make_test_iq())
        ack = stream_xsos.SMAcknowledgement()
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
        self.stream.recv_stanza(stream_xsos.SMRequest())
        run_coroutine(asyncio.sleep(0))
        response = self.sent_stanzas.get_nowait()
        self.assertIsInstance(
            response,
            stream_xsos.SMAcknowledgement
        )
        self.assertEqual(
            response.counter,
            self.stream.sm_inbound_ctr
        )

        # no opportunistic send after SMAck
        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_sm_unacked_list_is_a_copy(self):
        self.stream.start_sm()
        l1 = self.stream.sm_unacked_list
        l2 = self.stream.sm_unacked_list
        self.assertIsNot(l1, l2)
        l1.append("foo")
        self.assertFalse(self.stream.sm_unacked_list)

    def test_sm_ignore_late_remote_counter(self):
        self.stream.start_sm()
        self.stream.sm_ack(-1)

    def test_nonsm_ignore_sm_ack(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(stream_xsos.SMAcknowledgement())
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_nonsm_ignore_sm_req(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(stream_xsos.SMRequest())
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

        self.assertIsNone(caught_exc)

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
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0.02))

        self.sent_stanzas.get_nowait()
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
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0.02))

        request = self.sent_stanzas.get_nowait()
        response = request.make_reply(type_="result")
        self.stream.recv_stanza(response)
        run_coroutine(asyncio.sleep(0.011))

        self.assertIsNone(exc)

    def test_nonsm_ping_send_delayed(self):
        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)

        self.stream.start(self.xmlstream)
        time.sleep(0.02)
        run_coroutine(asyncio.sleep(0))

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
        run_coroutine(asyncio.sleep(0))
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

    def test_send_iq_and_wait_for_reply(self):
        iq = make_test_iq()
        response = iq.make_reply(type_="result")

        task = asyncio.async(
            self.stream.send_iq_and_wait_for_reply(iq),
            loop=self.loop)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.recv_stanza(response)
        result = run_coroutine(task)
        self.assertIs(
            response,
            result
        )

    def test_send_iq_and_wait_for_reply_timeout(self):
        iq = make_test_iq()

        task = asyncio.async(
            self.stream.send_iq_and_wait_for_reply(
                iq,
                timeout=0.01),
            loop=self.loop)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))

        @asyncio.coroutine
        def test_task():
            with self.assertRaises(asyncio.TimeoutError):
                yield from task

        run_coroutine(test_task())

    def test_flush_incoming(self):
        iqs = [make_test_iq(type_="result") for i in range(2)]
        futs = []

        for iq in iqs:
            fut = asyncio.Future()
            iq.autoset_id()
            self.stream.register_iq_response_future(
                iq.from_,
                iq.id_,
                fut)
            futs.append(fut)
            self.stream.recv_stanza(iq)

        self.stream.flush_incoming()

        run_coroutine(asyncio.sleep(0))
        for iq, fut in zip(iqs, futs):
            self.assertTrue(fut.done())
            self.assertIs(iq, fut.result())

    def test_fail_when_xmlstream_fails(self):
        exc = ConnectionError()
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.xmlstream.on_failure(exc)
        run_coroutine(asyncio.sleep(0))
        self.assertIs(caught_exc, exc)
        self.assertFalse(self.stream.running)

    def test_transactional_start_prepares_and_rolls_back_on_exception(self):
        with self.assertRaises(ValueError):
            with self.stream.transactional_start(self.xmlstream) as ctx:
                self.assertSequenceEqual(
                    [
                        unittest.mock.call.add_class(
                            stanza.IQ,
                            ctx._recv_stanza),
                        unittest.mock.call.add_class(
                            stanza.Message,
                            ctx._recv_stanza),
                        unittest.mock.call.add_class(
                            stanza.Presence,
                            ctx._recv_stanza),
                    ],
                    self.xmlstream.stanza_parser.mock_calls
                )
                self.xmlstream.stanza_parser.reset_mock()
                raise ValueError()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.remove_class(stanza.IQ),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

        self.assertFalse(self.stream.running)

    def test_transactional_start_rollback_drops_received_stanzas(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_future(
            TEST_FROM,
            iq.id_,
            fut)

        with self.assertRaises(ValueError):
            with self.stream.transactional_start(self.xmlstream) as ctx:
                ctx._recv_stanza(iq)
                raise ValueError()

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(fut.done())

    def test_transactional_start_commit_leaves_stream_running_and_has_stanzas(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_future(
            TEST_FROM,
            iq.id_,
            fut)

        with self.stream.transactional_start(self.xmlstream) as ctx:
            ctx._recv_stanza(iq)
            self.xmlstream.stanza_parser.reset_mock()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.IQ),
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.stream.recv_stanza),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

        self.assertTrue(self.stream.running)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(fut.done())

    def test_transactional_start_blocks_start_and_transactional_start(self):
        with self.stream.transactional_start(self.xmlstream) as ctx:
            with self.assertRaisesRegexp(RuntimeError,
                                         "in progress"):
                self.stream.start(self.xmlstream)
            with self.assertRaisesRegexp(RuntimeError,
                                         "in progress"):
                self.stream.transactional_start(self.xmlstream)

    def test_forbid_transactional_start_while_running(self):
        self.stream.start(self.xmlstream)
        self.assertTrue(self.stream.running)
        with self.assertRaisesRegexp(RuntimeError, "already started"):
            self.stream.transactional_start(self.xmlstream)

    def test_transactional_start_jit_sm_start(self):
        with self.stream.transactional_start(self.xmlstream) as ctx:
            self.xmlstream.stanza_parser.reset_mock()
            ctx.start_sm()
            self.assertSequenceEqual(
                [
                    unittest.mock.call.add_class(
                        stream_xsos.SMAcknowledgement,
                        ctx._recv_stanza),
                    unittest.mock.call.add_class(
                        stream_xsos.SMRequest,
                        ctx._recv_stanza)
                ],
                self.xmlstream.stanza_parser.mock_calls
            )
            self.xmlstream.stanza_parser.reset_mock()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.IQ),
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(
                    stream_xsos.SMAcknowledgement),
                unittest.mock.call.add_class(
                    stream_xsos.SMAcknowledgement,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stream_xsos.SMRequest),
                unittest.mock.call.add_class(
                    stream_xsos.SMRequest,
                    self.stream.recv_stanza)
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

        self.assertTrue(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)

    def test_transactional_start_blocks_start_sm(self):
        with self.stream.transactional_start(self.xmlstream) as ctx:
            with self.assertRaisesRegexp(RuntimeError,
                                         "during startup"):
                self.stream.start_sm()

    def test_transactional_start_blocks_resume_sm(self):
        self.stream.start_sm()
        with self.stream.transactional_start(self.xmlstream) as ctx:
            with self.assertRaisesRegexp(RuntimeError,
                                         "during startup"):
                self.stream.resume_sm(0)

    def test_transactional_start_blocks_stop_sm(self):
        self.stream.start_sm()
        with self.stream.transactional_start(self.xmlstream) as ctx:
            with self.assertRaisesRegexp(RuntimeError,
                                         "during startup"):
                self.stream.stop_sm()

    def test_transactional_start_jit_sm_stop(self):
        self.stream.start_sm()
        with self.stream.transactional_start(self.xmlstream) as ctx:
            self.assertSequenceEqual(
                [
                    unittest.mock.call.add_class(
                        stanza.IQ,
                        ctx._recv_stanza),
                    unittest.mock.call.add_class(
                        stanza.Message,
                        ctx._recv_stanza),
                    unittest.mock.call.add_class(
                        stanza.Presence,
                        ctx._recv_stanza),
                    unittest.mock.call.add_class(
                        stream_xsos.SMAcknowledgement,
                        ctx._recv_stanza),
                    unittest.mock.call.add_class(
                        stream_xsos.SMRequest,
                        ctx._recv_stanza)
                ],
                self.xmlstream.stanza_parser.mock_calls
            )
            ctx.stop_sm()
            self.xmlstream.stanza_parser.reset_mock()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.IQ),
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.stream.recv_stanza),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

        self.assertTrue(self.stream.running)
        self.assertFalse(self.stream.sm_enabled)

    def test_transactional_start_jit_sm_resume(self):
        self.stream.start_sm()
        with self.stream.transactional_start(self.xmlstream) as ctx:
            with unittest.mock.patch.object(self.stream, "_resume_sm") as mock:
                ctx.resume_sm(10)
                mock.assert_called_once_with(10)
            self.xmlstream.stanza_parser.reset_mock()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.IQ),
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(
                    stream_xsos.SMAcknowledgement),
                unittest.mock.call.add_class(
                    stream_xsos.SMAcknowledgement,
                    self.stream.recv_stanza),
                unittest.mock.call.remove_class(stream_xsos.SMRequest),
                unittest.mock.call.add_class(
                    stream_xsos.SMRequest,
                    self.stream.recv_stanza)
            ],
            self.xmlstream.stanza_parser.mock_calls
        )

        self.assertTrue(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)

    def test_transactional_start_propagate_transport_errors(self):
        exc = ConnectionError()

        fun = unittest.mock.MagicMock()
        fun.return_value = None

        self.stream.on_failure.connect(fun)

        with self.assertRaises(ConnectionError) as ctx:
            with self.stream.transactional_start(self.xmlstream):
                self.xmlstream.on_failure(exc)

        self.assertIs(exc, ctx.exception)

        self.assertFalse(fun.mock_calls)

    def test_cleanup_iq_response_listeners_on_stop_without_sm(self):
        fun = unittest.mock.MagicMock()

        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)

    def test_cleanup_iq_response_listeners_on_sm_stop(self):
        fun = unittest.mock.MagicMock()


        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        self.stream.stop_sm()
        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)

    def test_keep_iq_response_listeners_on_sm_stop(self):
        fun = unittest.mock.MagicMock()

        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        with self.assertRaisesRegexp(ValueError,
                                     "only one listener is allowed"):
            self.stream.register_iq_response_callback(
                structs.JID("foo", "bar", None), "baz",
                fun)

    def test_stanza_future_raises_if_stream_interrupts_without_sm(self):
        iq = make_test_iq()

        @asyncio.coroutine
        def kill_it():
            yield from asyncio.sleep(0)
            self.stream.stop()

        self.stream.start(self.xmlstream)
        with self.assertRaises(ConnectionError):
            run_coroutine(asyncio.gather(
                kill_it(),
                self.stream.send_iq_and_wait_for_reply(iq)
            ))


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

    def test_repr(self):
        token = stream.StanzaToken(make_test_iq())
        self.assertEqual(
            "<StanzaToken id=0x{:016x}>".format(id(token)),
            repr(token)
        )
