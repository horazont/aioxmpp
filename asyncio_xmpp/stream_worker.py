"""
Stream worker
#############
"""
import abc
import asyncio
import logging

from datetime import datetime, timedelta

from . import custom_queue, stanza, plugins
from .utils import *

logger = logging.getLogger(__name__)

def future_from_queue(queue, loop):
    return asyncio.async(
        queue.get(),
        loop=loop)

class StreamWorker(metaclass=abc.ABCMeta):
    def __init__(self, loop, shared_disconnect_event):
        super().__init__()
        self._loop = loop
        self._shared_disconnect_event = shared_disconnect_event
        self._task = None

    def _disconnect_future(self):
        return asyncio.async(
            self._shared_disconnect_event.wait(),
            loop=self._loop)

    def setup(self, xmlstream):
        self.xmlstream = xmlstream

    def start(self):
        self._task = asyncio.async(
            self.worker(),
            loop=self._loop)
        return self._task

    def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        self._task = None

    def teardown(self):
        del self.xmlstream

    @abc.abstractmethod
    @asyncio.coroutine
    def worker(self):
        pass

class StanzaBrokerSMInitializer:
    def __init__(self, broker):
        self.broker = broker

    def __enter__(self):
        self.broker._acked_remote_ctr = 0

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            # exception occured, do not enable SM, do not suppress exception
            return False

        self.broker._unacked_ctr_base = 0
        self.broker._sm_reset(enabled=True)

    def set_session_id(self, id):
        self.broker._sm_id = id

