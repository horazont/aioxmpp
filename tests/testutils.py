"""
This module contains utilities used for testing asyncio_xmpp code. These
utilities themselves are tested, which is meta, but cool.
"""
import asyncio
import collections
import unittest
import unittest.mock

from enum import Enum

import lxml.etree as etree

import asyncio_xmpp.hooks
import asyncio_xmpp.protocol


def element_path(el, upto=None):
    segments = []
    parent = el.getparent()

    while parent != upto:
        similar = list(parent.iterchildren(el.tag))
        index = similar.index(el)
        segments.insert(0, (el.tag, index))
        el = parent
        parent = el.getparent()

    base = "/" + el.tag
    if segments:
        return base + "/" + "/".join(
            "{}[{}]".format(tag, index)
            for tag, index in segments
        )
    return base


def make_protocol_mock():
    return unittest.mock.Mock([
        "connection_made",
        "eof_received",
        "connection_lost",
        "data_received",
        "pause_writing",
        "resume_writing",
    ])


class XMLTestCase(unittest.TestCase):
    def assertChildrenEqual(self, tree1, tree2,
                            strict_ordering=False,
                            ignore_surplus_children=False,
                            ignore_surplus_attr=False):
        if not strict_ordering:
            t1_childmap = {}
            for child in tree1:
                t1_childmap.setdefault(child.tag, []).append(child)
            t2_childmap = {}
            for child in tree2:
                t2_childmap.setdefault(child.tag, []).append(child)

            t1_childtags = frozenset(t1_childmap)
            t2_childtags = frozenset(t2_childmap)

            if not ignore_surplus_children or (t1_childtags - t2_childtags):
                self.assertSetEqual(
                    t1_childtags,
                    t2_childtags,
                    "Child tag occurence differences at {}".format(
                        element_path(tree2)))

            for tag, t1_children in t1_childmap.items():
                t2_children = t2_childmap.get(tag, [])
                self.assertLessEqual(
                    len(t1_children),
                    len(t2_children),
                    "Surplus child at {}".format(element_path(tree2))
                )
                if not ignore_surplus_children:
                    self.assertGreaterEqual(
                        len(t1_children),
                        len(t2_children),
                        "Surplus child at {}".format(element_path(tree2))
                    )

                for c1, c2 in zip(t1_children, t2_children):
                    self.assertSubtreeEqual(
                        c1, c2,
                        ignore_surplus_attr=ignore_surplus_attr,
                        ignore_surplus_children=ignore_surplus_children,
                        strict_ordering=strict_ordering)
        else:
            t1_children = list(tree1)
            t2_children = list(tree2)
            self.assertLessEqual(
                len(t1_children),
                len(t2_children),
                "Surplus child at {}".format(element_path(tree2))
            )
            if not ignore_surplus_children:
                self.assertGreaterEqual(
                    len(t1_children),
                    len(t2_children),
                    "Surplus child at {}".format(element_path(tree2))
                )

            for c1, c2 in zip(t1_children, t2_children):
                self.assertSubtreeEqual(
                    c1, c2,
                    ignore_surplus_attr=ignore_surplus_attr,
                    ignore_surplus_children=ignore_surplus_children,
                    strict_ordering=strict_ordering)

    def assertAttributesEqual(self, el1, el2,
                              ignore_surplus_attr=False):
        t1_attrdict = el1.attrib
        t2_attrdict = el2.attrib
        t1_attrs = set(t1_attrdict)
        t2_attrs = set(t2_attrdict)

        if not ignore_surplus_attr or (t1_attrs - t2_attrs):
            self.assertSetEqual(
                t1_attrs,
                t2_attrs,
                "Attribute key differences at {}".format(element_path(el2))
            )

        for attr in t1_attrs:
            self.assertEqual(
                t1_attrdict[attr],
                t2_attrdict[attr],
                "Attribute value difference at {}@{}".format(
                    element_path(el2),
                    attr))

    def assertSubtreeEqual(self, tree1, tree2,
                           ignore_surplus_attr=False,
                           ignore_surplus_children=False,
                           strict_ordering=False):
        self.assertEqual(tree1.tag, tree2.tag,
                         "tag mismatch at {}".format(element_path(tree2)))
        self.assertAttributesEqual(tree1, tree2,
                                   ignore_surplus_attr=ignore_surplus_attr)
        self.assertChildrenEqual(
            tree1, tree2,
            ignore_surplus_children=ignore_surplus_children,
            ignore_surplus_attr=ignore_surplus_attr,
            strict_ordering=strict_ordering)


