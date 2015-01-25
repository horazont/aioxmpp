"""
This module contains utilities used for testing asyncio_xmpp code. These
utilities themselves are tested, which is meta, but cool.
"""
import asyncio
import collections
import logging
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


def run_coroutine(coroutine, timeout=1.0, loop=None):
    if not loop:
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        asyncio.wait_for(
            coroutine,
            timeout=timeout))


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


_Write = collections.namedtuple("Write", ["data", "response"])
GenericTransportAction = collections.namedtuple(
    "GenericTransportAction",
    ["response"])
_LoseConnection = collections.namedtuple("LoseConnection", ["exc"])


class TransportMock(asyncio.ReadTransport, asyncio.WriteTransport):
    class Write(_Write):
        def __new__(cls, data, *, response=None):
            return _Write.__new__(cls, data=data, response=response)
        replace = _Write._replace

    class Abort(GenericTransportAction):
        def __new__(cls, *, response=None):
            return GenericTransportAction.__new__(cls, response=response)
        replace = GenericTransportAction._replace

    class WriteEof(GenericTransportAction):
        def __new__(cls, *, response=None):
            return GenericTransportAction.__new__(cls, response=response)
        replace = GenericTransportAction._replace

    class Receive(collections.namedtuple("Receive", ["data"])):
        pass

    class Close(GenericTransportAction):
        def __new__(cls, *, response=None):
            return GenericTransportAction.__new__(cls, response=response)
        replace = GenericTransportAction._replace

    class ReceiveEof:
        def __repr__(self):
            return "ReceiveEof()"

    class MakeConnection:
        def __repr__(self):
            return "MakeConnection()"

    class LoseConnection(_LoseConnection):
        def __new__(cls, exc=None):
            return _LoseConnection.__new__(cls, exc)

    def __init__(self, tester, protocol):
        self._protocol = protocol
        self._actions = None
        self._tester = tester
        self._connection_made = False

    def _check_done(self):
        if not self._done.done() and not self._actions:
            self._done.set_result(None)

    def execute(self, response):
        if isinstance(response, self.Receive):
            self._protocol.data_received(response.data)
        elif isinstance(response, self.ReceiveEof):
            self._protocol.eof_received()
        elif isinstance(response, self.LoseConnection):
            self._protocol.connection_lost(response.exc)
            self._connection_made = False
        elif isinstance(response, self.MakeConnection):
            self._connection_made = True
            self._protocol.connection_made(self)
        elif response is not None:
            if hasattr(response, "__iter__"):
                for item in response:
                    self.execute(item)
                return
            raise RuntimeError("test specification incorrect: "
                               "unknown response type: "+repr(response))

    @asyncio.coroutine
    def run_test(self, actions, stimulus=None):
        self._done = asyncio.Future()
        self._actions = actions
        if not self._connection_made:
            self.execute(self.MakeConnection())
        if stimulus:
            self.execute(self.Receive(stimulus))
        self._check_done()
        yield from self._done
        if self._connection_made:
            self.execute(self.LoseConnection())

    def can_write_eof(self):
        return True

    def write_eof(self):
        try:
            self._tester.assertTrue(
                self._actions,
                "unexpected write_eof (no actions left)")
            head = self._actions[0]
            self._tester.assertIsInstance(
                head, self.WriteEof,
                "unexpected write_eof (expected something else)")
            self._actions.pop(0)
            self.execute(head.response)
        except Exception as err:
            self._done.set_exception(err)
        else:
            self._check_done()

    def write(self, data):
        try:
            self._tester.assertTrue(
                self._actions,
                "unexpected write (no actions left)")
            head = self._actions[0]
            self._tester.assertIsInstance(head, self.Write)
            expected_data = head.data
            if not expected_data.startswith(data):
                logging.info("expected: %r", expected_data)
                logging.info("got this: %r", data)
                self._tester.assertEqual(
                    expected_data[:len(data)],
                    data,
                    "mismatch of expected and written data")
            expected_data = expected_data[len(data):]
            if not expected_data:
                self._actions.pop(0)
                self.execute(head.response)
            else:
                self._actions[0] = head.replace(data=expected_data)
        except Exception as err:
            if not self._done.done():
                self._done.set_exception(err)
        else:
            self._check_done()

    def abort(self):
        try:
            self._tester.assertTrue(
                self._actions,
                "unexpected abort (no actions left)")
            head = self._actions[0]
            self._tester.assertIsInstance(
                head, self.Abort,
                "unexpected abort (expected something else)")
            self._actions.pop(0)
            self.execute(head.response)
        except Exception as err:
            if not self._done.done():
                self._done.set_exception(err)
        else:
            self._check_done()

    def close(self):
        try:
            self._tester.assertTrue(
                self._actions,
                "unexpected close (no actions left)")
            head = self._actions[0]
            self._tester.assertIsInstance(
                head, self.Close,
                "unexpected close (expected something else)")
            self._actions.pop(0)
            self.execute(head.response)
        except Exception as err:
            if not self._done.done():
                self._done.set_exception(err)
        else:
            self._check_done()


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