class StanzaBroker(StreamWorker):
    def __init__(self, loop, shared_disconnect_event,
                 ping_timeout,
                 ping_timeout_callback,
                 stanza_callbacks):
        super().__init__(loop, shared_disconnect_event)
        self._acked_remote_ctr = 0
        self._interrupt = asyncio.Event()
        self._sm_id = None
        self._sm_enabled = False
        self._unacked_ctr_base = 0

        self._iq_response_tokens = {}

        self._callbacks = {
            "opportunistic_send": set()
        }

        (self._iq_request_callback,
         self._message_callback,
         self._presence_callback) = stanza_callbacks

        # this is exchanged for a StreamManagementLivenessHandler when sm is
        # enabled
        self._liveness_handler = PingLivenessHandler(
            loop, shared_disconnect_event)
        self._liveness_handler_task = None

        self.active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self.incoming_iq_queue = asyncio.Queue()
        self.incoming_message_queue = asyncio.Queue()
        self.incoming_presence_queue = asyncio.Queue()
        self.unacked_queue = list()

        self.ping_timeout = ping_timeout
        self.ping_timeout_callback = ping_timeout_callback

    def _flush_unacked_to_acked(self, new_ack_counter):
        upto_index = new_ack_counter-self._unacked_ctr_base
        self._unacked_ctr_base = new_ack_counter

        to_flush = self.unacked_queue[:upto_index]
        del self.unacked_queue[:upto_index]

        for token in to_flush:
            item._state = stanza.QueueState.ACKED
            if token.ack_callback:
                token.ack_callback()

    def _flush_unacked_to_sent_without_ack(self):
        to_hold = self.unacked_queue.copy()
        self.unacked_queue.clear()
        for token in to_hold:
            token._state = stanza.QueueState.SENT_WITHOUT_ACK

    def _queued_stanza_abort(self, stanza_token):
        try:
            self.active_queue.remove(stanza_token)
        except ValueError:
            pass

        return QueueState.ABORTED

    def _queued_stanza_resend(self, stanza_token):
        if stanza_token.state in {QueueState.SEND_WITHOUT_ACK,
                                  QueueState.ABORTED}:
            self.enqueue_token(stanza_token)
            return QueueState.ACTIVE
        return stanza_token._state

    def _send_token(self, token):
        if self._sm_enabled:
            token._state = stanza.QueueState.UNACKED
            self.unacked_queue.append(token)
        else:
            token._state = stanza.QueueState.SENT_WITHOUT_ACK

        self._send_token_noqueue(token)

    def _send_token_noqueue(self, token):
        token._last_sent = datetime.utcnow()
        self.xmlstream.send_node(token._stanza)
        if token.sent_callback:
            token.sent_callback()

    def _sm_reset(self, enabled=False, id=None):
        restart = False
        if self._sm_enabled ^ enabled:
            # state will change
            if self._liveness_handler_task:
                restart = True
                self._liveness_handler.stop()
                self._liveness_handler.teardown()

            if enabled:
                self._liveness_handler = StreamManagementLivenessHandler(
                    self._loop,
                    self._shared_disconnect_event)
            else:
                self._liveness_handler = PingLivenessHandler(
                    self._loop,
                    self._shared_disconnect_event)
            self._liveness_handler.setup(self)

        self._sm_id = id
        self._sm_enabled = enabled

        if not enabled:
            self._flush_unacked_to_sent_without_ack()

        if restart:
            self.start_liveness_handler()

    def _stanza_iq(self, iq):
        if iq.type in {"result", "error"}:
            try:
                token = self._iq_response_tokens.pop((iq.id, iq.from_))
            except KeyError:
                logger.warn("unexpected iq response: type=%s, id=%r, data=%s",
                            iq.type, iq.id, iq.data)
            else:
                token.response_future.set_result(iq)
            return

        self._loop.call_soon(self._iq_request_callback, iq)

    # StreamWorker interface

    def setup(self, xmlstream):
        super().setup(xmlstream)
        xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}iq",
            self.incoming_iq_queue)
        xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}message",
            self.incoming_message_queue)
        xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}presence",
            self.incoming_presence_queue)
        self._liveness_handler.setup(self)

    def start_liveness_handler(self):
        if self._liveness_handler_task is None:
            self._liveness_handler_task = self._liveness_handler.start()
            if self._task is not None:
                # we have to interrupt the task so that it starts watching the
                # liveness handler
                self._interrupt.set()

    def stop(self):
        self._liveness_handler.stop()
        super().stop()

    def teardown(self):
        self._liveness_handler.teardown()
        self.xmlstream.stream_level_hooks.remove_queue(
            "{jabber:client}iq",
            self.incoming_iq_queue)
        self.xmlstream.stream_level_hooks.remove_queue(
            "{jabber:client}message",
            self.incoming_message_queue)
        self.xmlstream.stream_level_hooks.remove_queue(
            "{jabber:client}presence",
            self.incoming_presence_queue)
        super().teardown()

    @asyncio.coroutine
    def worker(self):
        logger = logging.getLogger(__name__ + ".stanza_broker")

        disconnect_future = self._disconnect_future()
        interrupt_future = asyncio.async(
            self._interrupt.wait(),
            loop=self._loop)

        outgoing_stanza_future = asyncio.async(
            self.active_queue.popleft(),
            loop=self._loop)

        incoming_queues = [
            self.incoming_iq_queue,
            self.incoming_message_queue,
            self.incoming_presence_queue
        ]

        incoming_futures = [
            future_from_queue(queue, self._loop)
            for queue in incoming_queues
        ]

        incoming_handlers = [
            self._stanza_iq,
            self._message_callback,
            self._presence_callback
        ]

        while True:
            futures_to_wait_for = incoming_futures.copy()
            futures_to_wait_for.append(outgoing_stanza_future)
            futures_to_wait_for.append(disconnect_future)
            futures_to_wait_for.append(interrupt_future)
            if self._liveness_handler_task is not None:
                futures_to_wait_for.append(self._liveness_handler_task)

            done, _ = yield from asyncio.wait(
                futures_to_wait_for,
                loop=self._loop,
                return_when=asyncio.FIRST_COMPLETED)
            logger.debug("%r", done)

            if interrupt_future in done:
                logger.debug("received interrupt")
                self._interrupt.clear()
                interrupt_future = asyncio.async(
                    self._interrupt.wait(),
                    loop=self._loop)

            if disconnect_future in done:
                if outgoingstanza_future in done:
                    # re-queue that stanza
                    self.active_queue.appendleft(
                        outgoing_stanza_future.result())
                break

            if self._liveness_handler_task in done:
                raise RuntimeError("Liveness handler terminated unexpectedly") \
                    from self._liveness_handler_task.exception()

            if outgoing_stanza_future in done:
                token = outgoing_stanza_future.result()
                self._send_token(token)

                if self.active_queue.empty():
                    # opportunistic send
                    for fn in self._callbacks["opportunistic_send"]:
                        for token in fn():
                            self._send_token(token)

                outgoing_stanza_future = asyncio.async(
                    self.active_queue.popleft(),
                    loop=self._loop)

            for i, (future, queue, handler) in enumerate(
                    zip(incoming_futures, incoming_queues, incoming_handlers)):
                if future not in done:
                    continue

                received_stanza = future.result()
                self._loop.call_soon(handler, received_stanza)
                if self._sm_enabled:
                    self._acked_remote_ctr += 1

                incoming_futures[i] = future_from_queue(
                    queue,
                    self._loop)


    # StanzaBroker interface

    def enqueue_token(self, token):
        if token._stanza is None:
            raise ValueError("Cannot send token without stanza")
        token._stanza.autoset_id()
        token._stanza.validate()

        if token._stanza.tag.endswith("}iq"):
            # IQ stanza, register handlers
            iq = token._stanza
            if iq.type in {"set", "get"}:
                self._iq_response_tokens[iq.id, iq.from_] = token
        else:
            if token.response_future:
                raise ValueError("Response future is not supported for "
                                 "{}".format(token._stanza))

        self.active_queue.append(token)

    def make_stanza_token(self, for_stanza, **kwargs):
        return stanza.StanzaToken(
            for_stanza,
            abort_impl=self._queued_stanza_abort,
            resend_impl=self._queued_stanza_resend,
            **kwargs)

    @property
    def sm_enabled(self):
        return self._sm_enabled

    @property
    def sm_session_id(self):
        if not self.sm_enabled:
            return None
        return self._sm_id

    def sm_resume(self, remote_counter):
        self._flush_unacked_to_acked(remote_counter)
        # do not resend aborted tokens
        to_resend = [token for token in self.unacked_queue
                     if token._state == stanza.QueueState.UNACKED]
        self.unacked_queue.clear()
        for token in to_resend:
            self._send_token_noqueue(token)

    def sm_init(self):
        """
        Return a context manager which will, if run successfully, initialize
        stream management.
        """
        return StanzaBrokerSMInitializer(self)

    def sm_reset(self):
        self._sm_reset(False, None)

    def register_callback(self, cb, fn):
        fnset = self._callbacks[cb]
        fnset.add(fn)

    def unregister_callback(self, cb, fn):
        self._callbacks[cb].remove(fn)


