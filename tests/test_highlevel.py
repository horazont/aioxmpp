"""
Some tests which span multiple modules. These usually test high-level
functionality, or very obscure bugs, for example by testing against whole XML
stream dumps.
"""

import asyncio
import unittest

from datetime import timedelta

import aioxmpp.structs

from aioxmpp.testutils import (
    TransportMock,
    run_coroutine,
    run_coroutine_with_peer
)


TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example")
TEST_PEER = aioxmpp.structs.JID.fromstr("bar.example")

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


class TestProtocol(unittest.TestCase):
    def test_sm_works_correctly_with_invalid_payload(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            PEER_STREAM_HEADER_TEMPLATE.format(
                                minor=version[1],
                                major=version[0]).encode("utf-8")),
                        TransportMock.Receive(
                            b"<stream:features><sm xmlns='urn:xmpp:sm:3'/></stream:features>")
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        self.assertTrue(fut.done())

        s.ping_interval = timedelta(seconds=0.25)
        s.ping_opportunistic_interval = timedelta(seconds=0.25)

        s.start(p)
        run_coroutine_with_peer(
            s.start_sm(),
            t.run_test(
                [
                    TransportMock.Write(
                        b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                        response=[
                            TransportMock.Receive(
                                b'<enabled xmlns="urn:xmpp:sm:3" resume="true" id="foo"/>'
                            )
                        ]
                    )
                ],
                partial=True
            )
        )

        self.assertTrue(s.sm_enabled)
        self.assertEqual(s.sm_id, "foo")
        self.assertTrue(s.sm_resumable)

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        b'<r xmlns="urn:xmpp:sm:3"/>',
                        response=[
                            TransportMock.Receive(
                                b'<a xmlns="urn:xmpp:sm:3" h="0"/>',
                            ),
                            TransportMock.Receive(
                                b'<r xmlns="urn:xmpp:sm:3"/>',
                            )
                        ]
                    ),
                    TransportMock.Write(
                        b'<a xmlns="urn:xmpp:sm:3" h="0"/>'
                    )
                ],
                partial=True
            )
        )

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Write(
                        b'<iq id="foo" type="error"><error type="cancel"><feature-not-implemented xmlns="urn:ietf:params:xml:ns:xmpp-stanzas"/></error></iq>'
                    ),
                    TransportMock.Write(
                        b'<r xmlns="urn:xmpp:sm:3"/>',
                        response=[
                            TransportMock.Receive(
                                b'<a xmlns="urn:xmpp:sm:3" h="1"/>',
                            ),
                            TransportMock.Receive(
                                b'<r xmlns="urn:xmpp:sm:3"/>',
                            )
                        ]
                    ),
                    TransportMock.Write(
                        b'<a xmlns="urn:xmpp:sm:3" h="1"/>'
                    )
                ],
                stimulus=[
                    TransportMock.Receive(
                        b'<iq type="get" id="foo"><payload xmlns="fnord"/></iq>'
                    )
                ],
                partial=True
            )
        )
