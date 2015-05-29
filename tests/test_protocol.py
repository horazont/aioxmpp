import asyncio
import unittest
import unittest.mock

import aioxmpp.stanza as stanza
import aioxmpp.xso as xso
import aioxmpp.stream_xsos as stream_xsos

from .testutils import (
    TransportMock,
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer
)
from . import xmltestutils

from aioxmpp.protocol import XMLStream
from aioxmpp.structs import JID

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

    attr = xso.Attr("a", required=True)


class FakeIQ(stanza.IQ):
    TAG = ("jabber:client", "iq")


class RuntimeErrorRaisingStanza(stanza.StanzaBase):
    TAG = ("jabber:client", "foo")

    a = xso.Attr("a", required=True)

    def xso_error_handler(self, *args):
        raise RuntimeError("foobar")


FakeIQ.register_child(FakeIQ.payload, Child)


class TestXMLStream(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

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

    def test_connection_made_check_state(self):
        t, p = self._make_stream(to=TEST_PEER)
        with self.assertRaisesRegexp(RuntimeError, "invalid state"):
            run_coroutine(
                t.run_test(
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

    def test_close(self):
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
        p.close()
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(b"</stream:stream>"),
                    TransportMock.WriteEof(),
                    TransportMock.Close(),
                ],
            ))

    def test_reset(self):
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
                    TransportMock.WriteEof(),
                    TransportMock.Close(),
                ]
            ))

    def test_recover_unknown_iq_payload(self):
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
            TransportMock.Write(
                b'<iq from="foo@foo.example" id="1234"'
                b' to="foo@bar.example" type="error">' +
                STANZA_ERROR_TEMPLATE_WITHOUT_TEXT.format(
                    type="cancel",
                    condition="feature-not-implemented").encode("utf-8") +
                b'</iq>',
                response=[
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="get">'
                        b'<payload xmlns="uri:foo" a="test" />'
                        b'</iq>')
                ])
        ]))

    def test_recover_errornous_iq_payload(self):
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
            TransportMock.Write(
                b'<iq from="foo@foo.example" id="1234"'
                b' to="foo@bar.example" type="error">' +
                STANZA_ERROR_TEMPLATE_WITH_TEXT.format(
                    type="modify",
                    condition="bad-request",
                    text="missing attribute (None, 'a') on {uri:foo}payload"
                ).encode("utf-8") +
                b'</iq>',
                response=[
                    TransportMock.Receive(
                        b'<iq to="foo@foo.example" from="foo@bar.example"'
                        b' id="1234" type="get">'
                        b'<payload xmlns="uri:foo" a="test" />'
                        b'</iq>')
                ])
        ]))

    def test_send_stanza(self):
        st = FakeIQ()
        st.id_ = "id"
        st.from_ = JID.fromstr("u1@foo.example/test")
        st.to = JID.fromstr("u2@foo.example/test")
        st.type_ = "get"
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
        p.send_stanza(st)
        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        b'<iq from="u1@foo.example/test" id="id"'
                        b' to="u2@foo.example/test" type="get">'
                        b'<ns0:payload xmlns:ns0="uri:foo" a="foo"/>'
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
        with self.assertRaisesRegexp(RuntimeError, "no transport connected"):
            run_coroutine(p.starttls(object()))
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
        self.assertIsInstance(fut.result(), stream_xsos.StreamFeatures)

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


class Testsend_and_wait_for(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def _run_test(self, send, wait_for, actions, stimulus=None,
                  timeout=None):
        return run_coroutine(
            asyncio.gather(
                protocol.send_and_wait_for(
                    self.xmlstream,
                    send,
                    wait_for,
                    timeout=timeout),
                self.xmlstream.run_test(
                    actions,
                    stimulus=stimulus)
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

        with self.assertRaises(asyncio.TimeoutError):
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

    def tearDown(self):
        del self.xmlstream
        del self.loop


class Testreset_stream_and_get_features(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def _run_test(self, actions, stimulus=None,
                  timeout=None):
        return run_coroutine(
            asyncio.gather(
                protocol.reset_stream_and_get_features(
                    self.xmlstream,
                    timeout=timeout),
                self.xmlstream.run_test(
                    actions,
                    stimulus=stimulus)
            )
        )[0]

    def test_send_and_return_features(self):
        features = stream_xsos.StreamFeatures()

        result = self._run_test(
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(features)
                )
            ]
        )

        self.assertIs(result, features)

    def test_receive_exactly_one(self):
        features = stream_xsos.StreamFeatures()

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
        features = stream_xsos.StreamFeatures()

        with self.assertRaises(asyncio.TimeoutError):
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

    def tearDown(self):
        del self.xmlstream
        del self.loop
