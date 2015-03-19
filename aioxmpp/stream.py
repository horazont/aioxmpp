import asyncio
import functools
import logging

from datetime import datetime, timedelta
from enum import Enum

from . import stanza, errors, custom_queue, stream_elements, callbacks

from .plugins import xep0199
from .utils import namespaces


class PingEventType(Enum):
    SEND_OPPORTUNISTIC = 0
    SEND_NOW = 1
    TIMEOUT = 2


class StanzaState(Enum):
    ACTIVE = 0
    SENT = 1
    ACKED = 2
    SENT_WITHOUT_SM = 3
    ABORTED = 4



class StanzaToken:
    def __init__(self, stanza, *, on_state_change=None):
        self.stanza = stanza
        self._state = StanzaState.ACTIVE
        self.on_state_change = on_state_change

    @property
    def state(self):
        return self._state

    def _set_state(self, new_state):
        self._state = new_state
        if self.on_state_change is not None:
            self.on_state_change(self, new_state)

    def abort(self):
        if     (self._state != StanzaState.ACTIVE and
                self._state != StanzaState.ABORTED):
            raise RuntimeError("cannot abort stanza (already sent)")
        self._state = StanzaState.ABORTED


class StanzaStream:
    def __init__(self,
                 *,
                 loop=None,
                 base_logger=logging.getLogger("aioxmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._logger = base_logger.getChild("StanzaBroker")
        self._task = None

        self._active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self._incoming_queue = custom_queue.AsyncDeque(loop=self._loop)

        self._iq_response_map = callbacks.TagDispatcher()
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
                self._iq_response_map.unicast(key, stanza_obj)
            except KeyError:
                self._logger.warning(
                    "unexpected IQ response: from=%r, id=%r",
                    *key)
                return
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

    def _process_incoming(self, xmlstream, stanza_obj):
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
            if self._next_ping_event_type == PingEventType.TIMEOUT:
                self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
                self._next_ping_event_at = datetime.utcnow() + self.ping_interval
        elif isinstance(stanza_obj, stream_elements.SMRequest):
            if not self.sm_enabled:
                self._logger.warning("received sm:r, but sm not enabled")
                return
            response = stream_elements.SMAcknowledgement()
            response.counter = self.sm_inbound_ctr
            xmlstream.send_stanza(response)
        else:
            raise RuntimeError("unexpected stanza class: {}".format(stanza_obj))

    def _send_stanza(self, xmlstream, token):
        if token.state == StanzaState.ABORTED:
            return

        xmlstream.send_stanza(token.stanza)
        if self.sm_enabled:
            token._set_state(StanzaState.SENT)
            self.sm_unacked_list.append(token)
        else:
            token._set_state(StanzaState.SENT_WITHOUT_SM)

    def _process_outgoing(self, xmlstream, token):
        self._send_stanza(xmlstream, token)
        # try to send a bulk
        while True:
            try:
                token = self._active_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._send_stanza(xmlstream, token)

        self._send_ping(xmlstream)

    def _recv_pong(self, stanza):
        if not self.running:
            return
        if self._next_ping_event_type != PingEventType.TIMEOUT:
            return
        self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
        self._next_ping_event_at = datetime.utcnow() + self.ping_interval

    def _send_ping(self, xmlstream):
        if not self._ping_send_opportunistic:
            return
        if self.sm_enabled:
            xmlstream.send_stanza(stream_elements.SMRequest())
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
        if self._next_ping_event_type != PingEventType.TIMEOUT:
            self._next_ping_event_at = datetime.utcnow() + self.ping_interval
            self._next_ping_event_type = PingEventType.TIMEOUT

    def _process_ping_event(self, xmlstream):
        if self._next_ping_event_type == PingEventType.SEND_OPPORTUNISTIC:
            self._next_ping_event_at += self.ping_opportunistic_interval
            self._next_ping_event_type = PingEventType.SEND_NOW
            # ping send opportunistic is always true for sm
            if not self.sm_enabled:
                self._ping_send_opportunistic = True
        elif self._next_ping_event_type == PingEventType.SEND_NOW:
            self._send_ping(xmlstream)
        elif self._next_ping_event_type == PingEventType.TIMEOUT:
            raise ConnectionError("ping timeout")
        else:
            raise RuntimeError("unknown ping event type: {!r}".format(
                self._next_ping_event_type))

    def register_iq_response_callback(self, from_, id_, cb):
        self._iq_response_map.add_listener(
            (from_, id_),
            callbacks.OneshotAsyncTagListener(cb, loop=self._loop)
        )

    def register_iq_request_coro(self, type_, payload_cls, coro):
        self._iq_request_map[type_, payload_cls] = coro

    def register_message_callback(self, type_, from_, cb):
        self._message_map[type_, from_] = cb

    def register_presence_callback(self, type_, from_, cb):
        self._presence_map[type_, from_] = cb

    def start(self, xmlstream):
        if self.running:
            raise RuntimeError("already started")
        self._task = asyncio.async(self._run(xmlstream), loop=self._loop)
        self._task.add_done_callback(self._done_handler)
        xmlstream.stanza_parser.add_class(stanza.IQ, self.recv_stanza)
        xmlstream.stanza_parser.add_class(stanza.Message, self.recv_stanza)
        xmlstream.stanza_parser.add_class(stanza.Presence, self.recv_stanza)
        if self.sm_enabled:
            xmlstream.stanza_parser.add_class(stream_elements.SMAcknowledgement,
                                           self.recv_stanza)
            xmlstream.stanza_parser.add_class(stream_elements.SMRequest,
                                           self.recv_stanza)
        self._next_ping_event_at = datetime.utcnow() + self.ping_interval
        self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
        self._ping_send_opportunistic = self.sm_enabled

    def stop(self):
        if not self.running:
            return
        self._task.cancel()

    @asyncio.coroutine
    def _run(self, xmlstream):
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

                done, pending = yield from asyncio.wait(
                    [
                        active_fut,
                        incoming_fut,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout.total_seconds())

                if active_fut in done:
                    self._process_outgoing(xmlstream, active_fut.result())
                    active_fut = asyncio.async(
                        self._active_queue.get(),
                        loop=self._loop)

                if incoming_fut in done:
                    self._process_incoming(xmlstream, incoming_fut.result())
                    incoming_fut = asyncio.async(
                        self._incoming_queue.get(),
                        loop=self._loop)

                if self._next_ping_event_at is not None:
                    timeout = self._next_ping_event_at - datetime.utcnow()
                    if timeout.total_seconds() <= 0:
                        self._process_ping_event(xmlstream)

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

            xmlstream.stanza_parser.remove_class(stanza.Presence)
            xmlstream.stanza_parser.remove_class(stanza.Message)
            xmlstream.stanza_parser.remove_class(stanza.IQ)
            if self.sm_enabled:
                xmlstream.stanza_parser.remove_class(
                    stream_elements.SMRequest)
                xmlstream.stanza_parser.remove_class(
                    stream_elements.SMAcknowledgement)


    def recv_stanza(self, stanza):
        self._incoming_queue.put_nowait(stanza)

    def enqueue_stanza(self, stanza, **kwargs):
        token = StanzaToken(stanza, **kwargs)
        self._active_queue.put_nowait(token)
        return token

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    def start_sm(self):
        if self.running:
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
        for token in self.sm_unacked_list:
            token._set_state(StanzaState.SENT_WITHOUT_SM)
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

        acked = self.sm_unacked_list[:to_drop]
        del self.sm_unacked_list[:to_drop]
        self.sm_outbound_base = remote_ctr

        for token in acked:
            token._set_state(StanzaState.ACKED)

    @asyncio.coroutine
    def send_iq_and_wait_for_reply(self, iq, *,
                                   timeout=None,
                                   loop=None):
        fut = asyncio.Future(loop=loop)
        self.register_iq_response_callback(
            iq.to,
            iq.id_,
            fut.set_result)
        self.enqueue_stanza(iq)
        if not timeout:
            return fut
        else:
            return asyncio.wait_for(fut, timeout=timeout, loop=loop)