class TransportMock(asyncio.ReadTransport, asyncio.WriteTransport):
    """
    Mock a :class:`asyncio.Transport`.
    """

    def __init__(self, protocol):
        super().__init__()
        self.closed = False
        self._eof = False
        self._written = b""
        self._protocol = protocol

    def _require_non_eof(self):
        if self._eof:
            raise ConnectionError("Write connection already closed")

    def _require_open(self):
        if self.closed:
            raise ConnectionError("Underlying connection closed")

    def close(self):
        self._require_open()
        self.closed = True
        self._eof = True

    def get_extra_info(self, name, default=None):
        return default

    def abort(self):
        self.close()

    def can_write_eof(self):
        return True

    def write(self, data):
        self._require_non_eof()
        self._written += data

    def writelines(self, list_of_data):
        self.write(b"".join(list_of_data))

    def write_eof(self):
        self._require_non_eof()
        self._eof = True

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass

    def mock_connection_made(self):
        self._protocol.connection_made(self)

    def mock_eof_received(self):
        self._protocol.eof_received()

    def mock_connection_lost(self, exc):
        self._protocol.connection_lost(exc)

    def mock_data_received(self, data):
        self._protocol.data_received(data)

    def mock_pause_writing(self):
        self._protocol.pause_writing()

    def mock_resume_writing(self):
        self._protocol.resume_writing()

    def mock_buffer(self):
        return self._written, self._eof

    def mock_flush_buffer(self):
        buffer = self._written
        self._written = b""
        return buffer


class SSLWrapperMock:
    """
    Mock for :class:`asyncio_xmpp.ssl_wrapper.STARTTLSableTransportProtocol`.

    The *protocol* must be an :class:`XMLStreamMock`, as the
    :class:`SSLWrapperMock` depends on some private attributes to ensure the
    sequence of events is correct.
    """

    # FIXME: this mock is not covered by tests :(

    def __init__(self, loop, protocol):
        super().__init__()
        self._loop = loop
        self._protocol = protocol

    @asyncio.coroutine
    def starttls(self, ssl_context=None, post_handshake_callback=None):
        """
        Override the STARTTLS sequence. Instead of actually starting a TLS
        transport on the existing socket, only make sure that the test expects
        starttls to happen now. If so, return fake information on the TLS
        transport.
        """

        tester = self._protocol._tester
        tester.assertFalse(self._protocol._closed)
        tester.assertTrue(self._protocol._action_sequence,
                          "Unexpected client action (no actions left)")
        to_recv, to_send = self._protocol._action_sequence.pop(0)
        tester.assertTrue(to_recv.startswith("!starttls"),
                          "Unexpected starttls attempt by the client")
        return self, None

    def close(self):
        pass


_Special = collections.namedtuple("Special", ["type_", "response"])
_Node = collections.namedtuple("Node", ["type_", "response"])