class LivenessHandler(StreamWorker):
    """
    A liveness handler takes care of ensuring that the stream is still alive,
    and if not, calling the :meth:`Client._handle_ping_timeout` coroutine.

    Liveness handlers are tightly coupled with the :class:`Client` class, and
    generally need access to "protected" attributes, such as stream management
    state.
    """

    def __init__(self, loop, shared_disconnect_event):
        super().__init__(loop, shared_disconnect_event)
        self.last_liveness_indicator = datetime.utcnow()
        self.passive_request_timeout = timedelta(seconds=10)
        self.passive_request_until = None

    def _on_opportunistic_send(self):
        if self.passive_request_until:
            result = self.perform_request()
            self.passive_request_until = None
            return result
        return []

    def setup(self, stanza_broker):
        self.stanza_broker = stanza_broker
        super().setup(stanza_broker.xmlstream)
        self.stanza_broker.register_callback(
            "opportunistic_send",
            self._on_opportunistic_send)

    def start(self):
        """
        After the connection has been established, this is called by the
        client.

        The default implementation spawns a task running :meth:`_worker` here
        and resets the liveness indicator.
        """
        self.last_liveness_indicator = datetime.utcnow()
        self.passive_request_until = None
        return super().start()

    def stop(self):
        super().stop()

    def teardown(self):
        self.stanza_broker.unregister_callback(
            "opportunistic_send",
            self._on_opportunistic_send)
        del self.stanza_broker
        super().teardown()

    @abc.abstractmethod
    def perform_request(self):
        pass

class PingLivenessHandler(LivenessHandler):
    def perform_request(self):
        self.response_future = asyncio.Future()
        token = self.stanza_broker.make_stanza_token(
            self.xmlstream.make_iq(type="get"),
            response_future=self.response_future
        )
        token.stanza.data = plugins.xep0199.Ping()
        self.passive_request_until = None
        self.sent_ping_timeout = datetime.utcnow() + \
            self.stanza_broker.ping_timeout
        return [token]

    def start(self):
        logger.debug("starting ping liveness handler")
        self.response_future = None
        self.sent_ping_timeout = None
        return super().start()

    def stop(self):
        logger.debug("stopping ping liveness handler")
        super().stop()

    @asyncio.coroutine
    def worker(self):
        logger = logging.getLogger(__name__ + ".liveness")
        logger.info("using xmpp ping for liveness")

        disconnect_future = self._disconnect_future()

        now = datetime.utcnow()
        while True:
            ping_timeout = self.stanza_broker.ping_timeout
            if self.sent_ping_timeout is None:
                next_timed_event = (self.last_liveness_indicator + ping_timeout
                                    - self.passive_request_timeout)
            else:
                next_timed_event = self.sent_ping_timeout
            timeout = max(0, (next_timed_event - now).total_seconds())

            futures_to_wait_for = [
                disconnect_future,
            ]
            if self.response_future is not None:
                futures_to_wait_for.append(self.response_future)

            done, _ = yield from asyncio.wait(
                futures_to_wait_for,
                timeout=timeout,
                loop=self._loop,
                return_when=asyncio.FIRST_COMPLETED)
            now = datetime.utcnow()

            if disconnect_future in done:
                break

            if self.response_future in done:
                self.response_future.result()
                self.last_liveness_indicator = datetime.utcnow()
                self.sent_ping_timeout = None
                self.response_future = None

            if self.sent_ping_timeout:
                if now > self.sent_ping_timeout:
                    # ping timeout
                    logger.debug("ping timeout")
                    yield from self.stanza_broker.ping_timeout_callback
                    break
            elif self.passive_request_until:
                if now > self.passive_request_until:
                    logger.debug("forcing ping")
                    for token in self.perform_request():
                        self.stanza_broker.enqueue_token(token)
            else:
                if     ((now - self.last_liveness_indicator) >
                        (ping_timeout - self.passive_request_timeout)):
                    logger.debug("requesting to send ping")
                    # send ping
                    self.passive_request_until = now + self.passive_request_timeout

