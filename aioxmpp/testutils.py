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

from datetime import timedelta

import aioxmpp.callbacks as callbacks
import aioxmpp.xso as xso
import aioxmpp.nonza as nonza

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


def run_coroutine_with_peer(
        coroutine,
        peer_coroutine,
        timeout=1.0,
        loop=None):
    loop = loop or asyncio.get_event_loop()

    local_future = asyncio.async(coroutine, loop=loop)
    remote_future = asyncio.async(peer_coroutine, loop=loop)

    done, pending = loop.run_until_complete(
        asyncio.wait(
            [
                local_future,
                remote_future,
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_EXCEPTION)
    )
    if not done:
        raise asyncio.TimeoutError("Test timed out")

    if pending:
        pending_fut = next(iter(pending))
        pending_fut.cancel()
        fut = next(iter(done))
        try:
            fut.result()
        except:
            # everything is fine, the other one failed
            raise
        else:
            if pending_fut == remote_future:
                raise asyncio.TimeoutError(
                    "Peer coroutine did not return in time")
            else:
                raise asyncio.TimeoutError(
                    "Coroutine under test did not return in time")

    if local_future.exception():
        # re-throw the error properly
        local_future.result()

    remote_future.result()
    return local_future.result()


class ConnectedClientMock(unittest.mock.Mock):
    on_stream_established = callbacks.Signal()
    on_stream_destroyed = callbacks.Signal()
    on_failure = callbacks.Signal()
    on_stopped = callbacks.Signal()

    before_stream_established = callbacks.SyncSignal()

    negotiation_timeout = timedelta(milliseconds=100)

    def __init__(self):
        super().__init__([
            "stream",
            "start",
            "stop",
            "set_presence",
        ])

        self.established = True

        self.stream_features = nonza.StreamFeatures()
        self.stream.send_iq_and_wait_for_reply = CoroutineMock()
        self.mock_services = {}

    def _get_child_mock(self, **kw):
        return unittest.mock.Mock(**kw)

    def summon(self, cls):
        try:
            return self.mock_services[cls]
        except KeyError:
            raise AssertionError("service class not provisioned in mock")


def make_connected_client():
    return ConnectedClientMock()


class CoroutineMock(unittest.mock.Mock):
    delay = 0

    @asyncio.coroutine
    def __call__(self, *args, **kwargs):
        result = super().__call__(*args, **kwargs)
        yield from asyncio.sleep(self.delay)
        return result


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
            # we have the for loop outside this except: block, to have a
            # clearer traceback.
            if not hasattr(response, "__iter__"):
                raise RuntimeError("test specification incorrect: "
                                   "unknown response type: "+repr(response))
        else:
            self._execute_single(do)
            return

        for item in response:
            self._execute_response(item)


_Write = collections.namedtuple("Write", ["data", "response"])
_STARTTLS = collections.namedtuple("STARTTLS",
                                   ["ssl_context",
                                    "post_handshake_callback",
                                    "response"])
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

    class STARTTLS(_STARTTLS):
        def __new__(cls, ssl_context, post_handshake_callback, *,
                    response=None):
            return _STARTTLS.__new__(cls,
                                     ssl_context,
                                     post_handshake_callback,
                                     response=response)
        replace = _STARTTLS._replace

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

    def __init__(self, tester, protocol, *, with_starttls=False, loop=None):
        super().__init__(tester, loop=loop)
        self._protocol = protocol
        self._actions = None
        self._connection_made = False
        self._rxd = []
        self._queue = asyncio.Queue()
        self._with_starttls = with_starttls

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
            if isinstance(stimulus, bytes):
                self._execute_response(self.Receive(stimulus))
            else:
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
                if action == "write":
                    yield from self._write(*args)
                elif action == "write_eof":
                    yield from self._write_eof(*args)
                elif action == "close":
                    yield from self._close(*args)
                elif action == "abort":
                    yield from self._abort(*args)
                elif action == "starttls":
                    yield from self._starttls(*args)
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

    @asyncio.coroutine
    def _starttls(self, ssl_context, post_handshake_callback, fut):
        self._tester.assertTrue(
            self._actions,
            self._format_unexpected_action("starttls", "no actions left"),
        )
        head = self._actions[0]
        self._tester.assertIsInstance(
            head, self.STARTTLS,
            self._format_unexpected_action("starttls",
                                           "expected something else"),
        )
        self._actions.pop(0)

        self._tester.assertEqual(
            ssl_context,
            head.ssl_context,
            "mismatched starttls argument")
        self._tester.assertEqual(
            post_handshake_callback,
            head.post_handshake_callback,
            "mismatched starttls argument")

        if post_handshake_callback:
            try:
                yield from post_handshake_callback(self)
            except Exception as exc:
                fut.set_exception(exc)
            else:
                fut.set_result(None)
        else:
            fut.set_result(None)

        self._execute_response(head.response)

    def write(self, data):
        self._queue.put_nowait(("write", data))

    def write_eof(self):
        self._queue.put_nowait(("write_eof", ))

    def abort(self):
        self._queue.put_nowait(("abort", ))

    def close(self):
        self._queue.put_nowait(("close", ))

    def can_starttls(self):
        return self._with_starttls

    @asyncio.coroutine
    def starttls(self, ssl_context=None, post_handshake_callback=None):
        if not self._with_starttls:
            raise RuntimeError("STARTTLS not supported")

        fut = asyncio.Future()
        self._queue.put_nowait(
            ("starttls", ssl_context, post_handshake_callback, fut)
        )
        yield from fut


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

    class Fail(collections.namedtuple("Fail", ["exc"])):
        def do(self, xmlstream):
            xmlstream._exception = self.exc
            for fut in xmlstream._error_futures:
                if not fut.done():
                    fut.set_exception(self.exc)
            xmlstream.on_closing(self.exc)

    class Send(collections.namedtuple("Send", ["obj", "response"])):
        def __new__(cls, obj, *, response=None):
            return super().__new__(cls, obj, response)

    class Reset(collections.namedtuple("Reset", ["response"])):
        def __new__(cls, *, response=None):
            return super().__new__(cls, response)

    class Close(collections.namedtuple("Close", ["response"])):
        def __new__(cls, *, response=None):
            return super().__new__(cls, response)

    class STARTTLS(collections.namedtuple("STARTTLS", [
            "ssl_context", "post_handshake_callback", "response"])):
        def __new__(cls, ssl_context, post_handshake_callback,
                    *, response=None):
            return super().__new__(cls,
                                   ssl_context,
                                   post_handshake_callback,
                                   response)

    on_closing = callbacks.Signal()

    def __init__(self, tester, *, loop=None):
        super().__init__(tester, loop=loop)
        self._queue = asyncio.Queue()
        self._exception = None
        self._closed = False
        self.stanza_parser = xso.XSOParser()
        self.can_starttls_value = False
        self._error_futures = []

    def _execute_single(self, do):
        do(self)

    @asyncio.coroutine
    def run_test(self, actions,
                 stimulus=None):
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
                    yield from self._send_xso(*args)
                elif action == "reset":
                    yield from self._reset(*args)
                elif action == "close":
                    yield from self._close(*args)
                elif action == "starttls":
                    yield from self._starttls(*args)
                else:
                    assert False

            if self._done not in pending:
                break

    @asyncio.coroutine
    def _send_xso(self, obj):
        self._tester.assertTrue(
            self._actions,
            self._format_unexpected_action(
                "send_xso("+repr(obj)+")",
                "no actions left")
        )
        head = self._actions[0]
        self._tester.assertIsInstance(
            head, self.Send,
            self._format_unexpected_action(
                "send_xso",
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
        self._exception = ConnectionError("not connected")
        self.on_closing(None)
        for fut in self._error_futures:
            if not fut.done():
                fut.set_exception(self._exception)

    @asyncio.coroutine
    def _starttls(self, ssl_context, post_handshake_callback, fut):
        self._tester.assertTrue(
            self._actions,
            self._format_unexpected_action("starttls", "no actions left"),
        )
        head = self._actions[0]
        self._tester.assertIsInstance(
            head, self.STARTTLS,
            self._format_unexpected_action("starttls",
                                           "expected something else"),
        )
        self._actions.pop(0)

        self._tester.assertEqual(
            ssl_context,
            head.ssl_context,
            "mismatched starttls argument")
        self._tester.assertEqual(
            post_handshake_callback,
            head.post_handshake_callback,
            "mismatched starttls argument")

        if post_handshake_callback:
            try:
                yield from post_handshake_callback(self.transport)
            except Exception as exc:
                fut.set_exception(exc)
            else:
                fut.set_result(None)
        else:
            fut.set_result(None)

        self._execute_response(head.response)

    def send_xso(self, obj):
        if self._exception:
            raise self._exception
        self._queue.put_nowait(("send", obj))

    def reset(self):
        if self._exception:
            raise self._exception
        self._queue.put_nowait(("reset",))

    def close(self):
        if self._exception:
            raise self._exception
        self._queue.put_nowait(("close",))

    @asyncio.coroutine
    def starttls(self, ssl_context, post_handshake_callback=None):
        if self._exception:
            raise self._exception

        fut = asyncio.Future()
        self._queue.put_nowait(
            ("starttls", ssl_context, post_handshake_callback, fut)
        )
        yield from fut

    @asyncio.coroutine
    def close_and_wait(self):
        fut = asyncio.Future()
        self.on_closing.connect(fut, self.on_closing.AUTO_FUTURE)
        self.close()
        try:
            yield from fut
        except Exception:
            pass

    def can_starttls(self):
        return self.can_starttls_value

    def error_future(self):
        fut = asyncio.Future()
        self._error_futures.append(fut)
        return fut
