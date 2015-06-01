import asyncio
import unittest
import unittest.mock

from .testutils import (
    run_coroutine,
    make_protocol_mock,
    TransportMock,
    XMLStreamMock,
    run_coroutine_with_peer
)
from .xmltestutils import XMLTestCase

import aioxmpp.xso as xso

from aioxmpp.utils import etree


class TestRunCoroutine(unittest.TestCase):
    def test_result(self):
        obj = object()

        @asyncio.coroutine
        def test():
            return obj

        self.assertIs(
            obj,
            run_coroutine(test())
        )

    def test_exception(self):
        @asyncio.coroutine
        def test():
            raise ValueError()

        with self.assertRaises(ValueError):
            run_coroutine(test())

    def test_timeout(self):
        @asyncio.coroutine
        def test():
            yield from asyncio.sleep(1)

        with self.assertRaises(asyncio.TimeoutError):
            run_coroutine(test(), timeout=0.01)


class TestTransportMock(unittest.TestCase):
    def setUp(self):
        self.protocol = make_protocol_mock()
        self.loop = asyncio.get_event_loop()
        self.t = TransportMock(self, self.protocol, loop=self.loop)

    def _run_test(self, t, *args, **kwargs):
        return run_coroutine(t.run_test(*args, **kwargs), loop=self.loop)

    def test_run_test(self):
        self._run_test(self.t, [])
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.connection_made(self.t),
                unittest.mock.call.connection_lost(None),
            ])

    def test_stimulus(self):
        self._run_test(self.t, [], stimulus=b"foo")
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.connection_made(self.t),
                unittest.mock.call.data_received(b"foo"),
                unittest.mock.call.connection_lost(None),
            ])

    def test_request_response(self):
        def data_received(data):
            assert data in {b"foo", b"baz"}
            if data == b"foo":
                self.t.write(b"bar")
            elif data == b"baz":
                self.t.close()

        self.protocol.data_received = data_received
        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"bar",
                    response=TransportMock.Receive(b"baz")),
                TransportMock.Close()
            ],
            stimulus=b"foo")

    def test_request_multiresponse(self):
        def data_received(data):
            assert data in {b"foo", b"bar", b"baz"}
            if data == b"foo":
                self.t.write(b"bar")
            elif data == b"bar":
                self.t.write(b"baric")
            elif data == b"baz":
                self.t.close()

        self.protocol.data_received = data_received
        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"bar",
                    response=[
                        TransportMock.Receive(b"bar"),
                        TransportMock.Receive(b"baz")
                    ]),
                TransportMock.Write(b"baric"),
                TransportMock.Close()
            ],
            stimulus=b"foo")

    def test_catch_asynchronous_invalid_action(self):
        def connection_made(transport):
            self.loop.call_soon(transport.close)

        self.protocol.connection_made = connection_made
        with self.assertRaises(AssertionError):
            self._run_test(
                self.t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_invalid_write(self):
        def connection_made(transport):
            transport.write(b"fnord")

        self.protocol.connection_made = connection_made
        with self.assertRaisesRegexp(
                AssertionError,
                "mismatch of expected and written data"):
            self._run_test(
                self.t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_surplus_write(self):
        def connection_made(transport):
            transport.write(b"fnord")

        self.protocol.connection_made = connection_made
        with self.assertRaisesRegexp(AssertionError, "unexpected write"):
            self._run_test(
                self.t,
                [
                ])

    def test_catch_unexpected_close(self):
        def connection_made(transport):
            transport.close()

        self.protocol.connection_made = connection_made
        with self.assertRaisesRegexp(AssertionError, "unexpected close"):
            self._run_test(
                self.t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_surplus_close(self):
        def connection_made(transport):
            transport.close()

        self.protocol.connection_made = connection_made
        with self.assertRaisesRegexp(AssertionError, "unexpected close"):
            self._run_test(
                self.t,
                [
                ])

    def test_allow_asynchronous_partial_write(self):
        def connection_made(transport):
            self.loop.call_soon(transport.write, b"f")
            self.loop.call_soon(transport.write, b"o")
            self.loop.call_soon(transport.write, b"o")

        self.protocol.connection_made = connection_made
        self._run_test(
            self.t,
            [
                TransportMock.Write(b"foo")
            ])

    def test_asynchronous_request_response(self):
        def data_received(data):
            self.assertIn(data, {b"foo", b"baz"})
            if data == b"foo":
                self.loop.call_soon(self.t.write, b"bar")
            elif data == b"baz":
                self.loop.call_soon(self.t.close)

        self.protocol.data_received = data_received
        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"bar",
                    response=TransportMock.Receive(b"baz")),
                TransportMock.Close()
            ],
            stimulus=b"foo")

    def test_response_eof_received(self):
        def connection_made(transport):
            transport.close()

        self.protocol.connection_made = connection_made
        self._run_test(
            self.t,
            [
                TransportMock.Close(
                    response=TransportMock.ReceiveEof()
                )
            ])
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.eof_received(),
                unittest.mock.call.connection_lost(None)
            ])

    def test_response_lose_connection(self):
        def connection_made(transport):
            transport.close()

        obj = object()

        self.protocol.connection_made = connection_made
        self._run_test(
            self.t,
            [
                TransportMock.Close(
                    response=TransportMock.LoseConnection(obj)
                )
            ])
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.connection_lost(obj)
            ])

    def test_writelines(self):
        def connection_made(transport):
            transport.writelines([b"foo", b"bar"])

        self.protocol.connection_made = connection_made

        self._run_test(
            self.t,
            [
                TransportMock.Write(b"foobar")
            ])

    def test_can_write_eof(self):
        self.assertTrue(self.t.can_write_eof())

    def test_abort(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made

        self._run_test(
            self.t,
            [
                TransportMock.Abort()
            ])

    def test_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made

        self._run_test(
            self.t,
            [
                TransportMock.WriteEof()
            ])

    def test_catch_surplus_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected write_eof"):
            self._run_test(
                self.t,
                [
                ])

    def test_catch_unexpected_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected write_eof"):
            self._run_test(
                self.t,
                [
                    TransportMock.Abort()
                ])

    def test_catch_surplus_abort(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected abort"):
            self._run_test(
                self.t,
                [
                ])

    def test_catch_unexpected_abort(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected abort"):
            self._run_test(
                self.t,
                [
                    TransportMock.WriteEof()
                ])

    def test_invalid_response(self):
        def connection_made(transport):
            transport.write(b"foo")

        self.protocol.connection_made = connection_made

        with self.assertRaisesRegexp(
                RuntimeError,
                "test specification incorrect"):
            self._run_test(
                self.t,
                [
                    TransportMock.Write(
                        b"foo",
                        response=1)
                ])

    def test_response_sequence(self):
        def connection_made(transport):
            transport.write(b"foo")

        self.protocol.connection_made = connection_made

        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"foo",
                    response=[
                        TransportMock.Receive(b"foo"),
                        TransportMock.ReceiveEof()
                    ])
            ])

        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.data_received(b"foo"),
                unittest.mock.call.eof_received(),
                unittest.mock.call.connection_lost(None),
            ])

    def test_clear_error_message(self):
        def connection_made(transport):
            transport.write(b"foo")
            transport.write(b"bar")

        self.protocol.connection_made = connection_made

        with self.assertRaises(AssertionError):
            self._run_test(
                self.t,
                [
                    TransportMock.Write(b"baz")
                ])

    def test_detached_response(self):
        data = []

        def data_received(blob):
            data.append(blob)

        def connection_made(transport):
            transport.write(b"foo")
            self.assertFalse(data)

        self.protocol.connection_made = connection_made
        self.protocol.data_received = data_received

        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"foo",
                    response=TransportMock.Receive(b"bar")
                )
            ])

    def test_no_response_conflict(self):
        data = []

        def data_received(blob):
            data.append(blob)

        def connection_made(transport):
            transport.write(b"foo")
            self.assertFalse(data)
            transport.write(b"bar")

        self.protocol.connection_made = connection_made
        self.protocol.data_received = data_received

        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"foo",
                    response=TransportMock.Receive(b"baz"),
                ),
                TransportMock.Write(
                    b"bar",
                    response=TransportMock.Receive(b"baz")
                )
            ])

    def test_partial(self):
        def connection_made(transport):
            transport.write(b"foo")

        self.protocol.connection_made = connection_made

        self._run_test(
            self.t,
            [
                TransportMock.Write(
                    b"foo",
                ),
            ],
            partial=True
        )

        self.t.write_eof()
        self.t.close()

        self._run_test(
            self.t,
            [
                TransportMock.WriteEof(),
                TransportMock.Close()
            ]
        )

    def test_no_starttls_by_default(self):
        self.assertFalse(self.t.can_starttls())
        with self.assertRaises(RuntimeError):
            run_coroutine(self.t.starttls())

    def test_starttls(self):
        self.t = TransportMock(self, self.protocol,
                               with_starttls=True,
                               loop=self.loop)
        self.assertTrue(self.t.can_starttls())

        fut = asyncio.Future()
        def connection_made(transport):
            fut.set_result(None)

        self.protocol.connection_made = connection_made

        ssl_context = unittest.mock.Mock()
        post_handshake_callback = unittest.mock.Mock()
        post_handshake_callback.return_value = []

        @asyncio.coroutine
        def late_starttls():
            yield from fut
            yield from self.t.starttls(ssl_context,
                                       post_handshake_callback)

        run_coroutine_with_peer(
            late_starttls(),
            self.t.run_test(
                [
                    TransportMock.STARTTLS(ssl_context,
                                           post_handshake_callback)
                ]
            )
        )

        post_handshake_callback.assert_called_once_with(self.t)

    def test_starttls_without_callback(self):
        self.t = TransportMock(self, self.protocol,
                               with_starttls=True,
                               loop=self.loop)
        self.assertTrue(self.t.can_starttls())

        fut = asyncio.Future()
        def connection_made(transport):
            fut.set_result(None)

        self.protocol.connection_made = connection_made

        ssl_context = unittest.mock.Mock()

        @asyncio.coroutine
        def late_starttls():
            yield from fut
            yield from self.t.starttls(ssl_context)

        run_coroutine_with_peer(
            late_starttls(),
            self.t.run_test(
                [
                    TransportMock.STARTTLS(ssl_context, None)
                ]
            )
        )

    def tearDown(self):
        del self.t
        del self.loop
        del self.protocol


