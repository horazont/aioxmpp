########################################################################
# File name: test_stream.py
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
import asyncio
import contextlib
import functools
import ipaddress
import time
import unittest
import warnings
import sys
import time

import aioxmpp
import aioxmpp.ping as ping
import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.stanza as stanza
import aioxmpp.stream as stream
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.dispatcher

from datetime import timedelta

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    run_coroutine,
    run_coroutine_with_peer,
    XMLStreamMock,
    CoroutineMock,
    get_timeout,
)
from aioxmpp import xmltestutils


TEST_FROM = structs.JID.fromstr("foo@example.test/r1")
TEST_TO = structs.JID.fromstr("bar@example.test/r1")


class FancyTestIQ(xso.XSO):
    TAG = ("uri:tests:test_stream.py", "foo")


stanza.IQ.register_child(stanza.IQ.payload, FancyTestIQ)


CAN_AWAIT_STANZA_TOKEN = sys.version_info >= (3, 5)


def make_test_iq(from_=TEST_FROM, to=TEST_TO,
                 type_=structs.IQType.GET,
                 autoset_id=True):
    iq = stanza.IQ(type_=type_, from_=from_, to=to)
    iq.payload = FancyTestIQ()
    if autoset_id:
        iq.autoset_id()
    return iq


def make_test_message(from_=TEST_FROM, to=TEST_TO,
                      type_=structs.MessageType.CHAT):
    msg = stanza.Message(type_=type_, from_=from_, to=to)
    return msg


def make_test_presence(from_=TEST_FROM, to=TEST_TO,
                       type_=structs.PresenceType.AVAILABLE):
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


class TestAppFilter(unittest.TestCase):
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

        client = unittest.mock.Mock()
        client.local_jid = self.stream.local_jid
        client.stream = self.stream

        self.message_dispatcher = aioxmpp.dispatcher.SimpleMessageDispatcher(
            client
        )
        self.presence_dispatcher = aioxmpp.dispatcher.SimplePresenceDispatcher(
            client
        )

        self.stream._xxx_message_dispatcher = self.message_dispatcher
        self.stream._xxx_presence_dispatcher = self.presence_dispatcher

    def tearDown(self):
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        assert not self.stream.running
        del self.stream
        del self.xmlstream
        del self.sent_stanzas


