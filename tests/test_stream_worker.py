import asyncio
import unittest

import asyncio_xmpp.jid as jid
import asyncio_xmpp.stanza_model as stanza_model
import asyncio_xmpp.stanza as stanza
import asyncio_xmpp.stream_worker as stream_worker
import asyncio_xmpp.stream_elements as stream_elements
import asyncio_xmpp.errors as errors

from datetime import datetime, timedelta

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


def make_test_message(from_=TEST_FROM, to=TEST_TO, type_="chat"):
    msg = stanza.Message(type_=type_, from_=from_, to=to)
    return msg


def make_test_presence(from_=TEST_FROM, to=TEST_TO, type_=None):
    pres = stanza.Presence(type_=type_, from_=from_, to=to)
    return pres


class StanzaBrokerTestBase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.sent_stanzas = asyncio.Queue()
        self.stream = unittest.mock.MagicMock()
        self.stream.send_stanza = self._on_send_stanza
        self.stream.stanza_parser = unittest.mock.MagicMock()
        self.broker = stream_worker.StanzaBroker(loop=self.loop)

    def _on_send_stanza(self, obj):
        self.sent_stanzas.put_nowait(obj)

    def tearDown(self):
        self.broker.stop()
        run_coroutine(asyncio.sleep(0))
        assert not self.broker.running()
        del self.broker
        del self.stream
        del self.sent_stanzas

