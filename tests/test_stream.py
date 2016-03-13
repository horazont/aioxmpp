import asyncio
import ipaddress
import time
import unittest

import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.stanza as stanza
import aioxmpp.stream as stream
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service

from datetime import timedelta

from aioxmpp.utils import namespaces
from aioxmpp.plugins import xep0199

from aioxmpp.testutils import (
    run_coroutine,
    run_coroutine_with_peer,
    XMLStreamMock,
    CoroutineMock
)
from aioxmpp import xmltestutils


TEST_FROM = structs.JID.fromstr("foo@example.test/r1")
TEST_TO = structs.JID.fromstr("bar@example.test/r1")


class FancyTestIQ(xso.XSO):
    TAG = ("uri:tests:test_stream.py", "foo")


stanza.IQ.register_child(stanza.IQ.payload, FancyTestIQ)


def make_test_iq(from_=TEST_FROM, to=TEST_TO, type_="get", autoset_id=True):
    iq = stanza.IQ(type_=type_, from_=from_, to=to)
    iq.payload = FancyTestIQ()
    if autoset_id:
        iq.autoset_id()
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
    xmlstream = unittest.mock.Mock()
    xmlstream.send_xso = _on_send_xso
    xmlstream.on_closing = callbacks.AdHocSignal()
    xmlstream.close_and_wait = CoroutineMock()
    stanzastream = stream.StanzaStream(
        TEST_FROM.bare(),
        loop=loop)

    return sent_stanzas, xmlstream, stanzastream


class TestFilter_Token(unittest.TestCase):
    def test_each_is_unique(self):
        t1 = stream.Filter.Token()
        t2 = stream.Filter.Token()
        self.assertIsNot(t1, t2)
        self.assertNotEqual(t1, t2)

    def test_str(self):
        self.assertRegex(
            str(stream.Filter.Token()),
            r"<[a-zA-Z._]+\.Filter\.Token 0x[0-9a-f]+>"
        )


class TestFilter(unittest.TestCase):
    def setUp(self):
        self.f = stream.Filter()

    def test_register(self):
        func = unittest.mock.Mock()
        func.return_value = None

        token = self.f.register(func, 0)
        self.assertIsNotNone(token)

    def test_filter(self):
        func = unittest.mock.Mock()
        func.return_value = None

        self.f.register(func, 0)

        iq = stanza.IQ("get")

        self.assertIsNone(self.f.filter(iq))
        self.assertSequenceEqual(
            [
                unittest.mock.call(iq),
            ],
            func.mock_calls
        )

    def test_filter_chain(self):
        mock = unittest.mock.Mock()

        self.f.register(mock.func1, 0)
        self.f.register(mock.func2, 0)

        result = self.f.filter(mock.stanza)

        calls = list(mock.mock_calls)

        self.assertEqual(
            mock.func2(),
            result
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call.func1(mock.stanza),
                unittest.mock.call.func2(mock.func1()),
            ],
            calls
        )

    def test_filter_chain_aborts_on_None_result(self):
        mock = unittest.mock.Mock()

        mock.func2.return_value = None

        self.f.register(mock.func1, 0)
        self.f.register(mock.func2, 0)
        self.f.register(mock.func3, 0)

        result = self.f.filter(mock.stanza)

        calls = list(mock.mock_calls)

        self.assertIsNone(result)
        self.assertSequenceEqual(
            [
                unittest.mock.call.func1(mock.stanza),
                unittest.mock.call.func2(mock.func1()),
            ],
            calls
        )

    def test_unregister_by_token(self):
        func = unittest.mock.Mock()
        token = self.f.register(func, 0)
        self.f.unregister(token)
        self.f.filter(object())
        self.assertFalse(func.mock_calls)

    def test_unregister_raises_ValueError_if_token_not_found(self):
        with self.assertRaisesRegexp(ValueError, "unregistered token"):
            self.f.unregister(object())

    def test_register_with_order(self):
        mock = unittest.mock.Mock()

        self.f.register(mock.func1, 1)
        self.f.register(mock.func2, 0)
        self.f.register(mock.func3, -1)

        result = self.f.filter(mock.stanza)
        calls = list(mock.mock_calls)

        self.assertEqual(
            mock.func1(),
            result
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call.func3(mock.stanza),
                unittest.mock.call.func2(mock.func3()),
                unittest.mock.call.func1(mock.func2()),
            ],
            calls
        )


class TestAppFilter(TestFilter):
    def setUp(self):
        super().setUp()
        self.f = stream.AppFilter()

    def test_register_defaults_ordering(self):
        mock = unittest.mock.Mock()

        self.f.register(mock.func2)
        self.f.register(mock.func1, 1)
        self.f.register(mock.func3, -1)

        result = self.f.filter(mock.stanza)
        calls = list(mock.mock_calls)

        self.assertEqual(
            mock.func1(),
            result
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call.func3(mock.stanza),
                unittest.mock.call.func2(mock.func3()),
                unittest.mock.call.func1(mock.func2()),
            ],
            calls
        )


