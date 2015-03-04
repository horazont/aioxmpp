from .testutils import *
from .xmltestutils import XMLTestCase

from asyncio_xmpp.utils import etree


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

    def test_execute(self):
        self.t.execute(TransportMock.Receive(b"foo"))
        self.assertSequenceEqual(
            [
                unittest.mock.call.data_received(b"foo"),
            ],
            self.protocol.mock_calls)

    def test_execute_connection_made(self):
        self.t.execute(TransportMock.MakeConnection())
        self.assertSequenceEqual(
            [
                unittest.mock.call.connection_made(self.t),
            ],
            self.protocol.mock_calls)

    def test_execute_connection_made_mix(self):
        self.t.execute(TransportMock.MakeConnection())
        self._run_test(self.t, [])
        self.assertSequenceEqual(
            [
                unittest.mock.call.connection_made(self.t),
                unittest.mock.call.connection_lost(None),
            ],
            self.protocol.mock_calls)

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

    def tearDown(self):
        del self.protocol


class TestXMLStreamMock(XMLTestCase):
    def test_init(self):
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.CLOSE
            ])

        self.assertSequenceEqual(
            [
                XMLStreamMock.Special.CLOSE
            ],
            m._test_actions)

    def test_close(self):
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.CLOSE
            ])
        m.close()

        m = XMLStreamMock(self, [])
        with self.assertRaisesRegexp(AssertionError, "no actions left"):
            m.close()

        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.RESET
            ])
        with self.assertRaisesRegexp(AssertionError, "incorrect action"):
            m.close()

    def test_reset_stream(self):
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.RESET
            ])
        m.reset_stream()

        m = XMLStreamMock(self, [])
        with self.assertRaisesRegexp(AssertionError, "no actions left"):
            m.reset_stream()

    def test_reset_stream_with_response(self):
        response_node = etree.fromstring("<foo/>")
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.RESET.replace(
                    response=response_node)
            ])
        mock = unittest.mock.Mock()
        m.stream_level_hooks.add_callback("foo", mock)
        m.reset_stream()
        mock.assert_called_once_with(response_node)

    def test_mock_finalize(self):
        m = XMLStreamMock(self, [])
        m.mock_finalize()

        m = XMLStreamMock(self, [XMLStreamMock.Special.CLOSE])
        with self.assertRaisesRegexp(AssertionError,
                                     "expected actions were not performed"):
            m.mock_finalize()

    def test_mock_receive_node(self):
        m = XMLStreamMock(self, [])
        mock = unittest.mock.MagicMock()
        node = etree.fromstring("<foo/>")
        with self.assertRaisesRegexp(AssertionError, "no listener"):
            m.mock_receive_node(node)
        m.stream_level_hooks.add_callback("foo", mock)
        m.mock_receive_node(node)
        mock.assert_called_once_with(node)

    def test_send_node_mismatch(self):
        msg = etree.fromstring("<message/>")
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Node(etree.fromstring("<iq/>"),
                                   msg)
            ])
        mock = unittest.mock.MagicMock()
        m.stream_level_hooks.add_callback("message", mock)
        with self.assertRaises(AssertionError):
            m.send_node(etree.fromstring("<foo />"))
        mock.assert_not_called()

    def test_send_node(self):
        msg = etree.fromstring("<message/>")
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Node(etree.fromstring("<iq/>"),
                                   msg)
            ])
        mock = unittest.mock.MagicMock()
        m.stream_level_hooks.add_callback("message", mock)
        m.send_node(etree.fromstring("<iq />"))
        mock.assert_called_once_with(msg)

        with self.assertRaisesRegexp(AssertionError, "no actions left"):
            m.send_node(etree.fromstring("<iq />"))

    def test_some_sequence(self):
        m = XMLStreamMock(
            self,
            [
                XMLStreamMock.Special.RESET,
                XMLStreamMock.Node(etree.fromstring("<iq/>"), None),
                XMLStreamMock.Special.CLOSE,
            ])

        m.reset_stream()
        m.send_node(etree.fromstring("<iq />"))
        m.close()
        m.mock_finalize()

del TestXMLStreamMock