class TestStanzaStream(StanzaStreamTestBase):
    def test_init_local_jid(self):
        self.assertEqual(
            self.stream.local_jid,
            TEST_FROM.bare()
        )

    def test_init_default(self):
        s = stream.StanzaStream()
        self.assertIsNone(s.local_jid)

    def test_broker_iq_response(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)
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
        iq = make_test_iq(type_=structs.IQType.RESULT)
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
        iq = make_test_iq(type_=structs.IQType.ERROR)
        iq.autoset_id()
        iq.payload = None
        iq.error = stanza.Error(
            type_=structs.ErrorType.MODIFY,
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

        iq = make_test_iq(type_=structs.IQType.RESULT)
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

        iq = make_test_iq(type_=structs.IQType.ERROR)
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
        iq = make_test_iq(type_=structs.IQType.GET)

        self.stream.start(self.xmlstream)
        self.stream._enqueue(iq)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIs(obj, iq)

        self.stream.stop()

    def test_enqueue_validates_stanza(self):
        iq = unittest.mock.Mock()

        self.stream._enqueue(iq)

        iq.validate.assert_called_with()

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
            self.stream.recv_erroneous_stanza
        )
        self.xmlstream.stanza_parser.mock_calls.clear()

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"stop\(\) called and stream is not resumable"
        )

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

        iq = make_test_iq(type_=structs.IQType.RESULT)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(fut.done())
        self.assertFalse(cb.mock_calls)

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_register_iq_request_handler_casts_enum_and_warn(self):
        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.register_iq_request_handler(
                "get",
                FancyTestIQ,
                unittest.mock.sentinel.coro,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaisesRegex(
                ValueError,
                r"only one listener is allowed per tag"):
            self.stream.register_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ,
                unittest.mock.sentinel.coro,
            )

    def test_register_iq_request_handler_raises_on_string_type(self):
        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be IQType, got .*"):
            self.stream.register_iq_request_handler(
                "get",
                FancyTestIQ,
                unittest.mock.sentinel.coro,
            )

    def test_register_iq_request_handler_does_not_warn_on_enum(self):
        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.register_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ,
                unittest.mock.sentinel.coro,
            )

        self.assertFalse(w)

    def test_register_iq_request_handler_rejects_duplicate_registration(self):
        @asyncio.coroutine
        def handle_request(stanza):
            pass

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)

        @asyncio.coroutine
        def handle_request(stanza):
            pass

        with self.assertRaises(ValueError):
            self.stream.register_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ,
                handle_request)

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_unregister_iq_request_handler_casts_enum_and_warn(self):
        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            unittest.mock.sentinel.coro,
        )

        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.unregister_iq_request_handler(
                "get",
                FancyTestIQ,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaises(KeyError):
            self.stream.unregister_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ,
            )

    def test_unregister_iq_request_handler_raises_on_string_type(self):
        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            unittest.mock.sentinel.coro,
        )

        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be IQType, got .*"):
            self.stream.unregister_iq_request_handler(
                "get",
                FancyTestIQ,
            )

    def test_unregister_iq_request_handler_does_not_warn_on_enum(self):
        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            unittest.mock.sentinel.coro,
        )

        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.unregister_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ,
            )

        self.assertFalse(w)

    def test_register_iq_request_handler_raises_on_response_IQType(self):
        for member in structs.IQType:
            if member.is_request:
                self.stream.register_iq_request_handler(
                    member,
                    FancyTestIQ,
                    unittest.mock.sentinel.coro,
                )
            else:
                with self.assertRaisesRegex(
                        ValueError,
                        r".* is not a request IQType"):
                    self.stream.register_iq_request_handler(
                        member,
                        FancyTestIQ,
                        unittest.mock.sentinel.coro,
                    )

    def test_run_iq_request_coro_with_result(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_payload, response_iq = None, None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal response_payload
            response_payload = FancyTestIQ()
            return response_payload

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_iq = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(iq.to, response_iq.from_)
        self.assertEqual(iq.from_, response_iq.to)
        self.assertEqual(iq.id_, response_iq.id_)
        self.assertEqual(structs.IQType.RESULT, response_iq.type_)
        self.assertIs(response_payload, response_iq.payload)

        self.stream.stop()

    def test_run_iq_request_func_with_awaitable_result(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_payload, response_iq = None, None

        def handle_request(stanza):
            nonlocal response_payload
            response_payload = FancyTestIQ()
            fut = asyncio.Future()
            fut.set_result(response_payload)
            return fut

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_iq = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(iq.to, response_iq.from_)
        self.assertEqual(iq.from_, response_iq.to)
        self.assertEqual(iq.id_, response_iq.id_)
        self.assertEqual(structs.IQType.RESULT, response_iq.type_)
        self.assertIs(response_payload, response_iq.payload)

        self.stream.stop()

    def test_iq_request_without_handler_returns_service_unavailable(self):
        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            structs.IQType.ERROR,
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "service-unavailable"),
            response_got.error.condition
        )

        self.stream.stop()

    def test_run_iq_request_coro_with_generic_exception(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_got = None

        @asyncio.coroutine
        def handle_request(stanza):
            raise Exception("foo")

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            structs.IQType.ERROR,
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            response_got.error.condition
        )

        self.stream.stop()

    def test_run_iq_request_func_with_generic_exception(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_got = None

        def handle_request(stanza):
            raise Exception("foo")

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            structs.IQType.ERROR,
            response_got.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            response_got.error.condition
        )

        self.stream.stop()

    def test_run_iq_request_coro_with_xmpp_exception(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_got = None

        @asyncio.coroutine
        def handle_request(stanza):
            raise errors.XMPPWaitError(
                condition=(namespaces.stanzas, "gone"),
                text="foobarbaz",
            )

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            structs.IQType.ERROR,
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

    def test_run_iq_request_func_with_xmpp_exception(self):
        iq = make_test_iq()
        iq.autoset_id()

        response_got = None

        def handle_request(stanza):
            raise errors.XMPPWaitError(
                condition=(namespaces.stanzas, "gone"),
                text="foobarbaz",
            )

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        response_got = run_coroutine(self.sent_stanzas.get())
        self.assertEqual(
            structs.IQType.ERROR,
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

    def test_unregister_iq_request_handler_raises_if_none_was_registered(self):
        with self.assertRaises(KeyError):
            self.stream.unregister_iq_request_handler(
                structs.IQType.GET,
                FancyTestIQ)

    def test_unregister_iq_request_handler(self):
        iq = make_test_iq()
        iq.autoset_id()

        recvd = None

        @asyncio.coroutine
        def handle_request(stanza):
            nonlocal recvd
            recvd = stanza

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            handle_request)
        self.stream.unregister_iq_request_handler(
            structs.IQType.GET,
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
            structs.MessageType.CHAT,
            TEST_FROM,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    def test_run_message_callback_for_message_without_from(self):
        msg = make_test_message(from_=None)

        fut = asyncio.Future()

        self.stream.register_message_callback(
            structs.MessageType.CHAT,
            TEST_FROM.bare(),
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(msg, fut.result())

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_register_message_callback_casts_enum_and_warn(self):
        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.register_message_callback(
                "chat",
                None,
                unittest.mock.sentinel.cb,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaisesRegex(
                ValueError,
                r"only one listener allowed"):
            self.stream.register_message_callback(
                aioxmpp.structs.MessageType.CHAT,
                None,
                unittest.mock.sentinel.cb,
            )

    def test_register_message_callback_raises_on_string_type(self):
        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be MessageType, got .*"):
            self.stream.register_message_callback(
                "get",
                None,
                unittest.mock.sentinel.coro,
            )

    def test_register_message_callback_does_not_warn_on_enum(self):
        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.register_message_callback(
                structs.MessageType.CHAT,
                None,
                unittest.mock.sentinel.cb,
            )

        # the one warning is about the deprecation of register_message itself
        self.assertEqual(len(w), 1)

    def test_register_message_callback_rejects_duplicate_registration(self):
        self.stream.register_message_callback(
            structs.MessageType.CHAT,
            None,
            unittest.mock.sentinel.cb
        )

        with self.assertRaisesRegex(
                ValueError,
                r"only one listener allowed"):
            self.stream.register_message_callback(
                structs.MessageType.CHAT,
                None,
                unittest.mock.sentinel.cb,
            )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_unregister_message_callback_coro_casts_enum_and_warn(self):
        self.stream.register_message_callback(
            structs.MessageType.CHAT,
            None,
            unittest.mock.sentinel.cb,
        )

        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.unregister_message_callback(
                "chat",
                None,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaises(KeyError):
            self.stream.unregister_message_callback(
                structs.MessageType.CHAT,
                None,
            )

    def test_unregister_message_callback_raises_on_string_type(self):
        self.stream.register_message_callback(
            structs.MessageType.CHAT,
            None,
            unittest.mock.sentinel.cb,
        )

        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be MessageType, got .*"):
            self.stream.unregister_message_callback(
                "chat",
                None,
            )

    def test_unregister_message_callback_does_not_warn_on_enum(self):
        self.stream.register_message_callback(
            structs.MessageType.CHAT,
            None,
            unittest.mock.sentinel.cb,
        )

        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.unregister_message_callback(
                structs.MessageType.CHAT,
                None,
            )

        # the one warning is about the deprecation of unregister_message itself
        self.assertEqual(len(w), 1)

    def test_run_message_callback_from_wildcard(self):
        msg = make_test_message()

        fut = asyncio.Future()

        self.stream.register_message_callback(
            structs.MessageType.CHAT,
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
            structs.MessageType.CHAT, TEST_FROM,
            cb)

        self.stream.unregister_message_callback(
            structs.MessageType.CHAT,
            TEST_FROM
        )

        self.stream.start(self.xmlstream)

        msg = make_test_message(type_=structs.MessageType.CHAT,
                                from_=TEST_FROM)
        self.stream.recv_stanza(msg)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(cb.mock_calls)

    def test_run_presence_callback_from_wildcard(self):
        pres = make_test_presence()

        fut = asyncio.Future()

        self.stream.register_presence_callback(
            structs.PresenceType.AVAILABLE,
            None,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(pres)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(pres, fut.result())

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_register_presence_callback_casts_enum_and_warn(self):
        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.register_presence_callback(
                "probe",
                None,
                unittest.mock.sentinel.cb,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaisesRegex(
                ValueError,
                r"only one listener allowed"):
            self.stream.register_presence_callback(
                aioxmpp.structs.PresenceType.PROBE,
                None,
                unittest.mock.sentinel.cb,
            )

    def test_register_presence_callback_raises_on_string_type(self):
        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be PresenceType, got .*"):
            self.stream.register_presence_callback(
                "get",
                None,
                unittest.mock.sentinel.coro,
            )

    def test_register_presence_callback_does_not_warn_on_enum(self):
        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.register_presence_callback(
                structs.PresenceType.PROBE,
                None,
                unittest.mock.sentinel.cb,
            )

        # the one warning is about the deprecation of
        # register_presence_callback itself
        self.assertEqual(len(w), 1)

    def test_register_presence_callback_rejects_duplicate_registration(self):
        self.stream.register_presence_callback(
            structs.PresenceType.PROBE,
            None,
            unittest.mock.sentinel.cb
        )

        with self.assertRaisesRegex(
                ValueError,
                r"only one listener allowed"):
            self.stream.register_presence_callback(
                structs.PresenceType.PROBE,
                None,
                unittest.mock.sentinel.cb,
            )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_unregister_presence_callback_coro_casts_enum_and_warn(self):
        self.stream.register_presence_callback(
            structs.PresenceType.PROBE,
            None,
            unittest.mock.sentinel.cb,
        )

        self.stream._ALLOW_ENUM_COERCION = True
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"passing a non-enum value as type_ is deprecated and will "
                "be invalid as of aioxmpp 1.0") as ctx:
            self.stream.unregister_presence_callback(
                "probe",
                None,
            )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

        with self.assertRaises(KeyError):
            self.stream.unregister_presence_callback(
                structs.PresenceType.PROBE,
                None,
            )

    def test_unregister_presence_callback_raises_on_string_type(self):
        self.stream.register_presence_callback(
            structs.PresenceType.PROBE,
            None,
            unittest.mock.sentinel.cb,
        )

        if aioxmpp.version_info < (1, 0, 0):
            self.stream._ALLOW_ENUM_COERCION = False

        with self.assertRaisesRegex(
                TypeError,
                r"type_ must be PresenceType, got .*"):
            self.stream.unregister_presence_callback(
                "probe",
                None,
            )

    def test_unregister_presence_callback_does_not_warn_on_enum(self):
        self.stream.register_presence_callback(
            structs.PresenceType.PROBE,
            None,
            unittest.mock.sentinel.cb,
        )

        self.stream._ALLOW_ENUM_COERCION = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.stream.unregister_presence_callback(
                structs.PresenceType.PROBE,
                None,
            )

        # the one warning is about the deprecation of
        # unregister_presence_callback itself
        self.assertEqual(len(w), 1)

    def test_unregister_presence_callback(self):
        cb = unittest.mock.Mock()

        with self.assertRaises(KeyError):
            self.stream.unregister_presence_callback(
                structs.PresenceType.AVAILABLE,
                None
            )

        self.stream.register_presence_callback(
            structs.PresenceType.AVAILABLE,
            None, cb
        )

        self.stream.unregister_presence_callback(
            structs.PresenceType.AVAILABLE,
            None
        )

        self.stream.register_presence_callback(
            structs.PresenceType.SUBSCRIBE,
            TEST_FROM, cb
        )

        self.stream.unregister_presence_callback(
            structs.PresenceType.SUBSCRIBE,
            TEST_FROM
        )

        self.stream.start(self.xmlstream)

        msg = make_test_presence(type_=structs.PresenceType.SUBSCRIBE,
                                 from_=TEST_FROM)
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
        self.stream._enqueue(iq)

        iq_sent = run_coroutine(self.sent_stanzas.get())
        self.assertIs(iq, iq_sent)

        self.xmlstream.send_xso = unittest.mock.MagicMock(
            side_effect=RuntimeError())
        self.stream._enqueue(iq)
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
        self.stream._enqueue(iq)

        iq_sent = run_coroutine(self.sent_stanzas.get())
        self.assertIs(iq, iq_sent)

        self.xmlstream.send_xso = unittest.mock.MagicMock(
            side_effect=RuntimeError())
        self.stream._enqueue(iq)
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
        failure_handler = unittest.mock.Mock()
        failure_handler.return_value = None
        self.stream.on_failure.connect(failure_handler)

        self.assertFalse(self.stream.running)
        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertFalse(failure_handler.mock_calls)

    def test_close_after_error(self):
        caught_exc = None
        exc = Exception()

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

    def test_close_closes_iq_response_futures(self):
        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_FROM,
            "123",
            fut,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

        self.assertFalse(fut.done())

        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertTrue(fut.done())
        self.assertIsInstance(fut.exception(), ConnectionError)

    def test_close_closes_iq_response_futures_on_stopped_stream(self):
        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_FROM,
            "123",
            fut,
        )

        self.assertFalse(fut.done())

        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertTrue(fut.done())
        self.assertIsInstance(fut.exception(), ConnectionError)

    def test_close_cancels_running_iq_request_coroutines(self):
        exc = None
        running = False

        @asyncio.coroutine
        def coro(stanza):
            nonlocal exc, running
            running = True
            try:
                yield from asyncio.sleep(10)
            except Exception as inner_exc:
                exc = inner_exc
                raise

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            coro,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

        self.stream.recv_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(running)
        self.assertIsNone(exc)

        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertIsInstance(exc, asyncio.CancelledError)

    def test_close_cancels_running_iq_request_coroutines_on_stopped_stream(self):
        exc = None
        running = False

        @asyncio.coroutine
        def coro(stanza):
            nonlocal exc, running
            running = True
            try:
                yield from asyncio.sleep(10)
            except Exception as inner_exc:
                exc = inner_exc
                raise

        self.stream.register_iq_request_handler(
            structs.IQType.GET,
            FancyTestIQ,
            coro,
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

        self.stream.recv_stanza(make_test_iq())
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(running)
        self.assertIsNone(exc)

        run_coroutine(self.stream.wait_stop())

        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.running)

        self.assertIsInstance(exc, asyncio.CancelledError)

    def test_close_sets_active_stanza_tokens_to_aborted(self):
        get_mock = CoroutineMock()
        get_mock.delay = 1000
        # let’s mess with the processor a bit ...
        # otherwise, the stanza is sent before the close can happen
        with unittest.mock.patch.object(
                self.stream._active_queue,
                "get",
                new=get_mock):

            self.stream.start(self.xmlstream)
            run_coroutine(asyncio.sleep(0))
            self.assertTrue(self.stream.running)

            token = self.stream._enqueue(make_test_message())

            run_coroutine(self.stream.close())

        self.assertFalse(self.stream.running)

        self.assertEqual(token.state, stream.StanzaState.DISCONNECTED)

    def test_close_sets_active_stanza_tokens_to_aborted_on_stopped_stream(self):
        get_mock = CoroutineMock()
        get_mock.delay = 1000
        # let’s mess with the processor a bit ...
        # otherwise, the stanza is sent before the close can happen
        with unittest.mock.patch.object(
                self.stream._active_queue,
                "get",
                new=get_mock):

            token = self.stream._enqueue(make_test_message())

            run_coroutine(self.stream.close())

        self.assertFalse(self.stream.running)

        self.assertEqual(token.state, stream.StanzaState.DISCONNECTED)

    def test_enqueue_raises_after_close(self):
        run_coroutine(self.stream.close())

        with self.assertRaisesRegex(ConnectionError, r"close\(\) called"):
            self.stream._enqueue(unittest.mock.sentinel.stanza)

    def test_enqueue_works_after_close_and_start(self):
        run_coroutine(self.stream.close())

        iq = make_test_iq(type_=structs.IQType.GET)

        self.stream.start(self.xmlstream)
        self.stream._enqueue(iq)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIs(obj, iq)

        self.stream.stop()

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
            self.stream._enqueue(
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

    def test_enqueue_returns_token(self):
        token = self.stream._enqueue(make_test_iq())
        self.assertIsInstance(
            token,
            stream.StanzaToken)

    def test_abort_stanza(self):
        iqs = [make_test_iq() for i in range(3)]
        self.stream.start(self.xmlstream)
        tokens = [self.stream._enqueue(iq) for iq in iqs]
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

    def test_send_iq_and_wait_for_reply_uses_send(self):
        with contextlib.ExitStack() as stack:
            send = stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "send",
                new=CoroutineMock()
            ))
            send.return_value = unittest.mock.sentinel.result

            result = run_coroutine(self.stream.send_iq_and_wait_for_reply(
                unittest.mock.sentinel.iq,
                timeout=unittest.mock.sentinel.timeout,
            ))

        send.assert_called_once_with(
            unittest.mock.sentinel.iq,
            timeout=unittest.mock.sentinel.timeout,
        )

        self.assertEqual(result, unittest.mock.sentinel.result)

    def test_send_iq_and_wait_for_reply_emits_deprecation_warning(self):
        with contextlib.ExitStack() as stack:
            send = stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "send",
                new=CoroutineMock()
            ))

            task = asyncio.ensure_future(self.stream.send_iq_and_wait_for_reply(
                unittest.mock.sentinel.iq
            ))
            with self.assertWarnsRegex(
                    DeprecationWarning,
                    r"send_iq_and_wait_for_reply is deprecated and will be "
                    r"removed in 1.0"):
                run_coroutine(asyncio.sleep(0))

            task.cancel()

    def test_flush_incoming(self):
        iqs = [make_test_iq(type_=structs.IQType.RESULT) for i in range(2)]
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
                self.stream._send_immediately(iq)
            ))

    def _test_inbound_presence_filter(self, filter_attr, **register_kwargs):
        pres = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE)
        out = stanza.Presence(type_=structs.PresenceType.AVAILABLE)

        cb = unittest.mock.Mock([])
        cb.return_value = None

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.register_presence_callback(
            structs.PresenceType.AVAILABLE,
            None, cb
        )

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
        msg = stanza.Message(
            type_=structs.MessageType.CHAT,
            from_=TEST_FROM
        )
        out = stanza.Message(
            type_=structs.MessageType.GROUPCHAT,
            from_=TEST_FROM
        )

        cb = unittest.mock.Mock([])
        cb.return_value = None

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.register_message_callback(
            structs.MessageType.GROUPCHAT,
            None, cb
        )

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

        msg = stanza.Message(structs.MessageType.CHAT)

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
        pres = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE)
        pres.autoset_id()
        out = stanza.Presence(type_=structs.PresenceType.AVAILABLE)

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.start(self.xmlstream)
        token = self.stream._enqueue(pres)

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

        token = self.stream._enqueue(pres)

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
        self.stream._enqueue(pres)

        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call.app(pres),
                unittest.mock.call.service(pres)
            ],
            mock.mock_calls
        )

    def _test_outbound_message_filter(self, filter_attr, **register_kwargs):
        msg = stanza.Message(type_=structs.MessageType.CHAT)
        msg.autoset_id()
        out = stanza.Message(type_=structs.MessageType.GROUPCHAT)

        filter_func = unittest.mock.Mock()
        filter_func.return_value = out

        filter_attr.register(filter_func, **register_kwargs)

        self.stream.start(self.xmlstream)
        token = self.stream._enqueue(msg)

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

        token = self.stream._enqueue(msg)

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

        msg = stanza.Message(structs.MessageType.CHAT)
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
        self.stream._enqueue(msg)

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

        self.stream._enqueue(msg)

        self.xmlstream.on_closing(None)

        run_coroutine(asyncio.sleep(0))

        # we expect the stream to wait with the failure until it gets told the
        # actual problem by the XML stream through the on_failure callback
        self.assertFalse(self.stream.running)

        self.assertFalse(failure_handler.mock_calls)

    def test_handle_PayloadParsingError_at_iq_with_error_response(self):
        iq = make_test_iq()
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.IQ
        )
        self.assertEqual(
            obj.type_,
            structs.IQType.ERROR
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
        iq = make_test_iq(type_=structs.IQType.ERROR)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_PayloadParsingError_at_result_iq(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_PayloadParsingError_at_message_with_error_response(self):
        msg = make_test_message()
        msg.autoset_id()
        self.stream.recv_erroneous_stanza(
            msg,
            stanza.PayloadParsingError(msg, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.Message
        )
        self.assertEqual(
            obj.type_,
            structs.MessageType.ERROR
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
        msg = make_test_message(type_=structs.MessageType.ERROR)
        self.stream.recv_erroneous_stanza(
            msg,
            stanza.PayloadParsingError(msg, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_PayloadParsingError_at_presence_with_error_response(self):
        pres = make_test_presence()
        pres.autoset_id()
        self.stream.recv_erroneous_stanza(
            pres,
            stanza.PayloadParsingError(pres, ('end', 'foo'), None),
        )

        run_coroutine(asyncio.sleep(0.01))

        self.stream.start(self.xmlstream)

        obj = run_coroutine(self.sent_stanzas.get())
        self.assertIsInstance(
            obj,
            stanza.Presence
        )
        self.assertEqual(
            obj.type_,
            structs.PresenceType.ERROR
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
        pres = make_test_presence(type_=structs.PresenceType.ERROR)
        self.stream.recv_erroneous_stanza(
            pres,
            stanza.PayloadParsingError(pres, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_handle_UnknownIQPayload_at_iq_with_error_response(self):
        iq = make_test_iq()
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'), None)
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
            structs.IQType.ERROR,
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
            (namespaces.stanzas, "service-unavailable")
        )

    def test_ignore_UnknownIQPayload_at_error_iq(self):
        iq = make_test_iq(type_=structs.IQType.ERROR)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_UnknownIQPayload_at_result_iq(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_UnknownIQPayload_at_stanza_with_broken_type(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)
        aioxmpp.IQ.type_.mark_incomplete(iq)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.UnknownIQPayload(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_do_not_respond_to_PayloadParsingError_at_stanza_with_broken_type(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)
        aioxmpp.IQ.type_.mark_incomplete(iq)
        self.stream.recv_erroneous_stanza(
            iq,
            stanza.PayloadParsingError(iq, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0.01))

        with self.assertRaises(asyncio.QueueEmpty):
            self.sent_stanzas.get_nowait()

    def test_also_map_iq_from_bare_local_jid_to_None(self):
        iq = make_test_iq(from_=TEST_FROM.bare(), type_=structs.IQType.RESULT)
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

    def test_map_iq_from_None_to_bare_local_jid(self):
        iq = make_test_iq(from_=None, type_=structs.IQType.RESULT)
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_callback(
            TEST_FROM.bare(),
            iq.id_,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(iq, fut.result())

    def test_working_iq_from_bare_local_jid(self):
        iq = make_test_iq(from_=TEST_FROM.bare(), type_=structs.IQType.RESULT)
        iq.autoset_id()

        fut = asyncio.Future()

        self.stream.register_iq_response_callback(
            TEST_FROM.bare(),
            iq.id_,
            fut.set_result)
        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(iq)

        run_coroutine(fut)

        self.stream.stop()

        self.assertIs(iq, fut.result())

    def test_unicast_error_on_erroneous_iq_result(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_TO,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErroneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_unicast_error_on_erroneous_iq_result_where_from_is_None(self):
        req = make_test_iq(to=None)
        resp = req.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            None,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErroneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_unicast_error_on_erroneous_iq_error(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.ERROR)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            TEST_TO,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErroneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_unicast_error_on_erroneous_iq_error_where_from_is_None(self):
        req = make_test_iq(to=None)
        resp = req.make_reply(type_=structs.IQType.ERROR)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        fut = asyncio.Future()
        self.stream.register_iq_response_future(
            None,
            req.id_,
            fut)

        self.stream.start(self.xmlstream)
        with self.assertRaises(errors.ErroneousStanza) as ctx:
            run_coroutine(fut)

        self.assertIs(ctx.exception.partial_obj, resp)

    def test_do_not_crash_on_unsolicited_erroneous_iq_response(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_do_not_crash_on_iq_response_with_broken_from(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)
        aioxmpp.IQ.from_.mark_incomplete(resp)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_do_not_crash_on_iq_response_with_broken_type(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)
        aioxmpp.IQ.type_.mark_incomplete(resp)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_do_not_crash_on_iq_response_with_broken_id(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)
        aioxmpp.IQ.id_.mark_incomplete(resp)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_do_not_crash_on_iq_response_with_broken_to(self):
        req = make_test_iq(to=TEST_TO)
        resp = req.make_reply(type_=structs.IQType.RESULT)
        aioxmpp.IQ.to.mark_incomplete(resp)

        self.stream.recv_erroneous_stanza(
            resp,
            stanza.UnknownIQPayload(resp, ('end', 'foo'), None)
        )

        self.stream.start(self.xmlstream)

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.stream.running)

    def test_task_crash_leads_to_closing_of_xmlstream(self):
        base_timeout = get_timeout(0.01)

        self.stream.ping_interval = timedelta(
            seconds=base_timeout
        )
        self.stream.ping_opportunistic_interval = timedelta(
            seconds=base_timeout
        )

        self.stream.start(self.xmlstream)
        run_coroutine(asyncio.sleep(base_timeout * 2.5))

        self.sent_stanzas.get_nowait()
        run_coroutine(asyncio.sleep(base_timeout))

        self.assertFalse(self.stream.running)
        self.xmlstream.close.assert_called_with()

    def test_done_handler_can_deal_with_exception_from_abort(self):
        base_timeout = get_timeout(0.01)

        class FooException(Exception):
            pass

        exc = None

        def failure_handler(_exc):
            nonlocal exc
            exc = _exc

        self.stream.ping_interval = timedelta(
            seconds=base_timeout
        )
        self.stream.ping_opportunistic_interval = timedelta(
            seconds=base_timeout
        )
        self.stream.on_failure.connect(failure_handler)

        self.stream.start(self.xmlstream)
        self.xmlstream.close.side_effect = FooException()
        run_coroutine(asyncio.sleep(base_timeout * 2.5))

        self.sent_stanzas.get_nowait()
        run_coroutine(asyncio.sleep(base_timeout))

        self.assertIsInstance(
            exc,
            ConnectionError
        )

        self.assertFalse(self.stream.running)
        self.xmlstream.close.assert_called_with()

    def test_send_and_wait_for_sent_awaits_token(self):
        iq = make_test_iq()

        base = unittest.mock.Mock()
        base._enqueue = CoroutineMock()
        base._enqueue.return_value = \
            unittest.mock.sentinel.token_await_result
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            run_coroutine(self.stream.send_and_wait_for_sent(
                iq
            ))

        base._enqueue.assert_called_with(unittest.mock.ANY)

    def test_send_and_wait_for_sent_emits_deprecation_warning(self):
        iq = make_test_iq()

        task = asyncio.ensure_future(self.stream.send_and_wait_for_sent(iq))
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"send_and_wait_for_sent is deprecated and will be removed in 1.0"):
            run_coroutine(asyncio.sleep(0))
        task.cancel()

    def test_send_awaits_stanza_token_for_presence(self):
        pres = make_test_presence()

        base = unittest.mock.Mock()
        base._enqueue = CoroutineMock()
        base._enqueue.return_value = \
            unittest.mock.sentinel.token_await_result
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "register_iq_response_future",
                new=base.register_iq_response_future,
            ))

            run_coroutine(self.stream._send_immediately(pres))

        base.register_iq_response_future.assert_not_called()
        base._enqueue.assert_called_with(unittest.mock.ANY)

    def test_send_awaits_stanza_token_for_message(self):
        message = make_test_presence()

        base = unittest.mock.Mock()
        base._enqueue = CoroutineMock()
        base._enqueue.return_value = \
            unittest.mock.sentinel.token_await_result
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "register_iq_response_future",
                new=base.register_iq_response_future,
            ))

            run_coroutine(self.stream._send_immediately(message))

        base.register_iq_response_future.assert_not_called()
        base._enqueue.assert_called_with(unittest.mock.ANY)

    def test_send_awaits_stanza_token_for_iq_response(self):
        iq = make_test_iq(type_=aioxmpp.IQType.RESULT)

        base = unittest.mock.Mock()
        base._enqueue = CoroutineMock()
        base._enqueue.return_value = \
            unittest.mock.sentinel.token_await_result
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "register_iq_response_future",
                new=base.register_iq_response_future,
            ))

            run_coroutine(self.stream._send_immediately(iq))

        base.register_iq_response_future.assert_not_called()
        base._enqueue.assert_called_with(unittest.mock.ANY)

    def test_send_awaits_stanza_token_for_iq_and_registers_for_reply(self):
        iq = make_test_iq()
        response = iq.make_reply(type_=structs.IQType.RESULT)
        response.payload = FancyTestIQ()

        stanza_fut = asyncio.Future()

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(iq))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            stanza_fut.set_result(None)

            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())

            listener.data(response)

            payload = run_coroutine(task)

        self.assertIs(payload, response.payload)

    def test_send_raises_error_from_iq_reply(self):
        exc = Exception()

        iq = make_test_iq()

        stanza_fut = asyncio.Future()

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(iq))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            stanza_fut.set_result(None)

            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())

            listener.error(exc)

            with self.assertRaises(Exception) as ctx:
                run_coroutine(task)
            self.assertIs(ctx.exception, exc)

    def test_send_raises_stanza_error_from_reply(self):
        iq = make_test_iq()
        iq.autoset_id()
        reply = iq.make_reply(type_=structs.IQType.ERROR)
        reply.error = stanza.Error(
            condition=(namespaces.stanzas, "remote-server-not-found"),
            text="foo",
        )

        exc = Exception()

        stanza_fut = asyncio.Future()

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(iq))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            stanza_fut.set_result(None)

            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())

            listener.data(reply)

            with self.assertRaises(errors.XMPPCancelError) as ctx:
                run_coroutine(task)

            self.assertEqual(ctx.exception.condition,
                             (namespaces.stanzas, "remote-server-not-found"))
            self.assertEqual(ctx.exception.text, "foo")

    def test_send_timeout_affects_iq_reply(self):
        iq = make_test_iq()

        stanza_fut = asyncio.Future()

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(
                iq,
                timeout=0.001))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)

            stanza_fut.set_result(None)

            with self.assertRaises(TimeoutError):
                run_coroutine(task)

    def test_send_invalidates_listener_if_enqueue_fails(self):
        iq = make_test_iq()
        exc = Exception()

        stanza_fut = asyncio.Future()

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(
                iq,
                timeout=0.001))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            stanza_fut.set_exception(exc)

            with self.assertRaises(Exception) as ctx:
                run_coroutine(task)

            self.assertIs(ctx.exception, exc)

            self.assertFalse(listener.is_valid())

    def test_send_does_not_kill_stream_on_reply_when_cancelled(self):
        iq = make_test_iq()
        response = iq.make_reply(type_=structs.IQType.RESULT)
        response.payload = FancyTestIQ()

        stanza_fut = asyncio.Future()
        stanza_fut.set_result(None)

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(iq))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                run_coroutine(task)

            listener.data(response)

    def test_send_does_not_kill_stream_on_error_when_cancelled(self):
        iq = make_test_iq()
        exc = Exception()

        stanza_fut = asyncio.Future()
        stanza_fut.set_result(None)

        base = unittest.mock.Mock()
        base._enqueue.return_value = stanza_fut
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_enqueue",
                new=base._enqueue
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "_iq_response_map",
                new=base.iq_response_map,
            ))

            task = asyncio.ensure_future(self.stream._send_immediately(iq))
            run_coroutine(asyncio.sleep(0.01))

            self.assertFalse(task.done())
            base._enqueue.assert_called_with(unittest.mock.ANY)
            base.iq_response_map.add_listener.assert_called_once_with(
                (iq.to, iq.id_),
                unittest.mock.ANY,
            )

            _, (_, listener), _ = \
                base.iq_response_map.add_listener.mock_calls[0]

            task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                run_coroutine(task)

            listener.error(exc)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_handle_non_connection_exception_from_send_xso(self):
        msg = make_test_message()

        class FooException(Exception):
            pass

        exc = FooException()

        self.xmlstream.send_xso = unittest.mock.Mock()
        self.xmlstream.send_xso.side_effect = exc

        self.stream.start(self.xmlstream)
        token = self.stream._enqueue(msg)
        self.assertEqual(token.state, stream.StanzaState.ACTIVE)

        run_coroutine(asyncio.sleep(0.05))
        self.assertTrue(self.stream.running)

        self.assertEqual(token.state, stream.StanzaState.FAILED)

        with self.assertRaises(FooException):
            run_coroutine(token)

    def test_emit_on_message_received_event(self):
        msg = make_test_message()
        fut = asyncio.Future()

        self.stream.on_message_received.connect(
            fut,
            self.stream.on_message_received.AUTO_FUTURE
        )

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(msg)

        self.assertIs(run_coroutine(fut), msg)

    def test_emit_on_presence_received_event(self):
        pres = make_test_presence()
        fut = asyncio.Future()

        self.stream.on_presence_received.connect(
            fut,
            self.stream.on_presence_received.AUTO_FUTURE
        )

        self.stream.start(self.xmlstream)
        self.stream.recv_stanza(pres)

        self.assertIs(run_coroutine(fut), pres)

    def test_register_message_callback_calls_to_message_dispatcher(self):
        with unittest.mock.patch.object(
                self.message_dispatcher,
                "register_callback") as register_callback:
            with self.assertWarnsRegex(
                    DeprecationWarning,
                    "register_message_callback is deprecated; "
                    "use aioxmpp.dispatcher.SimpleMessageDispatcher "
                    "instead") as ctx:
                self.stream.register_message_callback(
                    aioxmpp.MessageType.CHAT,
                    unittest.mock.sentinel.from_,
                    unittest.mock.sentinel.cb,
                )

        register_callback.assert_called_once_with(
            aioxmpp.MessageType.CHAT,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

    def test_unregister_message_callback_calls_to_message_dispatcher(self):
        with unittest.mock.patch.object(
                self.message_dispatcher,
                "unregister_callback") as unregister_callback:
            with self.assertWarnsRegex(
                    DeprecationWarning,
                    "unregister_message_callback is deprecated; "
                    "use aioxmpp.dispatcher.SimpleMessageDispatcher "
                    "instead") as ctx:
                self.stream.unregister_message_callback(
                    aioxmpp.MessageType.CHAT,
                    unittest.mock.sentinel.from_,
                )

        unregister_callback.assert_called_once_with(
            aioxmpp.MessageType.CHAT,
            unittest.mock.sentinel.from_,
        )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

    def test_register_presence_callback_calls_to_presence_dispatcher(self):
        with unittest.mock.patch.object(
                self.presence_dispatcher,
                "register_callback") as register_callback:
            with self.assertWarnsRegex(
                    DeprecationWarning,
                    "register_presence_callback is deprecated; "
                    "use aioxmpp.dispatcher.SimplePresenceDispatcher "
                    "or aioxmpp.PresenceClient instead") as ctx:
                self.stream.register_presence_callback(
                    aioxmpp.PresenceType.AVAILABLE,
                    unittest.mock.sentinel.from_,
                    unittest.mock.sentinel.cb,
                )

        register_callback.assert_called_once_with(
            aioxmpp.PresenceType.AVAILABLE,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

    def test_unregister_presence_callback_calls_to_presence_dispatcher(self):
        with unittest.mock.patch.object(
                self.presence_dispatcher,
                "unregister_callback") as unregister_callback:
            with self.assertWarnsRegex(
                    DeprecationWarning,
                    "unregister_presence_callback is deprecated; "
                    "use aioxmpp.dispatcher.SimplePresenceDispatcher "
                    "or aioxmpp.PresenceClient instead") as ctx:
                self.stream.unregister_presence_callback(
                    aioxmpp.PresenceType.AVAILABLE,
                    unittest.mock.sentinel.from_,
                )

        unregister_callback.assert_called_once_with(
            aioxmpp.PresenceType.AVAILABLE,
            unittest.mock.sentinel.from_,
        )

        self.assertIn(
            "test_stream.py",
            ctx.filename,
        )

    def test_send_rejects_cb_argument_for_messages(self):
        msg = make_test_message()

        self.stream.start(self.xmlstream)

        with self.assertRaisesRegex(
                ValueError,
                r"cb not supported with non-IQ non-request stanzas"):
            run_coroutine(self.stream._send_immediately(
                msg,
                cb=unittest.mock.sentinel.cb))

        self.assertTrue(self.sent_stanzas.empty())

    def test_send_rejects_cb_argument_for_presences(self):
        pres = make_test_presence()

        self.stream.start(self.xmlstream)

        with self.assertRaisesRegex(
                ValueError,
                r"cb not supported with non-IQ non-request stanzas"):
            run_coroutine(self.stream._send_immediately(
                pres,
                cb=unittest.mock.sentinel.cb))

        self.assertTrue(self.sent_stanzas.empty())

    def test_send_rejects_cb_argument_for_iq_responses(self):
        iq = make_test_iq(type_=structs.IQType.RESULT)

        self.stream.start(self.xmlstream)

        with self.assertRaisesRegex(
                ValueError,
                r"cb not supported with non-IQ non-request stanzas"):
            run_coroutine(self.stream._send_immediately(
                iq,
                cb=unittest.mock.sentinel.cb))

        self.assertTrue(self.sent_stanzas.empty())

    def test_send_awaits_cb_result_and_returns_result(self):
        cb = unittest.mock.Mock()
        cb.return_value = asyncio.Future()

        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)

        task = asyncio.ensure_future(self.stream._send_immediately(iq, cb=cb))

        run_coroutine(self.sent_stanzas.get())
        self.assertFalse(task.done())
        cb.assert_not_called()

        reply = iq.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_stanza(reply)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(task.done())
        cb.assert_called_once_with(reply)

        cb.return_value.set_result(unittest.mock.sentinel.result)

        result = run_coroutine(task)

        self.assertEqual(
            result,
            unittest.mock.sentinel.result,
        )

    def test_send_awaits_cb_result_and_reraises_exception(self):
        class FooException(Exception):
            pass

        exc = FooException()

        cb = unittest.mock.Mock()
        cb.return_value = asyncio.Future()

        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)

        task = asyncio.ensure_future(self.stream._send_immediately(iq, cb=cb))

        run_coroutine(self.sent_stanzas.get())
        self.assertFalse(task.done())
        cb.assert_not_called()

        reply = iq.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_stanza(reply)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(task.done())
        cb.assert_called_once_with(reply)

        cb.return_value.set_exception(exc)

        with self.assertRaises(FooException):
            run_coroutine(task)

    def test_send_reraises_exception_from_cb(self):
        class FooException(Exception):
            pass

        exc = FooException()

        cb = unittest.mock.Mock()
        cb.side_effect = exc

        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)

        task = asyncio.ensure_future(self.stream._send_immediately(iq, cb=cb))

        run_coroutine(self.sent_stanzas.get())
        self.assertFalse(task.done())
        cb.assert_not_called()

        reply = iq.make_reply(type_=structs.IQType.RESULT)

        self.stream.recv_stanza(reply)

        run_coroutine(asyncio.sleep(0))

        cb.assert_called_once_with(reply)
        self.assertTrue(task.done())

        with self.assertRaises(FooException):
            run_coroutine(task)

    def test_send_awaits_cb_result_and_returns_result_for_stanza_errors(self):
        cb = unittest.mock.Mock()
        cb.return_value = asyncio.Future()

        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)

        task = asyncio.ensure_future(self.stream._send_immediately(iq, cb=cb))

        run_coroutine(self.sent_stanzas.get())
        self.assertFalse(task.done())
        cb.assert_not_called()

        reply = iq.make_reply(type_=structs.IQType.ERROR)

        self.stream.recv_stanza(reply)

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(task.done())
        cb.assert_called_once_with(reply)

        cb.return_value.set_result(unittest.mock.sentinel.result)

        result = run_coroutine(task)

        self.assertEqual(
            result,
            unittest.mock.sentinel.result,
        )

    def test_send_returns_normal_result_if_cb_returns_None(self):
        cb = unittest.mock.Mock()
        cb.return_value = None

        iq = make_test_iq()
        iq.autoset_id()

        self.stream.start(self.xmlstream)

        task = asyncio.ensure_future(self.stream._send_immediately(iq, cb=cb))

        run_coroutine(self.sent_stanzas.get())
        self.assertFalse(task.done())
        cb.assert_not_called()

        reply = iq.make_reply(type_=structs.IQType.RESULT)
        reply.payload = FancyTestIQ()

        self.stream.recv_stanza(reply)

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(task.done())
        cb.assert_called_once_with(reply)

        result = run_coroutine(task)

        self.assertIs(
            result,
            reply.payload,
        )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_register_iq_request_coro_warns_and_forwards_to_handler(self):
        with contextlib.ExitStack() as stack:
            handler = stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "register_iq_request_handler",
            ))

            stack.enter_context(
                self.assertWarnsRegex(
                    DeprecationWarning,
                    r"register_iq_request_coro is a deprecated alias to "
                    r"register_iq_request_handler and will be removed in "
                    r"aioxmpp 1.0")
            )

            result = self.stream.register_iq_request_coro(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.payload_class,
                unittest.mock.sentinel.coro,
            )

        handler.assert_called_once_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.payload_class,
            unittest.mock.sentinel.coro,
        )

        self.assertEqual(result, handler())

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "not applying to this version of aioxmpp")
    def test_unregister_iq_request_coro_warns_and_forwards_to_handler(self):
        with contextlib.ExitStack() as stack:
            handler = stack.enter_context(unittest.mock.patch.object(
                self.stream,
                "unregister_iq_request_handler",
            ))

            stack.enter_context(
                self.assertWarnsRegex(
                    DeprecationWarning,
                    r"unregister_iq_request_coro is a deprecated alias to "
                    r"unregister_iq_request_handler and will be removed in "
                    r"aioxmpp 1.0")
            )

            result = self.stream.unregister_iq_request_coro(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.payload_class,
            )

        handler.assert_called_once_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.payload_class,
        )

        self.assertEqual(result, handler())


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
        with self.assertRaisesRegex(RuntimeError, "is not running"):
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

    def test_start_sm_with_resumption_timeout(self):
        self.assertFalse(self.stream.sm_enabled)

        # we need interaction here to show that SM gets negotiated
        xmlstream = XMLStreamMock(self, loop=self.loop)

        self.stream.start(xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(request_resumption=True,
                                 resumption_timeout=1000),
            xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=True, max_=1000),
                        response=XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                            id_="foobar",
                                            location=("fe80::", 5222),
                                            max_=900)
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
            900,
            self.stream.sm_max
        )
        self.assertTrue(self.stream.sm_resumable)

        self.established_rec.assert_called_once_with()

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_start_sm_aliases_resumption_timeout_0_to_disabled(self):
        self.assertFalse(self.stream.sm_enabled)

        # we need interaction here to show that SM gets negotiated
        xmlstream = XMLStreamMock(self, loop=self.loop)

        self.stream.start(xmlstream)

        run_coroutine_with_peer(
            self.stream.start_sm(request_resumption=True,
                                 resumption_timeout=0),
            xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMEnable(resume=False),
                        response=XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=False,
                                            id_="foobar")
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
        self.assertIsNone(
            self.stream.sm_location
        )
        self.assertIsNone(
            self.stream.sm_max
        )
        self.assertFalse(self.stream.sm_resumable)

        self.established_rec.assert_called_once_with()

        self.stream.stop()
        run_coroutine(asyncio.sleep(0))

        self.assertTrue(self.destroyed_rec.mock_calls)

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
        error_iq = iq.make_reply(type_=structs.IQType.ERROR)
        error_iq.error = stanza.Error(
            condition=(namespaces.stanzas, "service-unavailable")
        )

        iq_sent = make_test_iq()

        @asyncio.coroutine
        def starter():
            sm_start_future = asyncio.ensure_future(self.stream.start_sm())
            self.stream._enqueue(iq_sent)

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
        with self.assertRaisesRegex(RuntimeError, "is not enabled"):
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
            self.stream._enqueue(
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

    def test_sm_outbound_counter_overflow(self):
        state_change_handler = unittest.mock.MagicMock()
        iqs = [make_test_iq() for i in range(3)]

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        tokens = [
            self.stream._enqueue(
                iq, on_state_change=state_change_handler)
            for iq in iqs]

        run_coroutine(asyncio.sleep(0))
        self.stream._sm_outbound_base = 0xfffffffe

        self.assertEqual(
            0xfffffffe,
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

        self.stream.sm_ack(0xffffffff)
        self.assertEqual(
            0xffffffff,
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

        self.stream.sm_ack(0xffffffff)
        self.assertEqual(
            0xffffffff,
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

        self.stream.sm_ack(1)
        self.assertEqual(
            1,
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
            iq.make_reply(type_=structs.IQType.ERROR)
            for iq in iqs
        ]
        for err_iq in error_iqs:
            err_iq.error = stanza.Error(
                condition=(namespaces.stanzas, "service-unavailable")
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

    def test_sm_inbound_counter_overflow(self):
        iqs = [make_test_iq() for i in range(3)]

        error_iqs = [
            iq.make_reply(type_=structs.IQType.ERROR)
            for iq in iqs
        ]
        for err_iq in error_iqs:
            err_iq.error = stanza.Error(
                condition=(namespaces.stanzas, "service-unavailable")
            )

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.stream._sm_inbound_ctr = 0xffffffff
        self.stream.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            0,
            self.stream.sm_inbound_ctr
        )

        self.stream.recv_stanza(iqs.pop())
        self.stream.recv_stanza(iqs.pop())
        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            2,
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
            self.stream._enqueue(iq)

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
        self.stream._enqueue(additional_iq)

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

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            ConnectionError,
        )
        self.assertRegex(
            str(exc),
            r"stream management disabled"
        )

    def test_sm_resume_overflow(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        for iq in iqs:
            self.stream._enqueue(iq)

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.established_rec.reset_mock()

        self.stream._sm_outbound_base = 0xfffffffe
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(iqs[0]),
            XMLStreamMock.Send(iqs[1]),
            XMLStreamMock.Send(iqs[2]),
            XMLStreamMock.Send(
                nonza.SMRequest(),
                response=XMLStreamMock.Receive(
                    nonza.SMAcknowledgement(counter=0xffffffff)
                )
            )
        ]))

        self.stream.stop()

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.destroyed_rec.mock_calls)

        # enqueue a stanza before resumption and check that the sequence is
        # correct (resumption-generated stanzas before new stanzas)
        self.stream._enqueue(additional_iq)

        run_coroutine_with_peer(
            self.stream.resume_sm(self.xmlstream),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(previd="foobar",
                                   counter=0),
                    response=XMLStreamMock.Receive(
                        nonza.SMResumed(previd="foobar",
                                        counter=0)
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

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            ConnectionError,
        )
        self.assertRegex(
            str(exc),
            r"stream management disabled"
        )

    def test_sm_race(self):
        iqs = [make_test_iq() for i in range(4)]

        additional_iq = iqs.pop()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        for iq in iqs:
            self.stream._enqueue(iq)

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
        self.stream._enqueue(additional_iq)

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
        with self.assertRaisesRegex(RuntimeError, "is running"):
            run_coroutine(self.stream.resume_sm(self.xmlstream))

    def test_sm_stop_requires_stopped_stream(self):
        self.stream.start_sm()
        self.stream.start(self.xmlstream)
        with self.assertRaisesRegex(RuntimeError, "is running"):
            self.stream.stop_sm()

    def test_sm_stop_requires_enabled_sm(self):
        with self.assertRaisesRegex(RuntimeError, "not enabled"):
            self.stream.stop_sm()

    def test_sm_start_requires_disabled_sm(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        with self.assertRaisesRegex(RuntimeError,
                                    "Stream Management already enabled"):
            run_coroutine(self.stream.start_sm())

    def test_sm_resume_requires_enabled_sm(self):
        with self.assertRaisesRegex(RuntimeError, "not enabled"):
            run_coroutine(self.stream.resume_sm(self.xmlstream))

    def test_sm_ack_too_many_stanzas_acked(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        with self.assertRaises(errors.StreamNegotiationFailure):
            self.stream.sm_ack(1)

    def test_stop_sm(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )
        self.stream.stop()
        run_coroutine(asyncio.sleep(0))
        self.stream.stop_sm()

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            ConnectionError,
        )
        self.assertRegex(
            str(exc),
            r"stream management disabled"
        )

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

        with self.assertRaisesRegex(ValueError,
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

        tokens = [self.stream._enqueue(iq) for iq in iqs]

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

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) .*called"
        )

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
                XMLStreamMock.Send(
                    nonza.SMAcknowledgement()
                ),
                XMLStreamMock.Close()
            ])
        )

        self.assertFalse(self.stream.sm_enabled)

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) called"
        )

    def test_close_deletes_sm_state_even_while_stopped(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.established_rec.assert_called_once_with()

        run_coroutine(self.stream.wait_stop())
        self.assertTrue(self.stream.sm_enabled)

        run_coroutine(self.stream.close())
        self.assertFalse(self.stream.sm_enabled)

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) called"
        )

    def test_close_sends_sm_ack(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.established_rec.assert_called_once_with()

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMAcknowledgement(),
                ),
                XMLStreamMock.Close()
            ])
        )

        self.assertFalse(self.stream.sm_enabled)

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) called"
        )

    def test_close_discards_sm_state_on_exception_during_close_if_resumable(self):
        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.established_rec.assert_called_once_with()

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        nonza.SMAcknowledgement()
                    ),
                    XMLStreamMock.Close()
                ],
                stimulus=XMLStreamMock.Fail(ConnectionError())
            )
        )

        self.assertFalse(self.stream.sm_enabled)

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) called"
        )

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
                    XMLStreamMock.Send(
                        nonza.SMAcknowledgement()
                    ),
                    XMLStreamMock.Close(
                        response=[
                            XMLStreamMock.Fail(ConnectionError())
                        ]
                    )
                ],
            )
        )

        self.assertFalse(self.stream.sm_enabled)

        self.destroyed_rec.assert_called_once_with(unittest.mock.ANY)
        _, (exc,), _ = self.destroyed_rec.mock_calls[0]
        self.assertIsInstance(
            exc,
            stream.DestructionRequested,
        )
        self.assertRegex(
            str(exc),
            r"close\(\) .*called"
        )

    def test_unprocessed_outgoing_stanza_does_not_get_lost_after_stop(self):
        pres = make_test_presence()
        pres.autoset_id()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.stream.stop()

        self.stream._enqueue(pres)

        self.assertIs(
            pres,
            run_coroutine(self.stream._active_queue.get()).stanza
        )

    def test_rescue_unprocessed_outgoing_stanza_on_stop(self):
        pres = make_test_presence()
        pres.autoset_id()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        self.stream._enqueue(pres)
        self.stream.stop()

        self.assertIs(
            pres,
            run_coroutine(self.stream._active_queue.get()).stanza
        )

    def test_close_sets_sent_stanza_tokens_to_sent_without_sm(self):
        pres = make_test_presence()
        pres.autoset_id()

        self.stream.start(self.xmlstream)
        run_coroutine_with_peer(
            self.stream.start_sm(),
            self.xmlstream.run_test(self.successful_sm)
        )

        token = self.stream._enqueue(pres)

        run_coroutine_with_peer(
            self.stream.close(),
            self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMAcknowledgement()
                ),
                XMLStreamMock.Close(),
                # this is a race-condition of the test suite
                # in a real stream, the Send would not happen as the stream
                # changes state immediately and raises an exception from
                # send_xso
                XMLStreamMock.Send(pres),
                XMLStreamMock.Send(nonza.SMRequest()),
            ]),
        )

        self.assertEqual(token.state,
                         stream.StanzaState.SENT_WITHOUT_SM)

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
    def setUp(self):
        self.stanza = make_test_iq()
        self.token = stream.StanzaToken(self.stanza)

    def tearDown(self):
        del self.token
        del self.stanza

    def test_init(self):
        self.assertIs(
            self.stanza,
            self.token.stanza
        )
        self.assertEqual(
            stream.StanzaState.ACTIVE,
            self.token.state
        )

    def test_state_not_writable(self):
        with self.assertRaises(AttributeError):
            self.token.state = stream.StanzaState.ACKED

    def test_state_change_callback(self):
        state_change_handler = unittest.mock.MagicMock()

        token = stream.StanzaToken(
            self.stanza,
            on_state_change=state_change_handler
        )

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
        self.token.abort()
        self.assertEqual(
            stream.StanzaState.ABORTED,
            self.token.state
        )

    def test_abort_while_sent(self):
        for state in set(stream.StanzaState) - {stream.StanzaState.ACTIVE,
                                                stream.StanzaState.ABORTED}:
            self.token._set_state(stream.StanzaState.SENT)
            with self.assertRaisesRegex(RuntimeError, "already sent"):
                self.token.abort()

    def test_abort_while_aborted(self):
        self.token.abort()
        self.token.abort()

    def test_repr(self):
        self.assertEqual(
            "<StanzaToken id=0x{:016x}>".format(id(self.token)),
            repr(self.token)
        )

    def test__set_state_still_idempotent_with_await(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)
        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)

        self.assertIsNone(run_coroutine(task))

    def test__set_state_with_exception(self):
        exc = Exception()
        self.token._set_state(stream.StanzaState.FAILED, exc)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_returns_on_SENT_WITHOUT_SM(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)

        self.assertIsNone(run_coroutine(task))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_returns_on_ACKED(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.ACKED)

        self.assertIsNone(run_coroutine(task))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_returns_on_ACKED_plainly_even_with_exception(
            self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.ACKED, Exception())

        self.assertIsNone(run_coroutine(task))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_waits_while_SENT(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.SENT)

        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.ACKED)

        self.assertIsNone(run_coroutine(task))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_ConnectionError_on_DISCONNECTED(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.DISCONNECTED)

        with self.assertRaisesRegex(
                ConnectionError,
                r"disconnected"):
            run_coroutine(task)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_RuntimeError_on_DROPPED(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.DROPPED)

        with self.assertRaisesRegex(
                RuntimeError,
                r"dropped by filter"):
            run_coroutine(task)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_RuntimeError_on_ABORTED(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token.abort()

        with self.assertRaisesRegex(
                RuntimeError,
                r"aborted"):
            run_coroutine(task)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_aborts_if_cancelled(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            run_coroutine(task)

        self.assertEqual(
            self.token.state,
            stream.StanzaState.ABORTED
        )

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_ValueError_on_failed(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.FAILED)

        with self.assertRaisesRegex(
                ValueError,
                "failed to send stanza for unknown local reasons") as ctx:
            run_coroutine(self.token)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_reraises_exception_from_failed(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        class FooException(Exception):
            pass
        exc = FooException()

        self.token._set_state(stream.StanzaState.FAILED, exc)

        with self.assertRaises(FooException) as ctx:
            run_coroutine(task)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_next_await_raises_usual_abort_error_after_cancel(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            run_coroutine(task)

        self.assertEqual(
            self.token.state,
            stream.StanzaState.ABORTED
        )

        with self.assertRaisesRegex(RuntimeError,
                                    r"aborted"):
            run_coroutine(self.token)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_does_not_abort_if_already_inflight(self):
        task = asyncio.ensure_future(self.token.__await__())
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(task.done())

        self.token._set_state(stream.StanzaState.SENT)

        run_coroutine(asyncio.sleep(0))

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            run_coroutine(task)

        self.assertEqual(
            self.token.state,
            stream.StanzaState.SENT,
        )

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_returns_immediately_if_already_SENT_WITHOUT_SM(self):
        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)
        self.assertIsNone(run_coroutine(self.token))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_returns_immediately_if_already_ACKED(self):
        self.token._set_state(stream.StanzaState.ACKED)
        self.assertIsNone(run_coroutine(self.token))

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_immediately_if_already_DISCONNECTED(self):
        self.token._set_state(stream.StanzaState.DISCONNECTED)

        with self.assertRaisesRegex(ConnectionError,
                                    r"disconnected"):
            run_coroutine(self.token)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_immediately_if_already_ABORTED(self):
        self.token._set_state(stream.StanzaState.ABORTED)

        with self.assertRaisesRegex(RuntimeError,
                                    r"aborted"):
            run_coroutine(self.token)

    @unittest.skipUnless(CAN_AWAIT_STANZA_TOKEN,
                         "requires Python 3.5+")
    def test_await_raises_immediately_if_already_DROPPED(self):
        self.token._set_state(stream.StanzaState.DROPPED)

        with self.assertRaisesRegex(RuntimeError,
                                    r"dropped by filter"):
            run_coroutine(self.token)

    def test_future_is_shared(self):
        self.assertIs(self.token.future, self.token.future)

    def test_future_is_created_on_first_access(self):
        with unittest.mock.patch("asyncio.Future") as Future:
            fut = self.token.future
            Future.assert_called_once_with()
            self.assertEqual(fut, Future())

    def test_future_finishes_on_SENT_WITHOUT_SM(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)

        self.assertIsNone(run_coroutine(fut))

    def test_future_finishes_on_ACKED(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.ACKED)

        self.assertIsNone(run_coroutine(fut))

    def test_future_finishes_on_ACKED_plainly_even_with_exception(
            self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.ACKED, Exception())

        self.assertIsNone(run_coroutine(fut))

    def test_future_finishes_while_SENT(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.SENT)

        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.ACKED)

        self.assertIsNone(run_coroutine(fut))

    def test_future_fails_with_ConnectionError_on_DISCONNECTED(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.DISCONNECTED)

        with self.assertRaisesRegex(
                ConnectionError,
                r"disconnected"):
            run_coroutine(fut)

    def test_future_fails_with_RuntimeError_on_DROPPED(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.DROPPED)

        with self.assertRaisesRegex(
                RuntimeError,
                r"dropped by filter"):
            run_coroutine(fut)

    def test_future_fails_with_RuntimeError_on_ABORTED(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token.abort()

        with self.assertRaisesRegex(
                RuntimeError,
                r"aborted"):
            run_coroutine(fut)

    def test_future_fails_with_ValueError_on_failed(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        self.token._set_state(stream.StanzaState.FAILED)

        with self.assertRaisesRegex(
                ValueError,
                "failed to send stanza for unknown local reasons"):
            run_coroutine(fut)

    def test_future_reraises_exception_from_failed(self):
        fut = self.token.future
        run_coroutine(asyncio.sleep(0.01))
        self.assertFalse(fut.done())

        class FooException(Exception):
            pass
        exc = FooException()

        self.token._set_state(stream.StanzaState.FAILED, exc)

        with self.assertRaises(FooException):
            run_coroutine(fut)

    def test_future_is_done_if_already_SENT_WITHOUT_SM(self):
        self.token._set_state(stream.StanzaState.SENT_WITHOUT_SM)
        self.assertTrue(self.token.future.done())

    def test_future_is_done_if_already_ACKED(self):
        self.token._set_state(stream.StanzaState.ACKED)
        self.assertTrue(self.token.future.done())

    def test_future_is_done_and_has_exception_if_already_DISCONNECTED(self):
        self.token._set_state(stream.StanzaState.DISCONNECTED)

        self.assertTrue(self.token.future)
        with self.assertRaisesRegex(ConnectionError,
                                    r"disconnected"):
            self.token.future.result()

    def test_future_is_done_and_has_exception_if_already_ABORTED(self):
        self.token._set_state(stream.StanzaState.ABORTED)

        self.assertTrue(self.token.future)
        with self.assertRaisesRegex(RuntimeError,
                                    r"aborted"):
            self.token.future.result()

    def test_future_is_done_and_has_exception_if_already_DROPPED(self):
        self.token._set_state(stream.StanzaState.DROPPED)

        self.assertTrue(self.token.future)
        with self.assertRaisesRegex(RuntimeError,
                                    r"dropped by filter"):
            self.token.future.result()


class Testiq_handler(unittest.TestCase):
    def setUp(self):
        self.stream = unittest.mock.Mock()
        self.cm = stream.iq_handler(
            self.stream,
            unittest.mock.sentinel.iqtype,
            unittest.mock.sentinel.payload,
            unittest.mock.sentinel.coro,
        )

    def tearDown(self):
        del self.cm
        del self.stream

    def test_is_context_manager(self):
        self.assertTrue(
            hasattr(self.cm, "__enter__")
        )
        self.assertTrue(
            hasattr(self.cm, "__exit__")
        )

    def test_enter_registers_coroutine(self):
        self.cm.__enter__()

        self.stream.register_iq_request_handler.assert_called_with(
            unittest.mock.sentinel.iqtype,
            unittest.mock.sentinel.payload,
            unittest.mock.sentinel.coro,
        )

    def test_exit_unregisters_coroutine(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        self.cm.__exit__(None, None, None)

        self.stream.unregister_iq_request_handler.assert_called_with(
            unittest.mock.sentinel.iqtype,
            unittest.mock.sentinel.payload,
        )

    def test_exit_does_not_swallow_exception_and_unregisters(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        # we need to generate a trackback object
        try:
            raise ValueError()
        except:  # NOQA
            info = sys.exc_info()

        result = self.cm.__exit__(*info)

        self.stream.unregister_iq_request_handler.assert_called_with(
            unittest.mock.sentinel.iqtype,
            unittest.mock.sentinel.payload,
        )

        self.assertFalse(result)


class Testmessage_handler(unittest.TestCase):
    def setUp(self):
        self.stream = unittest.mock.Mock()
        self.cm = stream.message_handler(
            self.stream,
            unittest.mock.sentinel.msgtype,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

    def tearDown(self):
        del self.cm
        del self.stream

    def test_is_context_manager(self):
        self.assertTrue(
            hasattr(self.cm, "__enter__")
        )
        self.assertTrue(
            hasattr(self.cm, "__exit__")
        )

    def test_enter_registers_callback(self):
        self.cm.__enter__()

        self.stream.register_message_callback.assert_called_with(
            unittest.mock.sentinel.msgtype,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

    def test_exit_unregisters_callbcak(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        self.cm.__exit__(None, None, None)

        self.stream.unregister_message_callback.assert_called_with(
            unittest.mock.sentinel.msgtype,
            unittest.mock.sentinel.from_,
        )

    def test_exit_does_not_swallow_exception_and_unregisters(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        # we need to generate a trackback object
        try:
            raise ValueError()
        except:  # NOQA
            info = sys.exc_info()

        result = self.cm.__exit__(*info)

        self.stream.unregister_message_callback.assert_called_with(
            unittest.mock.sentinel.msgtype,
            unittest.mock.sentinel.from_,
        )

        self.assertFalse(result)


class Testpresence_handler(unittest.TestCase):
    def setUp(self):
        self.stream = unittest.mock.Mock()
        self.cm = stream.presence_handler(
            self.stream,
            unittest.mock.sentinel.prestype,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

    def tearDown(self):
        del self.cm
        del self.stream

    def test_is_context_manager(self):
        self.assertTrue(
            hasattr(self.cm, "__enter__")
        )
        self.assertTrue(
            hasattr(self.cm, "__exit__")
        )

    def test_enter_registers_callback(self):
        self.cm.__enter__()

        self.stream.register_presence_callback.assert_called_with(
            unittest.mock.sentinel.prestype,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
        )

    def test_exit_unregisters_callback(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        self.cm.__exit__(None, None, None)

        self.stream.unregister_presence_callback.assert_called_with(
            unittest.mock.sentinel.prestype,
            unittest.mock.sentinel.from_,
        )

    def test_exit_does_not_swallow_exception_and_unregisters(self):
        self.cm.__enter__()
        self.stream.reset_mock()

        # we need to generate a trackback object
        try:
            raise ValueError()
        except:  # NOQA
            info = sys.exc_info()

        result = self.cm.__exit__(*info)

        self.stream.unregister_presence_callback.assert_called_with(
            unittest.mock.sentinel.prestype,
            unittest.mock.sentinel.from_,
        )

        self.assertFalse(result)


class Teststanza_filter(unittest.TestCase):
    def test_calls_to_filter_context_register(self):
        m = unittest.mock.Mock()
        result = stream.stanza_filter(
            m.filter_,
            unittest.mock.sentinel.func,
            unittest.mock.sentinel.order,
        )

        m.filter_.context_register.assert_called_once_with(
            unittest.mock.sentinel.func,
            unittest.mock.sentinel.order,
        )
        self.assertEqual(
            result,
            m.filter_.context_register()
        )

    def test_does_not_pass_order_if_not_given(self):
        m = unittest.mock.Mock()
        result = stream.stanza_filter(
            m.filter_,
            unittest.mock.sentinel.func,
        )

        m.filter_.context_register.assert_called_once_with(
            unittest.mock.sentinel.func,
        )
        self.assertEqual(
            result,
            m.filter_.context_register()
        )
