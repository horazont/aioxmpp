"""
:mod:`~asyncio_xmpp.stream_worker` --- Long-running tasks working on top of the XML stream
##########################################################################################

These classes implement the basic tasks running on top of a stream. These are:

* The stanza broker, which is responsible for receiving and sending stanzas, as
  well as counting Stream Management counters, and
* The liveness handler, which makes in regular intervals makes sure that the
  server is still reachable. If Stream Management is in use, the liveness
  handler also takes care of replying to Stream Management requests (and uses SM
  ack-requests instead of XMPP Ping for pinging the server).

Specific classes in direct use
==============================

.. autoclass:: StanzaBroker
   :members:

.. autoclass:: PingLivenessHandler
   :members:

.. autoclass:: StreamManagementLivenessHandler
   :members:

Base classes
============

.. autoclass:: StreamWorker
   :members:

.. autoclass:: LivenessHandler
   :members:

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
    def __init__(self, loop, disconnect_future_factory):
        super().__init__()
        self._loop = loop
        self._disconnect_future_factory = disconnect_future_factory
        self._task = None

    def _disconnect_future(self):
        @asyncio.coroutine
        def wrapper():
            fut = self._disconnect_future_factory()
            try:
                yield from fut
            except asyncio.CancelledError:
                raise
            except:
                pass
        return asyncio.async(wrapper(), loop=self._loop)

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
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            # exception occured, do not enable SM, do not suppress exception
            return False

        self.broker._unacked_ctr_base = 0
        self.broker._sm_reset(enabled=True)

    def set_session_id(self, id_):
        self.broker._sm_id = id_

class StanzaBroker(StreamWorker):
    """
    Manage sending and receiving of stanzas.

    :param loop: Event loop to use
    :param disconnect_future_factory: A callable which returns a new :class:`asyncio.Future` each time it is called. These futures must be fulfilled when the stream gets disconnected, possibly with a corresponding exception.
    :param ping_timeout: passed to the liveness handler
    :param ping_timeout_callback: coroutine called by the liveness handler on
        ping timeout
    :param stanza_callbacks: triple of three callables, one for IQ requests, one
        for messages and one for presence.
    :type loop: :class:`asyncio.BaseEventLoop`
    :type disconnect_future_factory: callable returning :class:`asyncio.Future`
    :type ping_timeout: :class:`datetime.timedelta`
    :type ping_timeout_callback: coroutine
    :type stanza_callbacks: triple of callables

    .. seealso::

       :class:`StreamWorker` for more methods.

    """

    def __init__(self, loop, disconnect_future_factory,
                 ping_timeout,
                 ping_timeout_callback,
                 stanza_callbacks):
        super().__init__(loop, disconnect_future_factory)
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
            loop, disconnect_future_factory)
        self._liveness_handler_task = None

        self.active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self.incoming_iq_queue = custom_queue.AsyncDeque(loop=self._loop)
        self.incoming_message_queue = custom_queue.AsyncDeque(loop=self._loop)
        self.incoming_presence_queue = custom_queue.AsyncDeque(loop=self._loop)
        self.unacked_queue = list()

        self.ping_timeout = ping_timeout
        self.ping_timeout_callback = ping_timeout_callback

    def _flush_unacked_to_acked(self, new_ack_counter):
        upto_index = new_ack_counter-self._unacked_ctr_base
        self._unacked_ctr_base = new_ack_counter

        to_flush = self.unacked_queue[:upto_index]
        del self.unacked_queue[:upto_index]

        for token in to_flush:
            token._state = stanza.QueueState.ACKED
            if token.ack_callback:
                token.ack_callback()

    def _flush_unacked_to_sent_without_ack(self):
        to_hold = self.unacked_queue.copy()
        self.unacked_queue.clear()
        for token in to_hold:
            token._state = stanza.QueueState.SENT_WITHOUT_ACK

    def _prepare_token(self, token):
        if token._stanza is None:
            raise ValueError("Cannot send token without stanza")
        token._stanza.autoset_id()
        token._stanza.validate()

        if token._stanza.tag.endswith("}iq"):
            # IQ stanza, register handlers
            iq = token._stanza
            if iq.type_ in {"set", "get"}:
                logger.debug("registering response handler for %r "
                             "(id=%r, from=%r)",
                             token._stanza, iq.id_, iq.from_)
                self._iq_response_tokens[iq.id_, iq.to] = token
        else:
            if token.response_future:
                raise ValueError("Response future is not supported for "
                                 "{}".format(token._stanza))

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

    def _sm_reset(self, enabled=False, id_=None):
        restart = False
        if self._sm_enabled ^ enabled:
            # state will change
            if self._liveness_handler_task:
                restart = True
                self._liveness_handler.stop()
                self._liveness_handler.teardown()
                self._liveness_handler_task = None

            if enabled:
                self._liveness_handler = StreamManagementLivenessHandler(
                    self._loop,
                    self._disconnect_future_factory)
            else:
                self._liveness_handler = PingLivenessHandler(
                    self._loop,
                    self._disconnect_future_factory)
            self._liveness_handler.setup(self)

        self._sm_id = id_
        self._sm_enabled = enabled

        if not enabled:
            self._flush_unacked_to_sent_without_ack()

        if restart:
            self.start_liveness_handler()

    def _stanza_iq(self, iq):
        if iq.type_ in {"result", "error"}:
            try:
                token = self._iq_response_tokens.pop((iq.id_, iq.from_ or None))
            except KeyError:
                logger.warn("unexpected iq response: "
                            "from=%r, type=%s, id=%r, data=%s",
                            iq.from_, iq.type_, iq.id_, iq.data)
                logger.debug("current token map: %r",
                             self._iq_response_tokens)
            else:
                token.response_future.set_result(iq)
            return

        self._loop.call_soon(self._iq_request_callback, iq)

    # StreamWorker interface

    def setup(self, xmlstream):
        """
        Set up the StanzaBroker to work with the given *xmlstream*. This
        registers queues for the different stanza types and sets up the current
        liveness handler (but does not start it yet).
        """
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
        """
        Start the current liveness handler.
        """
        if self._liveness_handler_task is None:
            self._liveness_handler_task = self._liveness_handler.start()
            if self._task is not None:
                # we have to interrupt the task so that it starts watching the
                # liveness handler
                self._interrupt.set()

    def stop(self):
        """
        Stop the stanza broker and the liveness handler.
        """
        self._liveness_handler.stop()
        self._liveness_handler_task = None
        super().stop()

    def teardown(self):
        """
        Tear down the liveness handler and remove all queues from the xml
        stream.
        """
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

        disconnect_future = self._disconnect_future_factory()
        interrupt_future = asyncio.async(
            self._interrupt.wait(),
            loop=self._loop)

        outgoing_stanza_future = future_from_queue(
            self.active_queue, self._loop)

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

        try:
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
                    try:
                        disconnect_future.result()
                    except:
                        pass
                    break

                if self._liveness_handler_task in done:
                    raise RuntimeError("Liveness handler terminated unexpectedly") \
                        from self._liveness_handler_task.exception()

                if outgoing_stanza_future in done:
                    token = outgoing_stanza_future.result()
                    logger.debug("outgoing stanza to send: %r", token._stanza)
                    self._send_token(token)

                    if self.active_queue.empty():
                        # opportunistic send
                        for fn in self._callbacks["opportunistic_send"]:
                            for token in fn():
                                try:
                                    self._prepare_token(token)
                                except:
                                    logger.exception("during opportunistic "
                                                     "send (ignored)")
                                    continue
                                self._send_token(token)

                    outgoing_stanza_future = asyncio.async(
                        self.active_queue.get(),
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
        finally:
            logger.debug("terminating ...")
            if     (outgoing_stanza_future.done() and
                    not outgoing_stanza_future.exception()):
                logger.debug("rescueing stanza")
                self.active_queue.putleft_nowait(outgoing_stanza_future.result())
                logger.debug("rescued stanza")
            else:
                logger.debug("killing outgoing_stanza_future")
                outgoing_stanza_future.cancel()
            for fut, queue in zip(incoming_futures, incoming_queues):
                if (fut.done() and not fut.exception()):
                    # re-insert stanza into incoming queue
                    queue.putleft_nowait(fut.result())
                else:
                    fut.cancel()

            # XXX: clear all incoming queues to avoid double stanza delivery on
            # SM resumption. The other option would be to submit the stanzas to
            # the handlers, but as we are most likely not connected anymore it
            # does not make a whole lot of sense to do that
            #
            # FIXME: maybe we should only clear the queues if SM is enabled. on
            # the other hand, most handlers will still not be able to do
            # something sensible with this.
            for queue in incoming_queues:
                queue.clear()
            disconnect_future.cancel()


    # StanzaBroker interface

    def enqueue_token(self, token):
        """
        Enqueue a stanza token for sending.

        This makes sure the ID of the stanza to be sent is initialized. If the
        stanza is an IQ and has a response future, it is registered so that a
        response will be forwarded to the corresponding future.

        The stanza is put into a queue which is handled by the stanza broker and
        sent as soon as possible.
        """
        self._prepare_token(token)
        self.active_queue.put_nowait(token)

    def make_stanza_token(self, for_stanza, **kwargs):
        """
        Construct a stanza token which works with this stream broker. The
        keyword arguments are forwarded to the constructor of
        :class:`~.stanza.StanzaToken`, but *abort_impl* and *resend_impl* are
        set by this function. Thus, specifying these in the arguments to this
        function results in a :class:`TypeError.

        Return the stanza token.
        """
        return stanza.StanzaToken(
            for_stanza,
            abort_impl=self._queued_stanza_abort,
            resend_impl=self._queued_stanza_resend,
            **kwargs)

    @property
    def sm_acked_remote_ctr(self):
        """
        The counter which counts the amount of stanzas received by the peer.
        """
        return self._acked_remote_ctr

    @property
    def sm_enabled(self):
        """
        Boolean attribute which is true if stream management has been negotiated
        successfully on the stream.
        """
        return self._sm_enabled

    @property
    def sm_session_id(self):
        """
        If :attr:`sm_enabled` is true, this is the stream management ID which
        was obtained during negotiation.
        """
        if not self.sm_enabled:
            return None
        return self._sm_id

    def sm_resume(self, remote_counter):
        """
        Resume stream management. *remote_counter* must be an integer which is
        equal to the remote counter received upon stream resumption.
        """

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
        """
        Disable and reset stream management state.
        """
        self._sm_reset(False, None)

    def register_callback(self, cb, fn):
        """
        Register a function *fn* for the given *cb*. The following callbacks are
        available:

        .. function:: opportunistic_send()

           Called whenever stanzas have been sent and the queue is empty. Return
           an iterable of tokens which should be sent, too.

        """
        fnset = self._callbacks[cb]
        fnset.add(fn)

    def unregister_callback(self, cb, fn):
        """
        Remove a function *fn* from the callback registry for *cb*.

        This raises :class:`KeyError` if the callback is undefined.
        """
        self._callbacks[cb].discard(fn)


class LivenessHandler(StreamWorker):
    """
    A liveness handler takes care of ensuring that the stream is still alive,
    and if not, calls the corresponding ping timeout coroutine passed to the
    :class:`StreamWorker`.

    Liveness handlers are tightly coupled with the :class:`StanzaBroker` class,
    and generally need access to "protected" attributes, such as stream
    management state.

    The general idea of liveness handlers is to periodically "ping" the XML
    stream peer. How this "ping" is implemented depends on the specific liveness
    handler. The interval of inactivity until which a ping is sent is given by
    the *ping_timeout* argument passed to the :class:`StanzaBroker`
    constructor.

    To save resources, the liveness handler will try to schedule sending the
    "ping" together with other stanzas, by using the :func:`opportunistic_send`
    callback provided by the :class:`StanzaBroker`. However, it will wait for at
    most :attr:`passive_request_timeout`, after which sending is forced.

    .. attribute:: passive_request_timeout

       :class:`datetime.timedelta` which defines the maximum time the liveness
       handler will wait for an opportunistic send event before forcing its
       "ping" to be sent.

    """

    def __init__(self, loop, disconnect_future_factory):
        super().__init__(loop, disconnect_future_factory)
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
        """
        Set up the liveness handler to work with the given *stanza_broker*. This
        is generally overriden by subclasses. This method also registers the
        opportunistic send callback.
        """
        self.stanza_broker = stanza_broker
        super().setup(stanza_broker.xmlstream)
        self.stanza_broker.register_callback(
            "opportunistic_send",
            self._on_opportunistic_send)

    def start(self):
        """
        Reset the internal state and start the worker coroutine.
        """
        self.last_liveness_indicator = datetime.utcnow()
        self.passive_request_until = None
        return super().start()

    def teardown(self):
        """
        Remove the callbacks and generally decouple from the xmlstream and the
        stanza broker.
        """
        self.stanza_broker.unregister_callback(
            "opportunistic_send",
            self._on_opportunistic_send)
        del self.stanza_broker
        super().teardown()

    @abc.abstractmethod
    def perform_request(self):
        """
        It is called when the opportunistic send event is received and a passive
        request has been scheduled.

        Either send the required elements directly over the xml stream, or
        return an iterable of nodes to be sent. If sending directly, this
        function must return an empty iterable.

        This must be implemented by subclasses.
        """

class PingLivenessHandler(LivenessHandler):
    """
    The ping liveness handler uses `XEP-0199
    <https://xmpp.org/extensions/xep-0199.html>`_ pings to check for stream
    liveness. Pings are sent periodically and whenever a reply (be it a "result"
    or an "error") is received, the stream is considered alive.
    """

    def perform_request(self):
        self.response_future = asyncio.Future()
        token = self.stanza_broker.make_stanza_token(
            self.xmlstream.tx_context.make_iq(type_="get"),
            response_future=self.response_future
        )
        token.stanza.autoset_id()
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

        disconnect_future = self._disconnect_future_factory()

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
                try:
                    disconnect_future.result()
                except:
                    pass
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
                    yield from self.stanza_broker.ping_timeout_callback()
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
    """
    The stream management liveness handler makes use of `XEP-0198
    <https://xmpp.org/extensions/xep-0198.html>`_ stream management ack-requests
    "ping" the peer.

    In addition it takes care of handling stream management ack-requests from
    the peer and replying to them correctly.
    """

    def __init__(self, loop, disconnect_future_factory):
        super().__init__(loop, disconnect_future_factory)
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
        self.E = self.xmlstream.tx_context.default_ns_builder(
            namespaces.stream_management)

    def teardown(self):
        del self.E
        self.xmlstream.stream_level_hooks.remove_queue(
            "{{{}}}r".format(namespaces.stream_management),
            self.request_queue)
        self.xmlstream.stream_level_hooks.remove_queue(
            "{{{}}}a".format(namespaces.stream_management),
            self.ack_queue)
        super().teardown()

    def perform_request(self):
        request = self.E("r")
        self.passive_request_until = None
        self.ack_pending = datetime.utcnow()
        self.xmlstream.send_node(request)
        return []

    @asyncio.coroutine
    def worker(self):
        logger = logging.getLogger(__name__ + ".liveness")
        logger.info("using stream management for liveness")

        disconnect_future = self._disconnect_future_factory()
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
                try:
                    disconnect_future.result()
                except:
                    pass
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
                ack_node = self.E(
                    "a",
                    h=str(self.stanza_broker._acked_remote_ctr))
                self.xmlstream.send_node(ack_node)

                request_future = future_from_queue(self.request_queue,
                                                   self._loop)

            if self.ack_pending:
                if (now - self.ack_pending) > ping_timeout:
                    logger.debug("ping timeout on ack request")
                    yield from self.stanza_broker.ping_timeout_callback()
                    self.ack_pending = None
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