class TestStanzaBroker(StanzaBrokerTestBase):

    def test_broker_iq_response(self):
        iq = make_test_iq(type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.broker.register_iq_response_callback(
            TEST_FROM,
            iq.id_,
            fut.set_result)
        self.broker.start(self.stream)
        self.broker.recv_stanza(iq)

        run_coroutine(fut)

        self.broker.stop()

        self.assertIs(iq, fut.result())

    def test_queue_stanza(self):
        iq = make_test_iq(type_="get")

        self.broker.start(self.stream)
        self.broker.enqueue_stanza(iq)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIs(obj, iq)

        self.broker.stop()

    def test_start_stop(self):
        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.add_class(
                    stanza.IQ,
                    self.broker.recv_stanza),
                unittest.mock.call.add_class(
                    stanza.Message,
                    self.broker.recv_stanza),
                unittest.mock.call.add_class(
                    stanza.Presence,
                    self.broker.recv_stanza),
            ],
            self.stream.stanza_parser.mock_calls
        )
        self.stream.stanza_parser.mock_calls.clear()

        self.broker.stop()

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.remove_class(stanza.IQ),
            ],
            self.stream.stanza_parser.mock_calls
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

        self.broker.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.broker.start(self.stream)
        self.broker.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertIs(response_got, response_put)

        self.broker.stop()

    def test_run_iq_request_without_handler(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        self.broker.start(self.stream)
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
        self.broker.start(self.stream)
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
        self.broker.start(self.stream)
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

    def test_run_message_callback(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.broker.register_message_callback(
            "chat",
            TEST_FROM,
            fut.set_result)
        self.broker.start(self.stream)
        self.broker.recv_stanza(msg)

        run_coroutine(fut)

        self.broker.stop()

        self.assertIs(msg, fut.result())

    def test_run_message_callback_from_wildcard(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.broker.register_message_callback(
            "chat",
            None,
            fut.set_result)
        self.broker.start(self.stream)
        self.broker.recv_stanza(msg)

        run_coroutine(fut)

        self.broker.stop()

        self.assertIs(msg, fut.result())

    def test_run_message_callback_full_wildcard(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.broker.register_message_callback(
            None,
            None,
            fut.set_result)
        self.broker.start(self.stream)
        self.broker.recv_stanza(msg)

        run_coroutine(fut)

        self.broker.stop()

        self.assertIs(msg, fut.result())

    def test_run_presence_callback_from_wildcard(self):
        pres = make_test_presence()

        fut = asyncio.Future()

        self.broker.register_presence_callback(
            None,  # note that None is a valid type value for presence
            None,
            fut.set_result)
        self.broker.start(self.stream)
        self.broker.recv_stanza(pres)

        run_coroutine(fut)

        self.broker.stop()

        self.assertIs(pres, fut.result())

    def test_rescue_unprocessed_incoming_stanza_on_stop(self):
        pres = make_test_presence()

        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        self.broker.recv_stanza(pres)
        self.broker.stop()

        self.assertIs(
            pres,
            run_coroutine(self.broker._incoming_queue.get())
        )

    def test_rescue_unprocessed_outgoing_stanza_on_stop(self):
        pres = make_test_presence()

        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        self.broker.enqueue_stanza(pres)
        self.broker.stop()

        self.assertIs(
            pres,
            run_coroutine(self.broker._active_queue.get())
        )

    def test_unprocessed_incoming_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()

        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        self.broker.stop()

        self.broker.recv_stanza(pres)

        self.assertIs(
            pres,
            run_coroutine(self.broker._incoming_queue.get())
        )

    def test_unprocessed_outgoing_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()

        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        self.broker.stop()

        self.broker.enqueue_stanza(pres)

        self.assertIs(
            pres,
            run_coroutine(self.broker._active_queue.get())
        )

    def test_fail_on_unknown_stanza_class(self):
        caught_exc = None
        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.broker.on_failure = failure_handler

        self.broker.start(self.stream)
        self.broker.recv_stanza(object())

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.broker.running())
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
        self.broker.on_failure = failure_handler

        self.broker.start(self.stream)
        self.broker.enqueue_stanza(iq)

        iq_sent = run_coroutine(self.sent_stanzas.get())
        self.assertIs(iq, iq_sent)

        self.broker.on_send_stanza = None
        self.broker.enqueue_stanza(iq)
        self.broker.recv_stanza(iq)
        self.broker.stop()

        self.assertIsNone(caught_exc)

    def test_opportunistic_send_event(self):
        mock = unittest.mock.MagicMock()
        iq = make_test_iq()

        self.assertIsNone(self.broker.on_opportunistic_send)
        self.broker.on_opportunistic_send = mock

        self.broker.start(self.stream)
        self.broker.enqueue_stanza(iq)

        run_coroutine(self.sent_stanzas.get())

        self.assertSequenceEqual(
            [
                unittest.mock.call.__bool__(),
                unittest.mock.call(self.stream),
            ],
            mock.mock_calls
        )

    def test_send_bulk(self):
        iqs = [make_test_iq() for i in range(3)]

        def send_handler(stanza_obj):
            # we send a cancel right when the stanza is enqueued for
            # sending.
            # by that, we ensure that the broker does not yield and sends
            # multiple stanzas if it can, optimizing the opportunistic send
            self.broker.stop()
            self._on_send_stanza(stanza_obj)

        self.broker.on_send_stanza = send_handler

        for iq in iqs:
            self.broker.enqueue_stanza(iq)

        self.broker.start(self.stream)

        for iq in iqs:
            self.assertIs(
                iq,
                run_coroutine(self.sent_stanzas.get()),
            )

    def test_running(self):
        self.assertFalse(self.broker.running())
        self.broker.start(self.stream)
        self.assertTrue(self.broker.running())
        self.broker.stop()
        # the task does not immediately terminate, it requires one cycle through
        # the event loop to do so
        self.assertTrue(self.broker.running())
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.broker.running())

    def test_forbid_starting_twice(self):
        self.broker.start(self.stream)
        with self.assertRaises(RuntimeError):
            self.broker.start(self.stream)

    def test_allow_stopping_twice(self):
        self.broker.start(self.stream)
        self.broker.stop()
        self.broker.stop()

    def test_sm_initialization_only_in_stopped_state(self):
        self.broker.start(self.stream)
        with self.assertRaises(RuntimeError):
            self.broker.start_sm()

    def test_start_sm(self):
        self.assertFalse(self.broker.sm_enabled)
        self.broker.start_sm()
        self.assertTrue(self.broker.sm_enabled)

        self.assertEqual(
            0,
            self.broker.sm_outbound_base
        )
        self.assertEqual(
            0,
            self.broker.sm_inbound_ctr
        )
        self.assertSequenceEqual(
            [],
            self.broker.sm_unacked_list
        )

    def test_sm_ack_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError, "is not enabled"):
            self.broker.sm_ack(0)

    def test_sm_outbound(self):
        iqs = [make_test_iq() for i in range(3)]

        self.broker.start_sm()
        self.broker.start(self.stream)
        for iq in iqs:
            self.broker.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            0,
            self.broker.sm_outbound_base
        )
        self.assertSequenceEqual(
            iqs,
            self.broker.sm_unacked_list
        )

        self.broker.sm_ack(1)
        self.assertEqual(
            1,
            self.broker.sm_outbound_base
        )
        self.assertSequenceEqual(
            iqs[1:],
            self.broker.sm_unacked_list
        )

        # idempotence with same number

        self.broker.sm_ack(1)
        self.assertEqual(
            1,
            self.broker.sm_outbound_base
        )
        self.assertSequenceEqual(
            iqs[1:],
            self.broker.sm_unacked_list
        )

        self.broker.sm_ack(3)
        self.assertEqual(
            3,
            self.broker.sm_outbound_base
        )
        self.assertSequenceEqual(
            [],
            self.broker.sm_unacked_list
        )

    def test_sm_inbound(self):
        iqs = [make_test_iq() for i in range(3)]

        self.broker.start_sm()
        self.broker.start(self.stream)

        self.broker.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            1,
            self.broker.sm_inbound_ctr
        )

        self.broker.recv_stanza(iqs.pop())
        self.broker.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            3,
            self.broker.sm_inbound_ctr
        )

    def test_sm_resume(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.broker.start_sm()
        self.broker.start(self.stream)
        for iq in iqs:
            self.broker.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))

        self.broker.sm_ack(1)
        self.broker.stop()

        run_coroutine(asyncio.sleep(0))

        # enqueue a stanza before resumption and check that the sequence is
        # correct (resumption-generated stanzas before new stanzas)
        self.broker.enqueue_stanza(additional_iq)

        self.broker.resume_sm(2)
        self.broker.start(self.stream)

        run_coroutine(asyncio.sleep(0))

        for iq in iqs + iqs[2:] + [additional_iq]:
            self.assertIs(
                iq,
                self.sent_stanzas.get_nowait()
            )

    def test_stop_sm(self):
        self.broker.start_sm()
        self.broker.stop_sm()

        self.assertFalse(self.broker.sm_enabled)
        self.assertFalse(hasattr(self.broker, "sm_outbound_base"))
        self.assertFalse(hasattr(self.broker, "sm_inbound_ctr"))
        self.assertFalse(hasattr(self.broker, "sm_unacked_list"))
