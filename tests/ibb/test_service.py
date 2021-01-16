########################################################################
# File name: test_service.py
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
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp
import aioxmpp.xso as xso
import aioxmpp.service as service
import aioxmpp.disco.xso as disco_xso
import aioxmpp.ibb as ibb
import aioxmpp.ibb.service as ibb_service
import aioxmpp.ibb.xso as ibb_xso

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")


class TestIBBService(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.s = ibb.IBBService(
            self.cc,
        )

    def tearDown(self):
        del self.cc
        del self.s

    def test_is_service(self):
        self.assertTrue(issubclass(
            ibb.IBBService,
            aioxmpp.service.Service
        ))

    def test_open_session_block_size_too_large(self):
        protocol = unittest.mock.Mock()
        with self.assertRaisesRegex(ValueError, r"^block_size too large$"):
            run_coroutine(
                self.s.open_session(protocol, TEST_JID1, block_size=(1<<16)))

    def test_open_session_default(self):
        with unittest.mock.patch("aioxmpp.utils.to_nmtoken")\
             as gsi:
            gsi.return_value = "sentinel"
            protocol = unittest.mock.Mock()
            handle, protocl = run_coroutine(
                self.s.open_session(protocol, TEST_JID1)
            )

        self.assertEqual(
            handle.get_extra_info("sid"),
            "sentinel"
        )

        self.assertEqual(
            handle.get_extra_info("block_size"),
            4096
        )

        self.assertEqual(
            handle.get_extra_info("stanza_type"),
            ibb_xso.IBBStanzaType.IQ
        )

        self.assertEqual(
            handle.get_extra_info("peer_jid"),
            TEST_JID1
        )

        (s, (iq,), kwargs), = self.cc.send.mock_calls
        self.assertFalse(kwargs)
        self.assertEqual(iq.to, TEST_JID1)
        self.assertEqual(iq.payload.sid, "sentinel")
        self.assertEqual(iq.payload.stanza, ibb_xso.IBBStanzaType.IQ)
        self.assertEqual(iq.payload.block_size, 4096)


    def test_open_session_non_default(self):
        with unittest.mock.patch("aioxmpp.utils.to_nmtoken")\
             as gsi:
            gsi.return_value = "sentinel"
            protocol = unittest.mock.Mock()
            handle, proto = run_coroutine(
                self.s.open_session(
                    protocol,
                    TEST_JID1,
                    stanza_type=ibb_xso.IBBStanzaType.MESSAGE,
                    block_size=8192,
                )
            )

        self.assertEqual(
            handle.get_extra_info("sid"),
            "sentinel"
        )

        self.assertEqual(
            handle.get_extra_info("block_size"),
            8192
        )

        self.assertEqual(
            handle.get_extra_info("peer_jid"),
            TEST_JID1
        )

        self.assertEqual(
            handle.get_extra_info("stanza_type"),
            ibb_xso.IBBStanzaType.MESSAGE
        )

        (s, (iq,), kwargs), = self.cc.send.mock_calls
        self.assertFalse(kwargs)
        self.assertEqual(iq.to, TEST_JID1)
        self.assertEqual(iq.payload.sid, "sentinel")
        self.assertEqual(iq.payload.stanza, ibb_xso.IBBStanzaType.MESSAGE)
        self.assertEqual(iq.payload.block_size, 8192)

    def test_open_request_enforce_limit(self):
        open_ = ibb_xso.Open()
        open_.sid = "sentinel"
        open_.block_size = 8192
        open_.stanza = ibb_xso.IBBStanzaType.IQ

        iq = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            payload=open_
        )
        try:
            run_coroutine(self.s._handle_open_request(iq))
        except aioxmpp.errors.XMPPCancelError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.NOT_ACCEPTABLE
            )
        else:
            self.fail("missing expected exception")

    def test_open_request_resource_constraint(self):
        open_ = ibb_xso.Open()
        open_.sid = "sentinel"
        open_.block_size = 1<<32
        open_.stanza = ibb_xso.IBBStanzaType.IQ

        iq = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            payload=open_
        )
        try:
            run_coroutine(self.s._handle_open_request(iq))
        except aioxmpp.errors.XMPPModifyError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.RESOURCE_CONSTRAINT
            )
        else:
            self.fail("missing expected exception")

    def test_open_request_allowed_limit(self):
        self.s.session_limit = 1
        self.s.default_protocol_factory = unittest.mock.Mock()

        def on_connection_accepted(transport, protocol):
            pass

        self.s.on_session_accepted.connect(
            on_connection_accepted
        )

        open_ = ibb_xso.Open()
        open_.sid = "sentinel"
        open_.block_size = 8192
        open_.stanza = ibb_xso.IBBStanzaType.IQ

        iq = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            payload=open_
        )

        run_coroutine(self.s._handle_open_request(iq))

    def test_open_request_expected_session(self):
        protocol_factory = unittest.mock.Mock()
        s_fut = self.s.expect_session(protocol_factory, TEST_JID1, "sentinel")

        open_ = ibb_xso.Open()
        open_.sid = "sentinel"
        open_.block_size = 8192
        open_.stanza = ibb_xso.IBBStanzaType.IQ

        iq = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            payload=open_
        )
        run_coroutine(self.s._handle_open_request(iq))

        async def await_s_fut():
            return await s_fut

        handle, proto = run_coroutine(await_s_fut())
        self.assertEqual(
            handle.get_extra_info("peer_jid"),
            TEST_JID1
        )
        self.assertEqual(
            handle.get_extra_info("sid"),
            "sentinel"
        )
        self.assertEqual(
            handle.get_extra_info("block_size"),
            8192
        )

        protocol_factory().connection_made.assert_called_with(handle)

    def test_remote_close_unknown_session(self):
        close = ibb_xso.Close()
        close.sid = "quark"
        stanza = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            to=TEST_FROM,
            payload=close
        )
        try:
            run_coroutine(self.s._handle_close_request(stanza))
        except aioxmpp.errors.XMPPCancelError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND
            )

    def test_handle_open_request_is_iq_handler(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.SET,
                ibb_xso.Open,
                ibb_service.IBBService._handle_open_request,
            )
        )

    def test_handle_close_request_is_iq_handler(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.SET,
                ibb_xso.Close,
                ibb_service.IBBService._handle_close_request,
            )
        )

    def test_handle_data_is_iq_handler(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.SET,
                ibb_xso.Data,
                ibb_service.IBBService._handle_data,
            )
        )

