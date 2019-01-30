########################################################################
# File name: test_protocol.py
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
import io
import logging
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors
import aioxmpp.utils

from aioxmpp.testutils import (
    TransportMock,
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer,
    get_timeout,
    make_listener,
)
from aioxmpp import xmltestutils

from aioxmpp.protocol import XMLStream, DebugWrapper
from aioxmpp.structs import JID
from aioxmpp.utils import namespaces

import aioxmpp.protocol as protocol

TEST_FROM = JID.fromstr("foo@bar.example")
TEST_PEER = JID.fromstr("bar.example")

STREAM_HEADER = b'''\
<?xml version="1.0"?>\
<stream:stream xmlns="jabber:client" \
xmlns:stream="http://etherx.jabber.org/streams" \
to="bar.example" \
version="1.0">'''

PEER_STREAM_HEADER_TEMPLATE = '''\
<stream:stream xmlns:stream="http://etherx.jabber.org/streams" \
xmlns="jabber:client" \
from="bar.example" \
to="foo@bar.example" \
id="abc" \
version="{major:d}.{minor:d}">'''

PEER_FEATURES_TEMPLATE = '''\
<stream:features/>'''

STREAM_ERROR_TEMPLATE_WITH_TEXT = '''\
<stream:error>\
<text xmlns="urn:ietf:params:xml:ns:xmpp-streams">{text}</text>\
<{condition} xmlns="urn:ietf:params:xml:ns:xmpp-streams"/>\
</stream:error>'''

STREAM_ERROR_TEMPLATE_WITHOUT_TEXT = '''\
<stream:error><{condition} xmlns="urn:ietf:params:xml:ns:xmpp-streams"/>\
</stream:error>'''

STANZA_ERROR_TEMPLATE_WITHOUT_TEXT = '''\
<error type="{type}">\
<{condition} xmlns="urn:ietf:params:xml:ns:xmpp-stanzas"/>\
</error>'''

STANZA_ERROR_TEMPLATE_WITH_TEXT = '''\
<error type="{type}">\
<text xmlns="urn:ietf:params:xml:ns:xmpp-stanzas">{text}</text>\
<{condition} xmlns="urn:ietf:params:xml:ns:xmpp-stanzas"/>\
</error>'''


class Child(xso.XSO):
    TAG = ("uri:foo", "payload")

    attr = xso.Attr("a")


class RuntimeErrorRaisingStanza(stanza.StanzaBase):
    TAG = ("jabber:client", "foo")

    a = xso.Attr("a")

    def xso_error_handler(self, *args):
        raise RuntimeError("foobar")


FakeIQ = stanza.IQ
FakeIQ.register_child(FakeIQ.payload, Child)


class TestDebugWrapper(unittest.TestCase):
    def setUp(self):
        self.buf = unittest.mock.Mock([
            "write",
            "flush",
        ])
        self.logger = unittest.mock.Mock([
            "debug",
        ])

    def test_forwards_writes(self):
        dw = DebugWrapper(self.buf, self.logger)
        self.buf.write.return_value = unittest.mock.sentinel.written
        self.assertEqual(dw.write(b"foobar"),
                         unittest.mock.sentinel.written)
        self.buf.write.assert_called_once_with(b"foobar")

    def test_forwards_flush_and_emits_log_message(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"foo")
        dw.write(b"bar")
        dw.write(b"bazfnord")

        dw.flush()

        self.buf.flush.assert_called_once_with()
        self.logger.debug.assert_called_once_with("SENT %r", b"foobarbazfnord")

    def test_flush_works_with_backend_which_does_not_support_flush(self):
        buf = unittest.mock.Mock(["write"])
        dw = DebugWrapper(buf, self.logger)
        dw.write(b"foo")
        dw.write(b"bar")
        dw.write(b"bazfnord")

        dw.flush()

        self.logger.debug.assert_called_once_with("SENT %r", b"foobarbazfnord")

    def test_flushes_log_after_write_with_more_than_4096_bytes(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"x"*4098)

        self.logger.debug.assert_called_once_with("SENT %r", b"x"*4098)
        self.buf.flush.assert_not_called()

    def test_flushes_log_after_accumulation_of_4096_bytes(self):
        dw = DebugWrapper(self.buf, self.logger)
        for i in range(4):
            dw.write(b"x" * 1024)

        self.logger.debug.assert_called_once_with("SENT %r", b"x"*4096)
        self.buf.flush.assert_not_called()

    def test_allows_to_reaccumulate_4096_bytes_after_autoflush(self):
        dw = DebugWrapper(self.buf, self.logger)
        for i in range(7):
            dw.write(b"x" * 1024)

        self.logger.debug.assert_called_once_with("SENT %r", b"x"*4096)
        self.buf.flush.assert_not_called()

    def test_allows_to_reaccumulate_4096_bytes_after_forced_flush(self):
        dw = DebugWrapper(self.buf, self.logger)
        for i in range(3):
            dw.write(b"x" * 1024)
        dw.flush()
        self.logger.debug.reset_mock()
        self.buf.flush.reset_mock()

        for i in range(3):
            dw.write(b"x" * 1024)

        self.logger.debug.assert_not_called()
        self.buf.flush.assert_not_called()

    def test_flushes_not_before_4096_bytes(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"x"*4095)

        self.logger.debug.assert_not_called()

    def test_mute_replaces_write_with_placeholder(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"foo")
        self.buf.write.assert_called_once_with(b"foo")
        self.buf.write.reset_mock()

        with dw.mute():
            dw.write(b"bar")
            self.buf.write.assert_called_once_with(b"bar")
            self.buf.write.reset_mock()

        dw.write(b"baz")
        self.buf.write.assert_called_once_with(b"baz")
        self.buf.write.reset_mock()

        dw.flush()

        self.logger.debug.assert_called_once_with(
            "SENT %r",
            b"foo<!-- some bytes omitted -->baz"
        )

    def test_mute_replaces_multiple_writes_with_single_placeholder(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"foo")
        self.buf.write.assert_called_once_with(b"foo")
        self.buf.write.reset_mock()

        with dw.mute():
            dw.write(b"bar")
            self.buf.write.assert_called_once_with(b"bar")
            self.buf.write.reset_mock()
            dw.write(b"fnord")
            self.buf.write.assert_called_once_with(b"fnord")
            self.buf.write.reset_mock()

        dw.write(b"baz")
        self.buf.write.assert_called_once_with(b"baz")
        self.buf.write.reset_mock()

        dw.flush()

        self.logger.debug.assert_called_once_with(
            "SENT %r",
            b"foo<!-- some bytes omitted -->baz"
        )

    def test_mute_creates_new_marker_for_new_mute_invocation(self):
        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"foo")
        self.buf.write.assert_called_once_with(b"foo")
        self.buf.write.reset_mock()

        with dw.mute():
            dw.write(b"bar")
            self.buf.write.assert_called_once_with(b"bar")
            self.buf.write.reset_mock()

        with dw.mute():
            dw.write(b"fnord")
            self.buf.write.assert_called_once_with(b"fnord")
            self.buf.write.reset_mock()

        dw.write(b"baz")
        self.buf.write.assert_called_once_with(b"baz")
        self.buf.write.reset_mock()

        dw.flush()

        self.logger.debug.assert_called_once_with(
            "SENT %r",
            b"foo<!-- some bytes omitted --><!-- some bytes omitted -->baz"
        )

    def test_mute_correctly_unmutes_on_exception(self):
        class FooException(Exception):
            pass

        dw = DebugWrapper(self.buf, self.logger)
        dw.write(b"foo")
        self.buf.write.assert_called_once_with(b"foo")
        self.buf.write.reset_mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(self.assertRaises(FooException))
            stack.enter_context(dw.mute())
            dw.write(b"bar")
            self.buf.write.assert_called_once_with(b"bar")
            self.buf.write.reset_mock()
            raise FooException()

        dw.write(b"baz")
        self.buf.write.assert_called_once_with(b"baz")
        self.buf.write.reset_mock()

        dw.flush()

        self.logger.debug.assert_called_once_with(
            "SENT %r",
            b"foo<!-- some bytes omitted -->baz"
        )


