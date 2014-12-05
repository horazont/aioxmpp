import asyncio
import unittest

import asyncio_xmpp.protocol as protocol
import asyncio_xmpp.errors as errors

from .mocks import TransportMock

class Test_State(unittest.TestCase):
    def test_UNCONNECTED(self):
        state = protocol._State.UNCONNECTED
        self.assertFalse(state.rx_open)
        self.assertFalse(state.tx_open)
        self.assertFalse(state.connected)
        self.assertFalse(state.stream_usable)

        self.assertEqual(state, state.with_closed_tx())
        self.assertEqual(state, state.with_closed_rx())

    def test_CONNECTED(self):
        state = protocol._State.CONNECTED
        self.assertTrue(state.rx_open)
        self.assertTrue(state.tx_open)
        self.assertTrue(state.connected)
        self.assertFalse(state.stream_usable)

        self.assertEqual(protocol._State.TX_CLOSED_RX_OPEN,
                         state.with_closed_tx())
        self.assertEqual(protocol._State.TX_OPEN_RX_CLOSED,
                         state.with_closed_rx())

    def test_STREAM_HEADER_RECEIVED(self):
        state = protocol._State.STREAM_HEADER_RECEIVED
        self.assertTrue(state.rx_open)
        self.assertTrue(state.tx_open)
        self.assertTrue(state.connected)
        self.assertTrue(state.stream_usable)

        self.assertEqual(protocol._State.TX_CLOSED_RX_OPEN,
                         state.with_closed_tx())
        self.assertEqual(protocol._State.TX_OPEN_RX_CLOSED,
                         state.with_closed_rx())

    def test_TX_CLOSED_RX_OPEN(self):
        state = protocol._State.TX_CLOSED_RX_OPEN
        self.assertTrue(state.rx_open)
        self.assertFalse(state.tx_open)
        self.assertFalse(state.connected)
        self.assertFalse(state.stream_usable)

        self.assertEqual(protocol._State.TX_CLOSED_RX_OPEN,
                         state.with_closed_tx())
        self.assertEqual(protocol._State.CLOSING,
                         state.with_closed_rx())

    def test_TX_OPEN_RX_CLOSED(self):
        state = protocol._State.TX_OPEN_RX_CLOSED
        self.assertFalse(state.rx_open)
        self.assertTrue(state.tx_open)
        self.assertFalse(state.connected)
        self.assertFalse(state.stream_usable)

        self.assertEqual(protocol._State.CLOSING,
                         state.with_closed_tx())
        self.assertEqual(protocol._State.TX_OPEN_RX_CLOSED,
                         state.with_closed_rx())

    def test_CLOSING(self):
        state = protocol._State.CLOSING
        self.assertFalse(state.rx_open)
        self.assertFalse(state.tx_open)
        self.assertFalse(state.connected)
        self.assertFalse(state.stream_usable)

        self.assertEqual(protocol._State.CLOSING,
                         state.with_closed_tx())
        self.assertEqual(protocol._State.CLOSING,
                         state.with_closed_rx())

