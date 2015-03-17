import asyncio
import functools
import logging

from datetime import datetime, timedelta
from enum import Enum

from . import stanza, errors, custom_queue, stream_elements

from .plugins import xep0199
from .utils import namespaces


class PingEventType(Enum):
    PING_SEND_OPPORTUNISTIC = 0
    PING_SEND_NOW = 1
    PING_TIMEOUT = 2


class StanzaBroker:
    def __init__(self,
                 *,
                 loop=None,
                 base_logger=logging.getLogger("asyncio_xmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._logger = base_logger.getChild("StanzaBroker")
        self._task = None

        self._active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self._incoming_queue = custom_queue.AsyncDeque(loop=self._loop)

        self._iq_response_map = {}
        self._iq_request_map = {}
        self._message_map = {}
        self._presence_map = {}

        self._ping_send_opportunistic = False
        self._next_ping_event_at = None
        self._next_ping_event_type = None

        self.ping_interval = timedelta(seconds=15)
        self.ping_opportunistic_interval = timedelta(seconds=15)

        self.on_send_stanza = None
        self.on_failure = None

        self.sm_enabled = False

    def _done_handler(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # normal termination
            pass
        except Exception as err:
            if self.on_failure:
                self.on_failure(err)
            raise

    def _iq_request_coro_done(self, request, task):
        try:
            response = task.result()
        except errors.XMPPError as err:
            response = request.make_reply(type_="error")
            response.error = stanza.Error.from_exception(err)
        except Exception as exc:
            response = request.make_reply(type_="error")
            response.error = stanza.Error(
                condition=(namespaces.stanzas, "undefined-condition"),
                type_="cancel",
            )
        self.enqueue_stanza(response)

    def _process_incoming_iq(self, stanza_obj):
        if stanza_obj.type_ == "result" or stanza_obj.type_ == "error":
            # iq response
            key = (stanza_obj.from_, stanza_obj.id_)
            try:
                cb = self._iq_response_map.pop(key)
            except KeyError:
                self._logger.warning(
                    "unexpected IQ response: from=%r, id=%r",
                    *key)
                return
            try:
                self._loop.call_soon(cb, stanza_obj)
            except:
                self._logger.warning(
                    "while handling IQ response",
                    exc_info=True)
        else:
            # iq request
            key = (stanza_obj.type_, type(stanza_obj.payload))
            try:
                coro = self._iq_request_map[key]
            except KeyError:
                self._logger.warning(
                    "unhandleable IQ request: from=%r, id=%r, payload=%r",
                    stanza_obj.from_,
                    stanza_obj.id_,
                    stanza_obj.payload
                )
                response = stanza_obj.make_reply(type_="error")
                response.error = stanza.Error(
                    condition=(namespaces.stanzas,
                               "feature-not-implemented"),
                )
                self.enqueue_stanza(response)
                return

            task = asyncio.async(coro(stanza_obj))
            task.add_done_callback(
                functools.partial(
                    self._iq_request_coro_done,
                    stanza_obj))

    def _process_incoming_message(self, stanza_obj):
        keys = [(stanza_obj.type_, stanza_obj.from_),
                (stanza_obj.type_, None),
                (None, None)]
        for key in keys:
            try:
                cb = self._message_map[key]
            except KeyError:
                continue
            self._loop.call_soon(cb, stanza_obj)
            break
        else:
            self._logger.warning(
                "unsolicited message dropped: from=%r, type=%r, id=%r",
                stanza_obj.from_,
                stanza_obj.type_,
                stanza_obj.id_
            )

    def _process_incoming_presence(self, stanza_obj):
        keys = [(stanza_obj.type_, stanza_obj.from_),
                (stanza_obj.type_, None)]
        for key in keys:
            try:
                cb = self._presence_map[key]
            except KeyError:
                continue
            self._loop.call_soon(cb, stanza_obj)
            break
        else:
            self._logger.warning(
                "unhandled presence dropped: from=%r, type=%r, id=%r",
                stanza_obj.from_,
                stanza_obj.type_,
                stanza_obj.id_
            )

    def _process_incoming(self, stream, stanza_obj):
        if self.sm_enabled:
            self.sm_inbound_ctr += 1

        if isinstance(stanza_obj, stanza.IQ):
            self._process_incoming_iq(stanza_obj)
        elif isinstance(stanza_obj, stanza.Message):
            self._process_incoming_message(stanza_obj)
        elif isinstance(stanza_obj, stanza.Presence):
            self._process_incoming_presence(stanza_obj)
        elif isinstance(stanza_obj, stream_elements.SMAcknowledgement):
            if not self.sm_enabled:
                self._logger.warning("received sm:a, but sm not enabled")
                return
            self.sm_ack(stanza_obj.counter)
            if self._next_ping_event_type == PingEventType.PING_TIMEOUT:
                self._next_ping_event_type = PingEventType.PING_SEND_OPPORTUNISTIC
                self._next_ping_event_at = datetime.utcnow() + self.ping_interval
        elif isinstance(stanza_obj, stream_elements.SMRequest):
            if not self.sm_enabled:
                self._logger.warning("received sm:r, but sm not enabled")
                return
            response = stream_elements.SMAcknowledgement()
            response.counter = self.sm_inbound_ctr
            stream.send_stanza(response)
        else:
            raise RuntimeError("unexpected stanza class: {}".format(stanza_obj))

    def _send_stanza(self, stream, stanza_obj):
        stream.send_stanza(stanza_obj)
        if self.sm_enabled:
            self.sm_unacked_list.append(stanza_obj)

    def _process_outgoing(self, stream, stanza_obj):
        self._send_stanza(stream, stanza_obj)
        # try to send a bulk
        while True:
            try:
                stanza_obj = self._active_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._send_stanza(stream, stanza_obj)

        self._send_ping(stream)

    def _recv_pong(self, stanza):
        if not self.running:
            return
        if self._next_ping_event_type != PingEventType.PING_TIMEOUT:
            return
        self._next_ping_event_type = PingEventType.PING_SEND_OPPORTUNISTIC
        self._next_ping_event_at = datetime.utcnow() + self.ping_interval

    def _send_ping(self, stream):
        if not self._ping_send_opportunistic:
            return
        if self.sm_enabled:
            stream.send_stanza(stream_elements.SMRequest())
        else:
            request = stanza.IQ(type_="get")
            request.payload = xep0199.Ping()
            request.autoset_id()
            self.register_iq_response_callback(
                None,
                request.id_,
                self._recv_pong
            )
            self.enqueue_stanza(request)
            self._ping_send_opportunistic = False
        if self._next_ping_event_type != PingEventType.PING_TIMEOUT:
            self._next_ping_event_at = datetime.utcnow() + self.ping_interval
            self._next_ping_event_type = PingEventType.PING_TIMEOUT

    def _process_ping_event(self, stream):
        if self._next_ping_event_type == PingEventType.PING_SEND_OPPORTUNISTIC:
            self._next_ping_event_at += self.ping_opportunistic_interval
            self._next_ping_event_type = PingEventType.PING_SEND_NOW
            # ping send opportunistic is always true for sm
            if not self.sm_enabled:
                self._ping_send_opportunistic = True
        elif self._next_ping_event_type == PingEventType.PING_SEND_NOW:
            self._send_ping(stream)
        elif self._next_ping_event_type == PingEventType.PING_TIMEOUT:
            raise ConnectionError("ping timeout")
        else:
            raise RuntimeError("unknown ping event type: {!r}".format(
                self._next_ping_event_type))

    def register_iq_response_callback(self, from_, id_, cb):
        self._iq_response_map[from_, id_] = cb

    def register_iq_request_coro(self, type_, payload_cls, coro):
        self._iq_request_map[type_, payload_cls] = coro

    def register_message_callback(self, type_, from_, cb):
        self._message_map[type_, from_] = cb

    def register_presence_callback(self, type_, from_, cb):
        self._presence_map[type_, from_] = cb

    def start(self, stream):
        if self.running():
            raise RuntimeError("already started")
        self._task = asyncio.async(self._run(stream), loop=self._loop)
        self._task.add_done_callback(self._done_handler)
        stream.stanza_parser.add_class(stanza.IQ, self.recv_stanza)
        stream.stanza_parser.add_class(stanza.Message, self.recv_stanza)
        stream.stanza_parser.add_class(stanza.Presence, self.recv_stanza)
        if self.sm_enabled:
            stream.stanza_parser.add_class(stream_elements.SMAcknowledgement,
                                           self.recv_stanza)
            stream.stanza_parser.add_class(stream_elements.SMRequest,
                                           self.recv_stanza)
        self._next_ping_event_at = datetime.utcnow() + self.ping_interval
        self._next_ping_event_type = PingEventType.PING_SEND_OPPORTUNISTIC
        self._ping_send_opportunistic = self.sm_enabled

    def stop(self):
        if not self.running():
            return
        self._task.cancel()

    @asyncio.coroutine
    def _run(self, stream):
        active_fut = asyncio.async(self._active_queue.get(),
                                   loop=self._loop)
        incoming_fut = asyncio.async(self._incoming_queue.get(),
                                     loop=self._loop)

        try:
            while True:
                if self._next_ping_event_at is not None:
                    timeout = self._next_ping_event_at - datetime.utcnow()
                    if timeout.total_seconds() < 0:
                        timeout = timedelta()
                else:
                    timeout = timedelta()

                print("before", timeout)
                done, pending = yield from asyncio.wait(
                    [
                        active_fut,
                        incoming_fut,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout.total_seconds())
                print("after", timeout)

                if active_fut in done:
                    self._process_outgoing(stream, active_fut.result())
                    active_fut = asyncio.async(
                        self._active_queue.get(),
                        loop=self._loop)

                if incoming_fut in done:
                    self._process_incoming(stream, incoming_fut.result())
                    incoming_fut = asyncio.async(
                        self._incoming_queue.get(),
                        loop=self._loop)

                if self._next_ping_event_at is not None:
                    timeout = self._next_ping_event_at - datetime.utcnow()
                    print("ping", timeout)
                    if timeout.total_seconds() <= 0:
                        print("ping event:", self._next_ping_event_type)
                        self._process_ping_event(stream)

        finally:
            # make sure we rescue any stanzas which possibly have already been
            # caught by the calls to get()
            if incoming_fut.done() and not incoming_fut.exception():
                self._incoming_queue.putleft_nowait(incoming_fut.result())
            else:
                incoming_fut.cancel()

            if active_fut.done() and not active_fut.exception():
                self._active_queue.putleft_nowait(active_fut.result())
            else:
                active_fut.cancel()

            stream.stanza_parser.remove_class(stanza.Presence)
            stream.stanza_parser.remove_class(stanza.Message)
            stream.stanza_parser.remove_class(stanza.IQ)
            if self.sm_enabled:
                stream.stanza_parser.remove_class(
                    stream_elements.SMRequest)
                stream.stanza_parser.remove_class(
                    stream_elements.SMAcknowledgement)


    def recv_stanza(self, stanza):
        self._incoming_queue.put_nowait(stanza)

    def enqueue_stanza(self, stanza):
        self._active_queue.put_nowait(stanza)

    def running(self):
        return self._task is not None and not self._task.done()

    def start_sm(self):
        if self.running():
            raise RuntimeError("cannot start Stream Management while"
                               " StanzaBroker is running")

        self.sm_outbound_base = 0
        self.sm_inbound_ctr = 0
        self.sm_unacked_list = []
        self.sm_enabled = True

    def resume_sm(self, remote_ctr):
        # remove any acked stanzas
        self.sm_ack(remote_ctr)
        # reinsert the remaining stanzas
        for stanza in self.sm_unacked_list:
            self._active_queue.putleft_nowait(stanza)
        self.sm_unacked_list.clear()

    def stop_sm(self):
        self.sm_enabled = False
        del self.sm_outbound_base
        del self.sm_inbound_ctr
        del self.sm_unacked_list

    def sm_ack(self, remote_ctr):
        if not self.sm_enabled:
            raise RuntimeError("Stream Management is not enabled")

        to_drop = remote_ctr - self.sm_outbound_base
        if to_drop < 0:
            self._logger.warning(
                "remote stanza counter is *less* than before "
                "(outbound_base=%d, remote_ctr=%d)",
                self.sm_outbound_base,
                remote_ctr)
            return

        del self.sm_unacked_list[:to_drop]
        self.sm_outbound_base = remote_ctr


class StreamManagementLivenessHandler:
    def __init__(self, stream, broker, *,
                 loop=None,
                 base_logger=logging.getLogger("asyncio_xmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._logger = base_logger.getChild("StreamManagementLivenessHandler")
        self._task = None

        self._stream = stream
        self._broker = broker
        self._last_req_sent = datetime.utcnow()
        self._send_request_until = None
        self._send_opportunistic_until = None
        self._expect_response_until = None

        self.activity_interval = timedelta(seconds=15)
        self.opportunistic_grace_period = timedelta(seconds=15)

    def _done_handler(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # normal termination
            pass
        except Exception as err:
            self._logger.error("task terminated unexpectedly", exc_info=True)
            return

    def _on_request(self, req):
        response = stream_elements.SMAcknowledgement()
        response.counter = self._broker.sm_inbound_ctr
        self._stream.send_stanza(response)

    def _on_ack(self, ack):
        self._broker.sm_ack(ack.counter)

    def start(self):
        self._task = asyncio.async(
            self._run(),
            loop=self._loop)
        self._task.add_done_callback(self._done_handler)

    def stop(self):
        self._task.cancel()

    def bump_activity(self):
        pass

    def opportunistic_send(self):
        return []
