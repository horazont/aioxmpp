"""
This module contains utilities used for testing aioxmpp code. These
utilities themselves are tested, which is meta, but cool.
"""
import asyncio
import collections
import functools
import logging
import unittest
import unittest.mock
import sys

from enum import Enum

import aioxmpp.callbacks
import aioxmpp.protocol
import aioxmpp.xso as xso

from aioxmpp.utils import etree


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


class SSLWrapperMock:
    """
    Mock for :class:`aioxmpp.ssl_wrapper.STARTTLSableTransportProtocol`.

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


class InteractivityMock:
    def __init__(self, tester, *, loop=None):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._tester = tester

    def _check_done(self):
        if not self._done.done() and not self._actions:
            self._done.set_result(None)

    def _pop_and_call_and_catch(self, fun, *args):
        @functools.wraps(fun)
        def wrap():
            try:
                self._actions.pop(0)
                fun(*args)
            except Exception as err:
                self._done.set_exception(err)
            else:
                self._check_done()
        self._loop.call_soon(wrap)

    def _format_unexpected_action(self, action_name, reason):
        return "unexpected {name} ({reason})".format(
            name=action_name,
            reason=reason
        )

    def _basic(self, name, action_cls):
        self._tester.assertTrue(
            self._actions,
            self._format_unexpected_action(name, "no actions left"),
        )
        head = self._actions[0]
        self._tester.assertIsInstance(
            head, action_cls,
            self._format_unexpected_action(name, "expected something else"),
        )
        self._actions.pop(0)
        self._execute_response(head.response)

    def _execute_response(self, response):
        if response is None:
            return

        try:
            do = response.do
        except AttributeError:
            # if we move the for-loop into the except block, *very* weird
            # things happen. weird enough so that I decided to snapshot the
            # state of the tree while I was debugging in the weird-things
            # branch.
            # Have a look if you’re brave.
            if not hasattr(response, "__iter__"):
                raise RuntimeError("test specification incorrect: "
                                   "unknown response type: "+repr(response))
        else:
            self._execute_single(do)
            return

        for item in response:
            self._execute_response(item)


_Write = collections.namedtuple("Write", ["data", "response"])
GenericTransportAction = collections.namedtuple(
    "GenericTransportAction",
    ["response"])
_LoseConnection = collections.namedtuple("LoseConnection", ["exc"])


class TransportMock(InteractivityMock,
                    asyncio.ReadTransport,
                    asyncio.WriteTransport):
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
        def do(self, transport, protocol):
            protocol.data_received(self.data)

    class Close(GenericTransportAction):
        def __new__(cls, *, response=None):
            return GenericTransportAction.__new__(cls, response=response)
        replace = GenericTransportAction._replace

    class ReceiveEof:
        def __repr__(self):
            return "ReceiveEof()"

        def do(self, transport, protocol):
            protocol.eof_received()

    class MakeConnection:
        def __repr__(self):
            return "MakeConnection()"

        def do(self, transport, protocol):
            transport._connection_made = True
            protocol.connection_made(transport)

    class LoseConnection(_LoseConnection):
        def __new__(cls, exc=None):
            return _LoseConnection.__new__(cls, exc)

        def do(self, transport, protocol):
            protocol.connection_lost(self.exc)
            transport._connection_made = False

    def __init__(self, tester, protocol, *, loop=None):
        super().__init__(tester, loop=loop)
        self._protocol = protocol
        self._actions = None
        self._connection_made = False
        self._rxd = []
        self._queue = asyncio.Queue()

    def _previously(self):
        buf = b"".join(self._rxd)
        result = [" (previously: "]
        if len(buf) > 100:
            result.append("[ {} more bytes ]".format(len(buf) - 100))
            buf = buf[-100:]
        result.append(str(buf)[1:])
        result.append(")")
        return "".join(result)

    def _format_unexpected_action(self, action_name, reason):
        return (
            super()._format_unexpected_action(action_name, reason) +
            self._previously()
        )

    def _execute_single(self, do):
        do(self, self._protocol)

    @asyncio.coroutine
    def run_test(self, actions, stimulus=None, partial=False):
        self._done = asyncio.Future()
        self._actions = actions
        if not self._connection_made:
            self._execute_response(self.MakeConnection())
        if stimulus:
            self._execute_response(self.Receive(stimulus))

        while not self._queue.empty() or self._actions:
            done, pending = yield from asyncio.wait(
                [
                    self._queue.get(),
                    self._done
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            if self._done not in pending:
                # raise if error
                self._done.result()
                done.remove(self._done)

            if done:
                value_future = next(iter(done))
                action, *args = value_future.result()
                if action == "write":
                    yield from self._write(*args)
                elif action == "write_eof":
                    yield from self._write_eof(*args)
                elif action == "close":
                    yield from self._close(*args)
                elif action == "abort":
                    yield from self._abort(*args)
                else:
                    assert False

            if self._done not in pending:
                break

        if self._connection_made and not partial:
            self._execute_response(self.LoseConnection())

    def can_write_eof(self):
        return True

    @asyncio.coroutine
    def _write_eof(self):
        self._basic("write_eof", self.WriteEof)

    @asyncio.coroutine
    def _write(self, data):
        self._tester.assertTrue(
            self._actions,
            "unexpected write (no actions left)"+self._previously()
        )
        head = self._actions[0]
        self._tester.assertIsInstance(head, self.Write)
        expected_data = head.data
        if not expected_data.startswith(data):
            logging.info("expected: %r", expected_data)
            logging.info("got this: %r", data)
            self._tester.assertEqual(
                expected_data[:len(data)],
                data,
                "mismatch of expected and written data"+self._previously()
            )
        self._rxd.append(data)
        expected_data = expected_data[len(data):]
        if not expected_data:
            self._actions.pop(0)
            self._execute_response(head.response)
        else:
            self._actions[0] = head.replace(data=expected_data)

    @asyncio.coroutine
    def _abort(self):
        self._basic("abort", self.Abort)

    @asyncio.coroutine
    def _close(self):
        self._basic("close", self.Close)

    def write(self, data):
        self._queue.put_nowait(("write", data))

    def write_eof(self):
        self._queue.put_nowait(("write_eof", ))

    def abort(self):
        self._queue.put_nowait(("abort", ))

    def close(self):
        self._queue.put_nowait(("close", ))


class XMLStreamMock(InteractivityMock):
    class Receive(collections.namedtuple("Receive", ["obj"])):
        def do(self, xmlstream):
            clsmap = xmlstream.stanza_parser.get_class_map()
            cls = type(self.obj)
            xmlstream._tester.assertIn(
                cls, clsmap,
                "no handler registered for {}".format(cls)
            )
            clsmap[cls](self.obj)

    class Send(collections.namedtuple("Send", ["obj", "response"])):
        def __new__(cls, obj, *, response=None):
            return super().__new__(cls, obj, response)

    class Reset(collections.namedtuple("Reset", ["response"])):
        def __new__(cls, *, response=None):
            return super().__new__(cls, response)

    class Close(collections.namedtuple("Close", ["response"])):
        def __new__(cls, *, response=None):
            return super().__new__(cls, response)

    def __init__(self, tester, *, loop=None):
        super().__init__(tester, loop=loop)
        self._queue = asyncio.Queue()
        self.stanza_parser = xso.XSOParser()

    def _execute_single(self, do):
        do(self)

    @asyncio.coroutine
    def run_test(self, actions, stimulus=None):
        self._done = asyncio.Future()
        self._actions = actions

        self._execute_response(stimulus)

        while not self._queue.empty() or self._actions:
            done, pending = yield from asyncio.wait(
                [
                    self._queue.get(),
                    self._done
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

            if self._done not in pending:
                # raise if error
                self._done.result()
                done.remove(self._done)

            if done:
                value_future = next(iter(done))
                action, *args = value_future.result()
                if action == "send":
                    yield from self._send_stanza(*args)
                elif action == "reset":
                    yield from self._reset(*args)
                elif action == "close":
                    yield from self._close(*args)
                else:
                    assert False

            if self._done not in pending:
                break

    @asyncio.coroutine
    def _send_stanza(self, obj):
        self._tester.assertTrue(
            self._actions,
            self._format_unexpected_action("send_stanza", "no actions left")
        )
        head = self._actions[0]
        self._tester.assertIsInstance(
            head, self.Send,
            self._format_unexpected_action(
                "send_stanza",
                "expected something different")
        )

        t1 = etree.Element("root")
        obj.unparse_to_node(t1)
        t2 = etree.Element("root")
        head.obj.unparse_to_node(t2)

        self._tester.assertSubtreeEqual(t1, t2)
        self._actions.pop(0)
        self._execute_response(head.response)

    @asyncio.coroutine
    def _reset(self):
        self._basic("reset", self.Reset)

    @asyncio.coroutine
    def _close(self):
        self._basic("close", self.Close)

    def send_stanza(self, obj):
        self._queue.put_nowait(("send", obj))

    def reset(self):
        self._queue.put_nowait(("reset",))

    def close(self):
        self._queue.put_nowait(("close",))
