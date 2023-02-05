########################################################################
# File name: test_highlevel.py
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
"""
Some tests which span multiple modules. These usually test high-level
functionality, or very obscure bugs, for example by testing against whole XML
stream dumps.
"""

import asyncio
import contextlib
import unittest

from datetime import timedelta

import aioxmpp.structs

from aioxmpp.testutils import (
    CoroutineMock,
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
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())
        s.soft_timeout = timedelta(seconds=0.25)

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
                            b"<stream:features><sm xmlns='urn:xmpp:sm:3'/>"
                            b"</stream:features>"
                        )
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        self.assertTrue(fut.done())

        s.start(p)
        run_coroutine_with_peer(
            s.start_sm(),
            t.run_test(
                [
                    TransportMock.Write(
                        b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                        response=[
                            TransportMock.Receive(
                                b'<enabled xmlns="urn:xmpp:sm:3" '
                                b'resume="true" id="foo"/>'
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
                        b'<iq id="foo" type="error"><error type="cancel">'
                        b'<service-unavailable'
                        b' xmlns="urn:ietf:params:xml:ns:xmpp-stanzas"/>'
                        b'</error></iq>'
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
                        b'<iq type="get" id="foo">'
                        b'<payload xmlns="fnord"/>'
                        b'</iq>'
                    )
                ],
                partial=True
            )
        )

    def test_sm_bootstrap_race(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())
        s.soft_timeout = timedelta(seconds=0.25)

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
                            b"<stream:features><sm xmlns='urn:xmpp:sm:3'/>"
                            b"</stream:features>"
                        )
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        self.assertTrue(fut.done())

        s.start(p)
        run_coroutine_with_peer(
            s.start_sm(),
            t.run_test(
                [
                    TransportMock.Write(
                        b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                        response=[
                            TransportMock.Receive(
                                b'<enabled xmlns="urn:xmpp:sm:3" '
                                b'resume="true" id="foo"/>'
                                b'<r xmlns="urn:xmpp:sm:3"/>'
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
                        b'<a xmlns="urn:xmpp:sm:3" h="0"/>'
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

    def test_sm_works_correctly_with_entirely_broken_stanza(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())
        s.soft_timeout = timedelta(seconds=0.25)

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
                            b"<stream:features><sm xmlns='urn:xmpp:sm:3'/>"
                            b"</stream:features>"
                        )
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        self.assertTrue(fut.done())

        s.start(p)
        run_coroutine_with_peer(
            s.start_sm(),
            t.run_test(
                [
                    TransportMock.Write(
                        b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                        response=[
                            TransportMock.Receive(
                                b'<enabled xmlns="urn:xmpp:sm:3" '
                                b'resume="true" id="foo"/>'
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
                        b'<a xmlns="urn:xmpp:sm:3" h="1"/>'
                    )
                ],
                stimulus=[
                    TransportMock.Receive(
                        b'<message type="get" from="foo/" id="foo">'
                        b'</message>'
                    )
                ],
                partial=True
            )
        )

    def test_iq_errors_are_not_replied_to(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            PEER_STREAM_HEADER_TEMPLATE.format(
                                minor=version[1],
                                major=version[0]).encode("utf-8")),
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        s.start(p)

        run_coroutine(
            t.run_test(
                [
                ],
                stimulus=[
                    TransportMock.Receive(
                        b'<iq type="error" id="foo">'
                        b'<payload xmlns="fnord"/>'
                        b'</iq>'
                    )
                ],
                partial=True,
            )
        )

        s.flush_incoming()

        run_coroutine(asyncio.sleep(0))

        run_coroutine(
            t.run_test(
                [
                ],
            )
        )

        s.stop()

    def test_iq_results_are_not_replied_to(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            PEER_STREAM_HEADER_TEMPLATE.format(
                                minor=version[1],
                                major=version[0]).encode("utf-8")),
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        s.start(p)

        run_coroutine(
            t.run_test(
                [
                ],
                stimulus=[
                    TransportMock.Receive(
                        b'<iq type="result" id="foo">'
                        b'<payload xmlns="fnord"/>'
                        b'</iq>'
                    )
                ],
                partial=True,
            )
        )

        s.flush_incoming()

        run_coroutine(asyncio.sleep(0))

        run_coroutine(
            t.run_test(
                [
                ],
            )
        )

        s.stop()

    def test_hard_deadtime_kills_stream(self):
        import aioxmpp.protocol
        import aioxmpp.stream

        version = (1, 0)

        fut = asyncio.Future()
        p = aioxmpp.protocol.XMLStream(
            to=TEST_PEER,
            sorted_attributes=True,
            features_future=fut)
        t = TransportMock(self, p)
        s = aioxmpp.stream.StanzaStream(TEST_FROM.bare())
        s.soft_timeout = timedelta(seconds=0.1)
        s.round_trip_time = timedelta(seconds=0.1)

        failure_fut = s.on_failure.future()

        run_coroutine(t.run_test(
            [
                TransportMock.Write(
                    STREAM_HEADER,
                    response=[
                        TransportMock.Receive(
                            PEER_STREAM_HEADER_TEMPLATE.format(
                                minor=version[1],
                                major=version[0]).encode("utf-8")),
                    ]
                ),
            ],
            partial=True
        ))

        self.assertEqual(p.state, aioxmpp.protocol.State.OPEN)

        s.start(p)

        IQ_bak = aioxmpp.IQ

        def fake_iq_constructor(*args, **kwargs):
            iq = IQ_bak(*args, **kwargs)
            iq.id_ = "ping"
            return iq

        with unittest.mock.patch("aioxmpp.stanza.IQ") as IQ:
            IQ.side_effect = fake_iq_constructor

            run_coroutine(
                t.run_test(
                    [
                        TransportMock.Write(
                            b'<iq id="ping" type="get">'
                            b'<ping xmlns="urn:xmpp:ping"/></iq>'
                        ),
                    ],
                    partial=True
                )
            )

        run_coroutine(
            t.run_test(
                [
                    TransportMock.Abort(),
                ],
            )
        )

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(s.running)

        self.assertTrue(failure_fut.done())
        self.assertIsInstance(failure_fut.exception(), ConnectionError)
        self.assertIn("timeout", str(failure_fut.exception()))

    def test_malformed_sm_failed_does_not_cause_loop(self):
        import aioxmpp.protocol
        import aioxmpp.stream
        import aioxmpp.node

        version = (1, 0)

        async def mk_pair():
            fut = asyncio.Future()
            p = aioxmpp.protocol.XMLStream(
                to=TEST_PEER,
                sorted_attributes=True,
                features_future=fut,
            )
            t = TransportMock(self, p)
            await t.run_test(
                [
                    TransportMock.Write(
                        STREAM_HEADER,
                        response=[
                            TransportMock.Receive(
                                PEER_STREAM_HEADER_TEMPLATE.format(
                                    minor=version[1],
                                    major=version[0]).encode("utf-8")),
                            TransportMock.Receive(
                                b"<stream:features>"
                                b"<sm xmlns='urn:xmpp:sm:3'/>"
                                b"</stream:features>"
                            )
                        ]
                    ),
                ],
                partial=True
            )
            features = await fut
            return t, p, features

        t, p, features = run_coroutine(mk_pair())

        client = aioxmpp.node.Client(
            local_jid=TEST_FROM,
            security_layer=aioxmpp.make_security_layer(
                password_provider="foobar2342",
            )._replace(tls_required=False),
            max_initial_attempts=None,
        )
        client.backoff_start = timedelta(seconds=0.05)

        id_counter = 0

        def autoset_id_impl(st):
            nonlocal id_counter
            if getattr(st, "id_", None) is None:
                st.id_ = str(id_counter)
                id_counter += 1

        with contextlib.ExitStack() as stack:
            connect_xmlstream = stack.enter_context(
                unittest.mock.patch("aioxmpp.node.connect_xmlstream",
                                    new=CoroutineMock())
            )
            connect_xmlstream.return_value = (None, p, features)

            autoset_id = stack.enter_context(unittest.mock.patch(
                "aioxmpp.stanza.StanzaBase.autoset_id",
                autospec=True,
            ))
            autoset_id.side_effect = autoset_id_impl

            done_future = asyncio.Future()
            client.on_stream_established.connect(
                done_future,
                client.on_stream_established.AUTO_FUTURE,
            )
            client.on_failure.connect(
                done_future,
                client.on_failure.AUTO_FUTURE,
            )
            client.start()

            run_coroutine_with_peer(
                done_future,
                t.run_test(
                    [
                        TransportMock.Write(
                            b'<iq id="0" type="set">'
                            b'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind"/>'
                            b'</iq>',
                            response=[
                                TransportMock.Receive(
                                    b'<iq id="0" type="result">'
                                    b'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">'
                                    b'<jid>foo@bar.example/fnord</jid>'
                                    b'</bind>'
                                    b'</iq>'
                                )
                            ]
                        ),
                        TransportMock.Write(
                            b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                            response=[
                                TransportMock.Receive(
                                    b'<enabled xmlns="urn:xmpp:sm:3"'
                                    b' resume="true" id="dronf"/>'
                                )
                            ]
                        ),
                    ],
                    partial=True
                )
            )

            done_future = asyncio.Future()
            client.on_stream_suspended.connect(
                done_future,
                client.on_stream_suspended.AUTO_FUTURE,
            )
            client.on_failure.connect(
                done_future,
                client.on_failure.AUTO_FUTURE,
            )

            # XXX: we are using try/except here instead of self.assertRaises,
            # because assertRaises calls traceback.clear_frames which for some
            # reason not clear to me in Python 3.9 and earlier causes the
            # _main() (from client._main_task) to be killed.
            #
            # This makes no sense, because _main_task is strongly referenced
            # from client, and we can even later print client._main_task. It
            # also doesn't go through __del__ of the task wrapped in
            # ensure_future, nor does it call close(), so this is really weird.
            #
            # I suspect some bug in clear_frames itself in Python 3.9 and
            # earlier, but given that we're at py 3.11 at this point and the
            # use of clear_frames is hopefully rather exotic, I'm not
            # inclined to debug further.
            #
            # Finding this out was a weekend **not** well-spent. At least I
            # learnt that `traceback.print_stack` reveals useful details even
            # in coroutines.
            try:
                run_coroutine_with_peer(
                    done_future,
                    t.run_test(
                        [],
                        stimulus=[
                            TransportMock.LoseConnection(
                                ConnectionError("ohno"),
                            )
                        ],
                        partial=True,
                    )
                )
            except ConnectionError:
                pass

            t, p, features = run_coroutine(mk_pair())
            connect_xmlstream.return_value = (None, p, features)

            done_future = asyncio.Future()
            client.on_stream_destroyed.connect(
                done_future,
                client.on_stream_destroyed.AUTO_FUTURE,
            )
            client.on_failure.connect(
                done_future,
                client.on_failure.AUTO_FUTURE,
            )

            run_coroutine(
                t.run_test(
                    [
                        TransportMock.Write(
                            b'<resume xmlns="urn:xmpp:sm:3" h="0"'
                            b' previd="dronf"/>',
                        ),
                    ],
                    partial=True
                )
            )

            # we have to delay the next attempt in order to re-mock stuff,
            # because the thing won't back-off in this specific condition
            connect_xmlstream.side_effect = ConnectionError()

            run_coroutine(
                t.run_test(
                    [
                        TransportMock.Write(
                            b'<stream:error><text xmlns="urn:ietf:params:xml:ns:xmpp-streams">Internal error while parsing XML. Client logs have more details.</text><internal-server-error xmlns="urn:ietf:params:xml:ns:xmpp-streams"/></stream:error>'
                            b'</stream:stream>'
                        ),
                        TransportMock.WriteEof(),
                        TransportMock.Close(),
                    ],
                    stimulus=[
                        TransportMock.Receive(
                            b'<failed xmlns="urn:xmpp:sm:3">'
                            b'<error type="cancel">'
                            b"<item-not-found"
                            b" xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>"
                            b"<text xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'>"
                            b"Unknown session"
                            b"</text>"
                            b"</error>"
                            b"</failed>"
                        )
                    ],
                    partial=True,
                ),
            )

            t, p, features = run_coroutine(mk_pair())
            connect_xmlstream.return_value = (None, p, features)
            connect_xmlstream.side_effect = None

            done_future = asyncio.Future()
            client.on_stream_established.connect(
                done_future,
                client.on_stream_established.AUTO_FUTURE,
            )
            client.on_failure.connect(
                done_future,
                client.on_failure.AUTO_FUTURE,
            )

            run_coroutine_with_peer(
                done_future,
                t.run_test(
                    [
                        TransportMock.Write(
                            b'<iq id="1" type="set">'
                            b'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">'
                            b'<resource>fnord</resource>'
                            b'</bind>'
                            b'</iq>',
                            response=[
                                TransportMock.Receive(
                                    b'<iq id="1" type="result">'
                                    b'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">'
                                    b'<jid>foo@bar.example/fnord</jid>'
                                    b'</bind>'
                                    b'</iq>'
                                )
                            ]
                        ),
                        TransportMock.Write(
                            b'<enable xmlns="urn:xmpp:sm:3" resume="true"/>',
                            response=[
                                TransportMock.Receive(
                                    b'<enabled xmlns="urn:xmpp:sm:3"'
                                    b' resume="true" id="dronf"/>'
                                )
                            ]
                        ),
                    ],
                    partial=True
                )
            )