class TestXMLStream(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.loop = asyncio.get_event_loop()
        self.monitor = unittest.mock.Mock(spec=aioxmpp.utils.AlivenessMonitor)

    def tearDown(self):
        del self.monitor
        self.loop.set_exception_handler(
            type(self.loop).default_exception_handler
        )

    def _make_peer_header(self, version=(1, 0)):
        return PEER_STREAM_HEADER_TEMPLATE.format(
            minor=version[1],
            major=version[0]).encode("utf-8")

    def _make_stream_error(self, condition):
        return STREAM_ERROR_TEMPLATE_WITHOUT_TEXT.format(
            condition=condition
        ).encode("utf-8")

    def _make_peer_features(self):
        return PEER_FEATURES_TEMPLATE.format().encode("utf-8")

    def _make_eos(self):
        return b"</stream:stream>"

    def _make_stream(self, *args,
                     features_future=None,
                     with_starttls=False,
                     monitor_mock=True,
                     **kwargs):
        if features_future is None:
            features_future = asyncio.Future()

        with contextlib.ExitStack() as stack:
            if monitor_mock:
                AlivenessMonitor = stack.enter_context(
                    unittest.mock.patch("aioxmpp.utils.AlivenessMonitor")
                )
                AlivenessMonitor.return_value = self.monitor
            else:
                AlivenessMonitor = None

            p = XMLStream(*args, sorted_attributes=True,
                          features_future=features_future,
                          **kwargs)

        if monitor_mock:
            AlivenessMonitor.assert_called_once_with(self.loop)
        t = TransportMock(self, p, with_starttls=with_starttls)
        return t, p

    def test_init(self):
        t, p = self._make_stream(to=TEST_PEER)
        self.assertEqual(
            protocol.State.READY,
            p.state
        )
        self.assertIsNone(p.error_handler, None)

    def test_connection_made_check_state(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegex(RuntimeError, "invalid state"):
            run_coroutine(
                t.run_test(
                    # implicit connection_made is at the start of each
                    # TransportMock test!
                    [
                        TransportMock.Write(
                            STREAM_HEADER,
                            response=TransportMock.MakeConnection()
                        )
                    ],
                ))

    def test_clean_empty_stream(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(
                                self._make_peer_header(version=(1, 0)) +
                                self._make_eos()),
                            TransportMock.ReceiveEof()
                        ]
                    ),
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(),
                    TransportMock.Close()
                ]
            ))

    def test_only_one_close_event_on_multiple_errors(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(
                        self._make_peer_header(version=(1, 0)) +
                        self._make_stream_error("undefined-condition") +
                        self._make_eos()),
                    TransportMock.ReceiveEof()
                ]),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

    def test_close_before_peer_header(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                    ),
                ],
                partial=True
            ))
        p.close()
        self.assertEqual(protocol.State.CLOSING, p.state)
        p.close()
        self.assertEqual(protocol.State.CLOSING, p.state)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(),
                    TransportMock.Close(),
                ],
            ))
        self.assertEqual(protocol.State.CLOSED, p.state)

    def test_close_after_peer_header(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(
                                self._make_peer_header(version=(1, 0))
                            )
                        ]
                    ),
                ],
                partial=True
            ))
        p.close()
        self.assertEqual(protocol.State.CLOSING, p.state)
        p.close()
        self.assertEqual(protocol.State.CLOSING, p.state)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(
                        response=[
                            TransportMock.Receive(b"</stream:stream>"),
                        ]
                    ),
                    TransportMock.Close(),
                ],
            ))
        self.assertEqual(protocol.State.CLOSED, p.state)

    def test_reset_before_peer_header(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                    ),
                ],
                partial=True
            ))
        p.reset()
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                    ),
                ],
            ))

    def test_reset_after_peer_header(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]
                    ),
                ],
                partial=True
            ))
        p.reset()
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                    ),
                ],
            ))

    def test_send_stream_error_from_feed(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive(b"&foo;")
                ]),
            TransportMock.Write(
                STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                    condition="restricted-xml",
                    text="non-predefined entities are not allowed in XMPP"
                ).encode("utf-8")
            ),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

    def test_send_stream_error_on_malformed_xml(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive("<</>".encode("utf-8"))
                ]),
            TransportMock.Write(
                STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                    condition="bad-format",
                    text="&lt;unknown&gt;:1:149: not well-formed (invalid token)"
                ).encode("utf-8")
            ),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

    def test_error_propagation(self):
        def cb(stanza):
            pass

        t, p = self._make_stream(to=TEST_PEER)
        p.stanza_parser.add_class(RuntimeErrorRaisingStanza, cb)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive("<foo xmlns='jabber:client' />")
                ]),
            TransportMock.Write(
                STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                    condition="internal-server-error",
                    text="Internal error while parsing XML. Client logs have "
                         "more details."
                ).encode("utf-8")
            ),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

    def test_check_version(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(
                                self._make_peer_header(version=(2, 0))),
                        ]),
                    TransportMock.Write(
                        STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                            condition="unsupported-version",
                            text="unsupported version").encode("utf-8")
                    ),
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(),
                    TransportMock.Close()
                ]
            ))

    def test_unknown_top_level_produces_stream_error(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                            TransportMock.Receive(
                                b'<foo xmlns="uri:bar"/>'),
                        ]),
                    TransportMock.Write(
                        STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                            condition="unsupported-stanza-type",
                            text="unsupported stanza: {uri:bar}foo",
                        ).encode("utf-8")),
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(
                        response=[
                            TransportMock.Receive(self._make_eos()),
                        ]
                    ),
                    TransportMock.Close()
                ]
            ))

    def test_unknown_iq_payload_ignored_without_error_handler(self):
        def catch_iq(obj):
            pass

        t, p = self._make_stream(to=TEST_PEER)
        p.stanza_parser.add_class(FakeIQ, catch_iq)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="get">'
                        b'<unknown-payload xmlns="uri:foo"/>'
                        b'</iq>'),
                ]),
        ]))

    def test_dispatch_unknown_iq_payload_to_error_handler(self):
        base = unittest.mock.Mock()

        t, p = self._make_stream(to=TEST_PEER)
        p.error_handler = base.error_handler

        p.stanza_parser.add_class(FakeIQ, base.iq_handler)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="result">'
                        b'<unknown-payload xmlns="uri:foo"/>'
                        b'</iq>'),
                ]),
        ]))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.error_handler(
                    unittest.mock.ANY,
                    unittest.mock.ANY)
            ]
        )

        call, = base.mock_calls
        name, args, kwargs = call
        partial_obj, exc = args
        self.assertIsInstance(
            partial_obj,
            FakeIQ
        )
        self.assertIsInstance(
            exc,
            stanza.UnknownIQPayload
        )

    def test_erroneous_iq_payload_ignored_without_error_handler(self):
        def catch_iq(obj):
            pass

        t, p = self._make_stream(to=TEST_PEER)
        p.stanza_parser.add_class(FakeIQ, catch_iq)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="get">'
                        b'<payload xmlns="uri:foo"/>'
                        b'</iq>'),
                ]),
        ]))

    def test_dispatch_erroneous_iq_payload_to_error_handler(self):
        base = unittest.mock.Mock()

        t, p = self._make_stream(to=TEST_PEER)
        p.error_handler = base.error_handler

        p.stanza_parser.add_class(FakeIQ, base.iq_handler)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(self._make_peer_header()),
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="result">'
                        b'<payload xmlns="uri:foo"/>'
                        b'</iq>'),
                ]),
        ]))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.error_handler(
                    unittest.mock.ANY,
                    unittest.mock.ANY)
            ]
        )

        call, = base.mock_calls
        name, args, kwargs = call
        partial_obj, exc = args
        self.assertIsInstance(
            partial_obj,
            FakeIQ
        )
        self.assertIsInstance(
            exc,
            stanza.PayloadParsingError
        )

    def test_detect_stream_header(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        self.assertEqual(
            protocol.State.OPEN,
            p.state
        )

    def test_send_xso(self):
        st = FakeIQ(structs.IQType.GET)
        st.id_ = "id"
        st.from_ = JID.fromstr("u1@foo.example/test")
        st.to = JID.fromstr("u2@foo.example/test")
        st.payload = Child()
        st.payload.attr = "foo"

        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        p.send_xso(st)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        b'<iq from="u1@foo.example/test" id="id"'
                        b' to="u2@foo.example/test" type="get">'
                        b'<payload xmlns="uri:foo" a="foo"/>'
                        b'</iq>'),
                ],
                partial=True
            )
        )

    def test_send_xso_reraises_error_from_writer(self):
        st = FakeIQ(structs.IQType.GET)
        st.id_ = "id"
        st.from_ = JID.fromstr("u1@foo.example/test")
        st.to = JID.fromstr("u2@foo.example/test")
        st.payload = Child()
        st.payload.attr = "foo"

        with contextlib.ExitStack() as stack:
            write_xmlstream = stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.XMLStreamWriter"
            ))

            t, p = self._make_stream(to=TEST_PEER)

            p.connection_made(t)

            stack.enter_context(unittest.mock.patch.object(
                p,
                "_require_connection",
            ))

            class FooException(Exception):
                pass

            exc = FooException()
            write_xmlstream().send.side_effect = exc

            with self.assertRaises(FooException) as ctx:
                p.send_xso(st)

            self.assertIs(ctx.exception, exc)

    def test_can_starttls(self):
        t, p = self._make_stream(to=TEST_PEER)
        self.assertFalse(p.can_starttls())
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        self.assertFalse(p.can_starttls())

    def test_starttls_raises_without_starttls_support(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        with self.assertRaisesRegex(RuntimeError, "starttls not available"):
            run_coroutine(p.starttls(object()))

    def test_starttls(self):
        t, p = self._make_stream(to=TEST_PEER, with_starttls=True)
        self.assertFalse(p.can_starttls())
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        self.assertTrue(p.can_starttls())

        ssl_context = unittest.mock.MagicMock()
        run_coroutine_with_peer(
            p.starttls(ssl_context),
            t.run_test(
                [
                    TransportMock.STARTTLS(ssl_context, None)
                ]
            )
        )

        # make sure that the state has been discarded
        self.assertIsNone(p._processor.remote_version)
        self.assertIsNone(p._processor.remote_from)
        self.assertIsNone(p._processor.remote_to)
        self.assertIsNone(p._processor.remote_id)

    def test_features_future(self):
        fut = asyncio.Future()
        t, p = self._make_stream(to=TEST_PEER, features_future=fut)

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                            TransportMock.Receive(self._make_peer_features()),
                        ]),
                ]
            )
        )

        self.assertTrue(fut.done())
        self.assertIsInstance(fut.result(), nonza.StreamFeatures)

    def test_transport_attribute(self):
        t, p = self._make_stream(to=TEST_PEER)

        self.assertIsNone(p.transport)

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )

        self.assertIs(p.transport, t)

        run_coroutine(
            t.run_test(
                [
                ],
                partial=False
            )
        )

        self.assertIsNone(p.transport)

    def test_clean_state_if_starttls_fails(self):
        had_exception = False
        def exc_handler(loop, context):
            nonlocal had_exception
            had_exception = True
            loop.default_exception_handler(context)

        self.loop.set_exception_handler(exc_handler)

        fut = asyncio.Future()
        t, p = self._make_stream(to=TEST_PEER,
                                 with_starttls=True,
                                 features_future=fut)

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )

        side_effect = ValueError()

        ssl_context = unittest.mock.MagicMock()
        # we raise from the callback to simulate a handshake failure
        post_handshake_callback = unittest.mock.MagicMock()
        # some unknown exception, definitely not an XMPP error
        post_handshake_callback.side_effect = side_effect

        starttls_result, test_result = run_coroutine(asyncio.gather(
            p.starttls(ssl_context, post_handshake_callback),
            t.run_test(
                [
                    TransportMock.STARTTLS(
                    ssl_context,
                        post_handshake_callback,
                        response=TransportMock.LoseConnection(side_effect)
                    )
                ]
            ),
            return_exceptions=True
        ))

        self.assertIs(side_effect, starttls_result)
        if test_result is not None:
            raise test_result

    def test_send_xso_raises_while_closed(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            p.send_xso(object())

    def test_send_xso_raises_while_closing(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        p.close()
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            p.send_xso(object())

    def test_starttls_raises_while_closed(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            run_coroutine(p.starttls(object()))

    def test_starttls_raises_while_closing(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        p.close()
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            run_coroutine(p.starttls(object()))

    def test_reset_raises_while_closed(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            p.reset()

    def test_reset_raises_while_closing(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(self._make_peer_header()),
                        ]),
                ],
                partial=True
            )
        )
        p.close()
        with self.assertRaisesRegex(ConnectionError,
                                     "not connected"):
            p.reset()

    def test_send_xso_reraises_connection_lost_error(self):
        exc = ValueError()
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.LoseConnection(exc=exc)
                        ]),
                ],
                partial=True
            )
        )
        with self.assertRaises(ValueError) as ctx:
            p.send_xso(stanza.IQ(structs.IQType.GET))
        self.assertIs(exc, ctx.exception)

    def test_starttls_reraises_connection_lost_error(self):
        exc = ValueError()
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.LoseConnection(exc=exc)
                        ]),
                ],
                partial=True
            )
        )
        with self.assertRaises(ValueError) as ctx:
            run_coroutine(p.starttls(object()))
        self.assertIs(exc, ctx.exception)

    def test_reset_reraises_connection_lost_error(self):
        exc = ValueError()
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.LoseConnection(exc=exc)
                        ]),
                ],
                partial=True
            )
        )
        with self.assertRaises(ValueError) as ctx:
            p.reset()
        self.assertIs(exc, ctx.exception)

    def test_reset_reraises_stream_error(self):
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(
                        self._make_peer_header(version=(1, 0)) +
                        self._make_stream_error("undefined-condition") +
                        self._make_eos()),
                    TransportMock.ReceiveEof()
                ]),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

        with self.assertRaises(errors.StreamError) as ctx:
            p.reset()

        self.assertEqual(
            errors.StreamErrorCondition.UNDEFINED_CONDITION,
            ctx.exception.condition
        )

    def test_streams_are_not_reusable(self):
        exc = ValueError()
        t, p = self._make_stream(to=TEST_PEER)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.LoseConnection(exc=exc)
                        ]),
                ],
                partial=True
            )
        )
        with self.assertRaisesRegex(RuntimeError,
                                    r"invalid state: State\.CLOSED"):
            run_coroutine(
                t.run_test(
                    [
                        TransportMock.Write(STREAM_HEADER),
                    ],
                    partial=True
                )
            )

    def test_on_closing_fires_on_connection_lost_with_error(self):
        fun = unittest.mock.MagicMock()
        fun.return_value = True
        exc = ValueError()

        t, p = self._make_stream(to=TEST_PEER)
        p.on_closing.connect(fun)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.LoseConnection(exc=exc)
                        ]),
                ],
                partial=True
            )
        )

        self.assertIsNotNone(fun.call_args, "on_closing did not fire")
        args = fun.call_args
        self.assertIs(exc, args[0][0])

    def test_on_closing_fires_on_stream_error(self):
        fun = unittest.mock.MagicMock()
        fun.return_value = True
        t, p = self._make_stream(to=TEST_PEER)
        p.on_closing.connect(fun)

        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(
                        self._make_peer_header(version=(1, 0)) +
                        self._make_stream_error("policy-violation") +
                        self._make_eos()),
                    TransportMock.ReceiveEof()
                ]),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

        self.assertIsNotNone(fun.call_args, "on_closing did not fire")
        args = fun.call_args
        self.assertIsInstance(args[0][0], errors.StreamError)
        self.assertEqual(
            errors.StreamErrorCondition.POLICY_VIOLATION,
            args[0][0].condition
        )

    def test_on_closing_fires_on_invalid_xml(self):
        fun = unittest.mock.MagicMock()
        fun.return_value = True

        t, p = self._make_stream(to=TEST_PEER)
        p.on_closing.connect(fun)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(
                                # I’m so sad I have to write this test case
                                "HTTP/1.1 400 Bad Request\r\nServer: nginx"
                            )
                        ]),
                    TransportMock.Write(
                        STREAM_ERROR_TEMPLATE_WITH_TEXT.format(
                            condition="bad-format",
                            text=(
                                "&lt;unknown&gt;:1:4: not well-formed "
                                "(invalid token)"
                            )
                        ).encode("utf-8")
                    ),
                    TransportMock.Write(
                        b"</stream:stream>"
                    ),
                    TransportMock.WriteEof(),
                    TransportMock.Close(),
                ],
                partial=True
            )
        )

        fun.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (exc,), _ = fun.mock_calls[0]
        self.assertIsInstance(
            exc,
            errors.StreamError,
        )
        self.assertEqual(
            exc.condition,
            errors.StreamErrorCondition.BAD_FORMAT
        )

    def test_fail_triggers_error_futures(self):
        t, p = self._make_stream(to=TEST_PEER)

        fut = p.error_future()

        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(
                        self._make_peer_header(version=(1, 0)) +
                        self._make_stream_error("policy-violation") +
                        self._make_eos()),
                    TransportMock.ReceiveEof()
                ]),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

        self.assertTrue(fut.done())

        exc = fut.exception()

        self.assertIsInstance(exc, errors.StreamError)
        self.assertEqual(
            errors.StreamErrorCondition.POLICY_VIOLATION,
            exc.condition
        )

    def test_fail_propagates_to_features_future(self):
        fut = asyncio.Future()
        t, p = self._make_stream(to=TEST_PEER, features_future=fut)

        run_coroutine(t.run_test([
            TransportMock.Write(
                STREAM_HEADER,
                response=[
                    TransportMock.Receive(
                        self._make_peer_header(version=(1, 0)) +
                        self._make_stream_error("policy-violation") +
                        self._make_eos()),
                    TransportMock.ReceiveEof()
                ]),
            TransportMock.Write(b"</stream:stream>"),
            TransportMock.WriteEof(),
            TransportMock.Close()
        ]))

        self.assertTrue(fut.done())

        exc = fut.exception()

        self.assertIsInstance(exc, errors.StreamError)
        self.assertEqual(
            errors.StreamErrorCondition.POLICY_VIOLATION,
            exc.condition
        )

    def test_mutual_shutdown(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        p.close()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(),
            ],
            partial=True
        ))

        run_coroutine(t.run_test(
            [
                TransportMock.Close()
            ],
            stimulus=[
                TransportMock.Receive(self._make_eos()),
                TransportMock.ReceiveEof()
            ]
        ))

    def test_close_and_wait(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        fut = asyncio.ensure_future(p.close_and_wait())

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSING
        )

        self.assertFalse(fut.done())

        run_coroutine(t.run_test(
            [
                TransportMock.Close()
            ],
            stimulus=[
                TransportMock.Receive(self._make_eos()),
                TransportMock.ReceiveEof()
            ]
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSED
        )

        self.assertTrue(fut.done())
        self.assertIsNone(fut.result())

    def test_close_and_wait_timeout(self):
        base_timeout = get_timeout(timedelta(seconds=0.1))
        t, p = self._make_stream(to=TEST_PEER, monitor_mock=False)

        p.deadtime_hard_limit = base_timeout

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        fut = asyncio.ensure_future(p.close_and_wait())

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSING
        )

        self.assertFalse(fut.done())

        run_coroutine(asyncio.sleep((base_timeout * 0.8).total_seconds()))

        self.assertFalse(fut.done())

        run_coroutine(asyncio.sleep(
            (base_timeout * 0.3 + base_timeout / 2).total_seconds()
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSING_STREAM_FOOTER_RECEIVED
        )

        self.assertTrue(fut.done())
        self.assertIsNone(fut.result())

        run_coroutine(t.run_test(
            [
                TransportMock.Abort(
                    response=[
                        TransportMock.Receive(
                            self._make_eos(),
                        ),
                        TransportMock.ReceiveEof(),
                    ]
                )
            ]
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSED
        )

    def test_ignore_unknown_stanzas_while_closing(self):
        # XXX: Without PEP 479, this test does never fail.

        catch_closing = unittest.mock.Mock()

        t, p = self._make_stream(to=TEST_PEER)

        p.on_closing.connect(catch_closing)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(self._make_peer_header()),
                    ]),
            ],
            partial=True
        ))

        p.close()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(
                    response=[
                        TransportMock.Receive(b"</stream:stream>"),
                        TransportMock.ReceiveEof(),
                    ]
                ),
                TransportMock.Close(),
            ],
            stimulus=[
                TransportMock.Receive(
                    b'<iq to="foo@foo.example" from="foo@bar.example"'
                    b' id="1234" type="get">'
                    b'</iq>'),
            ]
        ))

        self.assertSequenceEqual(
            [
                unittest.mock.call(None),
            ],
            catch_closing.mock_calls
        )

    def test_ignore_unknown_iq_payload_while_closing(self):
        # XXX: Without PEP 479, this test does never fail.

        catch_iq = unittest.mock.Mock()
        catch_closing = unittest.mock.Mock()

        t, p = self._make_stream(to=TEST_PEER)

        p.on_closing.connect(catch_closing)
        p.stanza_parser.add_class(FakeIQ, catch_iq)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(self._make_peer_header()),
                    ]),
            ],
            partial=True
        ))

        p.close()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(
                    response=[
                        TransportMock.Receive(b"</stream:stream>"),
                        TransportMock.ReceiveEof(),
                    ]
                ),
                TransportMock.Close(),
            ],
            stimulus=[
                TransportMock.Receive(
                    b'<iq to="foo@foo.example" from="foo@bar.example"'
                    b' id="1234" type="get"><fnord xmlns="fnord" />'
                    b'</iq>'),
            ]
        ))

        self.assertSequenceEqual(
            [
                unittest.mock.call(None),
            ],
            catch_closing.mock_calls
        )

    def test_ignore_incorrect_payload_while_closing(self):
        # XXX: Without PEP 479, this test does never fail.

        catch_iq = unittest.mock.Mock()
        catch_closing = unittest.mock.Mock()

        t, p = self._make_stream(to=TEST_PEER)

        p.on_closing.connect(catch_closing)
        p.stanza_parser.add_class(FakeIQ, catch_iq)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(self._make_peer_header()),
                    ]),
            ],
            partial=True
        ))

        p.close()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(
                    response=[
                        TransportMock.Receive(b"</stream:stream>"),
                        TransportMock.ReceiveEof(),
                    ]
                ),
                TransportMock.Close(),
            ],
            stimulus=[
                TransportMock.Receive(
                    b'<iq to="foo@foo.example" from="foo@bar.example"'
                    b' id="1234" type="get">'
                    b'<payload xmlns="uri:foo"/>'
                    b'</iq>'),
            ]
        ))

        self.assertSequenceEqual(
            [
                unittest.mock.call(None),
            ],
            catch_closing.mock_calls
        )

    def test_handle_unexpected_stream_footer(self):
        fun = unittest.mock.MagicMock()
        fun.return_value = True
        t, p = self._make_stream(to=TEST_PEER)
        p.on_closing.connect(fun)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0)) +
                            self._make_eos()),
                    ]
                ),
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(),
                TransportMock.Close()
            ],
            partial=True
        ))

        self.assertEqual(
            protocol.State.CLOSING_STREAM_FOOTER_RECEIVED,
            p.state
        )

        self.assertIsNotNone(fun.call_args, "on_closing did not fire")
        args = fun.call_args
        self.assertIsInstance(args[0][0], ConnectionError)
        self.assertRegex(
            str(args[0][0]),
            r"stream closed by peer"
        )

        run_coroutine(t.run_test(
            []
        ))

        self.assertEqual(
            protocol.State.CLOSED,
            p.state
        )

    def test_abort(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        p.abort()

        run_coroutine(t.run_test(
            [
                TransportMock.WriteEof(),
                TransportMock.Close()
            ],
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSED
        )

    def test_abort_is_noop_if_closed(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        p.abort()

        run_coroutine(t.run_test(
            [
                TransportMock.WriteEof(),
                TransportMock.Close()
            ],
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSED
        )

        p.abort()

    def test_abort_kills_closing_future_if_READY(self):
        t, p = self._make_stream(to=TEST_PEER)

        p.abort()

        self.assertEqual(
            p.state,
            protocol.State.CLOSED,
        )

    def test_abort_aborts_while_waiting_for_stream_footer(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertEqual(
            p.state,
            protocol.State.OPEN
        )

        p.close()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(b"</stream:stream>"),
                TransportMock.WriteEof(),
            ],
            partial=True,
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSING
        )

        p.abort()

        run_coroutine(t.run_test(
            [
                TransportMock.Close()
            ],
        ))

        self.assertEqual(
            p.state,
            protocol.State.CLOSED
        )

    def test_future_for_closing_state_is_disposed_of_in_connection_lost(
            self):
        with unittest.mock.patch("asyncio.ensure_future") as async_:
            t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertNotIn(
            unittest.mock.call().cancel(),
            async_.mock_calls,
        )

        p.connection_lost(None)

        self.assertIn(
            unittest.mock.call().cancel(),
            async_.mock_calls,
        )

    def test_mute_forwards_to_debug_wrapper(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertIsInstance(p._debug_wrapper, DebugWrapper)

        mute = unittest.mock.Mock()
        mute.return_value = unittest.mock.MagicMock(
            ["__enter__", "__exit__"]
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                p._debug_wrapper,
                "mute",
                new=mute,
            ))

            cm = p.mute()
            with cm:
                mute.assert_called_once_with()
                mute().__enter__.assert_called_once_with()
            mute().__exit__.assert_called_once_with(None, None, None)

    def test_mute_works_without_debugging_enabled(self):
        logger = logging.getLogger("test")
        logger.setLevel(logging.ERROR)

        t, p = self._make_stream(to=TEST_PEER, base_logger=logger)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertIsNone(p._debug_wrapper)

        with p.mute():
            pass

    def test_forwards_deadtime_attributes(self):
        _, p = self._make_stream(to=TEST_PEER)

        self.assertEqual(p.deadtime_soft_limit,
                         self.monitor.deadtime_soft_limit)
        self.assertEqual(p.deadtime_hard_limit,
                         self.monitor.deadtime_hard_limit)

        p.deadtime_hard_limit = unittest.mock.sentinel.hard
        p.deadtime_soft_limit = unittest.mock.sentinel.soft

        self.assertEqual(p.deadtime_soft_limit,
                         self.monitor.deadtime_soft_limit)
        self.assertEqual(p.deadtime_hard_limit,
                         self.monitor.deadtime_hard_limit)

        self.assertEqual(self.monitor.deadtime_soft_limit,
                         unittest.mock.sentinel.soft)
        self.assertEqual(self.monitor.deadtime_hard_limit,
                         unittest.mock.sentinel.hard)

    def test_registers_with_hard_limit_event_on_construction(self):
        _, p = self._make_stream(to=TEST_PEER)

        self.monitor.on_deadtime_hard_limit_tripped.connect.assert_called_once_with(
            p._deadtime_hard_limit_triggered
        )

    def test_registers_with_soft_limit_event_on_construction(self):
        _, p = self._make_stream(to=TEST_PEER)

        self.monitor.on_deadtime_soft_limit_tripped.connect.assert_called_once_with(
            p.on_deadtime_soft_limit_tripped
        )

    def test__deadtime_hard_limit_triggered_aborts_stream(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        p._deadtime_hard_limit_triggered()

        run_coroutine(t.run_test(
            [
                TransportMock.Abort(),
            ],
        ))

    def test__deadtime_hard_limit_triggered_generates_proper_error(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        fut = p.error_future()
        self.assertFalse(fut.done())

        p._deadtime_hard_limit_triggered()

        run_coroutine(t.run_test(
            [
                TransportMock.Abort(),
            ]
        ))

        self.assertTrue(fut.done())

        self.assertIsInstance(fut.exception(), ConnectionError)
        self.assertIn("timeout", str(fut.exception()))

    def test__deadtime_hard_limit_triggered_does_nothing_bad_if_invoked_after_closing(self):  # NOQA
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                        TransportMock.Close(),
                    ]),
            ],
        ))

        p._deadtime_hard_limit_triggered()

    def test_closure_clears_monitor_timeouts(self):
        t, p = self._make_stream(to=TEST_PEER)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                        TransportMock.Close(),
                    ]),
            ],
        ))

        self.assertIsNone(self.monitor.deadtime_hard_limit)
        self.assertIsNone(self.monitor.deadtime_soft_limit)

    def test_timeout_actually_works(self):
        dt = get_timeout(timedelta(seconds=0.1))
        t, p = self._make_stream(to=TEST_PEER, monitor_mock=False)

        p.deadtime_hard_limit = dt

        fut = p.error_future()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True,
        ))

        self.assertFalse(fut.done())

        run_coroutine(asyncio.sleep((dt * 1.1).total_seconds()))

        run_coroutine(t.run_test(
            [
                TransportMock.Abort(),
            ],
        ))

        self.assertTrue(fut.done())
        self.assertIsNotNone(fut.exception())
        self.assertIn("timeout", str(fut.exception()))

    def test_timeout_propagates_to_features_future(self):
        fut = asyncio.Future()
        t, p = self._make_stream(to=TEST_PEER, features_future=fut)

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            self._make_peer_header(version=(1, 0))
                        ),
                    ]),
            ],
            partial=True
        ))

        self.assertFalse(fut.done())

        p._deadtime_hard_limit_triggered()

        run_coroutine(t.run_test(
            [
                TransportMock.Abort(),
            ]
        ))

        self.assertTrue(fut.done())

        self.assertIsInstance(fut.exception(), ConnectionError)
        self.assertIn("timeout", str(fut.exception()))

    def test_data_received_notifies_monitor(self):
        t, p = self._make_stream(to=TEST_PEER)

        self.monitor.notify_received.assert_not_called()

        with unittest.mock.patch.object(p, "_rx_feed") as _rx_feed:
            # patch _rx_feed away to avoid it to do something sensible with it
            p.data_received(unittest.mock.sentinel.something)

        self.monitor.notify_received.assert_called_once_with()