class TestProtocol(asyncio.Protocol):

    def __init__(self):
        self.data = b""
        self.data_received_evt = asyncio.Event()
        self.connection_lost_fut = asyncio.Future()
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def connection_lost(self, e):
        self.connection_lost_fut.set_result(e)

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def data_received(self, data):
        self.data += data
        self.data_received_evt.set()

class TestIBBService_OpenConnection(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.s = ibb.IBBService(
            self.cc,
        )
        self.s.initial_wait_time = timedelta(milliseconds=1)
        protocol_factory = unittest.mock.Mock()
        self.handle, self.protocol = run_coroutine(
            self.s.open_session(protocol_factory, TEST_JID1)
        )
        self.cc.send.mock_calls.clear()

    def tearDown(self):
        # ensure clean-up
        self.s._on_stream_destroyed()
        del self.cc
        del self.s

    def test_send(self):
        arguments = []
        async def patched_send(stanza):
            fut.set_result(None)
            arguments.append(stanza)

        for i in range(5):
            fut = asyncio.Future()
            self.cc.send = patched_send
            self.handle.write(b"some data")
            run_coroutine(fut)

        total_content = b""
        for i, iq in enumerate(arguments):
            self.assertEqual(iq.to, TEST_JID1)
            self.assertIsInstance(iq.payload, ibb_xso.Data)
            self.assertEqual(iq.payload.sid, self.handle.get_extra_info("sid"))
            self.assertEqual(iq.payload.seq, i)
            self.assertTrue(iq.payload.content)
            total_content += iq.payload.content
        self.assertEqual(total_content, b"some data"*5)

    def test_receive(self):

        proto = TestProtocol()
        self.handle.set_protocol(proto)
        total_text = b""
        for i in range(5):
            text = "data{}".format(i).encode("us-ascii")
            stanza = aioxmpp.IQ(
                aioxmpp.IQType.SET,
                from_=TEST_JID1,
                to=TEST_FROM,
                payload=ibb_xso.Data(
                    self.handle.get_extra_info("sid"),
                    i,
                    text
                )
            )
            total_text += text
            run_coroutine(self.s._handle_data(stanza))

        self.assertEqual(
            proto.data, total_text
        )

    def test_open_request_established_session(self):
        self.s.session_limit = 2
        self.s.default_protocol_factory = unittest.mock.Mock()
        on_session_accepted = unittest.mock.Mock()
        self.s.on_session_accepted.connect(
            on_session_accepted
        )

        open_ = ibb_xso.Open()
        open_.sid = self.handle.get_extra_info("sid")
        open_.block_size = 4096
        open_.stanza = ibb_xso.IBBStanzaType.IQ

        iq = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            payload=open_
        )

        try:
            run_coroutine(self.s._handle_open_request(iq))
        except aioxmpp.errors.XMPPCancelError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.NOT_ACCEPTABLE
            )

        self.assertEqual(len(on_session_accepted.mock_calls), 0)

    def test_receive_invalid_session(self):
        proto = TestProtocol()
        self.handle.set_protocol(proto)

        stanza = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            to=TEST_FROM,
            payload=ibb_xso.Data(
                "fnord",
                0,
                b"data",
            )
        )
        try:
            run_coroutine(self.s._handle_data(stanza))
        except aioxmpp.errors.XMPPCancelError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND
            )
        else:
            self.fail("expected exception was not raised")
        self.assertEqual(proto.data, b"")

    def test_receive_invalid_seq(self):
        proto = TestProtocol()
        self.handle.set_protocol(proto)

        stanza = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            to=TEST_FROM,
            payload=ibb_xso.Data(
                self.handle.get_extra_info("sid"),
                1,
                b"data",
            )
        )
        try:
            run_coroutine(self.s._handle_data(stanza))
        except aioxmpp.errors.XMPPCancelError as e:
            self.assertEqual(
                e.condition,
                aioxmpp.errors.ErrorCondition.UNEXPECTED_REQUEST
            )
        else:
            self.fail("expected exception was not raised")
        self.assertEqual(proto.data, b"")

    def test_wait_error_timeout(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(e)
        self.cc.send.side_effect = aioxmpp.errors.XMPPWaitError(
            aioxmpp.errors.ErrorCondition.RECIPIENT_UNAVAILABLE
        )
        self.handle.write(b"data")
        run_coroutine(fut)
        self.assertEqual(self.handle._retries, self.s.max_retries)
        self.assertFalse(self.s._sessions)
        self.assertIsInstance(fut.result(), asyncio.TimeoutError)

    def test_wait_error_recover(self):
        fut = asyncio.Future()
        fut_close = asyncio.Future()

        def side_effect(*args, **kwargs):
            yield aioxmpp.errors.XMPPWaitError(
                aioxmpp.errors.ErrorCondition.RECIPIENT_UNAVAILABLE
            )
            fut.set_result((args, kwargs))
            yield unittest.mock.DEFAULT
            fut_close.set_result((args, kwargs))
            yield unittest.mock.DEFAULT

        self.cc.send.side_effect = side_effect()
        self.handle.write(b"data")
        run_coroutine(fut)
        self.handle.close()
        run_coroutine(fut_close)
        self.assertEqual(self.handle._wait_time,
                         self.s.initial_wait_time.total_seconds())
        self.assertEqual(self.handle._retries, 0)

    def test_remote_seq_error(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(e)
        self.cc.send.side_effect = aioxmpp.errors.XMPPCancelError(
            aioxmpp.errors.ErrorCondition.UNEXPECTED_REQUEST
        )
        self.handle.write(b"data")
        run_coroutine(fut)
        self.assertIs(fut.result(), self.cc.send.side_effect)
        self.assertFalse(self.s._sessions)

        (_, (iq1,), _), (_, (iq2,), _) = self.cc.send.mock_calls
        self.assertEqual(iq1.type_, aioxmpp.IQType.SET)
        self.assertIsInstance(iq1.payload, ibb_xso.Data)
        self.assertEqual(iq2.type_, aioxmpp.IQType.SET)
        self.assertIsInstance(iq2.payload, ibb_xso.Close)

    def test_remote_abort(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(e)
        self.cc.send.side_effect = aioxmpp.errors.XMPPCancelError(
            aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND
        )
        self.handle.write(b"data")
        run_coroutine(fut)
        self.assertIs(fut.result(), self.cc.send.side_effect)
        self.assertFalse(self.s._sessions)

        (_, (iq1,), _), (_, (iq2,), _) = self.cc.send.mock_calls
        self.assertEqual(iq1.type_, aioxmpp.IQType.SET)
        self.assertIsInstance(iq1.payload, ibb_xso.Data)
        self.assertEqual(iq2.type_, aioxmpp.IQType.SET)
        self.assertIsInstance(iq2.payload, ibb_xso.Close)


    def test_disconnect(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(e)
        self.cc.send.side_effect = ConnectionError()
        self.handle.write(b"data")
        run_coroutine(fut)
        self.assertIs(fut.result(), self.cc.send.side_effect)
        self.assertFalse(self.s._sessions)

        (_, (iq1,), _), = self.cc.send.mock_calls
        self.assertEqual(iq1.type_, aioxmpp.IQType.SET)
        self.assertIsInstance(iq1.payload, ibb_xso.Data)

    def test_remote_abort_during_close(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(e)
        self.cc.send.side_effect = aioxmpp.errors.XMPPCancelError(
            aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND
        )
        self.handle.close()
        run_coroutine(fut)
        self.assertIs(fut.result(), self.cc.send.side_effect)

    def test_close(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(None)
        self.handle.close()
        run_coroutine(fut)
        (_, (iq,), _), = self.cc.send.mock_calls
        self.assertEqual(iq.to, TEST_JID1)
        self.assertIsInstance(iq.payload, ibb_xso.Close)
        self.assertEqual(iq.payload.sid, self.handle.get_extra_info("sid"))
        self.assertFalse(self.s._sessions)

    def test_remote_close(self):
        fut = asyncio.Future()
        self.protocol.connection_lost = lambda e: fut.set_result(None)

        close = ibb_xso.Close()
        close.sid = self.handle.get_extra_info("sid")
        stanza = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            from_=TEST_JID1,
            to=TEST_FROM,
            payload=close
        )
        run_coroutine(self.s._handle_close_request(stanza))
        run_coroutine(fut)
        self.assertFalse(self.s._sessions)

    def test_fill_buffer(self):
        pause_fut = asyncio.Future()
        resume_fut = asyncio.Future()
        # hack the block size
        self.handle._block_size = 5
        self.handle.set_write_buffer_limits(20, 10)
        self.protocol.pause_writing = lambda: pause_fut.set_result(True)
        self.protocol.resume_writing = lambda: resume_fut.set_result(True)
        self.handle.write(b" " * 21)
        run_coroutine(pause_fut)
        run_coroutine(resume_fut)
        self.assertLess(len(self.handle._write_buffer), 10)
        self.assertGreater(len(self.handle._write_buffer), 0)

class TestIBBService_OpenConnectionMessage(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.s = ibb.IBBService(
            self.cc,
        )
        protocol_factory = unittest.mock.Mock()
        self.handle, self.protocol = run_coroutine(
            self.s.open_session(protocol_factory, TEST_JID1,
                                stanza_type=ibb_xso.IBBStanzaType.MESSAGE)
        )
        self.cc.send.mock_calls.clear()

    def tearDown(self):
        # ensure clean-up
        self.s._on_stream_destroyed()
        del self.cc
        del self.s

    def test_leave_non_protocol_messages_intact(self):
        stanza = aioxmpp.Message(
            aioxmpp.MessageType.NORMAL,
            from_=TEST_JID1,
            to=TEST_FROM,
        )
        self.assertIs(self.s._handle_message(stanza), stanza)

    def test_send(self):

        for i in range(5):
            fut = asyncio.Future()

            async def patched_send(stanza):
                fut.set_result(None)
                patched_send.argument = stanza

            self.cc.send = patched_send
            self.handle.write(b"some data")
            run_coroutine(fut)
            msg = patched_send.argument
            self.assertEqual(msg.to, TEST_JID1)
            self.assertIsInstance(msg.xep0047_data, ibb_xso.Data)
            self.assertEqual(msg.xep0047_data.sid,
                             self.handle.get_extra_info("sid"))
            self.assertEqual(msg.xep0047_data.seq, i)
            self.assertEqual(msg.xep0047_data.content, b"some data")

    # def test_send_long(self):
    #     run_coroutine(self.handle.send(b" " * 4097))
    #     self.assertEqual(
    #         len(self.cc.send.mock_calls),
    #         2
    #     )

    def test_receive(self):

        proto = TestProtocol()
        self.handle.set_protocol(proto)
        total_text = b""
        for i in range(5):
            text = "data{}".format(i).encode("us-ascii")
            stanza = aioxmpp.Message(
                aioxmpp.MessageType.NORMAL,
                from_=TEST_JID1,
                to=TEST_FROM,
            )
            stanza.xep0047_data = ibb_xso.Data(
                self.handle.get_extra_info("sid"),
                i,
                text
            )

            total_text += text
            self.s._handle_message(stanza)

        self.assertEqual(
            proto.data, total_text
        )

    def test_receive_invalid_session(self):
        proto = TestProtocol()
        self.handle.set_protocol(proto)

        stanza = aioxmpp.Message(
            aioxmpp.MessageType.NORMAL,
            from_=TEST_JID1,
            to=TEST_FROM,
        )
        stanza.xep0047_data = ibb_xso.Data(
            "fnord",
            0,
            b"data",
        )

        self.s._handle_message(stanza)
        self.assertEqual(proto.data, b"")

    def test_receive_invalid_seq(self):
        proto = TestProtocol()
        self.handle.set_protocol(proto)

        stanza = aioxmpp.Message(
            aioxmpp.MessageType.NORMAL,
            from_=TEST_JID1,
            to=TEST_FROM,
        )

        stanza.xep0047_data = ibb_xso.Data(
            self.handle.get_extra_info("sid"),
            1,
            b"data",
        )

        self.s._handle_message(stanza)
        self.assertEqual(proto.data, b"")


class TestIBBTransport(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.s = ibb.IBBService(
            self.cc,
        )
        protocol_factory = unittest.mock.Mock()
        self.handle, self.protocol = run_coroutine(
            self.s.open_session(protocol_factory, TEST_JID1)
        )
        self.cc.send.mock_calls.clear()

    def tearDown(self):
        # ensure clean-up
        self.s._on_stream_destroyed()
        del self.cc
        del self.s

    def test_set_write_buffer_limits(self):
        self.handle.set_write_buffer_limits(10000, 100)
        self.assertEqual(
            self.handle.get_write_buffer_limits(),
            (100, 10000)
        )

    def test_set_write_buffer_limits_only_high(self):
        low_before, high_before = self.handle.get_write_buffer_limits()
        self.handle.set_write_buffer_limits(high_before*2)
        self.assertEqual(
            self.handle.get_write_buffer_limits(),
            (low_before, high_before*2)
        )

    def test_set_write_buffer_limits_reject_negative(self):
        with self.assertRaises(ValueError):
            self.handle.set_write_buffer_limits(-10, 0)

        with self.assertRaises(ValueError):
            self.handle.set_write_buffer_limits(0, -10)

    def test_set_write_buffer_limits_set_to_zeroe(self):
        self.handle.set_write_buffer_limits(0)
        self.assertEqual(
            self.handle.get_write_buffer_limits(),
            (0, 0)
        )

    def test_set_write_buffer_limits_defaults(self):
        low_before, high_before = self.handle.get_write_buffer_limits()
        self.handle.set_write_buffer_limits(10000, 100)
        self.handle.set_write_buffer_limits()
        self.assertEqual(
            self.handle.get_write_buffer_limits(),
            (low_before, high_before)
        )

    def test_get_write_buffer_size(self):
        self.handle.write(b" "*10)
        self.assertEqual(self.handle.get_write_buffer_size(), 10)

    def test_get_protocol(self):
        self.assertIs(self.handle.get_protocol(), self.protocol)

    def test_pause_and_resume_reading(self):
        self.handle.pause_reading()
        self.handle._data_received(b"foo")
        self.handle._data_received(b"bar")
        self.assertSequenceEqual(
            self.protocol.data_received.mock_calls,
            []
        )
        self.handle.resume_reading()
        self.assertSequenceEqual(
            self.protocol.data_received.mock_calls,
            [unittest.mock.call(b"foobar")]
        )
