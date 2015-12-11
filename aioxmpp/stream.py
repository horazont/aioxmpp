"""
:mod:`~aioxmpp.stream` --- Stanza stream
########################################

The stanza stream is the layer of abstraction above the XML stream. It deals
with sending and receiving stream-level elements, mainly stanzas. It also
handles stream liveness and stream management.

It provides ways to track stanzas on their way to the remote, as far as that is
possible.

.. autoclass:: StanzaStream

Low-level stanza tracking
=========================

The following classes are used to track stanzas in the XML stream to the
server. This is independent of things like `XEP-0184 Message Delivery
Receipts`__ (for which services are provided at :mod:`aioxmpp.tracking`); it
only provides tracking to the remote server and even that only if stream
management is used. Otherwise, it only provides tracking in the :mod:`aioxmpp`
internal queues.

__ http://xmpp.org/extensions/xep-0184.html

.. autoclass:: StanzaToken

.. autoclass:: StanzaState

Filters
=======

The filters used by the :class:`StanzaStream` are implemented by the following
classes:

.. autoclass:: Filter

.. autoclass:: AppFilter

"""

import asyncio
import functools
import logging

from datetime import datetime, timedelta
from enum import Enum

from . import (
    stanza,
    errors,
    custom_queue,
    nonza,
    callbacks,
    protocol,
)

from .plugins import xep0199
from .utils import namespaces


class Filter:
    """
    A filter chain for stanzas. The idea is to process a stanza through a
    sequence of user- and service-definable functions.

    Each function must either return the stanza it received as argument or
    :data:`None`. If it returns :data:`None` the filtering aborts and the
    caller of :meth:`filter` also receives :data:`None`.

    Each function receives the result of the previous function for further
    processing.

    .. automethod:: register

    .. automethod:: filter

    .. automethod:: unregister
    """

    class Token:
        def __str__(self):
            return "<{}.{} 0x{:x}>".format(
                type(self).__module__,
                type(self).__qualname__,
                id(self))

    def __init__(self):
        super().__init__()
        self._filter_order = []

    def register(self, func, order):
        """
        Register a function `func` as filter in the chain. `order` must be a
        value which will be used to order the registered functions relative to
        each other.

        Functions with the same order are sorted in the order of their
        addition, with the function which was added earliest first.

        Remember that all values passed to `order` which are registered at the
        same time in the same :class:`Filter` need to be at least partially
        orderable with respect to each other.

        Return an opaque token which is needed to unregister a function.
        """
        token = self.Token()
        self._filter_order.append((order, token, func))
        self._filter_order.sort(key=lambda x: x[0])
        return token

    def filter(self, stanza_obj):
        """
        Pass the given `stanza_obj` through the filter chain and return the
        result of the chain. See :class:`Filter` for details on how the value
        is passed through the registered functions.
        """
        for _, _, func in self._filter_order:
            stanza_obj = func(stanza_obj)
            if stanza_obj is None:
                return None
        return stanza_obj

    def unregister(self, token_to_remove):
        """
        Unregister a function from the filter chain using the token returned by
        :meth:`register`.
        """
        for i, (_, token, _) in enumerate(self._filter_order):
            if token == token_to_remove:
                break
        else:
            raise ValueError("unregistered token: {!r}".format(
                token_to_remove))
        del self._filter_order[i]


class AppFilter(Filter):
    """
    A specialized :class:`Filter` version. The only difference is in the
    handling of the `order` argument to :meth:`register`:

    .. automethod:: register
    """

    def register(self, func, order=0):
        """
        This method works exactly like :meth:`Filter.register`, but `order` has
        a default value of ``0``.
        """
        return super().register(func, order)


class PingEventType(Enum):
    SEND_OPPORTUNISTIC = 0
    SEND_NOW = 1
    TIMEOUT = 2


class StanzaState(Enum):
    """
    The various states an outgoing stanza can have.

    .. attribute:: ACTIVE

       The stanza has just been enqueued for sending and has not been taken
       care of by the StanzaStream yet.

    .. attribute:: SENT

       The stanza has been sent over a stream with Stream Management enabled,
       but not acked by the remote yet.

    .. attribute:: ACKED

       The stanza has been sent over a stream with Stream Management enabled
       and has been acked by the remote. This is a final state.

    .. attribute:: SENT_WITHOUT_SM

       The stanza has been sent over a stream without Stream Management enabled
       or has been sent over a stream with Stream Management enabled, but for
       which resumption has failed before the stanza has been acked.

       This is a final state.

    .. attribute:: ABORTED

       The stanza has been retracted before it left the active queue.

       This is a final state.

    .. attribute:: DROPPED

       The stanza has been dropped by one of the filters configured in the
       :class:`StanzaStream`.

       This is a final state.

    """
    ACTIVE = 0
    SENT = 1
    ACKED = 2
    SENT_WITHOUT_SM = 3
    ABORTED = 4
    DROPPED = 5


class StanzaErrorAwareListener:
    def __init__(self, forward_to):
        self._forward_to = forward_to

    def data(self, stanza_obj):
        if stanza_obj.type_ == "error":
            return self._forward_to.error(
                stanza_obj.error.to_exception()
            )
        return self._forward_to.data(stanza_obj)

    def error(self, exc):
        return self._forward_to.error(exc)

    def is_valid(self):
        return self._forward_to.is_valid()


class StanzaToken:
    """
    A token to follow the processing of a `stanza`.

    `on_state_change` may be a function which will be called with the token and
    the new :class:`StanzaState` whenever the state of the token changes.

    .. autoattribute:: state

    .. automethod:: abort
    """

    def __init__(self, stanza, *, on_state_change=None):
        self.stanza = stanza
        self._state = StanzaState.ACTIVE
        self.on_state_change = on_state_change

    @property
    def state(self):
        """
        The current :class:`StanzaState` of the token. Tokens are created with
        :attr:`StanzaState.ACTIVE`.
        """

        return self._state

    def _set_state(self, new_state):
        self._state = new_state
        if self.on_state_change is not None:
            self.on_state_change(self, new_state)

    def abort(self):
        """
        Abort the stanza. Attempting to call this when the stanza is in any
        non-:class:`~StanzaState.ACTIVE`, non-:class:`~StanzaState.ABORTED`
        state results in a :class:`RuntimeError`.

        When a stanza is aborted, it will reside in the active queue of the
        stream, not will be sent and instead discarded silently.
        """
        if     (self._state != StanzaState.ACTIVE and
                self._state != StanzaState.ABORTED):
            raise RuntimeError("cannot abort stanza (already sent)")
        self._state = StanzaState.ABORTED

    def __repr__(self):
        return "<StanzaToken id=0x{:016x}>".format(id(self))