class Testsend_and_wait_for(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def tearDown(self):
        del self.xmlstream
        del self.loop

    def _run_test(self, send, wait_for, actions, stimulus=None,
                  timeout=None, **kwargs):
        return run_coroutine(
            asyncio.gather(
                protocol.send_and_wait_for(
                    self.xmlstream,
                    send,
                    wait_for,
                    timeout=timeout),
                self.xmlstream.run_test(
                    actions,
                    stimulus=stimulus,
                    **kwargs)
            )
        )[0]

    def test_send_and_return_response(self):
        class Q(xso.XSO):
            TAG = ("uri:foo", "Q")

        class R(xso.XSO):
            TAG = ("uri:foo", "R")

        instance = R()

        result = self._run_test(
            [
                Q(),
            ],
            [
                R
            ],
            [
                XMLStreamMock.Send(
                    Q(),
                    response=XMLStreamMock.Receive(instance)
                )
            ]
        )

        self.assertIs(result, instance)

    def test_receive_exactly_one(self):
        class Q(xso.XSO):
            TAG = ("uri:foo", "Q")

        class R(xso.XSO):
            TAG = ("uri:foo", "R")

        instance = R()

        with self.assertRaisesRegex(AssertionError,
                                    "no handler registered for"):
            self._run_test(
                [
                    Q(),
                ],
                [
                    R
                ],
                [
                    XMLStreamMock.Send(
                        Q(),
                        response=[
                            XMLStreamMock.Receive(instance),
                            XMLStreamMock.Receive(instance),
                        ]
                    )
                ]
            )

    def test_timeout(self):
        class Q(xso.XSO):
            TAG = ("uri:foo", "Q")

        class R(xso.XSO):
            TAG = ("uri:foo", "R")

        instance = R()

        with self.assertRaises(TimeoutError):
            self._run_test(
                [
                    Q(),
                ],
                [
                    R
                ],
                [
                    XMLStreamMock.Send(
                        Q(),
                    )
                ],
                timeout=0.1
            )

        with self.assertRaisesRegex(AssertionError,
                                    "no handler registered for"):
            run_coroutine(self.xmlstream.run_test(
                [],
                stimulus=XMLStreamMock.Receive(instance)
            ))

    def test_clean_up_if_sending_fails(self):
        class Q(xso.XSO):
            TAG = ("uri:foo", "Q")

        class R(xso.XSO):
            TAG = ("uri:foo", "R")

        instance = R()

        exc = ValueError()

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Fail(exc=exc)
        ))

        with self.assertRaises(ValueError) as ctx:
            self._run_test(
                [
                    Q(),
                ],
                [
                    R
                ],
                [
                ]
            )

        # asserts that the send did not do anything
        run_coroutine(self.xmlstream.run_test(
            [],
        ))

    def test_send_and_return_response(self):
        class Q(xso.XSO):
            TAG = ("uri:foo", "Q")

        class R(xso.XSO):
            TAG = ("uri:foo", "R")

        instance = R()

        exc = ValueError()

        with self.assertRaises(ValueError) as ctx:
            self._run_test(
                [
                    Q(),
                ],
                [
                    R
                ],
                [
                    XMLStreamMock.Send(
                        Q(),
                        response=XMLStreamMock.Fail(exc)
                    )
                ]
            )

        self.assertIs(exc, ctx.exception)

    def test_handles_setup_issues_properly(self):
        class FooException(Exception):
            pass

        def generate_results():
            yield
            yield FooException()

        xmlstream = unittest.mock.Mock(spec=protocol.XMLStream)
        xmlstream.stanza_parser = unittest.mock.Mock(spec=xso.XSOParser)
        xmlstream.stanza_parser.add_class.side_effect = generate_results()

        with self.assertRaises(FooException):
            run_coroutine(
                protocol.send_and_wait_for(
                    xmlstream,
                    [unittest.mock.sentinel.send],
                    [
                        unittest.mock.sentinel.c1,
                        unittest.mock.sentinel.c2,
                    ]
                )
            )

        self.assertSequenceEqual(
            xmlstream.stanza_parser.mock_calls,
            [
                unittest.mock.call.add_class(
                    unittest.mock.sentinel.c1,
                    unittest.mock.ANY,
                ),
                unittest.mock.call.add_class(
                    unittest.mock.sentinel.c2,
                    unittest.mock.ANY,
                ),
                unittest.mock.call.remove_class(
                    unittest.mock.sentinel.c1,
                ),
            ]
        )

    def test_handles_send_issues_properly(self):
        class FooException(Exception):
            pass

        xmlstream = unittest.mock.Mock(spec=protocol.XMLStream)
        xmlstream.stanza_parser = unittest.mock.Mock(spec=xso.XSOParser)
        xmlstream.send_xso.side_effect = FooException()

        with self.assertRaises(FooException):
            run_coroutine(
                protocol.send_and_wait_for(
                    xmlstream,
                    [unittest.mock.sentinel.send],
                    [
                        unittest.mock.sentinel.c1,
                        unittest.mock.sentinel.c2,
                    ]
                )
            )

        self.assertSequenceEqual(
            xmlstream.mock_calls,
            [
                unittest.mock.call.error_future(),
                unittest.mock.call.stanza_parser.add_class(
                    unittest.mock.sentinel.c1,
                    unittest.mock.ANY,
                ),
                unittest.mock.call.stanza_parser.add_class(
                    unittest.mock.sentinel.c2,
                    unittest.mock.ANY,
                ),
                unittest.mock.call.send_xso(unittest.mock.sentinel.send),
                unittest.mock.call.stanza_parser.remove_class(
                    unittest.mock.sentinel.c2,
                ),
                unittest.mock.call.stanza_parser.remove_class(
                    unittest.mock.sentinel.c1,
                ),
            ]
        )

    def test_receive_handler_invokes_cb(self):
        class_added_fut = asyncio.Future()
        error_future = asyncio.Future()

        def class_added(*args, **kwargs):
            class_added_fut.set_result(None)
            return None

        xmlstream = unittest.mock.Mock(spec=protocol.XMLStream)
        xmlstream.error_future.return_value = error_future
        xmlstream.stanza_parser = unittest.mock.Mock(spec=xso.XSOParser)
        xmlstream.stanza_parser.add_class.side_effect = class_added
        xmlstream._loop = self.loop

        cb_mock = unittest.mock.Mock()
        cb_mock.return_value = None

        task = asyncio.ensure_future(
            protocol.send_and_wait_for(
                xmlstream,
                [
                    unittest.mock.sentinel.send,
                ],
                [
                    unittest.mock.sentinel.c1,
                ],
                cb=cb_mock
            )
        )

        run_coroutine(class_added_fut)

        xmlstream.stanza_parser.add_class.assert_called_once_with(
            unittest.mock.sentinel.c1,
            unittest.mock.ANY,
        )

        _, (_, cb), _ = xmlstream.stanza_parser.add_class.mock_calls[0]

        cb_mock.assert_not_called()

        cb(unittest.mock.sentinel.obj)
        cb_mock.assert_called_once_with(unittest.mock.sentinel.obj)

        result = run_coroutine(task)
        self.assertEqual(result, unittest.mock.sentinel.obj)


