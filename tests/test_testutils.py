from .testutils import *


class TestTestUtils(unittest.TestCase):
    def test_element_path(self):
        el = etree.fromstring("<foo><bar><baz /></bar>"
                              "<subfoo />"
                              "<bar><baz /></bar></foo>")
        baz1 = el[0][0]
        subfoo = el[1]
        baz2 = el[2][0]

        self.assertEqual(
            "/foo",
            element_path(el))
        self.assertEqual(
            "/foo/bar[0]/baz[0]",
            element_path(baz1))
        self.assertEqual(
            "/foo/subfoo[0]",
            element_path(subfoo))
        self.assertEqual(
            "/foo/bar[1]/baz[0]",
            element_path(baz2))


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

    def _run_test(self, t, *args, **kwargs):
        return run_coroutine(t.run_test(*args, **kwargs), loop=self.loop)

    def test_run_test(self):
        t = TransportMock(self, self.protocol)
        self._run_test(t, [])
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.connection_made(t),
                unittest.mock.call.connection_lost(None),
            ])

    def test_stimulus(self):
        t = TransportMock(self, self.protocol)
        self._run_test(t, [], stimulus=b"foo")
        self.assertSequenceEqual(
            self.protocol.mock_calls,
            [
                unittest.mock.call.connection_made(t),
                unittest.mock.call.data_received(b"foo"),
                unittest.mock.call.connection_lost(None),
            ])

    def test_request_response(self):
        def data_received(data):
            assert data in {b"foo", b"baz"}
            if data == b"foo":
                t.write(b"bar")
            elif data == b"baz":
                t.close()

        self.protocol.data_received = data_received
        t = TransportMock(self, self.protocol)
        self._run_test(
            t,
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
        t = TransportMock(self, self.protocol)
        with self.assertRaises(AssertionError):
            self._run_test(
                t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_invalid_write(self):
        def connection_made(transport):
            transport.write(b"fnord")

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)
        with self.assertRaisesRegexp(
                AssertionError,
                "mismatch of expected and written data"):
            self._run_test(
                t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_surplus_write(self):
        def connection_made(transport):
            transport.write(b"fnord")

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)
        with self.assertRaisesRegexp(AssertionError, "unexpected write"):
            self._run_test(
                t,
                [
                ])

    def test_catch_unexpected_close(self):
        def connection_made(transport):
            transport.close()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)
        with self.assertRaisesRegexp(AssertionError, "unexpected close"):
            self._run_test(
                t,
                [
                    TransportMock.Write(b"foo")
                ])

    def test_catch_surplus_close(self):
        def connection_made(transport):
            transport.close()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)
        with self.assertRaisesRegexp(AssertionError, "unexpected close"):
            self._run_test(
                t,
                [
                ])

    def test_allow_asynchronous_partial_write(self):
        def connection_made(transport):
            self.loop.call_soon(transport.write, b"f")
            self.loop.call_soon(transport.write, b"o")
            self.loop.call_soon(transport.write, b"o")

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)
        self._run_test(
            t,
            [
                TransportMock.Write(b"foo")
            ])

    def test_asynchronous_request_response(self):
        def data_received(data):
            self.assertIn(data, {b"foo", b"baz"})
            if data == b"foo":
                self.loop.call_soon(t.write, b"bar")
            elif data == b"baz":
                self.loop.call_soon(t.close)

        self.protocol.data_received = data_received
        t = TransportMock(self, self.protocol)
        self._run_test(
            t,
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
        t = TransportMock(self, self.protocol)
        self._run_test(
            t,
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
        t = TransportMock(self, self.protocol)
        self._run_test(
            t,
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
        t = TransportMock(self, self.protocol)

        self._run_test(
            t,
            [
                TransportMock.Write(b"foobar")
            ])

    def test_can_write_eof(self):
        t = TransportMock(self, self.protocol)
        self.assertTrue(t.can_write_eof())

    def test_abort(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        self._run_test(
            t,
            [
                TransportMock.Abort()
            ])

    def test_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        self._run_test(
            t,
            [
                TransportMock.WriteEof()
            ])

    def test_catch_surplus_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected write_eof"):
            self._run_test(
                t,
                [
                ])

    def test_catch_unexpected_write_eof(self):
        def connection_made(transport):
            transport.write_eof()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected write_eof"):
            self._run_test(
                t,
                [
                    TransportMock.Abort()
                ])

    def test_catch_surplus_abort(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected abort"):
            self._run_test(
                t,
                [
                ])

    def test_catch_unexpected_write_eof(self):
        def connection_made(transport):
            transport.abort()

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        with self.assertRaisesRegexp(
                AssertionError,
                "unexpected abort"):
            self._run_test(
                t,
                [
                    TransportMock.WriteEof()
                ])

    def test_invalid_response(self):
        def connection_made(transport):
            transport.write(b"foo")

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        with self.assertRaisesRegexp(
                RuntimeError,
                "test specification incorrect"):
            self._run_test(
                t,
                [
                    TransportMock.Write(
                        b"foo",
                        response=1)
                ])


    def test_response_sequence(self):
        def connection_made(transport):
            transport.write(b"foo")

        self.protocol.connection_made = connection_made
        t = TransportMock(self, self.protocol)

        self._run_test(
            t,
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
        t = TransportMock(self, self.protocol)

        with self.assertRaises(AssertionError):
            self._run_test(
                t,
                [
                    TransportMock.Write(b"baz")
                ])

    def tearDown(self):
        del self.protocol


class TestXMLTestCase(XMLTestCase):
    def test_assertSubtreeEqual_tag(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<bar />")

        with self.assertRaisesRegexp(AssertionError, "tag mismatch"):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_key_missing(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo />")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_attr_surplus_key(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo />")
        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_allow_surplus(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<foo a='1'/>")
        self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_attr_value_mismatch(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo a='2'/>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_value_mismatch_allow_surplus(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo a='1' b='2'/>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_missing_child(self):
        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo />")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_surplus_child(self):
        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo><bar/><bar/></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_allow_surplus_child(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<foo><bar/></foo>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_children=True)

        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo><bar/><bar/><fnord /></foo>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_children=True)

    def test_assertSubtreeEqual_allow_relative_reordering(self):
        t1 = etree.fromstring("<foo><bar/><baz/></foo>")
        t2 = etree.fromstring("<foo><baz/><bar/></foo>")

        self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_forbid_reordering_of_same(self):
        t1 = etree.fromstring("<foo><bar a='1' /><bar a='2' /></foo>")
        t2 = etree.fromstring("<foo><bar a='2' /><bar a='1' /></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_strict_ordering(self):
        t1 = etree.fromstring("<foo><bar/><baz/></foo>")
        t2 = etree.fromstring("<foo><baz/><bar/></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, strict_ordering=True)


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