class StanzaStreamTestBase(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.sent_stanzas, self.xmlstream, self.stream = \
            make_mocked_streams(self.loop)

        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None
        self.stream.on_stream_destroyed.connect(self.destroyed_rec)

        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.stream.on_stream_established.connect(self.established_rec)

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

    def test_init(self):
        self.assertEqual(
            self.stream.local_jid,
            TEST_FROM.bare()
        )

    def test_init_default(self):
        s = stream.StanzaStream()
        self.assertIsNone(s.local_jid)

    def test_local_jid_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.stream.local_jid = TEST_TO.bare()

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

        iq = make_test_iq(type_="result")
        iq.autoset_id()
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_ignore_unexpected_iq_error(self):
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

    def test_enqueue_stanza_validates_stanza(self):
        iq = make_test_iq(type_="get")

        with unittest.mock.patch.object(iq, "validate") as validate:
            self.stream.enqueue_stanza(iq)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            validate.mock_calls
        )

    def test_start_stop(self):
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()

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
        self.assertEqual(
            self.xmlstream.error_handler,
            self.stream.recv_errorneous_stanza
        )
        self.xmlstream.stanza_parser.mock_calls.clear()

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.destroyed_rec.assert_called_once_with()

        self.assertSequenceEqual(
            [
                unittest.mock.call.remove_class(stanza.Presence),
                unittest.mock.call.remove_class(stanza.Message),
                unittest.mock.call.remove_class(stanza.IQ),
            ],
            self.xmlstream.stanza_parser.mock_calls
        )
        self.assertIsNone(self.xmlstream.error_handler)

    def test_unregister_iq_response(self):
        fut = asyncio.Future()
        cb = unittest.mock.Mock()

        self.stream.register_iq_response_future(
            TEST_FROM,
            "foobar",
            fut)
        self.stream.unregister_iq_response(TEST_FROM, "foobar")
        self.stream.register_iq_response_callback(
            TEST_FROM,
            "foobar",
            cb)
        self.stream.unregister_iq_response(TEST_FROM, "foobar")

        iq = make_test_iq(type_="result")
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(fut.done())
        self.assertFalse(cb.mock_calls)

    def test_register_iq_request_coro_rejects_duplicate_registration(self):
        @asyncio.coroutine
        def handle_request(stanza):
            pass

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)

        @asyncio.coroutine
        def handle_request(stanza):
            pass

        with self.assertRaises(ValueError):
            self.stream.register_iq_request_coro(
                "get",
                FancyTestIQ,
                handle_request)

    def test_run_iq_request_coro_with_result(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        response_payload, response_iq = None, None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal response_payload
            response_payload = FancyTestIQ()
            return response_payload

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_iq = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(iq.to, response_iq.from_)
        self.assertEqual(iq.from_, response_iq.to)
        self.assertEqual(iq.id_, response_iq.id_)
        self.assertEqual("result", response_iq.type_)
        self.assertIs(response_payload, response_iq.payload)

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

    def test_unregister_iq_request_coro_raises_if_none_was_registered(self):
        with self.assertRaises(KeyError):
            self.stream.unregister_iq_request_coro(
                "get",
                FancyTestIQ)

    def test_unregister_iq_request_coro(self):
        iq = make_test_iq(type_="get")
        iq.autoset_id()

        recvd = None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal recvd
            recvd = stanza

        self.stream.register_iq_request_coro(
            "get",
            FancyTestIQ,
            handle_request)
        self.stream.unregister_iq_request_coro(
            "get",
            FancyTestIQ)

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(asyncio.sleep(0))
        self.assertIsNone(recvd)

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

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

    def test_run_message_callback_to_bare_jid(self):
        msg = make_test_message(from_=TEST_FROM)

        fut = asyncio.Future()

        self.stream.register_message_callback(
            None,
            TEST_FROM.bare(),
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    def test_unregister_message_callback(self):
        cb = unittest.mock.Mock()

        with self.assertRaises(KeyError):
            self.stream.unregister_message_callback(None, None)

        self.stream.register_message_callback(
            None, None,
            cb)

        self.stream.unregister_message_callback(None, None)

        self.stream.register_message_callback(
            "chat", TEST_FROM,
            cb)

        self.stream.unregister_message_callback("chat", TEST_FROM)

        self.stream.start(self.xmlstream)

        msg = make_test_message(type_="chat", from_=TEST_FROM)
        self.stream.recv_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(cb.mock_calls)

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

    def test_unregister_presence_callback(self):
        cb = unittest.mock.Mock()

        with self.assertRaises(KeyError):
            self.stream.unregister_presence_callback(None, None)

        self.stream.register_presence_callback(
            None, None,
            cb)

        self.stream.unregister_presence_callback(None, None)

        self.stream.register_presence_callback(
            "subscribe", TEST_FROM,
            cb)

        self.stream.unregister_presence_callback("subscribe", TEST_FROM)

        self.stream.start(self.xmlstream)

        msg = make_test_presence(type_="subscribe", from_=TEST_FROM)
        self.stream.recv_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(cb.mock_calls)

    def test_rescue_unprocessed_incoming_stanza_on_stop(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.stream.recv_stanza(pres)
        self.stream.stop()

        self.assertEqual(
            (pres, None),
            run_coroutine(self.stream._incoming_queue.get())
        )

    def test_rescue_unprocessed_outgoing_stanza_on_stop(self):
        pres = make_test_presence()
        pres.autoset_id()

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

        self.assertEqual(
            (pres, None),
            run_coroutine(self.stream._incoming_queue.get())
        )

    def test_unprocessed_outgoing_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()
        pres.autoset_id()

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

    def test_stop_induces_clean_shutdown_and_no_call_to_transport(self):
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

    def test_stop_removes_stanza_handlers(self):
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

        def cb():
            pass

        self.xmlstream.stanza_parser.add_class(stanza.IQ, cb)
        self.xmlstream.stanza_parser.add_class(stanza.Presence, cb)
        self.xmlstream.stanza_parser.add_class(stanza.Message, cb)

    def test_wait_stop(self):
        self.stream.start(self.xmlstream)
        self.assertTrue(self.stream.running)
        run_coroutine(self.stream.wait_stop())
        self.assertFalse(self.stream.running)

    def test_wait_stop_passes_if_not_started(self):
        self.assertFalse(self.stream.running)
        run_coroutine(self.stream.wait_stop())
        self.assertFalse(self.stream.running)

    def test_wait_stop_does_not_reemit_failures(self):
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.xmlstream.on_closing(ConnectionError())
        self.assertTrue(self.stream.running)
        run_coroutine(self.stream.wait_stop())
        self.assertFalse(self.stream.running)

    def test_close_normally(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)
        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.xmlstream.close_and_wait.assert_called_once_with()
        self.assertIsNone(caught_exc)

    def test_close_when_stopped(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.on_failure.connect(failure_handler)

        self.assertFalse(self.stream.running)
        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertIsNone(caught_exc)

    def test_close_after_error(self):
        caught_exc = None
        exc = ConnectionError()

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.xmlstream.on_closing(exc)
        self.assertTrue(self.stream.running)
        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertIs(exc, caught_exc)
        self.assertFalse(self.xmlstream.close.mock_calls)

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

    def test_nonsm_ignore_sm_ack(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(nonza.SMAcknowledgement())
        run_coroutine(asyncio.sleep(0))
        self.stream.stop()

        self.assertIsNone(caught_exc)

    def test_nonsm_ignore_sm_req(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(nonza.SMRequest())
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
        response.payload = FancyTestIQ()

        task = asyncio.ensure_future(
            self.stream.send_iq_and_wait_for_reply(iq),
            loop=self.loop,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.recv_stanza(response)
        result = run_coroutine(task)
        self.assertIs(
            response.payload,
            result,
        )

    def test_send_iq_and_wait_for_reply_with_error(self):
        iq = make_test_iq()
        response = iq.make_reply(type_="error")
        response.error = stanza.Error.from_exception(
            errors.XMPPCancelError(
                condition=(namespaces.stanzas, "item-not-found")
            )
        )

        task = asyncio.ensure_future(
            self.stream.send_iq_and_wait_for_reply(iq),
            loop=self.loop,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.stream.recv_stanza(response)
        with self.assertRaises(errors.XMPPCancelError) as ctx:
            run_coroutine(task)
        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            ctx.exception.condition
        )

    def test_send_iq_and_wait_for_reply_autosets_id(self):
        iq = make_test_iq(autoset_id=False)

        task = asyncio.ensure_future(
            self.stream.send_iq_and_wait_for_reply(iq),
            loop=self.loop,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        # this is a hack, which only works because send_iq_and_wait_for_reply
        # mutates the object
        response = iq.make_reply(type_="result")
        response.payload = FancyTestIQ()
        self.stream.recv_stanza(response)
        result = run_coroutine(task)
        self.assertIs(
            response.payload,
            result
        )

    def test_send_iq_and_wait_for_reply_timeout(self):
        iq = make_test_iq()

        task = asyncio.ensure_future(
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
        self.xmlstream.on_closing(exc)
        run_coroutine(asyncio.sleep(0))
        self.assertIs(caught_exc, exc)
        self.assertFalse(self.stream.running)

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

    def _test_inbound_presence_filter(self, filter_attr, **register_kwargs):
        pres = stanza.Presence(type_="unavailable")
        out = stanza.Presence(type_=None)

        cb = unittest.mock.Mock([])
        cb.return_value = None

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.register_presence_callback(None, None, cb)

        self.stream.recv_stanza(pres)
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(pres),
            ],
            filter_func.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(out),
            ],
            cb.mock_calls
        )

        cb.reset_mock()
        cb.return_value = None
        filter_func.reset_mock()
        filter_func.return_value = None

        self.stream.recv_stanza(pres)
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(pres),
            ],
            filter_func.mock_calls
        )

        self.assertSequenceEqual([], cb.mock_calls)

        self.assertTrue(self.stream.running)

    def test_app_inbound_presence_filter(self):
        self._test_inbound_presence_filter(
            self.stream.app_inbound_presence_filter
        )

    def test_service_inbound_presence_filter(self):
        class Service(service.Service):
            pass

        self._test_inbound_presence_filter(
            self.stream.service_inbound_presence_filter,
            order=Service
        )

    def test_service_inbound_presence_filter_before_app(self):
        class Service(service.Service):
            pass

        pres = stanza.Presence()

        mock = unittest.mock.Mock()
        mock.service.return_value = pres
        mock.app.return_value = pres

        self.stream.app_inbound_presence_filter.register(mock.app)
        self.stream.service_inbound_presence_filter.register(
            mock.service,
            order=Service)

        self.stream.recv_stanza(pres)
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.service(pres),
                unittest.mock.call.app(pres),
            ],
            mock.mock_calls
        )

    def _test_inbound_message_filter(self, filter_attr, **register_kwargs):
        msg = stanza.Message(type_="chat", from_=TEST_FROM)
        out = stanza.Message(type_="groupchat", from_=TEST_FROM)

        cb = unittest.mock.Mock([])
        cb.return_value = None

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.register_message_callback("groupchat", None, cb)

        self.stream.recv_stanza(msg)
        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(msg),
            ],
            filter_func.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(out),
            ],
            cb.mock_calls
        )

        cb.reset_mock()
        cb.return_value = None
        filter_func.reset_mock()
        filter_func.return_value = None

        self.stream.recv_stanza(msg)
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(msg),
            ],
            filter_func.mock_calls
        )

        self.assertSequenceEqual([], cb.mock_calls)

        self.assertTrue(self.stream.running)

    def test_app_inbound_message_filter(self):
        self._test_inbound_message_filter(
            self.stream.app_inbound_message_filter
        )

    def test_service_inbound_message_filter(self):
        class Service(service.Service):
            pass

        self._test_inbound_message_filter(
            self.stream.service_inbound_message_filter,
            order=Service
        )

    def test_service_inbound_message_filter_before_app(self):
        class Service(service.Service):
            pass

        msg = stanza.Message("chat")

        mock = unittest.mock.Mock()
        mock.service.return_value = msg
        mock.app.return_value = msg

        self.stream.app_inbound_message_filter.register(mock.app)
        self.stream.service_inbound_message_filter.register(
            mock.service,
            order=Service)

        self.stream.recv_stanza(msg)
        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.service(msg),
                unittest.mock.call.app(msg),
            ],
            mock.mock_calls
        )

    def _test_outbound_presence_filter(self, filter_attr, **register_kwargs):
        pres = stanza.Presence(type_="unavailable")
        pres.autoset_id()
        out = stanza.Presence(type_=None)

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.start(self.xmlstream)
        token = self.stream.enqueue_stanza(pres)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(pres),
            ],
            filter_func.mock_calls
        )

        self.assertEqual(
            stream.StanzaState.SENT_WITHOUT_SM,
            token.state
        )

        self.assertIs(
            out,
            self.sent_stanzas.get_nowait()
        )

        filter_func.reset_mock()
        filter_func.return_value = None

        token = self.stream.enqueue_stanza(pres)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(pres),
            ],
            filter_func.mock_calls
        )

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

        self.assertEqual(
            stream.StanzaState.DROPPED,
            token.state
        )

    def test_app_outbound_presence_filter(self):
        self._test_outbound_presence_filter(
            self.stream.app_outbound_presence_filter
        )

    def test_service_outbound_presence_filter(self):
        class Service(service.Service):
            pass

        self._test_outbound_presence_filter(
            self.stream.service_outbound_presence_filter,
            order=Service
        )

    def test_service_outbound_presence_filter_after_app(self):
        class Service(service.Service):
            pass

        pres = stanza.Presence()
        pres.autoset_id()

        mock = unittest.mock.Mock()

        mock.app.return_value = pres
        mock.service.return_value = pres

        self.stream.app_outbound_presence_filter.register(mock.app)
        self.stream.service_outbound_presence_filter.register(
            mock.service,
            order=Service
        )

        self.stream.start(self.xmlstream)
        self.stream.enqueue_stanza(pres)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.app(pres),
                unittest.mock.call.service(pres)
            ],
            mock.mock_calls
        )

    def _test_outbound_message_filter(self, filter_attr, **register_kwargs):
        msg = stanza.Message(type_="chat")
        msg.autoset_id()
        out = stanza.Message(type_="groupchat")

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.start(self.xmlstream)
        token = self.stream.enqueue_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(msg),
            ],
            filter_func.mock_calls
        )

        self.assertEqual(
            stream.StanzaState.SENT_WITHOUT_SM,
            token.state
        )

        self.assertIs(
            out,
            self.sent_stanzas.get_nowait()
        )

        filter_func.reset_mock()
        filter_func.return_value = None

        token = self.stream.enqueue_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call(msg),
            ],
            filter_func.mock_calls
        )

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

        self.assertEqual(
            stream.StanzaState.DROPPED,
            token.state
        )

    def test_app_outbound_message_filter(self):
        self._test_outbound_message_filter(
            self.stream.app_outbound_message_filter
        )

    def test_service_outbound_message_filter(self):
        class Service(service.Service):
            pass

        self._test_outbound_message_filter(
            self.stream.service_outbound_message_filter,
            order=Service
        )

    def test_service_outbound_message_filter_after_app(self):
        class Service(service.Service):
            pass

        msg = stanza.Message("chat")
        msg.autoset_id()

        mock = unittest.mock.Mock()

        mock.app.return_value = msg
        mock.service.return_value = msg

        self.stream.app_outbound_message_filter.register(mock.app)
        self.stream.service_outbound_message_filter.register(
            mock.service,
            order=Service
        )

        self.stream.start(self.xmlstream)
        self.stream.enqueue_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.app(msg),
                unittest.mock.call.service(msg)
            ],
            mock.mock_calls
        )

    def test_handle_on_closing_with_None_argument(self):
        failure_handler = unittest.mock.Mock()
        failure_handler.return_value = False

        def fail(xso):
            raise ConnectionError("xmlstream not connected")

        self.stream.on_failure.connect(failure_handler)
        self.stream.start(self.xmlstream)
        self.xmlstream.send_xso = fail

        msg = make_test_message()
        msg.autoset_id()

        self.stream.enqueue_stanza(msg)

        self.xmlstream.on_closing(None)

        run_coroutine(asyncio.sleep(0))

        # we expect the stream to wait with the failure until it gets told the
        # actual problem by the XML stream through the on_failure callback
        self.assertFalse(self.stream.running)

        self.assertFalse(failure_handler.mock_calls)

    def test_handle_PayloadParsingError_at_iq_with_error_response(self):
        iq = make_test_iq()
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.IQ
        )
        self.assertEqual(
            obj.type_,
            "error"
        )
        self.assertEqual(
            obj.id_,
            iq.id_
        )
        self.assertEqual(
            obj.from_,
            iq.to
        )
        self.assertEqual(
            obj.to,
            iq.from_
        )
        self.assertIsInstance(
            obj.error,
            stanza.Error
        )
        self.assertEqual(
            obj.error.condition,
            (namespaces.stanzas, "bad-request")
        )

    def test_do_not_respond_to_PayloadParsingError_at_error_iq(self):
        iq = make_test_iq(type_="error")
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_PayloadParsingError_at_result_iq(self):
        iq = make_test_iq(type_="result")
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_PayloadParsingError_at_message_with_error_response(self):
        msg = make_test_message()
        self.stream.recv_errorneous_stanza(
            msg,
            stanza.PayloadParsingError(msg, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.Message
        )
        self.assertEqual(
            obj.type_,
            "error"
        )
        self.assertEqual(
            obj.id_,
            msg.id_
        )
        self.assertEqual(
            obj.from_,
            msg.to
        )
        self.assertEqual(
            obj.to,
            msg.from_
        )
        self.assertIsInstance(
            obj.error,
            stanza.Error
        )
        self.assertEqual(
            obj.error.condition,
            (namespaces.stanzas, "bad-request")
        )

    def test_do_not_respond_to_PayloadParsingError_at_error_message(self):
        msg = make_test_message(type_="error")
        self.stream.recv_errorneous_stanza(
            msg,
            stanza.PayloadParsingError(msg, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_PayloadParsingError_at_presence_with_error_response(self):
        pres = make_test_message()
        self.stream.recv_errorneous_stanza(
            pres,
            stanza.PayloadParsingError(pres, ('end', 'foo'))
        )

        run_coroutine(asyncio.sleep(0.01))

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.Message
        )
        self.assertEqual(
            obj.type_,
            "error"
        )
        self.assertEqual(
            obj.id_,
            pres.id_
        )
        self.assertEqual(
            obj.from_,
            pres.to
        )
        self.assertEqual(
            obj.to,
            pres.from_
        )
        self.assertIsInstance(
            obj.error,
            stanza.Error
        )
        self.assertEqual(
            obj.error.condition,
            (namespaces.stanzas, "bad-request")
        )

    def test_do_not_respond_to_PayloadParsingError_at_error_presence(self):
        pres = make_test_presence(type_="error")
        self.stream.recv_errorneous_stanza(
            pres,
            stanza.PayloadParsingError(pres, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_UnknownIQPayload_at_iq_with_error_response(self):
        iq = make_test_iq()
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'))
        )

        run_coroutine(asyncio.sleep(0.01))

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.IQ
        )
        self.assertEqual(
            obj.type_,
            "error"
        )
        self.assertEqual(
            obj.id_,
            iq.id_
        )
        self.assertEqual(
            obj.from_,
            iq.to
        )
        self.assertEqual(
            obj.to,
            iq.from_
        )
        self.assertIsInstance(
            obj.error,
            stanza.Error
        )
        self.assertEqual(
            obj.error.condition,
            (namespaces.stanzas, "feature-not-implemented")
        )

    def test_ignore_UnknownIQPayload_at_error_iq(self):
        iq = make_test_iq(type_="error")
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_UnknownIQPayload_at_result_iq(self):
        iq = make_test_iq(type_="result")
        self.stream.recv_errorneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_map_iq_from_bare_local_jid_to_None(self):
        iq = make_test_iq(from_=TEST_FROM.bare(), type_="result")
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_callback(
            None,
            iq.id_,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(iq, fut.result())

    def test_unicast_error_on_errorneous_iq_result(self):
        req = make_test_iq(type_="get", to=TEST_TO)
        resp = req.make_reply(type_="result")

        self.stream.recv_errorneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'))
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_TO,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErrorneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_unicast_error_on_errorneous_iq_error(self):
        req = make_test_iq(type_="get", to=TEST_TO)
        resp = req.make_reply(type_="error")

        self.stream.recv_errorneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'))
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_TO,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErrorneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_unicast_error_on_errorneous_iq_error_unless_from_is_None(self):
        req = make_test_iq(type_="get", to=None)
        resp = req.make_reply(type_="error")

        self.stream.recv_errorneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'))
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            req.to,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(asyncio.TimeoutError):
            run_coroutine(fut, timeout=0.1)

    def test_do_not_crash_on_unsolicited_errorneous_iq_response(self):
        req = make_test_iq(type_="get", to=TEST_TO)
        resp = req.make_reply(type_="result")

        self.stream.recv_errorneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'))
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_message_callback_fallback_order(self):
        base = unittest.mock.Mock()

        self.stream.register_message_callback(
            "chat", TEST_FROM,
            base.chat_full
        )
        base.chat_full.return_value = None
        base.chat_full._is_coroutine = False

        self.stream.register_message_callback(
            "chat", TEST_FROM.bare(),
            base.chat_bare
        )
        base.chat_bare.return_value = None
        base.chat_bare._is_coroutine = False

        self.stream.register_message_callback(
            None, TEST_FROM,
            base.wildcard_full
        )
        base.wildcard_full.return_value = None
        base.wildcard_full._is_coroutine = False

        self.stream.register_message_callback(
            None, TEST_FROM.bare(),
            base.wildcard_bare
        )
        base.wildcard_bare.return_value = None
        base.wildcard_bare._is_coroutine = False

        self.stream.register_message_callback(
            "chat", None,
            base.chat_wildcard
        )
        base.chat_wildcard.return_value = None
        base.chat_wildcard._is_coroutine = False

        self.stream.register_message_callback(
            None, None,
            base.fallback
        )
        base.fallback.return_value = None
        base.fallback._is_coroutine = False

        test_set = [
            ("chat", TEST_FROM, "chat_full"),
            ("chat", TEST_FROM.replace(resource="r2"), "chat_bare"),
            ("chat", TEST_FROM.bare(), "chat_bare"),
            ("chat", TEST_FROM.replace(domain="bar.example"), "chat_wildcard"),
            ("headline", TEST_FROM, "wildcard_full"),
            ("headline", TEST_FROM.replace(resource="r2"), "wildcard_bare"),
            ("headline", TEST_FROM.bare(), "wildcard_bare"),
            ("headline", TEST_FROM.replace(domain="bar.example"), "fallback"),
        ]

        stanza_set = []

        self.stream.start(self.xmlstream)

        for type_, from_, dest in test_set:
            stanza = make_test_message(type_=type_, from_=from_)
            stanza_set.append((stanza, dest))
            self.stream.recv_stanza(
                stanza
            )

        run_coroutine(asyncio.sleep(0.01))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, dest)(st)
                for st, dest in stanza_set
            ]
        )