class Testreset_stream_and_get_features(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def _run_test(self, actions, stimulus=None,
                  timeout=None, **kwargs):
        return run_coroutine(
            asyncio.gather(
                protocol.reset_stream_and_get_features(
                    self.xmlstream,
                    timeout=timeout),
                self.xmlstream.run_test(
                    actions,
                    stimulus=stimulus,
                    **kwargs)
            )
        )[0]

    def test_send_and_return_features(self):
        features = nonza.StreamFeatures()

        result = self._run_test(
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(features)
                )
            ]
        )

        self.assertIs(result, features)

    def test_receive_exactly_one(self):
        features = nonza.StreamFeatures()

        with self.assertRaisesRegex(AssertionError,
                                     "no handler registered for"):
            self._run_test(
                [
                    XMLStreamMock.Reset(
                        response=[
                            XMLStreamMock.Receive(features),
                            XMLStreamMock.Receive(features),
                        ]
                    )
                ]
            )

    def test_timeout(self):
        features = nonza.StreamFeatures()

        with self.assertRaises(TimeoutError):
            self._run_test(
                [
                    XMLStreamMock.Reset()
                ],
                timeout=0.1
            )

        with self.assertRaisesRegex(AssertionError,
                                     "no handler registered for"):
            run_coroutine(self.xmlstream.run_test(
                [],
                stimulus=XMLStreamMock.Receive(features)
            ))

    def test_clean_up_if_sending_fails(self):
        features = nonza.StreamFeatures()

        exc = ValueError()

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Fail(exc=exc)
        ))

        with self.assertRaises(ValueError) as ctx:
            self._run_test(
                [
                ],
            )

        # asserts that the send did not do anything
        run_coroutine(self.xmlstream.run_test(
            [],
        ))

    def test_do_not_timeout_if_stream_fails(self):
        features = nonza.StreamFeatures()

        exc = ValueError()

        with self.assertRaises(ValueError) as ctx:
            self._run_test(
                [
                    XMLStreamMock.Reset(response=XMLStreamMock.Fail(
                        exc=exc))
                ]
            )

    def tearDown(self):
        del self.xmlstream
        del self.loop


class Testsend_stream_error_and_close(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def test_sends_and_closes(self):
        protocol.send_stream_error_and_close(
            self.xmlstream,
            errors.StreamErrorCondition.CONNECTION_TIMEOUT,
            text="foobar",
            custom_condition=("uri:foo", "bar"))

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.StreamError(
                    condition=errors.StreamErrorCondition.CONNECTION_TIMEOUT,
                    text="foobar")
            ),
            XMLStreamMock.Close()
        ]))