class StanzaStream:
    """
    A stanza stream. This is the next layer of abstraction above the XMPP XML
    stream, which mostly deals with stanzas (but also with certain other
    stream-level elements, such as XEP-0198 Stream Management Request/Acks).

    It is independent from a specific :class:`~aioxmpp.protocol.XMLStream`
    instance. A :class:`StanzaStream` can be started with one XML stream,
    stopped later and then resumed with another XML stream. The user of the
    :class:`StanzaStream` has to make sure that the XML streams are compatible,
    identity-wise (use the same JID).

    `local_jid` may be the **bare** sender JID associated with the stanza
    stream. This is required for compatibility with ejabberd. If it is omitted,
    communication with ejabberd instances may not work.

    `loop` may be used to explicitly specify the :class:`asyncio.BaseEventLoop`
    to use, otherwise the current event loop is used.

    `base_logger` can be used to explicitly specify a :class:`logging.Logger`
    instance to fork off the logger from. The :class:`StanzaStream` will use a
    child logger of `base_logger` called ``StanzaStream``.

    .. versionchanged:: 0.4

       The `local_jid` argument was added.

    The stanza stream takes care of ensuring stream liveness. For that, pings
    are sent in a periodic interval. If stream management is enabled, stream
    management ack requests are used as pings, otherwise XEP-0199 pings are
    used.

    The general idea of pinging is, to save computing power, to send pings only
    when other stanzas are also about to be sent, if possible. The time window
    for waiting for other stanzas is defined by
    :attr:`ping_opportunistic_interval`. The general time which the
    :class:`StanzaStream` waits between the reception of the previous ping and
    contemplating the sending of the next ping is controlled by
    :attr:`ping_interval`. See the attributes descriptions for details:

    .. attribute:: ping_interval = timedelta(seconds=15)

       A :class:`datetime.timedelta` instance which controls the time between a
       ping response and starting the next ping. When this time elapses,
       opportunistic mode is engaged for the time defined by
       :attr:`ping_opportunistic_interval`.

    .. attribute:: ping_opportunistic_interval = timedelta(seconds=15)

       This is the time interval after :attr:`ping_interval`. During that
       interval, :class:`StanzaStream` waits for other stanzas to be sent. If a
       stanza gets send during that interval, the ping is fired. Otherwise, the
       ping is fired after the interval.

    After a ping has been sent, the response must arrive in a time of
    :attr:`ping_interval` for the stream to be considered alive. If the
    response fails to arrive within that interval, the stream fails (see
    :attr:`on_failure`).

    Starting/Stopping the stream:

    .. automethod:: start

    .. automethod:: stop

    .. automethod:: wait_stop

    .. automethod:: close

    .. autoattribute:: running

    .. automethod:: flush_incoming

    Sending stanzas:

    .. automethod:: enqueue_stanza

    .. automethod:: send_iq_and_wait_for_reply

    Receiving stanzas:

    .. automethod:: register_iq_request_coro

    .. automethod:: unregister_iq_request_coro

    .. automethod:: register_iq_response_future

    .. automethod:: register_iq_response_callback

    .. automethod:: unregister_iq_response

    .. automethod:: register_message_callback

    .. automethod:: unregister_message_callback

    .. automethod:: register_presence_callback

    .. automethod:: unregister_presence_callback

    Inbound stanza filters allow to hook into the stanza processing by
    replacing, modifying or otherwise processing stanza contents *before* the
    above callbacks are invoked. With inbound stanza filters, there are no
    restrictions as to what processing may take place on a stanza, as no one
    but the stream may have references to its contents. See below for a
    guideline on when to use stanza filters.

    .. warning::

       Raising an exception from within a stanza filter kills the stream.

    Note that if a filter function drops an incoming stanza (by returning
    :data:`None`), it **must** ensure that the client still behaves RFC
    compliant.

    .. attribute:: app_inbound_presence_filter

       This is a :class:`AppFilter` based filter chain on inbound presence
       stanzas. It can be used to attach application-specific filters.

    .. attribute:: service_inbound_presence_filter

       This is another filter chain for inbound presence stanzas. It runs
       *before* the :attr:`app_inbound_presence_filter` chain and all functions
       registered there must have :class:`service.Service` *classes* as `order`
       value (see :meth:`Filter.register`).

       This filter chain is intended to be used by library services, such as a
       XEP-0115 implementation which may start a XEP-0030 lookup at the target
       entity to resolve the capability hash or prime the XEP-0030 cache with
       the service information obtained by interpreting the XEP-0115 hash
       value.

    .. attribute:: app_inbound_message_filter

       This is a :class:`AppFilter` based filter chain on inbound message
       stanzas. It can be used to attach application-specific filters.

    .. attribute:: service_inbound_message_filter

       This is the analogon of :attr:`service_inbound_presence_filter` for
       :attr:`app_inbound_message_filter`.

    Outbound stanza filters work similar to inbound stanza filters, but due to
    their location in the processing chain and possible interactions with
    senders of stanzas, there are some things to consider:

    * Per convention, a outbound stanza filter **must not** modify any child
      elements which are already present in the stanza when it receives the
      stanza.

      It may however add new child elements or remove existing child elements,
      as well as copying and *then* modifying existing child elements.

    * If the stanza filter replaces the stanza, it is responsible for making
      sure that the new stanza has appropriate
      :attr:`~.stanza.StanzaBase.from_`, :attr:`~.stanza.StanzaBase.to` and
      :attr:`~.stanza.StanzaBase.id` values. There are no checks to enforce
      this, because errorr handling at this point is peculiar. The stanzas will
      be sent as-is.

    * Similar to inbound filters, it is the responsibility of the filters that
      if stanzas are dropped, the client still behaves RFC-compliant.

    Now that you have been warned, here are the attributes for accessing the
    outbound filter chains. These otherwise work exactly like their inbound
    counterparts, but service filters run *after* application filters on
    outbound processing.

    .. attribute:: app_outbound_presence_filter

       This is a :class:`AppFilter` based filter chain on outbound presence
       stanzas. It can be used to attach application-specific filters.

       Before using this attribute, make sure that you have read the notes
       above.

    .. attribute:: service_outbound_presence_filter

       This is the analogon of :attr:`service_inbound_presence_filter`, but for
       outbound presence. It runs *after* the
       :meth:`app_outbound_presence_filter`.

       Before using this attribute, make sure that you have read the notes
       above.

    .. attribute:: app_outbound_message_filter

       This is a :class:`AppFilter` based filter chain on inbound message
       stanzas. It can be used to attach application-specific filters.

       Before using this attribute, make sure that you have read the notes
       above.

    .. attribute:: service_outbound_messages_filter

       This is the analogon of :attr:`service_outbound_presence_filter`, but
       for outbound messages.

       Before using this attribute, make sure that you have read the notes
       above.

    When to use stanza filters? In general, applications will rarely need
    them. However, services may make profitable use of them, and it is a
    convenient way for them to inspect incoming or outgoing stanzas without
    having to take up the registration slots (remember that
    :meth:`register_message_callback` et. al. only allow *one* callback per
    designator).

    In general, whenever you do something which *supplements* the use of the
    stanza with respect to the RFC but does not fulfill the orignial intent of
    the stanza, it is advisable to use a filter instead of a callback on the
    actual stanza.

    Vice versa, if you were to develop a service which manages presence
    subscriptions, it would be more correct to use
    :meth:`register_presence_callback`; this prevents other services which try
    to do the same from conflicting with you. You would then provide callbacks
    to the application to let it learn about presence subscriptions.

    Using stream management:

    .. automethod:: start_sm

    .. automethod:: resume_sm

    .. automethod:: stop_sm

    .. autoattribute:: sm_enabled

    Stream management state inspection:

    .. autoattribute:: sm_outbound_base

    .. autoattribute:: sm_inbound_ctr

    .. autoattribute:: sm_unacked_list

    .. autoattribute:: sm_id

    .. autoattribute:: sm_max

    .. autoattribute:: sm_location

    .. autoattribute:: sm_resumable

    Miscellaneous:

    .. autoattribute:: local_jid

    Signals:

    .. signal:: on_failure(exc)

       A signal which will fire when the stream has failed. A failure
       occurs whenever the main task of the :class:`StanzaStream` (the one
       started by :meth:`start`) terminates with an exception.

       Examples are :class:`ConnectionError` as raised upon a ping timeout and
       any exceptions which may be raised by the
       :meth:`aioxmpp.protocol.XMLStream.send_xso` method.

       The exception which occured is given as `exc`.

    .. signal:: on_stream_destroyed()

       When a stream is destroyed so that all state shall be discarded (for
       example, pending futures), this signal is fired.

       This happens if a non-SM stream is stopped or if SM is being disabled.

    .. signal:: on_stream_established()

       When a stream is newly established, this signal is fired. This happens
       whenever a non-SM stream is started and whenever a stream which
       previously had SM disabled is started with SM enabled.

    """

    on_failure = callbacks.Signal()
    on_stream_destroyed = callbacks.Signal()
    on_stream_established = callbacks.Signal()

    def __init__(self,
                 local_jid=None,
                 *,
                 loop=None,
                 base_logger=logging.getLogger("aioxmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._logger = base_logger.getChild("StanzaStream")
        self._task = None

        self._local_jid = local_jid

        self._active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self._incoming_queue = custom_queue.AsyncDeque(loop=self._loop)

        self._iq_response_map = callbacks.TagDispatcher()
        self._iq_request_map = {}
        self._message_map = {}
        self._presence_map = {}

        self._ping_send_opportunistic = False
        self._next_ping_event_at = None
        self._next_ping_event_type = None

        self._xmlstream_exception = None

        self._established = False

        self.ping_interval = timedelta(seconds=15)
        self.ping_opportunistic_interval = timedelta(seconds=15)

        self._sm_enabled = False

        self._broker_lock = asyncio.Lock(loop=loop)

        self.app_inbound_presence_filter = AppFilter()
        self.service_inbound_presence_filter = Filter()

        self.app_inbound_message_filter = AppFilter()
        self.service_inbound_message_filter = Filter()

        self.app_outbound_presence_filter = AppFilter()
        self.service_outbound_presence_filter = Filter()

        self.app_outbound_message_filter = AppFilter()
        self.service_outbound_message_filter = Filter()

    @property
    def local_jid(self):
        """
        The `local_jid` argument to the constructor. This cannot be changed.
        """
        return self._local_jid

    def _done_handler(self, task):
        """
        Called when the main task (:meth:`_run`, :attr:`_task`) returns.
        """
        try:
            task.result()
        except asyncio.CancelledError:
            # normal termination
            pass
        except Exception as err:
            if self.on_failure:
                self.on_failure(err)
            self._logger.exception("broker task failed")

    def _xmlstream_failed(self, exc):
        self._xmlstream_exception = exc
        self.stop()

    def _destroy_stream_state(self, exc):
        """
        Destroy all state which does not make sense to keep after an disconnect
        (without stream management).
        """
        self._iq_response_map.close_all(exc)
        if self._established:
            self.on_stream_destroyed()
            self._established = False

    def _iq_request_coro_done(self, request, task):
        """
        Called when an IQ request handler coroutine returns. `request` holds
        the IQ request which triggered the excecution of the coroutine and
        `task` is the :class:`asyncio.Task` which tracks the running coroutine.

        Compose a response and send that response.
        """
        try:
            payload = task.result()
        except errors.XMPPError as err:
            response = request.make_reply(type_="error")
            response.error = stanza.Error.from_exception(err)
        except Exception:
            response = request.make_reply(type_="error")
            response.error = stanza.Error(
                condition=(namespaces.stanzas, "undefined-condition"),
                type_="cancel",
            )
        else:
            response = request.make_reply(type_="result")
            response.payload = payload
        self.enqueue_stanza(response)

    def _process_incoming_iq(self, stanza_obj):
        """
        Process an incoming IQ stanza `stanza_obj`. Calls the response handler,
        spawns a request handler coroutine or drops the stanza while logging a
        warning if no handler can be found.
        """
        self._logger.debug("incoming iq: %r", stanza_obj)
        if stanza_obj.type_ == "result" or stanza_obj.type_ == "error":
            # iq response
            self._logger.debug("iq is response")
            key = (stanza_obj.from_, stanza_obj.id_)
            if key[0] == self._local_jid:
                key = (None, key[1])
            try:
                self._iq_response_map.unicast(key, stanza_obj)
            except KeyError:
                self._logger.warning(
                    "unexpected IQ response: from=%r, id=%r",
                    *key)
                return
        else:
            # iq request
            self._logger.debug("iq is request")
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
            self._logger.debug("started task to handle request: %r", task)

    def _process_incoming_message(self, stanza_obj):
        """
        Process an incoming message stanza `stanza_obj`.
        """
        self._logger.debug("incoming messgage: %r", stanza_obj)

        stanza_obj = self.service_inbound_message_filter.filter(stanza_obj)
        if stanza_obj is None:
            self._logger.debug("incoming message dropped by service "
                               "filter chain")
            return

        stanza_obj = self.app_inbound_message_filter.filter(stanza_obj)
        if stanza_obj is None:
            self._logger.debug("incoming message dropped by application "
                               "filter chain")
            return

        keys = [(stanza_obj.type_, stanza_obj.from_),
                (stanza_obj.type_, stanza_obj.from_.bare()),
                (None, stanza_obj.from_),
                (None, stanza_obj.from_.bare()),
                (stanza_obj.type_, None),
                (None, None)]

        for key in keys:
            try:
                cb = self._message_map[key]
            except KeyError:
                continue
            self._logger.debug("dispatching message using key %r to %r",
                               key, cb)
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
        """
        Process an incoming presence stanza `stanza_obj`.
        """
        self._logger.debug("incoming presence: %r", stanza_obj)

        stanza_obj = self.service_inbound_presence_filter.filter(stanza_obj)
        if stanza_obj is None:
            self._logger.debug("incoming presence dropped by service filter"
                               " chain")
            return

        stanza_obj = self.app_inbound_presence_filter.filter(stanza_obj)
        if stanza_obj is None:
            self._logger.debug("incoming presence dropped by application "
                               "filter chain")
            return

        keys = [(stanza_obj.type_, stanza_obj.from_),
                (stanza_obj.type_, None)]
        for key in keys:
            try:
                cb = self._presence_map[key]
            except KeyError:
                continue
            self._logger.debug("dispatching presence using key: %r", key)
            self._loop.call_soon(cb, stanza_obj)
            break
        else:
            self._logger.warning(
                "unhandled presence dropped: from=%r, type=%r, id=%r",
                stanza_obj.from_,
                stanza_obj.type_,
                stanza_obj.id_
            )

    def _process_incoming_errorneous_stanza(self, stanza_obj, exc):
        if stanza_obj.type_ == "error" or stanza_obj.type_ == "result":
            if     (isinstance(stanza_obj, stanza.IQ) and
                    stanza_obj.from_ is not None):
                key = (stanza_obj.from_, stanza_obj.id_)
                try:
                    self._iq_response_map.unicast_error(
                        key,
                        errors.ErrorneousStanza(stanza_obj)
                    )
                except KeyError:
                    pass
            return

        if isinstance(exc, stanza.PayloadParsingError):
            reply = stanza_obj.make_error(error=stanza.Error(condition=(
                namespaces.stanzas,
                "bad-request")
            ))
            self.enqueue_stanza(reply)
        elif isinstance(exc, stanza.UnknownIQPayload):
            reply = stanza_obj.make_error(error=stanza.Error(condition=(
                namespaces.stanzas,
                "feature-not-implemented")
            ))
            self.enqueue_stanza(reply)

    def _process_incoming(self, xmlstream, queue_entry):
        """
        Dispatch to the different methods responsible for the different stanza
        types or handle a non-stanza stream-level element from `stanza_obj`,
        which has arrived over the given `xmlstream`.
        """

        stanza_obj, exc = queue_entry

        # first, handle SM stream objects
        if isinstance(stanza_obj, nonza.SMAcknowledgement):
            self._logger.debug("received SM ack: %r", stanza_obj)
            if not self._sm_enabled:
                self._logger.warning("received SM ack, but SM not enabled")
                return
            self.sm_ack(stanza_obj.counter)

            if self._next_ping_event_type == PingEventType.TIMEOUT:
                self._logger.debug("resetting ping timeout")
                self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
                self._next_ping_event_at = (datetime.utcnow() +
                                            self.ping_interval)
            return
        elif isinstance(stanza_obj, nonza.SMRequest):
            self._logger.debug("received SM request: %r", stanza_obj)
            if not self._sm_enabled:
                self._logger.warning("received SM request, but SM not enabled")
                return
            response = nonza.SMAcknowledgement()
            response.counter = self._sm_inbound_ctr
            self._logger.debug("sending SM ack: %r", stanza_obj)
            xmlstream.send_xso(response)
            return

        # raise if it is not a stanza
        if not isinstance(stanza_obj, stanza.StanzaBase):
            raise RuntimeError(
                "unexpected stanza class: {}".format(stanza_obj))

        # now handle stanzas, these always increment the SM counter
        if self._sm_enabled:
            self._sm_inbound_ctr += 1

        # check if the stanza has errors
        if exc is not None:
            self._process_incoming_errorneous_stanza(stanza_obj, exc)
            return

        if isinstance(stanza_obj, stanza.IQ):
            self._process_incoming_iq(stanza_obj)
        elif isinstance(stanza_obj, stanza.Message):
            self._process_incoming_message(stanza_obj)
        elif isinstance(stanza_obj, stanza.Presence):
            self._process_incoming_presence(stanza_obj)

    def flush_incoming(self):
        """
        Flush all incoming queues to the respective processing methods. The
        handlers are called as usual, thus it may require at least one
        iteration through the asyncio event loop before effects can be seen.

        The incoming queues are empty after a call to this method.

        It is legal (but pretty useless) to call this method while the stream
        is :attr:`running`.
        """
        while True:
            try:
                stanza_obj = self._incoming_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._process_incoming(None, stanza_obj)

    def _send_stanza(self, xmlstream, token):
        """
        Send a stanza token `token` over the given `xmlstream`.

        Only sends if the `token` has not been aborted (see
        :meth:`StanzaToken.abort`). Sends the state of the token acoording to
        :attr:`sm_enabled`.
        """
        if token.state == StanzaState.ABORTED:
            return

        stanza_obj = token.stanza

        if isinstance(stanza_obj, stanza.Presence):
            stanza_obj = self.app_outbound_presence_filter.filter(
                stanza_obj
            )
            if stanza_obj is not None:
                stanza_obj = self.service_outbound_presence_filter.filter(
                    stanza_obj
                )
        elif isinstance(stanza_obj, stanza.Message):
            stanza_obj = self.app_outbound_message_filter.filter(
                stanza_obj
            )
            if stanza_obj is not None:
                stanza_obj = self.service_outbound_message_filter.filter(
                    stanza_obj
                )

        if stanza_obj is None:
            token._set_state(StanzaState.DROPPED)
            self._logger.debug("outgoing stanza %r dropped by filter chain",
                               token.stanza)
            return

        self._logger.debug("forwarding stanza to xmlstream: %r",
                           stanza_obj)

        xmlstream.send_xso(stanza_obj)
        if self._sm_enabled:
            token._set_state(StanzaState.SENT)
            self._sm_unacked_list.append(token)
        else:
            token._set_state(StanzaState.SENT_WITHOUT_SM)

    def _process_outgoing(self, xmlstream, token):
        """
        Process the current outgoing stanza `token` and also any other outgoing
        stanza which is currently in the active queue. After all stanzas have
        been processed, use :meth:`_send_ping` to allow an opportunistic ping
        to be sent.
        """

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
        """
        Process the reception of a XEP-0199 ping reply.
        """

        if not self.running:
            return
        if self._next_ping_event_type != PingEventType.TIMEOUT:
            return
        self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
        self._next_ping_event_at = datetime.utcnow() + self.ping_interval

    def _send_ping(self, xmlstream):
        """
        Opportunistically send a ping over the given `xmlstream`.

        If stream management is enabled, an SM request is always sent,
        independent of the current ping state. Otherwise, a XEP-0199 ping is
        sent if and only if we are currently in the opportunistic ping interval
        (see :attr:`ping_opportunistic_interval`).

        If a ping is sent, and we are currently not waiting for a pong to be
        received, the ping timeout is configured.
        """
        if not self._ping_send_opportunistic:
            return

        if self._sm_enabled:
            self._logger.debug("sending SM req")
            xmlstream.send_xso(nonza.SMRequest())
        else:
            request = stanza.IQ(type_="get")
            request.payload = xep0199.Ping()
            request.autoset_id()
            self.register_iq_response_callback(
                None,
                request.id_,
                self._recv_pong
            )
            self._logger.debug("sending XEP-0199 ping: %r", request)
            xmlstream.send_xso(request)
            self._ping_send_opportunistic = False

        if self._next_ping_event_type != PingEventType.TIMEOUT:
            self._logger.debug("configuring ping timeout")
            self._next_ping_event_at = datetime.utcnow() + self.ping_interval
            self._next_ping_event_type = PingEventType.TIMEOUT

    def _process_ping_event(self, xmlstream):
        """
        Process a ping timed event on the current `xmlstream`.
        """
        if self._next_ping_event_type == PingEventType.SEND_OPPORTUNISTIC:
            self._logger.debug("ping: opportunistic interval started")
            self._next_ping_event_at += self.ping_opportunistic_interval
            self._next_ping_event_type = PingEventType.SEND_NOW
            # ping send opportunistic is always true for sm
            if not self._sm_enabled:
                self._ping_send_opportunistic = True
        elif self._next_ping_event_type == PingEventType.SEND_NOW:
            self._logger.debug("ping: requiring ping to be sent now")
            self._send_ping(xmlstream)
        elif self._next_ping_event_type == PingEventType.TIMEOUT:
            self._logger.warning("ping: response timeout tripped")
            raise ConnectionError("ping timeout")
        else:
            raise RuntimeError("unknown ping event type: {!r}".format(
                self._next_ping_event_type))

    def register_iq_response_callback(self, from_, id_, cb):
        """
        Register a callback function `cb` to be called when a IQ stanza with
        type ``result`` or ``error`` is recieved from the
        :class:`~aioxmpp.structs.JID` `from_` with the id `id_`.

        The callback is called at most once.

        .. note::

           In contrast to :meth:`register_iq_response_future`, errors which
           occur on a level below XMPP stanzas cannot be caught using a
           callback.

           If you need notification about other errors and still want to use
           callbacks, use of a future with
           :meth:`asyncio.Future.add_done_callback` is recommended.

        """

        self._iq_response_map.add_listener(
            (from_, id_),
            callbacks.OneshotAsyncTagListener(cb, loop=self._loop)
        )
        self._logger.debug("iq response callback registered: from=%r, id=%r",
                           from_, id_)

    def register_iq_response_future(self, from_, id_, fut):
        """
        Register a future `fut` for an IQ stanza with type ``result`` or
        ``error`` from the :class:`~aioxmpp.structs.JID` `from_` with the id
        `id_`.

        If the type of the IQ stanza is ``result``, the stanza is set as result
        to the future. If the type of the IQ stanza is ``error``, the stanzas
        error field is converted to an exception and set as the exception of
        the future.

        The future might also receive different exceptions:

        * :class:`.errors.ErrorneousStanza`, if the response stanza received
          could not be parsed.

          Note that this exception is not emitted if the ``from`` address of
          the stanza is unset, because the code cannot determine whether a
          sender deliberately used an errorneous address to make parsing fail
          or no sender address was used. In the former case, an attacker could
          use that to inject a stanza which would be taken as a stanza from the
          peer server. Thus, the future will never be fulfilled in these
          cases.

          Also note that this exception does not derive from
          :class:`.errors.XMPPError`, as it cannot provide the same
          attributes. Instead, it dervies from :class:`.errors.StanzaError`,
          from which :class:`.errors.XMPPError` also derives; to catch all
          possible stanza errors, catching :class:`.errors.StanzaError` is
          sufficient and future-proof.

        """

        self._iq_response_map.add_listener(
            (from_, id_),
            StanzaErrorAwareListener(
                callbacks.FutureListener(fut)
            )
        )
        self._logger.debug("iq response future registered: from=%r, id=%r",
                           from_, id_)

    def unregister_iq_response(self, from_, id_):
        """
        Unregister a registered callback or future for the IQ response
        identified by `from_` and `id_`. See
        :meth:`register_iq_response_future` or
        :meth:`register_iq_response_callback` for details on the arguments
        meanings and how to register futures and callbacks respectively.

        .. note::

           Futures will automatically be unregistered when they are cancelled.

        """
        self._iq_response_map.remove_listener((from_, id_))
        self._logger.debug("iq response unregistered: from=%r, id=%r",
                           from_, id_)

    def register_iq_request_coro(self, type_, payload_cls, coro):
        """
        Register a coroutine `coro` to IQ requests of type `type_` which have a
        payload of the given `payload_cls` class.

        Whenever a matching IQ stanza is received, the coroutine is started
        with the stanza as its only argument. The coroutine must return a valid
        value for the :attr:`.stanza.IQ.payload` attribute. The value will be
        set as the payload attribute value of an IQ response (with type
        ``"result"``) which is generated and sent by the stream.

        If the coroutine raises an exception, it will be converted to a
        :class:`~.stanza.Error` object. That error object is then used as
        payload for an IQ response (with type ``"error"``) which is generated
        and sent by the stream.

        If the exception is a subclass of :class:`aioxmpp.errors.XMPPError`, it
        is converted to an :class:`~.stanza.Error` instance
        directly. Otherwise, it is wrapped in a
        :class:`aioxmpp.errors.XMPPCancelError` with ``undefined-condition``.

        If there is already a coroutine registered for the given (`type_`,
        `payload_cls`) pair, :class:`ValueError` is raised.
        """
        key = type_, payload_cls

        if key in self._iq_request_map:
            raise ValueError("only one listener is allowed per tag")

        self._iq_request_map[key] = coro
        self._logger.debug(
            "iq request coroutine registered: type=%r, payload=%r",
            type_, payload_cls)

    def unregister_iq_request_coro(self, type_, payload_cls):
        """
        Unregister a coroutine previously registered with
        :meth:`register_iq_request_coro`. The match is solely made using the
        `type_` and `payload_cls` arguments, which have the same meaning as in
        :meth:`register_iq_request_coro`.

        This raises :class:`KeyError` if no coroutine has previously been
        registered for the `type_` and `payload_cls`.
        """
        del self._iq_request_map[type_, payload_cls]
        self._logger.debug(
            "iq request coroutine unregistered: type=%r, payload=%r",
            type_, payload_cls)

    def register_message_callback(self, type_, from_, cb):
        """
        Register a callback function `cb` to be called whenever a message
        stanza of the given `type_` from the given
        :class:`~aioxmpp.structs.JID` `from_` arrives.

        Both `type_` and `from_` can be :data:`None`, each, to indicate a
        wildcard match.

        More specific callbacks win over less specific callbacks, and the
        match on the `from_` address takes precedence over the match on the
        `type_`.

        To be explicit, the order in which callbacks are searched for a given
        ``type`` and ``from_`` of a stanza is:

        * ``type``, ``from_``
        * ``type``, ``from_.bare()``
        * ``None``, ``from_``
        * ``None``, ``from_.bare()``
        * ``type``, ``None``
        * ``None``, ``None``
        """
        self._message_map[type_, from_] = cb
        self._logger.debug(
            "message callback registered: type=%r, from=%r",
            type_, from_)

    def unregister_message_callback(self, type_, from_):
        """
        Unregister a callback previously registered with
        :meth:`register_message_callback`. `type_` and `from_` have the same
        semantics as in :meth:`register_message_callback`.

        Attempting to unregister a `type_`, `from_` tuple for which no handler
        has been registered results in a :class:`KeyError`.
        """
        del self._message_map[type_, from_]
        self._logger.debug(
            "message callback unregistered: type=%r, from=%r",
            type_, from_)

    def register_presence_callback(self, type_, from_, cb):
        """
        Register a callback function `cb` to be called whenever a presence
        stanza of the given `type_` arrives from the given
        :class:`~aioxmpp.structs.JID`.

        `from_` may be :data:`None` to indicate a wildcard. Like with
        :meth:`register_message_callback`, more specific callbacks win over
        less specific callbacks.

        .. note::

           A `type_` of :data:`None` is a valid value for
           :class:`aioxmpp.stanza.Presence` stanzas and is **not** a wildcard
           here.

        """
        self._presence_map[type_, from_] = cb
        self._logger.debug(
            "presence callback registered: type=%r, from=%r",
            type_, from_)

    def unregister_presence_callback(self, type_, from_):
        """
        Unregister a callback previously registered with
        :meth:`register_presence_callback`. `type_` and `from_` have the same
        semantics as in :meth:`register_presence_callback`.

        Attempting to unregister a `type_`, `from_` tuple for which no handler
        has been registered results in a :class:`KeyError`.
        """
        del self._presence_map[type_, from_]
        self._logger.debug(
            "presence callback unregistered: type=%r, from=%r",
            type_, from_)

    def _start_prepare(self, xmlstream, receiver):
        self._xmlstream_failure_token = xmlstream.on_closing.connect(
            self._xmlstream_failed
        )

        xmlstream.stanza_parser.add_class(stanza.IQ, receiver)
        xmlstream.stanza_parser.add_class(stanza.Message, receiver)
        xmlstream.stanza_parser.add_class(stanza.Presence, receiver)
        xmlstream.error_handler = self.recv_errorneous_stanza

        if self._sm_enabled:
            self._logger.debug("using SM")
            xmlstream.stanza_parser.add_class(nonza.SMAcknowledgement,
                                              receiver)
            xmlstream.stanza_parser.add_class(nonza.SMRequest,
                                              receiver)

        self._xmlstream_exception = None

    def _start_rollback(self, xmlstream):
        xmlstream.error_handler = None
        xmlstream.stanza_parser.remove_class(stanza.Presence)
        xmlstream.stanza_parser.remove_class(stanza.Message)
        xmlstream.stanza_parser.remove_class(stanza.IQ)
        if self._sm_enabled:
            xmlstream.stanza_parser.remove_class(
                nonza.SMRequest)
            xmlstream.stanza_parser.remove_class(
                nonza.SMAcknowledgement)

        xmlstream.on_closing.disconnect(
            self._xmlstream_failure_token
        )

    def _start_commit(self, xmlstream):
        if not self._established:
            self.on_stream_established()
            self._established = True

        self._task = asyncio.async(self._run(xmlstream), loop=self._loop)
        self._task.add_done_callback(self._done_handler)
        self._logger.debug("broker task started as %r", self._task)

        self._next_ping_event_at = datetime.utcnow() + self.ping_interval
        self._next_ping_event_type = PingEventType.SEND_OPPORTUNISTIC
        self._ping_send_opportunistic = self._sm_enabled

    def start(self, xmlstream):
        """
        Start or resume the stanza stream on the given
        :class:`aioxmpp.protocol.XMLStream` `xmlstream`.

        This starts the main broker task, registers stanza classes at the
        `xmlstream` and reconfigures the ping state.
        """

        if self.running:
            raise RuntimeError("already started")

        self._start_prepare(xmlstream, self.recv_stanza)
        self._start_commit(xmlstream)

    def stop(self):
        """
        Send a signal to the main broker task to terminate. You have to check
        :attr:`running` and possibly wait for it to become :data:`False` ---
        the task takes at least one loop through the event loop to terminate.

        It is guarenteed that the task will not attempt to send stanzas over
        the existing `xmlstream` after a call to :meth:`stop` has been made.

        It is legal to call :meth:`stop` even if the task is already
        stopped. It is a no-op in that case.
        """
        if not self.running:
            return
        self._logger.debug("sending stop signal to task")
        self._task.cancel()

    @asyncio.coroutine
    def wait_stop(self):
        """
        Stop the stream and wait for it to stop.

        See :meth:`stop` for the general stopping conditions. You can assume
        that :meth:`stop` is the first thing this coroutine calls.
        """
        if not self.running:
            return
        self.stop()
        try:
            yield from self._task
        except asyncio.CancelledError:
            pass

    @asyncio.coroutine
    def close(self):
        """
        Close the stream and the underlying XML stream (if any is connected).

        This calls :meth:`wait_stop` and cleans up any Stream Management state,
        if no error occurs. If an error occurs while the stream stops, that
        error is re-raised and the stream management state is not cleared,
        unless resumption is disabled.
        """
        if not self.running:
            return
        yield from self._xmlstream.close_and_wait()  # does not raise
        yield from self.wait_stop()

        if self._xmlstream_exception is not None:
            exc = self._xmlstream_exception
            if self.sm_enabled:
                if self.sm_resumable:
                    raise exc
                self._destroy_stream_state(exc)
                self.stop_sm()
                return
        else:
            self._destroy_stream_state(ConnectionError("close() called"))
            if self.sm_enabled:
                self.stop_sm()

    @asyncio.coroutine
    def _run(self, xmlstream):
        self._xmlstream = xmlstream
        active_fut = asyncio.async(self._active_queue.get(),
                                   loop=self._loop)
        incoming_fut = asyncio.async(self._incoming_queue.get(),
                                     loop=self._loop)

        try:
            while True:
                timeout = self._next_ping_event_at - datetime.utcnow()
                if timeout.total_seconds() < 0:
                    timeout = timedelta()

                done, pending = yield from asyncio.wait(
                    [
                        active_fut,
                        incoming_fut,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout.total_seconds())

                with (yield from self._broker_lock):
                    if active_fut in done:
                        self._process_outgoing(xmlstream, active_fut.result())
                        active_fut = asyncio.async(
                            self._active_queue.get(),
                            loop=self._loop)

                    if incoming_fut in done:
                        self._process_incoming(xmlstream,
                                               incoming_fut.result())
                        incoming_fut = asyncio.async(
                            self._incoming_queue.get(),
                            loop=self._loop)

                    timeout = self._next_ping_event_at - datetime.utcnow()
                    if timeout.total_seconds() <= 0:
                        self._process_ping_event(xmlstream)

        finally:
            # make sure we rescue any stanzas which possibly have already been
            # caught by the calls to get()
            self._logger.debug("task terminating, rescuing stanzas and "
                               "clearing handlers")
            if incoming_fut.done() and not incoming_fut.exception():
                self._incoming_queue.putleft_nowait(incoming_fut.result())
            else:
                incoming_fut.cancel()

            if active_fut.done() and not active_fut.exception():
                self._active_queue.putleft_nowait(active_fut.result())
            else:
                active_fut.cancel()

            # we also lock shutdown, because the main race is among the SM
            # variables
            with (yield from self._broker_lock):
                if not self.sm_enabled or not self.sm_resumable:
                    if self.sm_enabled:
                        self._stop_sm()
                    self._destroy_stream_state(
                        self._xmlstream_exception or
                        ConnectionError("stream terminating"))

                self._start_rollback(xmlstream)

            if self._xmlstream_exception:
                raise self._xmlstream_exception

    def recv_stanza(self, stanza):
        """
        Inject a `stanza` into the incoming queue.
        """
        self._incoming_queue.put_nowait((stanza, None))

    def recv_errorneous_stanza(self, partial_obj, exc):
        self._incoming_queue.put_nowait((partial_obj, exc))

    def enqueue_stanza(self, stanza, **kwargs):
        """
        Enqueue a `stanza` to be sent. Return a :class:`StanzaToken` to track
        the stanza. The `kwargs` are passed to the :class:`StanzaToken`
        constructor.

        This method calls :meth:`~.stanza.StanzaBase.autoset_id` on the stanza
        automatically.
        """

        stanza.validate()
        token = StanzaToken(stanza, **kwargs)
        self._active_queue.put_nowait(token)
        stanza.autoset_id()
        self._logger.debug("enqueued stanza %r with token %r",
                           stanza, token)
        return token

    @property
    def running(self):
        """
        :data:`True` if the broker task is currently running, and :data:`False`
        otherwise.
        """
        return self._task is not None and not self._task.done()

    @asyncio.coroutine
    def start_sm(self, request_resumption=True):
        """
        Start stream management (version 3). This negotiates stream management
        with the server.

        If the server rejects the attempt to enable stream management, a
        :class:`.errors.StreamNegotiationFailure` is raised. The stream is
        still running in that case.

        .. warning::

           This method cannot and does not check whether the server advertised
           support for stream management. Attempting to negotiate stream
           management without server support might lead to termination of the
           stream.

        If an XML stream error occurs during the negotiation, the result
        depends on a few factors. In any case, the stream is not running
        afterwards. If the :class:`SMEnabled` response was not received before
        the XML stream died, SM is also disabled and the exception which caused
        the stream to die is re-raised (this is due to the implementation of
        :func:`~.protocol.send_and_wait_for`). If the :class:`SMEnabled`
        response was received and annonuced support for resumption, SM is
        enabled. Otherwise, it is disabled. No exception is raised if
        :class:`SMEnabled` was received, as this method has no way to determine
        that the stream failed.

        If negotiation succeeds, this coroutine initializes a new stream
        management session. The stream management state attributes become
        available and :attr:`sm_enabled` becomes :data:`True`.
        """
        if not self.running:
            raise RuntimeError("cannot start Stream Management while"
                               " StanzaStream is not running")
        if self.sm_enabled:
            raise RuntimeError("Stream Management already enabled")

        with (yield from self._broker_lock):
            response = yield from protocol.send_and_wait_for(
                self._xmlstream,
                [
                    nonza.SMEnable(resume=bool(request_resumption)),
                ],
                [
                    nonza.SMEnabled,
                    nonza.SMFailed
                ]
            )

            if isinstance(response, nonza.SMFailed):
                raise errors.StreamNegotiationFailure(
                    "Server rejected SM request")

            self._sm_outbound_base = 0
            self._sm_inbound_ctr = 0
            self._sm_unacked_list = []
            self._sm_enabled = True
            self._sm_id = response.id_
            self._sm_resumable = response.resume
            self._sm_max = response.max_
            self._sm_location = response.location
            self._ping_send_opportunistic = True

            self._logger.info("SM started: resumable=%s, stream id=%r",
                              self._sm_resumable,
                              self._sm_id)

            # if not self._xmlstream:
            #     # stream died in the meantime...
            #     if self._xmlstream_exception:
            #         raise self._xmlstream_exception

            self._xmlstream.stanza_parser.add_class(
                nonza.SMRequest,
                self.recv_stanza)
            self._xmlstream.stanza_parser.add_class(
                nonza.SMAcknowledgement,
                self.recv_stanza)

    @property
    def sm_enabled(self):
        """
        :data:`True` if stream management is currently enabled on the stream,
        :data:`False` otherwise.
        """

        return self._sm_enabled

    @property
    def sm_outbound_base(self):
        """
        The last value of the remote stanza counter.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_outbound_base

    @property
    def sm_inbound_ctr(self):
        """
        The current value of the inbound stanza counter.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_inbound_ctr

    @property
    def sm_unacked_list(self):
        """
        A **copy** of the list of stanza tokens which have not yet been acked
        by the remote party.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

           Accessing this attribute is expensive, as the list is copied. In
           general, access to this attribute should not be neccessary at all.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_unacked_list[:]

    @property
    def sm_max(self):
        """
        The value of the ``max`` attribute of the
        :class:`~.nonza.SMEnabled` response from the server.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_max

    @property
    def sm_location(self):
        """
        The value of the ``location`` attribute of the
        :class:`~.nonza.SMEnabled` response from the server.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_location

    @property
    def sm_id(self):
        """
        The value of the ``id`` attribute of the
        :class:`~.nonza.SMEnabled` response from the server.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_id

    @property
    def sm_resumable(self):
        """
        The value of the ``resume`` attribute of the
        :class:`~.nonza.SMEnabled` response from the server.

        .. note::

           Accessing this attribute when :attr:`sm_enabled` is :data:`False`
           raises :class:`RuntimeError`.

        """

        if not self.sm_enabled:
            raise RuntimeError("Stream Management not enabled")
        return self._sm_resumable

    def _resume_sm(self, remote_ctr):
        """
        Version of :meth:`resume_sm` which can be used during slow start.
        """
        self._logger.info("resuming SM stream with remote_ctr=%d", remote_ctr)
        # remove any acked stanzas
        self.sm_ack(remote_ctr)
        # reinsert the remaining stanzas
        for token in self._sm_unacked_list:
            self._active_queue.putleft_nowait(token)
        self._sm_unacked_list.clear()

    @asyncio.coroutine
    def resume_sm(self, xmlstream):
        """
        Resume an SM-enabled stream using the given `xmlstream`.

        If the server rejects the attempt to resume stream management, a
        :class:`.errors.StreamNegotiationFailure` is raised. The stream is then
        in stopped state and stream management has been stopped.

        .. warning::

           This method cannot and does not check whether the server advertised
           support for stream management. Attempting to negotiate stream
           management without server support might lead to termination of the
           stream.

        If the XML stream dies at any point during the negotiation, the SM
        state is left unchanged. If no response has been received yet, the
        exception which caused the stream to die is re-raised. The state of the
        stream depends on whether the main task already noticed the dead
        stream.

        If negotiation succeeds, this coroutine resumes the stream management
        session and initiates the retransmission of any unacked stanzas. The
        stream is then in running state.
        """

        if self.running:
            raise RuntimeError("Cannot resume Stream Management while"
                               " StanzaStream is running")

        self._start_prepare(xmlstream, self.recv_stanza)
        try:
            response = yield from protocol.send_and_wait_for(
                xmlstream,
                [
                    nonza.SMResume(previd=self.sm_id,
                                         counter=self._sm_inbound_ctr)
                ],
                [
                    nonza.SMResumed,
                    nonza.SMFailed
                ]
            )

            if isinstance(response, nonza.SMFailed):
                xmlstream.stanza_parser.remove_class(
                    nonza.SMRequest)
                xmlstream.stanza_parser.remove_class(
                    nonza.SMAcknowledgement)
                self.stop_sm()
                raise errors.StreamNegotiationFailure(
                    "Server rejected SM resumption")

            self._resume_sm(response.counter)
        except:
            self._start_rollback(xmlstream)
            raise
        self._start_commit(xmlstream)

    def _stop_sm(self):
        """
        Version of :meth:`stop_sm` which can be called during startup.
        """
        if not self.sm_enabled:
            raise RuntimeError("Stream Management is not enabled")

        self._logger.info("stopping SM stream")
        self._sm_enabled = False
        del self._sm_outbound_base
        del self._sm_inbound_ctr
        for token in self._sm_unacked_list:
            token._set_state(StanzaState.SENT_WITHOUT_SM)
        del self._sm_unacked_list

        self._destroy_stream_state(ConnectionError(
            "stream management disabled"
        ))

    def stop_sm(self):
        """
        Disable stream management on the stream.

        Attempting to call this method while the stream is running or without
        stream management enabled results in a :class:`RuntimeError`.

        Any sent stanzas which have not been acked by the remote yet are put
        into :attr:`StanzaState.SENT_WITHOUT_SM` state.
        """
        if self.running:
            raise RuntimeError("Cannot stop Stream Management while"
                               " StanzaStream is running")
        return self._stop_sm()

    def sm_ack(self, remote_ctr):
        """
        Process the remote stanza counter `remote_ctr`. Any acked stanzas are
        dropped from :attr:`sm_unacked_list` and put into
        :attr:`StanzaState.ACKED` state and the counters are increased
        accordingly.

        Attempting to call this without Stream Management enabled results in a
        :class:`RuntimeError`.
        """

        if not self._sm_enabled:
            raise RuntimeError("Stream Management is not enabled")

        self._logger.debug("sm_ack(%d)", remote_ctr)
        to_drop = remote_ctr - self._sm_outbound_base
        if to_drop < 0:
            self._logger.warning(
                "remote stanza counter is *less* than before "
                "(outbound_base=%d, remote_ctr=%d)",
                self._sm_outbound_base,
                remote_ctr)
            return

        acked = self._sm_unacked_list[:to_drop]
        del self._sm_unacked_list[:to_drop]
        self._sm_outbound_base = remote_ctr

        if acked:
            self._logger.debug("%d stanzas acked by remote", len(acked))
        for token in acked:
            token._set_state(StanzaState.ACKED)

    @asyncio.coroutine
    def send_iq_and_wait_for_reply(self, iq, *,
                                   timeout=None):
        """
        Send an IQ stanza `iq` and wait for the response. If `timeout` is not
        :data:`None`, it must be the time in seconds for which to wait for a
        response.

        If the response is a ``"result"`` IQ, the value of the
        :attr:`~aioxmpp.stanza.IQ.payload` attribute is returned. Otherwise,
        the exception generated from the :attr:`~aioxmpp.stanza.IQ.error`
        attribute is raised.

        .. seealso::

           :meth:`register_iq_request_future` for other cases raising
           exceptions.

        """
        iq.autoset_id()
        fut = asyncio.Future(loop=self._loop)
        self.register_iq_response_future(
            iq.to,
            iq.id_,
            fut)
        self.enqueue_stanza(iq)
        if not timeout:
            reply = yield from fut
        else:
            reply = yield from asyncio.wait_for(
                fut, timeout=timeout,
                loop=self._loop)
        return reply.payload