class StreamManagementLivenessHandler(LivenessHandler):
    def __init__(self, loop, shared_disconnect_event):
        super().__init__(loop, shared_disconnect_event)
        self.ack_pending = None

    def setup(self, stanza_broker):
        super().setup(stanza_broker)
        self.ack_queue = asyncio.Queue()
        self.request_queue = asyncio.Queue()
        self.xmlstream.stream_level_hooks.add_queue(
            "{{{}}}r".format(namespaces.stream_management),
            self.request_queue)
        self.xmlstream.stream_level_hooks.add_queue(
            "{{{}}}a".format(namespaces.stream_management),
            self.ack_queue)

    def teardown(self):
        self.xmlstream.stream_level_hooks.remove_queue(
            "{{{}}}r".format(namespaces.stream_management),
            self.request_queue)
        self.xmlstream.stream_level_hooks.remove_queue(
            "{{{}}}a".format(namespaces.stream_management),
            self.ack_queue)
        super().teardown()

    def perform_request(self):
        """
        Send a stream management ack-request without going through queues.
        """
        request = self.xmlstream.E("{{{}}}r".format(
            namespaces.stream_management))
        self.passive_request_until = None
        self.ack_pending = datetime.utcnow()
        self.xmlstream.send_node(request)
        return []

    @asyncio.coroutine
    def worker(self):
        """
        Worker task to ensure that the stream is still alive. This
        implementation uses the stream management features to provide liveness.
        This is generally cheaper, because we will only ask for confirmations
        whenever stanzas have been sent.
        """
        logger = logging.getLogger(__name__ + ".liveness")
        logger.info("using stream management for liveness")

        disconnect_future = self._disconnect_future()
        request_future = future_from_queue(self.request_queue,
                                           self._loop)
        ack_future = future_from_queue(self.ack_queue,
                                       self._loop)

        now = datetime.utcnow()
        while True:
            ping_timeout = self.stanza_broker.ping_timeout
            if self.ack_pending:
                next_timed_event = self.ack_pending + ping_timeout
            else:
                next_timed_event = self.passive_request_until or (
                    self.last_liveness_indicator
                    + ping_timeout - self.passive_request_timeout)


            timeout = max((next_timed_event - now).total_seconds(), 0)
            logger.debug("next timed event in %s", timeout)

            done, pending = yield from asyncio.wait(
                [
                    disconnect_future,
                    request_future,
                    ack_future,
                ],
                loop=self._loop,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED)
            now = datetime.utcnow()

            if disconnect_future in done:
                self._sm_queue.clear()
                break

            if ack_future in done:
                node = ack_future.result()
                logger.debug("received ack")
                # ack from remote side
                try:
                    new_ack_counter = int(node.get("h"))
                except ValueError:
                    logger.warn("received SM ack with invalid data: %s",
                                node.get("h"))
                else:
                    self.stanza_broker._flush_unacked_to_acked(
                        new_ack_counter)
                    # disable any pending requests, set stream live
                    self.last_liveness_indicator = now
                    self.passive_request_until = None
                    self.ack_pending = None
                ack_future = future_from_queue(self.ack_queue, self._loop)

            if request_future in done:
                logger.debug("received ack request")
                # remote side requests ack
                ack_node = self._xmlstream.E(
                    "{{{}}}a".format(namespaces.stream_management),
                    h=str(self._acked_remote_ctr))
                self.xmlstream.send_node(ack_node)

                request_future = future_from_queue(self.request_queue,
                                                   self._loop)

            if self.ack_pending:
                if (now - self.ack_pending) > ping_timeout:
                    logger.debug("ping timeout on ack request")
                    yield from self.stanza_broker.ping_timeout_callback
                    break
            elif self.passive_request_until:
                if now > self.passive_request_until:
                    logger.debug("request to send ack request is pending for too"
                                 " long, forcing it now")
                    self.perform_request()
            else:
                if     ((now - self.last_liveness_indicator) >
                        (ping_timeout - self.passive_request_timeout)):
                    logger.debug("ping interval triggered")
                    if not self.passive_request_until:
                        logger.debug("requesting to send ack request")
                        self.passive_request_until = (
                            datetime.utcnow() + self.passive_request_timeout)
