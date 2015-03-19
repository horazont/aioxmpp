import unittest
import unittest.mock

import aioxmpp.stanza as stanza
import aioxmpp.xso as xso

from .testutils import TransportMock, run_coroutine

from aioxmpp.protocol import XMLStream
from aioxmpp.structs import JID


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

    def _make_eos(self):
        return b"</stream:stream>"

    def _make_stream(self, *args, **kwargs):
        p = XMLStream(*args, sorted_attributes=True, **kwargs)
        t = TransportMock(self, p)
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