class TestStanzaStreamSM(StanzaStreamTestBase):
    def setUp(self):
        super().setUp()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

        self.successful_sm = [
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=XMLStreamMock.Receive(
                    nonza.SMEnabled(resume=True,
                                          id_="foobar")
                )
            )
        ]
        self.sm_without_resume = [
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=XMLStreamMock.Receive(
                    nonza.SMEnabled(resume=False)
                )
            )
        ]

        del self.sent_stanzas

    def test_sm_initialization_only_in_stopped_state(self):
        with self.assertRaisesRegexp(RuntimeError, "is not running"):
            run_coroutine(self.stream.start_sm())

    def test_start_sm(self):
        self.assertFalse(self.stream.sm_enabled)

        # we need interaction here to show that SM gets negotiated
        xmlstream = XMLStreamMock(self, loop=self.loop)

        self.stream.start(xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(request_resumption=True),
            xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True),
                        response=XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                                  id_="foobar",
                                                  location=("fe80::", 5222),
                                                  max_=1200)
                        )
                    )
                ]
            )
        )

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
        self.assertEqual(
            "foobar",
            self.stream.sm_id
        )
        self.assertEqual(
            (ipaddress.IPv6Address("fe80::"), 5222),
            self.stream.sm_location
        )
        self.assertEqual(
            1200,
            self.stream.sm_max
        )
        self.assertTrue(self.stream.sm_resumable)

        self.established_rec.assert_called_once_with()

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_sm_start_failure(self):
        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.StreamNegotiationFailure):
            run_coroutine_with_peer(
                self.stream.start_sm(),
                self.xmlstream.run_test([
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True),
                        response=XMLStreamMock.Receive(
                            nonza.SMFailed()
                        )
                    )
                ])
            )

        self.assertTrue(self.stream.running)
        self.assertFalse(self.stream.sm_enabled)

    def test_sm_start_re_raise_xmlstream_errors_during_negotiation(self):
        exc = ValueError()

        self.stream.start(self.xmlstream)
        with self.assertRaises(ValueError) as ctx:
            run_coroutine_with_peer(
                self.stream.start_sm(),
                self.xmlstream.run_test([
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True),
                        response=XMLStreamMock.Fail(
                            exc
                        )
                    )
                ])
            )

        self.assertIs(ctx.exception, exc)

        self.assertFalse(self.stream.running)
        self.assertFalse(self.stream.sm_enabled)

    def test_sm_start_sm_enabled_on_xmlstream_errors_after_SMEnabled_if_resumable(self):
        exc = ValueError()

        self.stream.start(self.xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                                  id_="foobar"),
                        ),
                        XMLStreamMock.Fail(exc)
                    ]
                )
            ])
        )

        self.assertFalse(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)

        self.assertTrue(self.established_rec.mock_calls)
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_sm_start_sm_disabled_on_xmlstream_errors_after_SMEnabled_if_not_resumable(self):
        exc = ValueError()

        self.stream.start(self.xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=False),
                        ),
                        XMLStreamMock.Fail(exc)
                    ]
                )
            ])
        )

        self.assertFalse(self.stream.running)
        self.assertFalse(self.stream.sm_enabled)

        self.assertTrue(self.established_rec.mock_calls)
        self.assertTrue(self.destroyed_rec.mock_calls)

    def test_sm_start_stanza_race_processing(self):
        iq = make_test_iq()
        error_iq = iq.make_reply(type_="error")
        error_iq.error = stanza.Error(
            condition=(namespaces.stanzas, "feature-not-implemented")
        )

        iq_sent = make_test_iq()

        @asyncio.coroutine
        def starter():
            asyncio.ensure_future(self.stream.start_sm())
            self.stream.enqueue_stanza(iq_sent)

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            starter(),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                                  id_="barbaz")
                        ),
                        XMLStreamMock.Receive(iq)
                    ]
                ),
                XMLStreamMock.Send(
                    iq_sent,
                ),
                XMLStreamMock.Send(nonza.SMRequest()),
                XMLStreamMock.Send(error_iq),
                XMLStreamMock.Send(nonza.SMRequest()),
            ])
        )

        self.assertTrue(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)

        self.assertEqual(
            0,
            self.stream.sm_outbound_base
        )
        self.assertEqual(
            2,
            len(self.stream.sm_unacked_list)
        )
        self.assertEqual(
            1,
            self.stream.sm_inbound_ctr
        )

    def test_sm_ack_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError, "is not enabled"):
            self.stream.sm_ack(0)

    def test_sm_outbound(self):
        state_change_handler = unittest.mock.MagicMock()
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

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
        state_change_handler.reset_mock()

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

        # we don’t want XMLStreamMock testing
        self.xmlstream = XMLStreamMock(self, loop=self)

    def test_sm_inbound(self):
        iqs = [make_test_iq() for i in range(3)]

        error_iqs = [
            iq.make_reply(type_="error")
            for iq in iqs
        ]
        for err_iq in error_iqs:
            err_iq.error = stanza.Error(
                condition=(namespaces.stanzas, "feature-not-implemented")
            )

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

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

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(error_iqs.pop()),
            XMLStreamMock.Send(nonza.SMRequest()),
            XMLStreamMock.Send(error_iqs.pop()),
            XMLStreamMock.Send(nonza.SMRequest()),
            XMLStreamMock.Send(error_iqs.pop()),
            XMLStreamMock.Send(nonza.SMRequest()),
        ]))

    def test_sm_resume(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        for iq in iqs:
            self.stream.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.established_rec.reset_mock()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(iqs[2]),
            XMLStreamMock.Send(
                nonza.SMRequest(),
                response=XMLStreamMock.Receive(
                    nonza.SMAcknowledgement(counter=1)
                )
            )
        ]))

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.destroyed_rec.mock_calls)

        # enqueue a stanza before resumption and check that the sequence is
        # correct (resumption-generated stanzas before new stanzas)
        self.stream.enqueue_stanza(additional_iq)

        run_coroutine_with_peer(
            self.stream.resume_sm(self.xmlstream),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(previd="foobar",
                                         counter=0),
                    response=XMLStreamMock.Receive(
                        nonza.SMResumed(previd="foobar",
                                              counter=2)
                    )
                ),
                XMLStreamMock.Send(iqs[2]),
                XMLStreamMock.Send(additional_iq),
                XMLStreamMock.Send(nonza.SMRequest()),
            ])
        )

        self.assertFalse(self.established_rec.mock_calls)

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.stream.stop_sm()
        self.destroyed_rec.assert_called_once_with()

    def test_sm_race(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        for iq in iqs:
            self.stream.enqueue_stanza(iq)

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.established_rec.reset_mock()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(iqs[2]),
            XMLStreamMock.Send(
                nonza.SMRequest(),
                response=XMLStreamMock.Receive(
                    nonza.SMAcknowledgement(counter=1)
                )
            )
        ]))

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.destroyed_rec.mock_calls)

        # enqueue a stanza before resumption and check that the sequence is
        # correct (resumption-generated stanzas before new stanzas)
        self.stream.enqueue_stanza(additional_iq)

        run_coroutine_with_peer(
            self.stream.resume_sm(self.xmlstream),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(previd="foobar",
                                         counter=0),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(previd="foobar",
                                                  counter=2)
                        ),
                        XMLStreamMock.Receive(
                            nonza.SMRequest()
                        )
                    ]
                ),
                XMLStreamMock.Send(iqs[2]),
                XMLStreamMock.Send(additional_iq),
                XMLStreamMock.Send(nonza.SMRequest()),
                XMLStreamMock.Send(nonza.SMAcknowledgement(counter=0)),
            ])
        )

        self.assertFalse(self.established_rec.mock_calls)

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.stream.stop_sm()
        self.destroyed_rec.assert_called_once_with()

    def test_sm_resumption_failure(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.stop()

        with self.assertRaises(errors.StreamNegotiationFailure):
            run_coroutine_with_peer(
                self.stream.resume_sm(self.xmlstream),
                self.xmlstream.run_test([
                    XMLStreamMock.Send(
                        nonza.SMResume(previd="foobar",
                                             counter=0),
                        response=XMLStreamMock.Receive(
                            nonza.SMFailed()
                        )
                    )
                ])
            )

        self.assertFalse(self.stream.running)
        self.assertFalse(self.stream.sm_enabled)

    def test_sm_resume_requires_stopped_stream(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.assertTrue(self.stream.running)
        with self.assertRaisesRegexp(RuntimeError, "is running"):
            run_coroutine(self.stream.resume_sm(self.xmlstream))

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
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        with self.assertRaisesRegexp(RuntimeError,
                                     "Stream Management already enabled"):
            run_coroutine(self.stream.start_sm())

    def test_sm_resume_requires_enabled_sm(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     "not enabled"):
            run_coroutine(self.stream.resume_sm(self.xmlstream))

    def test_stop_sm(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.stream.stop_sm()

        self.destroyed_rec.assert_called_once_with()
        self.established_rec.assert_called_once_with()

        self.assertFalse(self.stream.sm_enabled)
        with self.assertRaises(RuntimeError):
            self.stream.sm_outbound_base
        with self.assertRaises(RuntimeError):
            self.stream.sm_inbound_ctr
        with self.assertRaises(RuntimeError):
            self.stream.sm_unacked_list
        with self.assertRaises(RuntimeError):
            self.stream.sm_id
        with self.assertRaises(RuntimeError):
            self.stream.sm_max
        with self.assertRaises(RuntimeError):
            self.stream.sm_location
        with self.assertRaises(RuntimeError):
            self.stream.sm_resumable

    def test_sm_ping_automatic(self):
        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.ping_opportunistic_interval = timedelta(seconds=0.01)
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        run_coroutine(asyncio.sleep(0.005))
        # the next would raise if anything had been sent before
        run_coroutine(self.xmlstream.run_test([]))
        run_coroutine(asyncio.sleep(0.009))

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(nonza.SMRequest())
        ]))

    def test_sm_ping_opportunistic(self):
        # sm ping is always opportunistic: it also allows the server to ACK our
        # stanzas, which is great.

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        iq = make_test_iq()
        self.stream.enqueue_stanza(iq)

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iq),
            XMLStreamMock.Send(
                nonza.SMRequest()
            )
        ]))

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Receive(
                nonza.SMAcknowledgement(counter=1)
            )
        ))

        self.assertEqual(1, self.stream.sm_outbound_base)

    def test_sm_ping_timeout(self):
        exc = None

        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        iqs = [make_test_iq() for i in range(2)]

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        run_coroutine(asyncio.sleep(0))
        self.stream.enqueue_stanza(iqs[0])
        run_coroutine(asyncio.sleep(0.005))
        self.stream.enqueue_stanza(iqs[1])
        run_coroutine(asyncio.sleep(0.006))

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(nonza.SMRequest()),
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(nonza.SMRequest()),
        ]))

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

        iqs = [make_test_iq() for i in range(2)]

        self.stream.ping_interval = timedelta(seconds=0.01)
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.stream.enqueue_stanza(iqs[0])
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(nonza.SMRequest()),
        ]))
        self.stream.enqueue_stanza(iqs[1])
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(
                nonza.SMRequest(),
                response=XMLStreamMock.Receive(
                    nonza.SMAcknowledgement(counter=1)
                )
            ),
        ]))
        run_coroutine(asyncio.sleep(0.006))
        self.assertIsNone(exc)
        self.assertEqual(
            1,
            self.stream.sm_outbound_base
        )

    def test_sm_handle_req(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Send(nonza.SMAcknowledgement(counter=0))
            ],
            stimulus=XMLStreamMock.Receive(nonza.SMRequest())
        ))

    def test_sm_unacked_list_is_a_copy(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        l1 = self.stream.sm_unacked_list
        l2 = self.stream.sm_unacked_list
        self.assertIsNot(l1, l2)
        l1.append("foo")
        self.assertFalse(self.stream.sm_unacked_list)

    def test_sm_ignore_late_remote_counter(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.sm_ack(-1)

    def test_cleanup_iq_response_listeners_on_sm_stop(self):
        fun = unittest.mock.MagicMock()

        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        self.stream.stop_sm()
        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)

    def test_keep_iq_response_listeners_on_stop_with_sm(self):
        fun = unittest.mock.MagicMock()

        self.stream.register_iq_response_callback(
            structs.JID("foo", "bar", None), "baz",
            fun)
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        with self.assertRaisesRegexp(ValueError,
                                     "only one listener is allowed"):
            self.stream.register_iq_response_callback(
                structs.JID("foo", "bar", None), "baz",
                fun)

    def test_set_stanzas_to_sent_without_sm_when_sm_gets_turned_off(self):
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        tokens = [self.stream.enqueue_stanza(iq) for iq in iqs]

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(iqs[2]),
            XMLStreamMock.Send(nonza.SMRequest()),
        ]))

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

    def test_close_swallows_exceptions_if_sm_disabled(self):
        self.stream.start(self.xmlstream)

        self.established_rec.assert_called_once_with()

        self.assertFalse(self.stream.sm_enabled)

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test(
                [
                    XMLStreamMock.Close(
                        response=[
                            XMLStreamMock.Fail(ConnectionError())
                        ]
                    )
                ]
            )
        )

        self.assertFalse(self.stream.running)
        self.destroyed_rec.assert_called_once_with()

    def test_close_deletes_sm_state(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.established_rec.assert_called_once_with()

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test([
                XMLStreamMock.Close()
            ])
        )

        self.assertFalse(self.stream.sm_enabled)
        self.destroyed_rec.assert_called_once_with()

    def test_close_keeps_sm_state_on_exception_during_close_if_resumable(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.established_rec.assert_called_once_with()

        with self.assertRaises(ConnectionError):
            run_coroutine_with_peer(
                self.stream.close(),
                self.xmlstream.run_test(
                    [
                        XMLStreamMock.Close()
                    ],
                    stimulus=XMLStreamMock.Fail(ConnectionError())
                )
            )

        self.assertTrue(self.stream.sm_enabled)
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_close_clears_sm_state_on_exception_during_close_if_not_resumable(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.sm_without_resume)
        )
        self.assertFalse(self.stream.sm_resumable)

        self.established_rec.assert_called_once_with()

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test(
                [
                    XMLStreamMock.Close(
                        response=[
                            XMLStreamMock.Fail(ConnectionError())
                        ]
                    )
                ],
            )
        )

        self.assertFalse(self.stream.sm_enabled)
        self.destroyed_rec.assert_called_once_with()

    def test_stop_removes_stanza_handlers(self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        # we need interaction here to show that SM gets negotiated
        xmlstream = XMLStreamMock(self, loop=self.loop)

        iq = make_test_iq()
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(request_resumption=True),
            xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True),
                        response=XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                                  id_="foobar",
                                                  location=("fe80::", 5222),
                                                  max_=1200)
                        )
                    )
                ]
            )
        )

        self.assertTrue(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.stream.running)

        def cb():
            pass

        xmlstream.stanza_parser.add_class(stanza.IQ, cb)
        xmlstream.stanza_parser.add_class(stanza.Presence, cb)
        xmlstream.stanza_parser.add_class(stanza.Message, cb)
        xmlstream.stanza_parser.add_class(nonza.SMRequest, cb)
        xmlstream.stanza_parser.add_class(
            nonza.SMAcknowledgement, cb)

    def test_stop_removes_stanza_handlers_even_on_failure_during_resumption(
            self):
        caught_exc = None

        def failure_handler(exc):
            nonlocal caught_exc
            caught_exc = exc

        # we need interaction here to show that SM gets negotiated
        xmlstream = XMLStreamMock(self, loop=self.loop)

        iq = make_test_iq()
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(request_resumption=True),
            xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True),
                        response=[
                            XMLStreamMock.Receive(
                                nonza.SMEnabled(resume=True,
                                                      id_="foobar",
                                                      location=("fe80::", 5222),
                                                      max_=1200)
                            ),
                            XMLStreamMock.Fail(
                                ConnectionError()
                            )
                        ]
                    )
                ]
            )
        )

        self.assertFalse(self.stream.running)
        self.assertTrue(self.stream.sm_enabled)

        xmlstream = XMLStreamMock(self, loop=self.loop)

        with self.assertRaises(errors.StreamNegotiationFailure):
            run_coroutine_with_peer(
                self.stream.resume_sm(xmlstream),
                xmlstream.run_test(
                    [
                        XMLStreamMock.Send(
                            nonza.SMResume(counter=0, previd="foobar"),
                            response=[
                                XMLStreamMock.Receive(
                                    nonza.SMFailed()
                                ),
                            ]
                        )
                    ]
                )
            )

        def cb():
            pass

        xmlstream.stanza_parser.add_class(stanza.IQ, cb)
        xmlstream.stanza_parser.add_class(stanza.Presence, cb)
        xmlstream.stanza_parser.add_class(stanza.Message, cb)
        xmlstream.stanza_parser.add_class(nonza.SMRequest, cb)
        xmlstream.stanza_parser.add_class(
            nonza.SMAcknowledgement, cb)

    def tearDown(self):
        run_coroutine(self.xmlstream.run_test([]))
        # to satisfy del.sent_stanzas in inherited tearDown
        self.sent_stanzas = object()
        super().tearDown()


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