class XMLStreamMock(asyncio_xmpp.protocol.XMLStream):
    class SpecialType(Enum):
        CLOSE = 0
        STARTTLS = 1
        RESET = 2

    class Special(_Special):
        def __new__(cls, type_, response=None):
            return _Special.__new__(cls, type_, response)
        replace = _Special._replace

    class Node(_Node):
        pass

    Special.CLOSE = Special(SpecialType.CLOSE)
    Special.STARTTLS = Special(SpecialType.STARTTLS)
    Special.RESET = Special(SpecialType.RESET)

    def __init__(self, tester, actions):
        self._tester = tester
        self._test_actions = actions
        self._stream_level_node_hooks = asyncio_xmpp.hooks.NodeHooks()

    def _require_action(self):
        self._tester.assertTrue(
            self._test_actions,
            "Unexpected client action (no actions left)")

    def _process_special(self, action):
        self._require_action()
        expected_action, response = self._test_actions.pop(0)
        self._tester.assertIs(
            action,
            expected_action,
            "Unexpected client action (incorrect action)")
        return response

    def _produce_response(self, response):
        if response is not None:
            self.mock_receive_node(response)

    def close(self):
        response = self._process_special(self.SpecialType.CLOSE)
        self._produce_response(response)

    def reset_stream(self):
        response = self._process_special(self.SpecialType.RESET)
        self._produce_response(response)

    def mock_finalize(self):
        self._tester.assertFalse(
            self._test_actions,
            "Some expected actions were not performed")

    def mock_receive_node(self, node):
        try:
            self._stream_level_node_hooks.unicast(node.tag, node)
        except KeyError:
            raise AssertionError(
                "Client has no listener for node sent by test: {}".format(
                    node.tag))

    def _tx_send_node(self, node):
        self._require_action()
        expected_node, response = self._test_actions.pop(0)
        self._tester.assertSubtreeEqual(expected_node, node)
        self._produce_response(response)

    def send_node(self, node):
        return self._tx_send_node(node)

# Tests for testing the test utils


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


class TestTransportMock(unittest.TestCase):
    def setUp(self):
        self.protocol = make_protocol_mock()

    def test_mock_connection_made(self):
        t = TransportMock(self.protocol)
        t.mock_connection_made()
        self.protocol.connection_made.assert_called_once_with(t)

    def test_mock_eof_received(self):
        t = TransportMock(self.protocol)
        t.mock_eof_received()
        self.protocol.eof_received.assert_called_once_with()

    def test_mock_pause_writing(self):
        t = TransportMock(self.protocol)
        t.mock_pause_writing()
        self.protocol.pause_writing.assert_called_once_with()

    def test_mock_resume_writing(self):
        t = TransportMock(self.protocol)
        t.mock_resume_writing()
        self.protocol.resume_writing.assert_called_once_with()

    def test_mock_connection_lost(self):
        instance = object()
        t = TransportMock(self.protocol)
        t.mock_connection_lost(instance)
        self.protocol.connection_lost.assert_called_once_with(instance)

    def test_mock_data_received(self):
        instance = object()
        t = TransportMock(self.protocol)
        t.mock_data_received(instance)
        self.protocol.data_received.assert_called_once_with(instance)

    def test_close(self):
        t = TransportMock(self.protocol)
        t.close()
        with self.assertRaises(ConnectionError):
            t.close()

    def test_write_eof(self):
        t = TransportMock(self.protocol)
        self.assertFalse(t.mock_buffer()[1])
        t.write_eof()
        with self.assertRaises(ConnectionError):
            t.write_eof()
        self.assertTrue(t.mock_buffer()[1])

    def test_can_write_eof(self):
        t = TransportMock(self.protocol)
        self.assertTrue(t.can_write_eof())

    def test_write(self):
        t = TransportMock(self.protocol)
        t.write(b"foo")
        self.assertEqual(
            b"foo",
            t.mock_buffer()[0])
        t.write(b"bar")
        self.assertEqual(
            b"foobar",
            t.mock_buffer()[0])

    def test_writelines(self):
        t = TransportMock(self.protocol)
        t.writelines([b"foo", b"bar"])
        self.assertEqual(
            b"foobar",
            t.mock_buffer()[0])

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