class TestXMLStream(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self._loop = asyncio.get_event_loop()
        self._proto = protocol.XMLStream(
            to="localhost.localdomain",
            mode=protocol.Mode.C2S,
            loop=self._loop)
        self._mock = TransportMock(self._proto)

    def _mock_stream_header(self):
        self._mock.mock_data_received(
            b'<?xml version="1.0" ?>\n'
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="jabber:client"'
            b' from="localhost.localdomain"'
            b' version="1.0"'
            b' id="foobar">')

    def test_disconnect_cleanly(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(
            b'</stream:stream>')
        mock.mock_eof_received()
        mock.mock_connection_lost(None)
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b"</stream:stream>")

    def test_error_on_unknown_element(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(b"<foo />")
        mock.mock_eof_received()
        mock.mock_connection_lost(None)
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<unsupported-stanza-type/>'
            b'<text>no handler for {jabber:client}foo</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_duplicate_stream_header(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="jabber:client"'
            b' from="localhost.localdomain"'
            b' version="1.0"'
            b' id="foobar">')
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<unsupported-stanza-type/>'
            b'<text>Duplicate stream header</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_unsupported_version(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        mock.mock_data_received(
            b'<?xml version="1.0" ?>'
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="jabber:client"'
            b' from="localhost.localdomain"'
            b' version="2.0"'
            b' id="foobar">')
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<unsupported-version/>'
            b'<text>Unsupported version</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_malformed_version(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        mock.mock_data_received(
            b'<?xml version="1.0" ?>'
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="jabber:client"'
            b" version='foobar'"
            b' from="localhost.localdomain"'
            b' id="foobar">')
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<unsupported-version/>'
            b'<text>Malformed version</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_missing_version(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        mock.mock_data_received(
            b'<?xml version="1.0" ?>'
            b'<stream:stream xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="jabber:client"'
            b' from="localhost.localdomain"'
            b' id="foobar">')
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<unsupported-version/>'
            b'<text>Missing version tag</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_broken_xml(self):
        proto, mock = self._proto, self._mock

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(b"<foo <bar />")
        mock.mock_eof_received()
        mock.mock_connection_lost(None)
        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<not-well-formed/>'
            b'<text>'
            b'error parsing attribute name, line 2, column 55'
            b'</text>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_error_on_critical_timeout(self):
        proto, mock, loop = self._proto, self._mock, self._loop

        mock.mock_connection_made()
        self._mock_stream_header()

        @asyncio.coroutine
        def task():
            yield from proto.send_and_wait_for(
                [],
                ["{http://etherx.jabber.org/streams}features"],
                timeout=0,
            )

        with self.assertRaises(ConnectionError):
            loop.run_until_complete(task())

        self.assertTrue(mock.closed)

        self.assertSequenceEqual(
            mock.mock_buffer()[0],
            b"""<?xml version="1.0" ?>\n"""
            b"<stream:stream"
            b" xmlns='jabber:client'"
            b" xmlns:stream='http://etherx.jabber.org/streams'"
            b" version='1.0'"
            b" to='localhost.localdomain'>"
            b'<stream:error'
            b' xmlns:stream="http://etherx.jabber.org/streams"'
            b' xmlns="urn:ietf:params:xml:ns:xmpp-streams">'
            b'<connection-timeout/>'
            b'</stream:error>'
            b"</stream:stream>")

    def test_stream_level_element_hooks_success(self):
        proto, mock, loop = self._proto, self._mock, self._loop

        f = asyncio.Future()
        proto.stream_level_hooks.add_future(
            "{http://etherx.jabber.org/streams}features",
            f)

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(b"<stream:features />")

        @asyncio.coroutine
        def task():
            yield from asyncio.wait_for(f, 0, loop=loop)

        loop.run_until_complete(task())

        self.assertTrue(mock.closed)

    def test_stream_level_element_hooks_success(self):
        proto, mock, loop = self._proto, self._mock, self._loop

        f = asyncio.Future()
        proto.stream_level_hooks.add_future(
            "{http://etherx.jabber.org/streams}features",
            f)

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(b"<stream:features />")

        @asyncio.coroutine
        def task():
            yield from asyncio.wait_for(f, 0, loop=loop)

        loop.run_until_complete(task())

    def test_stream_level_element_hooks_stream_error(self):
        proto, mock, loop = self._proto, self._mock, self._loop

        f = asyncio.Future()
        proto.stream_level_hooks.add_future(
            "{http://etherx.jabber.org/streams}features",
            f)

        mock.mock_connection_made()
        self._mock_stream_header()
        mock.mock_data_received(
            b"<stream:error>"
            b"<reset xmlns='urn:ietf:params:xml:ns:xmpp-streams' />"
            b"<text xmlns='urn:ietf:params:xml:ns:xmpp-streams'>"
            b"foobar"
            b"</text>"
            b"</stream:error>"
        )

        @asyncio.coroutine
        def task():
            yield from asyncio.wait_for(f, 0, loop=loop)

        with self.assertRaises(errors.StreamError) as cm:
            loop.run_until_complete(task())

        self.assertEqual(
            cm.exception.error_tag,
            "reset")
        self.assertEqual(
            cm.exception.text,
            "foobar")
        self.assertIsNone(cm.exception.application_defined_condition)
        self.assertTrue(mock.closed)