class TestXMLStreamMock(XMLTestCase):
    def setUp(self):
        class Cls(xso.XSO):
            TAG = ("uri:foo", "foo")

        self.Cls = Cls
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)

    def test_register_stanza_handler(self):
        received = []

        def handler(obj):
            nonlocal received
            received.append(obj)

        obj = self.Cls()

        self.xmlstream.stanza_parser.add_class(self.Cls, handler)

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Receive(obj)
        ))

        self.assertSequenceEqual(
            [
                obj
            ],
            received
        )

    def test_send_xso(self):
        obj = self.Cls()

        def handler(obj):
            self.xmlstream.send_xso(obj)

        self.xmlstream.stanza_parser.add_class(self.Cls, handler)
        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Send(obj),
            ],
            stimulus=XMLStreamMock.Receive(obj)
        ))

    def test_catch_missing_stanza_handler(self):
        obj = self.Cls()

        with self.assertRaisesRegexp(AssertionError, "no handler registered"):
            run_coroutine(self.xmlstream.run_test(
                [
                ],
                stimulus=XMLStreamMock.Receive(obj)
            ))

    def test_no_termination_on_missing_action(self):
        obj = self.Cls()

        with self.assertRaises(asyncio.TimeoutError):
            run_coroutine(
                self.xmlstream.run_test(
                    [
                        XMLStreamMock.Send(obj),
                    ],
                ),
                timeout=0.05)

    def test_catch_surplus_send(self):
        self.xmlstream.send_xso(self.Cls())

        with self.assertRaisesRegexp(
                AssertionError,
                r"unexpected send_xso\(<tests.test_testutils.TestXMLStreamMock"
                r".setUp.<locals>.Cls object at 0x[a-f0-9]+>\)"):
            run_coroutine(self.xmlstream.run_test(
                [
                ],
            ))

    def test_reset(self):
        obj = self.Cls()

        def handler(obj):
            self.xmlstream.reset()

        self.xmlstream.stanza_parser.add_class(self.Cls, handler)
        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Reset(),
            ],
            stimulus=XMLStreamMock.Receive(obj)
        ))

    def test_catch_surplus_reset(self):
        self.xmlstream.reset()

        with self.assertRaisesRegexp(AssertionError,
                                     "unexpected reset"):
            run_coroutine(self.xmlstream.run_test(
                [
                ],
            ))

    def test_close(self):
        obj = self.Cls()

        def handler(obj):
            self.xmlstream.close()

        self.xmlstream.stanza_parser.add_class(self.Cls, handler)
        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Close(),
            ],
            stimulus=XMLStreamMock.Receive(obj)
        ))

    def test_catch_surplus_close(self):
        self.xmlstream.close()

        with self.assertRaisesRegexp(AssertionError,
                                     "unexpected close"):
            run_coroutine(self.xmlstream.run_test(
                [
                ],
            ))

    def test_starttls(self):
        ssl_context = unittest.mock.MagicMock()
        post_handshake_callback = unittest.mock.MagicMock()

        self.xmlstream.transport = object()

        run_coroutine(
            asyncio.gather(
                self.xmlstream.starttls(ssl_context, post_handshake_callback),
                self.xmlstream.run_test(
                    [
                        XMLStreamMock.STARTTLS(
                            ssl_context,
                            post_handshake_callback)
                    ],
                )
            )
        )

        post_handshake_callback.assert_called_once_with(
            self.xmlstream.transport)

    def test_starttls_without_callback(self):
        ssl_context = unittest.mock.MagicMock()

        self.xmlstream.transport = object()

        run_coroutine(
            asyncio.gather(
                self.xmlstream.starttls(ssl_context, None),
                self.xmlstream.run_test(
                    [
                        XMLStreamMock.STARTTLS(ssl_context, None)
                    ],
                )
            )
        )

    def test_starttls_reject_incorrect_arguments(self):
        ssl_context = unittest.mock.MagicMock()
        post_handshake_callback = unittest.mock.MagicMock()

        self.xmlstream.transport = object()

        with self.assertRaisesRegexp(AssertionError,
                                     "mismatched starttls argument"):
            run_coroutine(
                asyncio.gather(
                    self.xmlstream.starttls(object(), post_handshake_callback),
                    self.xmlstream.run_test(
                        [
                            XMLStreamMock.STARTTLS(
                                ssl_context,
                                post_handshake_callback)
                        ],
                    )
                )
            )

        with self.assertRaisesRegexp(AssertionError,
                                     "mismatched starttls argument"):
            run_coroutine(
                asyncio.gather(
                    self.xmlstream.starttls(ssl_context, object()),
                    self.xmlstream.run_test(
                        [
                            XMLStreamMock.STARTTLS(
                                ssl_context,
                                post_handshake_callback)
                        ],
                    )
                )
            )

    def test_starttls_propagates_exception_from_callback(self):
        ssl_context = unittest.mock.MagicMock()
        post_handshake_callback = unittest.mock.MagicMock()

        self.xmlstream.transport = object()

        exc = ValueError()
        post_handshake_callback.side_effect = exc

        caught_exception, other_result = run_coroutine(
            asyncio.gather(
                self.xmlstream.starttls(ssl_context, post_handshake_callback),
                self.xmlstream.run_test(
                    [
                        XMLStreamMock.STARTTLS(
                            ssl_context,
                            post_handshake_callback)
                    ],
                ),
                return_exceptions=True
            )
        )

        self.assertIs(caught_exception, exc)
        self.assertIs(other_result, None)

    def test_fail(self):
        exc = ValueError()
        fun = unittest.mock.MagicMock()
        fun.return_value = None

        ec_future = asyncio.async(self.xmlstream.error_future())

        self.xmlstream.on_failure.connect(fun)

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            stimulus=XMLStreamMock.Fail(exc=exc)
        ))

        self.assertTrue(ec_future.done())
        self.assertIs(exc, ec_future.exception())

        fun.assert_called_once_with(exc)

        with self.assertRaises(ValueError) as ctx:
            self.xmlstream.reset()
        self.assertIs(exc, ctx.exception)
        with self.assertRaises(ValueError) as ctx:
            run_coroutine(self.xmlstream.starttls(object()))
        self.assertIs(exc, ctx.exception)
        with self.assertRaises(ValueError) as ctx:
            self.xmlstream.send_xso(object())
        self.assertIs(exc, ctx.exception)

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            clear_exception=True
        ))

        self.xmlstream.reset()

        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Reset()
            ],
        ))

    def test_clean_failure(self):
        exc = ValueError()
        fun = unittest.mock.MagicMock()
        fun.return_value = None

        self.xmlstream.on_failure.connect(fun)

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            stimulus=[
                XMLStreamMock.Fail(exc=exc),
                XMLStreamMock.CleanFailure()
            ]
        ))

        fun.assert_called_once_with(exc)

        self.xmlstream.reset()

        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Reset()
            ],
        ))

    def tearDown(self):
        del self.xmlstream
        del self.loop
