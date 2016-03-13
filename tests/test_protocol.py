import asyncio
import unittest
import unittest.mock

import aioxmpp.stanza as stanza
import aioxmpp.xso as xso
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors

from aioxmpp.testutils import (
    TransportMock,
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer
)
from aioxmpp import xmltestutils

from aioxmpp.protocol import XMLStream
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


class TestXMLStream(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.loop = asyncio.get_event_loop()

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
                     **kwargs):
        if features_future is None:
            features_future = asyncio.Future()
        p = XMLStream(*args, sorted_attributes=True,
                      features_future=features_future,
                      **kwargs)
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
        with self.assertRaisesRegexp(RuntimeError, "invalid state"):
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

    def test_errorneous_iq_payload_ignored_without_error_handler(self):
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

    def test_dispatch_errorneous_iq_payload_to_error_handler(self):
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
        st = FakeIQ("get")
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
        with self.assertRaisesRegexp(RuntimeError, "starttls not available"):
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
        with self.assertRaisesRegexp(ConnectionError,
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
        with self.assertRaisesRegexp(ConnectionError,
                                     "not connected"):
            p.send_xso(object())

    def test_starttls_raises_while_closed(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegexp(ConnectionError,
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
        with self.assertRaisesRegexp(ConnectionError,
                                     "not connected"):
            run_coroutine(p.starttls(object()))

    def test_reset_raises_while_closed(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegexp(ConnectionError,
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
        with self.assertRaisesRegexp(ConnectionError,
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
            p.send_xso(stanza.IQ("get"))
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
            (namespaces.streams, "undefined-condition"),
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
            (namespaces.streams, "policy-violation"),
            args[0][0].condition
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
            (namespaces.streams, "policy-violation"),
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
        t, p = self._make_stream(to=TEST_PEER)

        self.assertEqual(
            15,
            p.shutdown_timeout
        )

        p.shutdown_timeout = 0.1

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

        run_coroutine(asyncio.sleep(0.08))

        self.assertFalse(fut.done())

        run_coroutine(asyncio.sleep(0.03))

        self.assertEqual(
            p.state,
            protocol.State.CLOSING_STREAM_FOOTER_RECEIVED
        )

        self.assertTrue(fut.done())
        self.assertIsNone(fut.result())

        run_coroutine(t.run_test(
            [
                TransportMock.Close(
                    response=[
                        TransportMock.Receive(
                            self._make_eos(),
                        ),
                        TransportMock.ReceiveEof(),
                    ]
                ),
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

    def tearDown(self):
        self.loop.set_exception_handler(
            type(self.loop).default_exception_handler
        )


class Testsend_and_wait_for(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

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

        with self.assertRaisesRegexp(AssertionError,
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

        with self.assertRaisesRegexp(AssertionError,
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


    def tearDown(self):
        del self.xmlstream
        del self.loop


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

        with self.assertRaisesRegexp(AssertionError,
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

        with self.assertRaisesRegexp(AssertionError,
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
            condition=(namespaces.streams, "connection-timeout"),
            text="foobar",
            custom_condition=("uri:foo", "bar"))

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.StreamError(
                    condition=(namespaces.streams, "connection-timeout"),
                    text="foobar")
            ),
            XMLStreamMock.Close()
        ]))
