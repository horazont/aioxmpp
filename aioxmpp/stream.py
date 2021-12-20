########################################################################
# File name: stream.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.stream` --- Stanza stream
########################################

The stanza stream is the layer of abstraction above the XML stream. It deals
with sending and receiving stream-level elements, mainly stanzas. It also
handles stream liveness and stream management.

It provides ways to track stanzas on their way to the remote, as far as that is
possible.

.. _aioxmpp.stream.General Information:

General information
===================

.. _aioxmpp.stream.General Information.Timeouts:

Timeouts / Stream Aliveness checks
----------------------------------

The :class:`StanzaStream` relies on the :class:`XMLStream` dead time aliveness
monitoring (see also :attr:`~.XMLStream.deadtime_soft_limit`) to detect a
broken stream.

The limits can be configured with the two attributes
:attr:`~.StanzaStream.soft_timeout` and :attr:`~.StanzaStream.round_trip_time`.
When :attr:`~.StanzaStream.soft_timeout` elapses after the last bit of data
received from the server, the :class:`StanzaStream` issues a ping. The server
then has one :attr:`~.StanzaStream.round_trip_time` worth of time to answer.
If this does not happen, the :class:`XMLStream` will be terminated by the
aliveness monitor and normal handling of a broken connection takes over.

.. _aioxmpp.stream.General Information.Filters:

Stanza Filters
--------------

Stanza filters allow to hook into the stanza sending/reception pipeline
after/before the application sees the stanza.

Inbound stanza filters
~~~~~~~~~~~~~~~~~~~~~~

Inbound stanza filters allow to hook into the stanza processing by replacing,
modifying or otherwise processing stanza contents *before* the usual handlers
for that stanza are invoked. With inbound stanza filters, there are no
restrictions as to what processing may take place on a stanza, as no one but
the stream may have references to its contents.

.. warning::

    Raising an exception from within a stanza filter kills the stream.

Note that if a filter function drops an incoming stanza (by returning
:data:`None`), it **must** ensure that the client still behaves RFC
compliant. The inbound stanza filters are found here:

* :attr:`~.StanzaStream.service_inbound_message_filter`
* :attr:`~.StanzaStream.service_inbound_presence_filter`
* :attr:`~.StanzaStream.app_inbound_message_filter`
* :attr:`~.StanzaStream.app_inbound_presence_filter`

Outbound stanza filters
~~~~~~~~~~~~~~~~~~~~~~~

Outbound stanza filters work similar to inbound stanza filters, but due to
their location in the processing chain and possible interactions with senders
of stanzas, there are some things to consider:

* Per convention, a outbound stanza filter **must not** modify any child
  elements which are already present in the stanza when it receives the
  stanza.

  It may however add new child elements or remove existing child elements,
  as well as copying and *then* modifying existing child elements.

* If the stanza filter replaces the stanza, it is responsible for making
  sure that the new stanza has appropriate
  :attr:`~.stanza.StanzaBase.from_`, :attr:`~.stanza.StanzaBase.to` and
  :attr:`~.stanza.StanzaBase.id` values. There are no checks to enforce
  this, because error handling at this point is peculiar. The stanzas will
  be sent as-is.

* Similar to inbound filters, it is the responsibility of the filters that
  if stanzas are dropped, the client still behaves RFC-compliant.

Now that you have been warned, here are the attributes for accessing the
outbound filter chains. These otherwise work exactly like their inbound
counterparts, but service filters run *after* application filters on
outbound processing.

* :attr:`~.StanzaStream.service_outbound_message_filter`
* :attr:`~.StanzaStream.service_outbound_presence_filter`
* :attr:`~.StanzaStream.app_outbound_message_filter`
* :attr:`~.StanzaStream.app_outbound_presence_filter`

When to use stanza filters?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In general, applications will rarely need them. However, services may make
profitable use of them, and it is a convenient way for them to inspect or
modify incoming or outgoing stanzas before any normally registered handler
processes them.

In general, whenever you do something which *supplements* the use of the stanza
with respect to the RFC but does not fulfill the original intent of the stanza,
it is advisable to use a filter instead of a callback on the actual stanza.

Vice versa, if you were to develop a service which manages presence
subscriptions, it would be more correct to use
:meth:`register_presence_callback`; this prevents other services which try
to do the same from conflicting with you. You would then provide callbacks
to the application to let it learn about presence subscriptions.

Stanza Stream class
===================

This section features the complete documentation of the (rather important and
complex) :class:`StanzaStream`. Some more general information has been moved to
the previous section (:ref:`aioxmpp.stream.General Information`) to make it
easier to read and find.

.. autoclass:: StanzaStream

Context managers
================

The following context managers can be used together with :class:`StanzaStream`
instances and the filters available on them.

.. autofunction:: iq_handler

.. autofunction:: message_handler

.. autofunction:: presence_handler

.. autofunction:: stanza_filter

Low-level stanza tracking
=========================

The following classes are used to track stanzas in the XML stream to the
server. This is independent of things like :xep:`Message Delivery Receipts
<0184>` (for which services are provided at :mod:`aioxmpp.tracking`); it
only provides tracking to the remote server and even that only if stream
management is used. Otherwise, it only provides tracking in the :mod:`aioxmpp`
internal queues.

.. autoclass:: StanzaToken

.. autoclass:: StanzaState

Filters
=======

The service-level filters used by the :class:`StanzaStream` use
:class:`~.callbacks.Filter`. The application-level filters are using the
following class:

.. autoclass:: AppFilter

Exceptions
==========

.. autoclass:: DestructionRequested

"""

import asyncio
import contextlib
import functools
import logging
import warnings

from datetime import timedelta
from enum import Enum

from . import (
    stanza,
    stanza as stanza_,
    errors,
    custom_queue,
    nonza,
    callbacks,
    protocol,
    structs,
    ping,
)


class AppFilter(callbacks.Filter):
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


class DestructionRequested(ConnectionError):
    """
    Subclass of :class:`ConnectionError` indicating that the destruction of the
    stream was requested by the user, directly or indirectly.
    """


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
       and has been acked by the remote.

       This is a final state.

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

    .. attribute:: DISCONNECTED

       The stream has been stopped (without SM) or closed before the stanza was
       sent.

       This is a final state.

    .. attribute:: FAILED

       It was attempted to send the stanza, but it failed to serialise to
       valid XML or another non-fatal transport error occurred.

       This is a final state.

       .. versionadded:: 0.9

    """
    ACTIVE = 0
    SENT = 1
    ACKED = 2
    SENT_WITHOUT_SM = 3
    ABORTED = 4
    DROPPED = 5
    DISCONNECTED = 6
    FAILED = 7


class StanzaErrorAwareListener:
    def __init__(self, forward_to):
        self._forward_to = forward_to

    def data(self, stanza_obj):
        if stanza_obj.type_.is_error:
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

    .. versionadded:: 0.8

       Stanza tokens are :term:`awaitable`.

    .. describe:: await token
    .. describe:: yield from token

       Wait until the stanza is either sent or failed to sent.

       .. warning::

          This only works with Python 3.5 or newer.

       :raises ConnectionError: if the stanza enters
                                :attr:`~.StanzaState.DISCONNECTED` state.
       :raises RuntimeError: if the stanza enters :attr:`~.StanzaState.ABORTED`
                             or :attr:`~.StanzaState.DROPPED` state.
       :raises Exception: re-raised if the stanza token fails to serialise or
                          another transient transport problem occurs.
       :return: :data:`None`

       If a coroutine awaiting a token is cancelled, the token is aborted. Use
       :func:`asyncio.shield` to prevent this.

       .. warning::

          This is no guarantee that the recipient received the stanza. Without
          stream management, it can not even guaranteed that the server has
          seen the stanza.

          This is primarily useful as a synchronisation primitive between the
          sending of a stanza and another stream operation, such as closing the
          stream.

    .. note::

       Exceptions sent to the stanza token (when it enters
       :attr:`StanzaState.FAILED`) are only available by awaiting the token,
       not via the callback.

    .. autoattribute:: state

    .. automethod:: abort
    """
    __slots__ = ("stanza", "_state", "on_state_change", "_sent_future",
                 "_state_exception")

    def __init__(self, stanza, *, on_state_change=None):
        self.stanza = stanza
        self._state = StanzaState.ACTIVE
        self._state_exception = None
        self._sent_future = None
        self.on_state_change = on_state_change

    @property
    def state(self):
        """
        The current :class:`StanzaState` of the token. Tokens are created with
        :attr:`StanzaState.ACTIVE`.
        """

        return self._state

    @property
    def future(self):
        if self._sent_future is None:
            self._sent_future = asyncio.Future()
            self._update_future()
        return self._sent_future

    def _update_future(self):
        if self._sent_future.done():
            return

        if self._state == StanzaState.DISCONNECTED:
            self._sent_future.set_exception(ConnectionError("disconnected"))
        elif self._state == StanzaState.DROPPED:
            self._sent_future.set_exception(
                RuntimeError("stanza dropped by filter")
            )
        elif self._state == StanzaState.ABORTED:
            self._sent_future.set_exception(RuntimeError("stanza aborted"))
        elif self._state == StanzaState.FAILED:
            self._sent_future.set_exception(
                self._state_exception or
                ValueError("failed to send stanza for unknown local reasons")
            )
        elif (self._state == StanzaState.SENT_WITHOUT_SM or
                  self._state == StanzaState.ACKED):
            self._sent_future.set_result(None)

    def _set_state(self, new_state, exception=None):
        self._state = new_state
        self._state_exception = exception
        if self.on_state_change is not None:
            self.on_state_change(self, new_state)

        if self._sent_future is not None:
            self._update_future()

    def abort(self):
        """
        Abort the stanza. Attempting to call this when the stanza is in any
        non-:class:`~StanzaState.ACTIVE`, non-:class:`~StanzaState.ABORTED`
        state results in a :class:`RuntimeError`.

        When a stanza is aborted, it will reside in the active queue of the
        stream, not will be sent and instead discarded silently.
        """
        if (self._state != StanzaState.ACTIVE and
                self._state != StanzaState.ABORTED):
            raise RuntimeError("cannot abort stanza (already sent)")
        self._set_state(StanzaState.ABORTED)

    def __repr__(self):
        return "<StanzaToken id=0x{:016x}>".format(id(self))

    def __await__(self):
        try:
            yield from asyncio.shield(self.future)
        except asyncio.CancelledError:
            if self._state == StanzaState.ACTIVE:
                self.abort()
            raise

    __iter__ = __await__


class StanzaStream:
    """
    A stanza stream. This is the next layer of abstraction above the XMPP XML
    stream, which mostly deals with stanzas (but also with certain other
    stream-level elements, such as :xep:`0198` Stream Management Request/Acks).

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

    .. versionchanged:: 0.10

        Ping handling was reworked.

    Starting/Stopping the stream:

    .. automethod:: start

    .. automethod:: stop

    .. automethod:: wait_stop

    .. automethod:: close

    .. autoattribute:: running

    .. automethod:: flush_incoming

    Timeout configuration (see
    :ref:`aioxmpp.stream.General Information.Timeouts`):

    .. autoattribute:: round_trip_time

    .. autoattribute:: soft_timeout

    Sending stanzas:

    .. deprecated:: 0.10

        Sending stanzas directly on the stream is deprecated. The methods
        have been moved to the client:

        .. autosummary::

            aioxmpp.Client.send
            aioxmpp.Client.enqueue

    .. automethod:: send

    .. automethod:: enqueue

    .. method:: enqueue_stanza

       Alias of :meth:`enqueue`.

       .. deprecated:: 0.8

          This alias is deprecated and will be removed in 1.0.

    .. automethod:: send_and_wait_for_sent

    .. automethod:: send_iq_and_wait_for_reply

    Receiving stanzas:

    .. automethod:: register_iq_request_handler

    .. automethod:: unregister_iq_request_handler

    .. automethod:: register_message_callback

    .. automethod:: unregister_message_callback

    .. automethod:: register_presence_callback

    .. automethod:: unregister_presence_callback

    Rarely used registries / deprecated aliases:

    .. automethod:: register_iq_request_coro

    .. automethod:: unregister_iq_request_coro

    .. automethod:: register_iq_response_future

    .. automethod:: register_iq_response_callback

    .. automethod:: unregister_iq_response

    Inbound Stanza Filters (see
    :ref:`aioxmpp.stream.General Information.Filters`):

    .. attribute:: app_inbound_presence_filter

       This is a :class:`AppFilter` based filter chain on inbound presence
       stanzas. It can be used to attach application-specific filters.

    .. attribute:: service_inbound_presence_filter

       This is another filter chain for inbound presence stanzas. It runs
       *before* the :attr:`app_inbound_presence_filter` chain and all functions
       registered there must have :class:`service.Service` *classes* as `order`
       value (see :meth:`Filter.register`).

       This filter chain is intended to be used by library services, such as a
       :xep:`115` implementation which may start a :xep:`30` lookup at the
       target entity to resolve the capability hash or prime the :xep:`30`
       cache with the service information obtained by interpreting the
       :xep:`115` hash value.

    .. attribute:: app_inbound_message_filter

       This is a :class:`AppFilter` based filter chain on inbound message
       stanzas. It can be used to attach application-specific filters.

    .. attribute:: service_inbound_message_filter

       This is the analogon of :attr:`service_inbound_presence_filter` for
       :attr:`app_inbound_message_filter`.

    Outbound Stanza Filters (see
    :ref:`aioxmpp.stream.General Information.Filters`):

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

       Emits when the stream has failed, i.e. entered stopped state without
       request by the user.

       :param exc: The exception which caused the stream to fail.
       :type exc: :class:`Exception`

       A failure occurs whenever the main task of the :class:`StanzaStream`
       (the one started by :meth:`start`) terminates with an exception.

       Examples are :class:`ConnectionError` as raised upon a ping timeout and
       any exceptions which may be raised by the
       :meth:`aioxmpp.protocol.XMLStream.send_xso` method.

       Before :meth:`on_failure` is emitted, the :class:`~.protocol.XMLStream`
       is :meth:`~.protocol.XMLStream.abort`\\ -ed if SM is enabled and
       :meth:`~.protocol.XMLStream.close`\\ -ed if SM is not enabled.

       .. versionchanged:: 0.6

          The closing behaviour was added.

    .. signal:: on_stream_destroyed(reason)

       The stream has been stopped in a manner which means that all state must
       be discarded.

       :param reason: The exception which caused the stream to be destroyed.
       :type reason: :class:`Exception`

       When this signal is emitted, others have or will most likely see
       unavailable presence from the XMPP resource associated with the stream,
       and stanzas sent in the mean time are not guaranteed to be received.

       `reason` may be a :class:`DestructionRequested` instance to indicate
       that the destruction was requested by the user, in some way.

       There is no guarantee (it is not even likely) that it is possible to
       send stanzas over the stream at the time this signal is emitted.

       .. versionchanged:: 0.8

          The `reason` argument was added.

    .. signal:: on_stream_established()

       When a stream is newly established, this signal is fired. This happens
       whenever a non-SM stream is started and whenever a stream which
       previously had SM disabled is started with SM enabled.

    .. signal:: on_message_received(stanza)

        Emits when a :class:`aioxmpp.Message` stanza has been received.

        :param stanza: The received stanza.
        :type stanza: :class:`aioxmpp.Message`

        .. seealso::

            :class:`aioxmpp.dispatcher.SimpleMessageDispatcher`
                for a service which allows to register callbacks for messages
                based on the sender and type of the message.

        .. versionadded:: 0.9

    .. signal:: on_presence_received(stanza)

        Emits when a :class:`aioxmpp.Presence` stanza has been received.

        :param stanza: The received stanza.
        :type stanza: :class:`aioxmpp.Presence`

        .. seealso::

            :class:`aioxmpp.dispatcher.SimplePresenceDispatcher`
                for a service which allows to register callbacks for presences
                based on the sender and type of the message.

        .. versionadded:: 0.9

    """

    _ALLOW_ENUM_COERCION = True

    on_failure = callbacks.Signal()
    on_stream_destroyed = callbacks.Signal()
    on_stream_established = callbacks.Signal()

    on_message_received = callbacks.Signal()
    on_presence_received = callbacks.Signal()

    def __init__(self,
                 local_jid=None,
                 *,
                 loop=None,
                 base_logger=logging.getLogger("aioxmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._logger = base_logger.getChild("StanzaStream")
        self._task = None

        self._xmlstream = None
        self._soft_timeout = timedelta(minutes=1)
        self._round_trip_time = timedelta(minutes=1)

        self._xxx_message_dispatcher = None
        self._xxx_presence_dispatcher = None

        self._local_jid = local_jid

        self._active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self._incoming_queue = custom_queue.AsyncDeque(loop=self._loop)

        self._iq_response_map = callbacks.TagDispatcher()
        self._iq_request_map = {}

        # list of running IQ request coroutines: used to cancel them when the
        # stream is destroyed
        self._iq_request_tasks = []

        self._xmlstream_exception = None

        self._established = False
        self._closed = False

        self._sm_enabled = False

        self._broker_lock = asyncio.Lock()

        self.app_inbound_presence_filter = AppFilter()
        self.service_inbound_presence_filter = callbacks.Filter()

        self.app_inbound_message_filter = AppFilter()
        self.service_inbound_message_filter = callbacks.Filter()

        self.app_outbound_presence_filter = AppFilter()
        self.service_outbound_presence_filter = callbacks.Filter()

        self.app_outbound_message_filter = AppFilter()
        self.service_outbound_message_filter = callbacks.Filter()

    @property
    def local_jid(self):
        """
        The `local_jid` argument to the constructor.

        .. warning::

           Changing this arbitrarily while the stream is running may have
           unintended side effects.

        """
        return self._local_jid

    @local_jid.setter
    def local_jid(self, value):
        self._local_jid = value

    @property
    def round_trip_time(self):
        """
        The maximum expected round-trip time as :class:`datetime.timedelta`.

        This is used to configure the maximum time between asking the server to
        send something and receiving something from the server in stream
        aliveness checks.

        This does **not** affect IQ requests or other stanzas.

        If set to :data:`None`, no application-level timeouts are used at all.
        This is not recommended since TCP timeouts are generally not sufficient
        for interactive applications.
        """
        return self._round_trip_time

    @round_trip_time.setter
    def round_trip_time(self, value):
        self._round_trip_time = value
        self._update_xmlstream_limits()

    @property
    def soft_timeout(self):
        """
        Soft timeout after which the server will be asked to send something
        if nothing has been received.

        If set to :data:`None`, no application-level timeouts are used at all.
        This is not recommended since TCP timeouts are generally not sufficient
        for interactive applications.
        """
        return self._soft_timeout

    @soft_timeout.setter
    def soft_timeout(self, value):
        self._soft_timeout = value
        self._update_xmlstream_limits()

    def _coerce_enum(self, value, enum_class):
        if not isinstance(value, enum_class):
            if self._ALLOW_ENUM_COERCION:
                warnings.warn(
                    "passing a non-enum value as type_ is deprecated and will "
                    "be invalid as of aioxmpp 1.0",
                    DeprecationWarning,
                    stacklevel=3)
                return enum_class(value)
            else:
                raise TypeError("type_ must be {}, got {!r}".format(
                    enum_class.__name__,
                    value
                ))
        return value

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
            try:
                if self._sm_enabled:
                    self._xmlstream.abort()
                else:
                    self._xmlstream.close()
            except Exception:
                pass
            self.on_failure(err)
            self._logger.debug("broker task failed", exc_info=True)

    def _xmlstream_failed(self, exc):
        self._xmlstream_exception = exc
        self.stop()

    def _destroy_stream_state(self, exc):
        """
        Destroy all state which does not make sense to keep after a disconnect
        (without stream management).
        """
        self._logger.debug("destroying stream state (exc=%r)", exc)
        self._iq_response_map.close_all(exc)
        for task in self._iq_request_tasks:
            # we don’t need to remove, that’s handled by their
            # add_done_callback
            task.cancel()
        while not self._active_queue.empty():
            token = self._active_queue.get_nowait()
            token._set_state(StanzaState.DISCONNECTED)

        if self._established:
            self.on_stream_destroyed(exc)
            self._established = False

    def _compose_undefined_condition(self, request):
        response = request.make_reply(type_=structs.IQType.ERROR)
        response.error = stanza.Error(
            condition=errors.ErrorCondition.UNDEFINED_CONDITION,
            type_=structs.ErrorType.CANCEL,
        )
        return response

    def _send_iq_reply(self, request, result):
        try:
            if isinstance(result, errors.XMPPError):
                response = request.make_reply(type_=structs.IQType.ERROR)
                response.error = stanza.Error.from_exception(result)
            else:
                response = request.make_reply(type_=structs.IQType.RESULT)
                response.payload = result
        except Exception:
            self._logger.exception("invalid payload for an IQ response")
            response = self._compose_undefined_condition(
                request
            )
        self._enqueue(response)

    def _iq_request_coro_done_remove_task(self, task):
        self._iq_request_tasks.remove(task)

    def _iq_request_coro_done_send_reply(self, request, task):
        """
        Called when an IQ request handler coroutine returns. `request` holds
        the IQ request which triggered the execution of the coroutine and
        `task` is the :class:`asyncio.Task` which tracks the running coroutine.

        Compose a response and send that response.
        """
        try:
            payload = task.result()
        except errors.XMPPError as err:
            self._send_iq_reply(request, err)
        except Exception:
            response = self._compose_undefined_condition(request)
            self._enqueue(response)
            self._logger.exception("IQ request coroutine failed")
        else:
            self._send_iq_reply(request, payload)

    def _iq_request_coro_done_check(self, task):
        try:
            task.result()
        except Exception:
            self._logger.exception("IQ request coroutine failed")

    def _process_incoming_iq(self, stanza_obj):
        """
        Process an incoming IQ stanza `stanza_obj`. Calls the response handler,
        spawns a request handler coroutine or drops the stanza while logging a
        warning if no handler can be found.
        """
        self._logger.debug("incoming iq: %r", stanza_obj)
        if stanza_obj.type_.is_response:
            # iq response
            self._logger.debug("iq is response")
            keys = [(stanza_obj.from_, stanza_obj.id_)]
            if self._local_jid is not None:
                # needed for some servers
                if keys[0][0] == self._local_jid:
                    keys.append((None, keys[0][1]))
                elif keys[0][0] is None:
                    keys.append((self._local_jid, keys[0][1]))
            for key in keys:
                try:
                    self._iq_response_map.unicast(key, stanza_obj)
                    self._logger.debug("iq response delivered to key %r", key)
                    break
                except KeyError:
                    pass
            else:
                self._logger.warning(
                    "unexpected IQ response: from=%r, id=%r",
                    *key)
        else:
            # iq request
            self._logger.debug("iq is request")
            key = (stanza_obj.type_, type(stanza_obj.payload))
            try:
                coro, with_send_reply = self._iq_request_map[key]
            except KeyError:
                self._logger.warning(
                    "unhandleable IQ request: from=%r, type_=%r, payload=%r",
                    stanza_obj.from_,
                    stanza_obj.type_,
                    stanza_obj.payload
                )
                response = stanza_obj.make_reply(type_=structs.IQType.ERROR)
                response.error = stanza.Error(
                    condition=errors.ErrorCondition.SERVICE_UNAVAILABLE,
                )
                self._enqueue(response)
                return

            args = [stanza_obj]
            if with_send_reply:

                def send_reply(result=None):
                    nonlocal task, stanza_obj, send_reply_callback
                    if task.done():
                        raise RuntimeError(
                            "send_reply called after the handler is done")
                    if task.remove_done_callback(send_reply_callback) == 0:
                        raise RuntimeError(
                            "send_reply called more than once")
                    task.add_done_callback(self._iq_request_coro_done_check)
                    self._send_iq_reply(stanza_obj, result)

                args.append(send_reply)

            try:
                awaitable = coro(*args)
            except Exception as exc:
                awaitable = asyncio.Future()
                awaitable.set_exception(exc)

            task = asyncio.ensure_future(awaitable)
            send_reply_callback = functools.partial(
                self._iq_request_coro_done_send_reply,
                stanza_obj)
            task.add_done_callback(self._iq_request_coro_done_remove_task)
            task.add_done_callback(send_reply_callback)
            self._iq_request_tasks.append(task)
            self._logger.debug("started task to handle request: %r", task)

    def _process_incoming_message(self, stanza_obj):
        """
        Process an incoming message stanza `stanza_obj`.
        """
        self._logger.debug("incoming message: %r", stanza_obj)

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

        self.on_message_received(stanza_obj)

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

        self.on_presence_received(stanza_obj)

    def _process_incoming_erroneous_stanza(self, stanza_obj, exc):
        self._logger.debug(
            "erroneous stanza received (may be incomplete): %r",
            stanza_obj,
            exc_info=exc,
        )

        try:
            type_ = stanza_obj.type_
        except AttributeError:
            # ugh, type is broken
            # exit early
            self._logger.debug(
                "stanza has broken type, cannot properly handle"
            )
            return

        if type_.is_response:
            try:
                from_ = stanza_obj.from_
                id_ = stanza_obj.id_
            except AttributeError:
                pass
            else:
                if isinstance(stanza_obj, stanza.IQ):
                    self._logger.debug(
                        "erroneous stanza can be forwarded to handlers as "
                        "error"
                    )

                    key = (from_, id_)
                    try:
                        self._iq_response_map.unicast_error(
                            key,
                            errors.ErroneousStanza(stanza_obj)
                        )
                    except KeyError:
                        pass
        elif isinstance(exc, stanza.UnknownIQPayload):
            reply = stanza_obj.make_error(error=stanza.Error(
                condition=errors.ErrorCondition.SERVICE_UNAVAILABLE
            ))
            self._enqueue(reply)
        elif isinstance(exc, stanza.PayloadParsingError):
            reply = stanza_obj.make_error(error=stanza.Error(
                condition=errors.ErrorCondition.BAD_REQUEST
            ))
            self._enqueue(reply)

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
            return
        elif isinstance(stanza_obj, nonza.SMRequest):
            self._logger.debug("received SM request: %r", stanza_obj)
            if not self._sm_enabled:
                self._logger.warning("received SM request, but SM not enabled")
                return
            response = nonza.SMAcknowledgement()
            response.counter = self._sm_inbound_ctr
            self._logger.debug("sending SM ack: %r", response)
            xmlstream.send_xso(response)
            return

        # raise if it is not a stanza
        if not isinstance(stanza_obj, stanza.StanzaBase):
            raise RuntimeError(
                "unexpected stanza class: {}".format(stanza_obj))

        # now handle stanzas, these always increment the SM counter
        if self._sm_enabled:
            self._sm_inbound_ctr += 1
            self._sm_inbound_ctr &= 0xffffffff

        # check if the stanza has errors
        if exc is not None:
            self._process_incoming_erroneous_stanza(stanza_obj, exc)
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
        self._logger.debug("flushing incoming queue")
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
        :meth:`StanzaToken.abort`). Sends the state of the token according to
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

        try:
            xmlstream.send_xso(stanza_obj)
        except Exception as exc:
            self._logger.warning("failed to send stanza", exc_info=True)
            token._set_state(StanzaState.FAILED, exc)
            return

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

        if self._sm_enabled:
            self._logger.debug("sending SM req")
            xmlstream.send_xso(nonza.SMRequest())

    def register_iq_response_callback(self, from_, id_, cb):
        """
        Register a callback function `cb` to be called when a IQ stanza with
        type ``result`` or ``error`` is received from the
        :class:`~aioxmpp.JID` `from_` with the id `id_`.

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
        ``error`` from the :class:`~aioxmpp.JID` `from_` with the id
        `id_`.

        If the type of the IQ stanza is ``result``, the stanza is set as result
        to the future. If the type of the IQ stanza is ``error``, the stanzas
        error field is converted to an exception and set as the exception of
        the future.

        The future might also receive different exceptions:

        * :class:`.errors.ErroneousStanza`, if the response stanza received
          could not be parsed.

          Note that this exception is not emitted if the ``from`` address of
          the stanza is unset, because the code cannot determine whether a
          sender deliberately used an erroneous address to make parsing fail
          or no sender address was used. In the former case, an attacker could
          use that to inject a stanza which would be taken as a stanza from the
          peer server. Thus, the future will never be fulfilled in these
          cases.

          Also note that this exception does not derive from
          :class:`.errors.XMPPError`, as it cannot provide the same
          attributes. Instead, it derives from :class:`.errors.StanzaError`,
          from which :class:`.errors.XMPPError` also derives; to catch all
          possible stanza errors, catching :class:`.errors.StanzaError` is
          sufficient and future-proof.

        * :class:`ConnectionError` if the stream is :meth:`stop`\\ -ped (only
          if SM is not enabled) or :meth:`close`\\ -ed.

        * Any :class:`Exception` which may be raised from
          :meth:`~.protocol.XMLStream.send_xso`, which are generally also
          :class:`ConnectionError` or at least :class:`OSError` subclasses.

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
        Alias of :meth:`register_iq_request_handler`.

        .. deprecated:: 0.10

            This alias will be removed in version 1.0.
        """
        warnings.warn(
            "register_iq_request_coro is a deprecated alias to "
            "register_iq_request_handler and will be removed in aioxmpp 1.0",
            DeprecationWarning,
            stacklevel=2)
        return self.register_iq_request_handler(type_, payload_cls, coro)

    def register_iq_request_handler(self, type_, payload_cls, cb, *,
                                    with_send_reply=False):
        """
        Register a coroutine function or a function returning an awaitable to
        run when an IQ request is received.

        :param type_: IQ type to react to (must be a request type).
        :type type_: :class:`~aioxmpp.IQType`
        :param payload_cls: Payload class to react to (subclass of
            :class:`~xso.XSO`)
        :type payload_cls: :class:`~.XMLStreamClass`
        :param cb: Function or coroutine function to invoke
        :param with_send_reply: Whether to pass a function to send a reply
             to `cb` as second argument.
        :type with_send_reply: :class:`bool`
        :raises ValueError: if there is already a coroutine registered for this
                            target
        :raises ValueError: if `type_` is not a request IQ type
        :raises ValueError: if `type_` is not a valid
                            :class:`~.IQType` (and cannot be cast to a
                            :class:`~.IQType`)

        The callback `cb` will be called whenever an IQ stanza with the given
        `type_` and payload being an instance of the `payload_cls` is received.

        The callback must either be a coroutine function or otherwise return an
        awaitable. The awaitable must evaluate to a valid value for the
        :attr:`.IQ.payload` attribute. That value will be set as the payload
        attribute value of an IQ response (with type :attr:`~.IQType.RESULT`)
        which is generated and sent by the stream.

        If the awaitable or the function raises an exception, it will be
        converted to a :class:`~.stanza.Error` object. That error object is
        then used as payload for an IQ response (with type
        :attr:`~.IQType.ERROR`) which is generated and sent by the stream.

        If the exception is a subclass of :class:`aioxmpp.errors.XMPPError`, it
        is converted to an :class:`~.stanza.Error` instance directly.
        Otherwise, it is wrapped in a :class:`aioxmpp.XMPPCancelError`
        with ``undefined-condition``.

        For this to work, `payload_cls` *must* be registered using
        :meth:`~.IQ.as_payload_class`. Otherwise, the payload will
        not be recognised by the stream parser and the IQ is automatically
        responded to with a ``feature-not-implemented`` error.

        .. warning::

            When using a coroutine function for `cb`, there is no guarantee
            that concurrent IQ handlers and other coroutines will execute in
            any defined order. This implies that the strong ordering guarantees
            normally provided by XMPP XML Streams are lost when using coroutine
            functions for `cb`. For this reason, the use of non-coroutine
            functions is allowed.

        .. note::

            Using a non-coroutine function for `cb` will generally lead to
            less readable code. For the sake of readability, it is recommended
            to prefer coroutine functions when strong ordering guarantees are
            not needed.

        .. versionadded:: 0.11

            When the argument `with_send_reply` is true `cb` will be
            called with two arguments: the IQ stanza to handle and a
            unary function `send_reply(result=None)` that sends a
            response to the IQ request and prevents that an automatic
            response is sent. If `result` is an instance of
            :class:`~aioxmpp.XMPPError` an error result is generated.

            This is useful when the handler function needs to execute
            actions which happen after the IQ result has been sent,
            for example, sending other stanzas.

        .. versionchanged:: 0.10

            Accepts an awaitable as last argument in addition to coroutine
            functions.

            Renamed from :meth:`register_iq_request_coro`.

        .. versionadded:: 0.6

           If the stream is :meth:`stop`\\ -ped (only if SM is not enabled) or
           :meth:`close`\\ ed, running IQ response coroutines are
           :meth:`asyncio.Task.cancel`\\ -led.

           To protect against that, fork from your coroutine using
           :func:`asyncio.ensure_future`.

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a :class:`~.IQType`
           member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.
        """
        type_ = self._coerce_enum(type_, structs.IQType)
        if not type_.is_request:
            raise ValueError(
                "{!r} is not a request IQType".format(type_)
            )

        key = type_, payload_cls

        if key in self._iq_request_map:
            raise ValueError("only one listener is allowed per tag")

        self._iq_request_map[key] = cb, with_send_reply
        self._logger.debug(
            "iq request coroutine registered: type=%r, payload=%r",
            type_, payload_cls)

    def unregister_iq_request_coro(self, type_, payload_cls):
        warnings.warn(
            "unregister_iq_request_coro is a deprecated alias to "
            "unregister_iq_request_handler and will be removed in aioxmpp 1.0",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.unregister_iq_request_handler(type_, payload_cls)

    def unregister_iq_request_handler(self, type_, payload_cls):
        """
        Unregister a coroutine previously registered with
        :meth:`register_iq_request_handler`.

        :param type_: IQ type to react to (must be a request type).
        :type type_: :class:`~structs.IQType`
        :param payload_cls: Payload class to react to (subclass of
            :class:`~xso.XSO`)
        :type payload_cls: :class:`~.XMLStreamClass`
        :raises KeyError: if no coroutine has been registered for the given
                          ``(type_, payload_cls)`` pair
        :raises ValueError: if `type_` is not a valid
                            :class:`~.IQType` (and cannot be cast to a
                            :class:`~.IQType`)

        The match is solely made using the `type_` and `payload_cls` arguments,
        which have the same meaning as in :meth:`register_iq_request_coro`.

        .. versionchanged:: 0.10

            Renamed from :meth:`unregister_iq_request_coro`.

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a :class:`~.IQType`
           member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.
        """
        type_ = self._coerce_enum(type_, structs.IQType)
        del self._iq_request_map[type_, payload_cls]
        self._logger.debug(
            "iq request coroutine unregistered: type=%r, payload=%r",
            type_, payload_cls)

    def register_message_callback(self, type_, from_, cb):
        """
        Register a callback to be called when a message is received.

        :param type_: Message type to listen for, or :data:`None` for a
                      wildcard match.
        :type type_: :class:`~.MessageType` or :data:`None`
        :param from_: Sender JID to listen for, or :data:`None` for a wildcard
                      match.
        :type from_: :class:`~aioxmpp.JID` or :data:`None`
        :param cb: Callback function to call
        :raises ValueError: if another function is already registered for the
                            same ``(type_, from_)`` pair.
        :raises ValueError: if `type_` is not a valid
                            :class:`~.MessageType` (and cannot be cast
                            to a :class:`~.MessageType`)

        `cb` will be called whenever a message stanza matching the `type_` and
        `from_` is received, according to the wildcarding rules below. More
        specific callbacks win over less specific callbacks, and the match on
        the `from_` address takes precedence over the match on the `type_`.

        See :meth:`.SimpleStanzaDispatcher.register_callback` for the exact
        wildcarding rules.

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a
           :class:`~.MessageType` member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.

        .. deprecated:: 0.9

           This method has been deprecated in favour of and is now implemented
           in terms of the :class:`aioxmpp.dispatcher.SimpleMessageDispatcher`
           service.

           It is equivalent to call
           :meth:`~.SimpleStanzaDispatcher.register_callback`, except that the
           latter is not deprecated.
        """
        if type_ is not None:
            type_ = self._coerce_enum(type_, structs.MessageType)
        warnings.warn(
            "register_message_callback is deprecated; use "
            "aioxmpp.dispatcher.SimpleMessageDispatcher instead",
            DeprecationWarning,
            stacklevel=2
        )
        self._xxx_message_dispatcher.register_callback(
            type_,
            from_,
            cb,
        )

    def unregister_message_callback(self, type_, from_):
        """
        Unregister a callback previously registered with
        :meth:`register_message_callback`.

        :param type_: Message type to listen for.
        :type type_: :class:`~.MessageType` or :data:`None`
        :param from_: Sender JID to listen for.
        :type from_: :class:`~aioxmpp.JID` or :data:`None`
        :raises KeyError: if no function is currently registered for the given
                          ``(type_, from_)`` pair.
        :raises ValueError: if `type_` is not a valid
                            :class:`~.MessageType` (and cannot be cast
                            to a :class:`~.MessageType`)

        The match is made on the exact pair; it is not possible to unregister
        arbitrary listeners by passing :data:`None` to both arguments (i.e. the
        wildcarding only applies for receiving stanzas, not for unregistering
        callbacks; unregistering the super-wildcard with both arguments set to
        :data:`None` is of course possible).

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a
           :class:`~.MessageType` member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.

        .. deprecated:: 0.9

           This method has been deprecated in favour of and is now implemented
           in terms of the :class:`aioxmpp.dispatcher.SimpleMessageDispatcher`
           service.

           It is equivalent to call
           :meth:`~.SimpleStanzaDispatcher.unregister_callback`, except that
           the latter is not deprecated.
        """
        if type_ is not None:
            type_ = self._coerce_enum(type_, structs.MessageType)
        warnings.warn(
            "unregister_message_callback is deprecated; use "
            "aioxmpp.dispatcher.SimpleMessageDispatcher instead",
            DeprecationWarning,
            stacklevel=2
        )
        self._xxx_message_dispatcher.unregister_callback(
            type_,
            from_,
        )

    def register_presence_callback(self, type_, from_, cb):
        """
        Register a callback to be called when a presence stanza is received.

        :param type_: Presence type to listen for.
        :type type_: :class:`~.PresenceType`
        :param from_: Sender JID to listen for, or :data:`None` for a wildcard
                      match.
        :type from_: :class:`~aioxmpp.JID` or :data:`None`.
        :param cb: Callback function
        :raises ValueError: if another listener with the same ``(type_,
                            from_)`` pair is already registered
        :raises ValueError: if `type_` is not a valid
                            :class:`~.PresenceType` (and cannot be cast
                            to a :class:`~.PresenceType`)

        `cb` will be called whenever a presence stanza matching the `type_` is
        received from the specified sender. `from_` may be :data:`None` to
        indicate a wildcard. Like with :meth:`register_message_callback`, more
        specific callbacks win over less specific callbacks. The fallback order
        is identical, except that the ``type_=None`` entries described there do
        not apply for presence stanzas and are thus omitted.

        See :meth:`.SimpleStanzaDispatcher.register_callback` for the exact
        wildcarding rules.

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a
           :class:`~.PresenceType` member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.

        .. deprecated:: 0.9

           This method has been deprecated. It is recommended to use
           :class:`aioxmpp.PresenceClient` instead.

        """
        type_ = self._coerce_enum(type_, structs.PresenceType)
        warnings.warn(
            "register_presence_callback is deprecated; use "
            "aioxmpp.dispatcher.SimplePresenceDispatcher or "
            "aioxmpp.PresenceClient instead",
            DeprecationWarning,
            stacklevel=2
        )
        self._xxx_presence_dispatcher.register_callback(
            type_,
            from_,
            cb,
        )

    def unregister_presence_callback(self, type_, from_):
        """
        Unregister a callback previously registered with
        :meth:`register_presence_callback`.

        :param type_: Presence type to listen for.
        :type type_: :class:`~.PresenceType`
        :param from_: Sender JID to listen for, or :data:`None` for a wildcard
                      match.
        :type from_: :class:`~aioxmpp.JID` or :data:`None`.
        :raises KeyError: if no callback is currently registered for the given
                          ``(type_, from_)`` pair
        :raises ValueError: if `type_` is not a valid
                            :class:`~.PresenceType` (and cannot be cast
                            to a :class:`~.PresenceType`)

        The match is made on the exact pair; it is not possible to unregister
        arbitrary listeners by passing :data:`None` to the `from_` arguments
        (i.e. the wildcarding only applies for receiving stanzas, not for
        unregistering callbacks; unregistering a wildcard match with `from_`
        set to :data:`None` is of course possible).

        .. versionchanged:: 0.7

           The `type_` argument is now supposed to be a
           :class:`~.PresenceType` member.

        .. deprecated:: 0.7

           Passing a :class:`str` as `type_` argument is deprecated and will
           raise a :class:`TypeError` as of the 1.0 release. See the Changelog
           for :ref:`api-changelog-0.7` for further details on how to upgrade
           your code efficiently.

        .. deprecated:: 0.9

           This method has been deprecated. It is recommended to use
           :class:`aioxmpp.PresenceClient` instead.

        """
        type_ = self._coerce_enum(type_, structs.PresenceType)
        warnings.warn(
            "unregister_presence_callback is deprecated; use "
            "aioxmpp.dispatcher.SimplePresenceDispatcher or "
            "aioxmpp.PresenceClient instead",
            DeprecationWarning,
            stacklevel=2
        )
        self._xxx_presence_dispatcher.unregister_callback(
            type_,
            from_,
        )

    def _xmlstream_soft_limit_tripped(self, xmlstream):
        self._logger.debug(
            "XMLStream has reached dead-time soft limit, sending ping"
        )

        if self._sm_enabled:
            req = nonza.SMRequest()
            xmlstream.send_xso(req)
        else:
            iq = stanza.IQ(
                type_=structs.IQType.GET,
                payload=ping.Ping()
            )
            iq.autoset_id()
            self.register_iq_response_callback(
                None,
                iq.id_,
                # we don’t care, just wanna make sure that this doesn’t fail
                lambda stanza: None,
            )
            self._enqueue(iq)

    def _start_prepare(self, xmlstream, receiver):
        self._xmlstream_failure_token = xmlstream.on_closing.connect(
            self._xmlstream_failed
        )

        self._xmlstream_soft_limit_token = \
            xmlstream.on_deadtime_soft_limit_tripped.connect(
                functools.partial(self._xmlstream_soft_limit_tripped,
                                  xmlstream)
            )

        xmlstream.stanza_parser.add_class(stanza.IQ, receiver)
        xmlstream.stanza_parser.add_class(stanza.Message, receiver)
        xmlstream.stanza_parser.add_class(stanza.Presence, receiver)
        xmlstream.error_handler = self.recv_erroneous_stanza

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
        xmlstream.on_deadtime_soft_limit_tripped.disconnect(
            self._xmlstream_soft_limit_token
        )

    def _update_xmlstream_limits(self):
        if self._xmlstream is None:
            return

        self._xmlstream.deadtime_soft_limit = self._soft_timeout
        if (self._soft_timeout is not None and
                self._round_trip_time is not None):
            self._xmlstream.deadtime_hard_limit = \
                self._soft_timeout + self._round_trip_time
        else:
            self._xmlstream.deadtime_hard_limit = None

    def _start_commit(self, xmlstream):
        if not self._established:
            self.on_stream_established()
            self._established = True

        self._task = asyncio.ensure_future(self._run(xmlstream),
                                           loop=self._loop)
        self._task.add_done_callback(self._done_handler)
        self._logger.debug("broker task started as %r", self._task)

    def start(self, xmlstream):
        """
        Start or resume the stanza stream on the given
        :class:`aioxmpp.protocol.XMLStream` `xmlstream`.

        This starts the main broker task, registers stanza classes at the
        `xmlstream` .
        """

        if self.running:
            raise RuntimeError("already started")

        self._start_prepare(xmlstream, self.recv_stanza)
        self._closed = False
        self._start_commit(xmlstream)

    def stop(self):
        """
        Send a signal to the main broker task to terminate. You have to check
        :attr:`running` and possibly wait for it to become :data:`False` ---
        the task takes at least one loop through the event loop to terminate.

        It is guaranteed that the task will not attempt to send stanzas over
        the existing `xmlstream` after a call to :meth:`stop` has been made.

        It is legal to call :meth:`stop` even if the task is already
        stopped. It is a no-op in that case.
        """
        if not self.running:
            return
        self._logger.debug("sending stop signal to task")
        self._task.cancel()

    async def wait_stop(self):
        """
        Stop the stream and wait for it to stop.

        See :meth:`stop` for the general stopping conditions. You can assume
        that :meth:`stop` is the first thing this coroutine calls.
        """
        if not self.running:
            return
        self.stop()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def close(self):
        """
        Close the stream and the underlying XML stream (if any is connected).

        This is essentially a way of saying "I do not want to use this stream
        anymore" (until the next call to :meth:`start`). If the stream is
        currently running, the XML stream is closed gracefully (potentially
        sending an SM ack), the worker is stopped and any Stream Management
        state is cleaned up.

        If an error occurs while the stream stops, the error is ignored.

        After the call to :meth:`close` has started, :meth:`on_failure` will
        not be emitted, even if the XML stream fails before closure has
        completed.

        After a call to :meth:`close`, the stream is stopped, all SM state is
        discarded and calls to :meth:`enqueue_stanza` raise a
        :class:`DestructionRequested` ``"close() called"``. Such a
        :class:`StanzaStream` can be re-started by calling :meth:`start`.

        .. versionchanged:: 0.8

           Before 0.8, an error during a call to :meth:`close` would stop the
           stream from closing completely, and the exception was re-raised. If
           SM was enabled, the state would have been kept, allowing for
           resumption and ensuring that stanzas still enqueued or
           unacknowledged would get a chance to be sent.

           If you want to have guarantees that all stanzas sent up to a certain
           point are sent, you should be using :meth:`send_and_wait_for_sent`
           with stream management.
        """
        exc = DestructionRequested("close() called")

        if self.running:
            if self.sm_enabled:
                self._xmlstream.send_xso(nonza.SMAcknowledgement(
                    counter=self._sm_inbound_ctr
                ))

            await self._xmlstream.close_and_wait()  # does not raise
            await self.wait_stop()  # may raise

        self._closed = True
        self._xmlstream_exception = exc
        self._destroy_stream_state(self._xmlstream_exception)
        if self.sm_enabled:
            self.stop_sm()

    def _drain_incoming(self):
        """
        Drain the incoming queue **without** processing any contents.
        """
        self._logger.debug("draining incoming queue")
        while True:
            # this cannot loop for infinity because we do not yield control
            # and the queue cannot be filled across threads.
            try:
                self._incoming_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _run(self, xmlstream):
        self._xmlstream = xmlstream
        self._update_xmlstream_limits()
        active_fut = asyncio.ensure_future(self._active_queue.get(),
                                           loop=self._loop)
        incoming_fut = asyncio.ensure_future(self._incoming_queue.get(),
                                             loop=self._loop)

        try:
            while True:
                timeout = None
                done, pending = await asyncio.wait(
                    [
                        active_fut,
                        incoming_fut,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout)

                async with self._broker_lock:
                    if active_fut in done:
                        self._process_outgoing(xmlstream, active_fut.result())
                        active_fut = asyncio.ensure_future(
                            self._active_queue.get(),
                            loop=self._loop)

                    if incoming_fut in done:
                        self._process_incoming(xmlstream,
                                               incoming_fut.result())
                        incoming_fut = asyncio.ensure_future(
                            self._incoming_queue.get(),
                            loop=self._loop)

        finally:
            # make sure we rescue any stanzas which possibly have already been
            # caught by the calls to get()
            self._logger.debug("task terminating, rescuing stanzas and "
                               "clearing handlers")
            # Drain the incoming queue:
            # 1. Either we have an SM-resumable stream and we'll SM-resume it,
            #    in which case we can reply to stanzas in here; however, then
            #    we'd get them re-transmitted anyway.
            # 2. Or the stream is not SM-resumed, in which case it would be
            #    invalid to reply to anything in the incoming queue or process
            #    it in any way, as it may refer to old, stale state.
            #    Imagine an incremental roster update slipping in here and
            #    getting processed after a reconnect. Terrible. Let's flush
            #    this queue immediately.
            if incoming_fut.done():
                # discard
                try:
                    incoming_fut.result()
                except BaseException:  # noqa
                    # we truly do not care, because we are going to drain the
                    # queue anyway. if anything is fatally wrong with the
                    # queue, it'll reraise there. if anything is fatally
                    # wrong with the event loop, it'll hit us elsewhere
                    # eventually. if it was successful, good, let's drop the
                    # stanza because we want to drain right now.
                    pass
            else:
                incoming_fut.cancel()
            self._drain_incoming()

            if active_fut.done() and not active_fut.exception():
                self._active_queue.putleft_nowait(active_fut.result())
            else:
                active_fut.cancel()

            # we also lock shutdown, because the main race is among the SM
            # variables
            async with self._broker_lock:
                if not self.sm_enabled or not self.sm_resumable:
                    self._destroy_stream_state(
                        self._xmlstream_exception or
                        DestructionRequested(
                            "close() or stop() called and stream is not "
                            "resumable"
                        )
                    )
                    if self.sm_enabled:
                        self._stop_sm()

                self._start_rollback(xmlstream)

            if self._xmlstream_exception:
                raise self._xmlstream_exception

    def recv_stanza(self, stanza):
        """
        Inject a `stanza` into the incoming queue.
        """
        self._incoming_queue.put_nowait((stanza, None))

    def recv_erroneous_stanza(self, partial_obj, exc):
        self._incoming_queue.put_nowait((partial_obj, exc))

    def _enqueue(self, stanza, **kwargs):
        if self._closed:
            raise self._xmlstream_exception

        stanza.validate()
        token = StanzaToken(stanza, **kwargs)
        self._active_queue.put_nowait(token)
        stanza.autoset_id()
        self._logger.debug("enqueued stanza %r with token %r",
                           stanza, token)
        return token

    enqueue_stanza = _enqueue

    def enqueue(self, stanza, **kwargs):
        """
        Deprecated alias of :meth:`aioxmpp.Client.enqueue`.

        This is only available on streams owned by a :class:`aioxmpp.Client`.

        .. deprecated:: 0.10
        """
        raise NotImplementedError(
            "only available on streams owned by a Client"
        )

    @property
    def running(self):
        """
        :data:`True` if the broker task is currently running, and :data:`False`
        otherwise.
        """
        return self._task is not None and not self._task.done()

    async def start_sm(self, request_resumption=True, resumption_timeout=None):
        """
        Start stream management (version 3).

        :param request_resumption: Request that the stream shall be resumable.
        :type request_resumption: :class:`bool`
        :param resumption_timeout: Maximum time in seconds for a stream to be
            resumable.
        :type resumption_timeout: :class:`int`
        :raises aioxmpp.errors.StreamNegotiationFailure: if the server rejects
            the attempt to enable stream management.

        This method attempts to starts stream management on the stream.

        `resumption_timeout` is the ``max`` attribute on
        :class:`.nonza.SMEnabled`; it can be used to set a maximum time for
        which the server shall consider the stream to still be alive after the
        underlying transport (TCP) has failed. The server may impose its own
        maximum or ignore the request, so there are no guarantees that the
        session will stay alive for at most or at least `resumption_timeout`
        seconds. Passing a `resumption_timeout` of 0 is equivalent to passing
        false to `request_resumption` and takes precedence over
        `request_resumption`.

        .. note::

            In addition to server implementation details, it is very well
            possible that the server does not even detect that the underlying
            transport has failed for quite some time for various reasons
            (including high TCP timeouts).

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
        afterwards. If the :class:`.nonza.SMEnabled` response was not received
        before the XML stream died, SM is also disabled and the exception which
        caused the stream to die is re-raised (this is due to the
        implementation of :func:`~.protocol.send_and_wait_for`). If the
        :class:`.nonza.SMEnabled` response was received and annonuced support
        for resumption, SM is enabled. Otherwise, it is disabled. No exception
        is raised if :class:`.nonza.SMEnabled` was received, as this method has
        no way to determine that the stream failed.

        If negotiation succeeds, this coroutine initializes a new stream
        management session. The stream management state attributes become
        available and :attr:`sm_enabled` becomes :data:`True`.
        """
        if not self.running:
            raise RuntimeError("cannot start Stream Management while"
                               " StanzaStream is not running")
        if self.sm_enabled:
            raise RuntimeError("Stream Management already enabled")

        if resumption_timeout == 0:
            request_resumption = False
            resumption_timeout = None

        # sorry for the callback spaghetti code
        # we have to handle the response synchronously, so we have to use a
        # callback.
        # otherwise, it is possible that an SM related nonza (e.g. <r/>) is
        # received (and attempted to be deserialized) before the handlers are
        # registered
        # see tests/test_highlevel.py:TestProtocoltest_sm_bootstrap_race
        def handle_response(response):
            if isinstance(response, nonza.SMFailed):
                # we handle the error down below
                return

            self._sm_outbound_base = 0
            self._sm_inbound_ctr = 0
            self._sm_unacked_list = []
            self._sm_enabled = True
            self._sm_id = response.id_
            self._sm_resumable = response.resume
            self._sm_max = response.max_
            self._sm_location = response.location

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

        async with self._broker_lock:
            response = await protocol.send_and_wait_for(
                self._xmlstream,
                [
                    nonza.SMEnable(resume=bool(request_resumption),
                                   max_=resumption_timeout),
                ],
                [
                    nonza.SMEnabled,
                    nonza.SMFailed
                ],
                cb=handle_response,
            )

            if isinstance(response, nonza.SMFailed):
                raise errors.StreamNegotiationFailure(
                    "Server rejected SM request")

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
           general, access to this attribute should not be necessary at all.

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

    def _clear_unacked(self, new_state, *args):
        for token in self._sm_unacked_list:
            token._set_state(new_state, *args)
        self._sm_unacked_list.clear()

    async def resume_sm(self, xmlstream):
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

        .. versionchanged:: 0.11

            Support for using the counter value provided some servers on a
            failed resumption was added. Stanzas which are covered by the
            counter will be marked as :attr:`~StanzaState.ACKED`; other stanzas
            will be marked as :attr:`~StanzaState.DISCONNECTED`.

            This is in contrast to the behaviour when resumption fails
            *without* a counter given. In that case, stanzas which have not
            been acked are marked as :attr:`~StanzaState.SENT_WITHOUT_SM`.
        """

        if self.running:
            raise RuntimeError("Cannot resume Stream Management while"
                               " StanzaStream is running")

        self._start_prepare(xmlstream, self.recv_stanza)
        try:
            response = await protocol.send_and_wait_for(
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
                exc = errors.StreamNegotiationFailure(
                    "Server rejected SM resumption"
                )

                if response.counter is not None:
                    self.sm_ack(response.counter)
                    self._clear_unacked(StanzaState.DISCONNECTED)

                xmlstream.stanza_parser.remove_class(
                    nonza.SMRequest)
                xmlstream.stanza_parser.remove_class(
                    nonza.SMAcknowledgement)
                self.stop_sm()
                raise exc

            self._resume_sm(response.counter)
        except:  # NOQA
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
        self._clear_unacked(StanzaState.SENT_WITHOUT_SM)
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

        If called with an erroneous remote stanza counter
        :class:`.errors.StreamNegotationFailure` will be raised.

        Attempting to call this without Stream Management enabled results in a
        :class:`RuntimeError`.
        """

        if not self._sm_enabled:
            raise RuntimeError("Stream Management is not enabled")

        self._logger.debug("sm_ack(%d)", remote_ctr)
        to_drop = (remote_ctr - self._sm_outbound_base) & 0xffffffff
        self._logger.debug("sm_ack: to drop %d, unacked: %d",
                           to_drop, len(self._sm_unacked_list))
        if to_drop > len(self._sm_unacked_list):
            raise errors.StreamNegotiationFailure(
                "acked more stanzas than have been sent "
                "(outbound_base={}, remote_ctr={})".format(
                    self._sm_outbound_base,
                    remote_ctr
                )
            )

        acked = self._sm_unacked_list[:to_drop]
        del self._sm_unacked_list[:to_drop]
        self._sm_outbound_base = remote_ctr

        if acked:
            self._logger.debug("%d stanzas acked by remote", len(acked))
        for token in acked:
            token._set_state(StanzaState.ACKED)

    async def send_iq_and_wait_for_reply(self, iq, *, timeout=None):
        """
        Send an IQ stanza `iq` and wait for the response. If `timeout` is not
        :data:`None`, it must be the time in seconds for which to wait for a
        response.

        If the response is a ``"result"`` IQ, the value of the
        :attr:`~aioxmpp.IQ.payload` attribute is returned. Otherwise,
        the exception generated from the :attr:`~aioxmpp.IQ.error`
        attribute is raised.

        .. seealso::

           :meth:`register_iq_response_future` and
           :meth:`send_and_wait_for_sent` for other cases raising exceptions.

        .. deprecated:: 0.8

           This method will be removed in 1.0. Use :meth:`send` instead.

        .. versionchanged:: 0.8

           On a timeout, :class:`TimeoutError` is now raised instead of
           :class:`asyncio.TimeoutError`.

        """
        warnings.warn(
            r"send_iq_and_wait_for_reply is deprecated and will be removed in"
            r" 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        return await self.send(iq, timeout=timeout)

    async def send_and_wait_for_sent(self, stanza):
        """
        Send the given `stanza` over the given :class:`StanzaStream` `stream`.

        .. deprecated:: 0.8

           This method will be removed in 1.0. Use :meth:`send` instead.
        """
        warnings.warn(
            r"send_and_wait_for_sent is deprecated and will be removed in 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        await self._enqueue(stanza)

    async def _send_immediately(self, stanza, *, timeout=None, cb=None):
        """
        Send a stanza without waiting for the stream to be ready to send
        stanzas.

        This is only useful from within :class:`aioxmpp.node.Client` before
        the stream is fully established.
        """
        stanza.autoset_id()
        self._logger.debug("sending %r and waiting for it to be sent",
                           stanza)

        if not isinstance(stanza, stanza_.IQ) or stanza.type_.is_response:
            if cb is not None:
                raise ValueError(
                    "cb not supported with non-IQ non-request stanzas"
                )
            await self._enqueue(stanza)
            return

        # we use the long way with a custom listener instead of a future here
        # to ensure that the callback is called synchronously from within the
        # queue handling loop.
        # we need that to ensure that the strong ordering guarantees reach the
        # `cb` function.

        fut = asyncio.Future()

        def nested_cb(task):
            """
            This callback is used to handle awaitables returned by the `cb`.
            """
            nonlocal fut
            if task.exception() is None:
                fut.set_result(task.result())
            else:
                fut.set_exception(task.exception())

        def handler_ok(stanza):
            """
            This handler is invoked synchronously by
            :meth:`_process_incoming_iq` (via
            :class:`aioxmpp.callbacks.TagDispatcher`) for response stanzas
            (including error stanzas).
            """
            nonlocal fut
            if fut.cancelled():
                return

            if cb is not None:
                try:
                    nested_fut = cb(stanza)
                except Exception as exc:
                    fut.set_exception(exc)
                else:
                    if nested_fut is not None:
                        nested_fut.add_done_callback(nested_cb)
                        return

            # we can’t even use StanzaErrorAwareListener because we want to
            # forward error stanzas to the cb too...
            if stanza.type_.is_error:
                fut.set_exception(stanza.error.to_exception())
            else:
                fut.set_result(stanza.payload)

        def handler_error(exc):
            """
            This handler is invoked synchronously by
            :meth:`_process_incoming_iq` (via
            :class:`aioxmpp.callbacks.TagDispatcher`) for response errors (
            such as parsing errors, connection errors, etc.).
            """
            nonlocal fut
            if fut.cancelled():
                return
            fut.set_exception(exc)

        listener = callbacks.OneshotTagListener(
            handler_ok,
            handler_error,
        )
        listener_tag = (stanza.to, stanza.id_)

        self._iq_response_map.add_listener(
            listener_tag,
            listener,
        )

        try:
            await self._enqueue(stanza)
        except Exception:
            listener.cancel()
            raise

        try:
            if not timeout:
                reply = await fut
            else:
                try:
                    reply = await asyncio.wait_for(
                        fut,
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError
        finally:
            try:
                self._iq_response_map.remove_listener(listener_tag)
            except KeyError:
                pass

        return reply

    async def send(self, stanza, timeout=None, *, cb=None):
        """
        Deprecated alias of :meth:`aioxmpp.Client.send`.

        This is only available on streams owned by a :class:`aioxmpp.Client`.

        .. deprecated:: 0.10
        """
        raise NotImplementedError(
            "only available on streams owned by a Client"
        )


@contextlib.contextmanager
def iq_handler(stream, type_, payload_cls, coro, *, with_send_reply=False):
    """
    Context manager to temporarily register a coroutine to handle IQ requests
    on a :class:`StanzaStream`.

    :param stream: Stanza stream to register the coroutine at
    :type stream: :class:`StanzaStream`
    :param type_: IQ type to react to (must be a request type).
    :type type_: :class:`~aioxmpp.IQType`
    :param payload_cls: Payload class to react to (subclass of
                        :class:`~xso.XSO`)
    :type payload_cls: :class:`~.XMLStreamClass`
    :param coro: Coroutine to register
    :param with_send_reply: Whether to pass a function to send the reply
                            early to `cb`.
    :type with_send_reply: :class:`bool`

    The coroutine is registered when the context is entered and unregistered
    when the context is exited. Running coroutines are not affected by exiting
    the context manager.

    .. versionadded:: 0.11

       The `with_send_reply` argument. See
       :meth:`aioxmpp.stream.StanzaStream.register_iq_request_handler` for
       more detail.

    .. versionadded:: 0.8
    """

    stream.register_iq_request_handler(
        type_,
        payload_cls,
        coro,
        with_send_reply=with_send_reply,
    )
    try:
        yield
    finally:
        stream.unregister_iq_request_handler(type_, payload_cls)


@contextlib.contextmanager
def message_handler(stream, type_, from_, cb):
    """
    Context manager to temporarily register a callback to handle messages on a
    :class:`StanzaStream`.

    :param stream: Stanza stream to register the coroutine at
    :type stream: :class:`StanzaStream`
    :param type_: Message type to listen for, or :data:`None` for a wildcard
                  match.
    :type type_: :class:`~.MessageType` or :data:`None`
    :param from_: Sender JID to listen for, or :data:`None` for a wildcard
                  match.
    :type from_: :class:`~aioxmpp.JID` or :data:`None`
    :param cb: Callback to register

    The callback is registered when the context is entered and unregistered
    when the context is exited.

    .. versionadded:: 0.8
    """

    stream.register_message_callback(
        type_,
        from_,
        cb,
    )
    try:
        yield
    finally:
        stream.unregister_message_callback(
            type_,
            from_,
        )


@contextlib.contextmanager
def presence_handler(stream, type_, from_, cb):
    """
    Context manager to temporarily register a callback to handle presence
    stanzas on a :class:`StanzaStream`.

    :param stream: Stanza stream to register the coroutine at
    :type stream: :class:`StanzaStream`
    :param type_: Presence type to listen for.
    :type type_: :class:`~.PresenceType`
    :param from_: Sender JID to listen for, or :data:`None` for a wildcard
                  match.
    :type from_: :class:`~aioxmpp.JID` or :data:`None`.
    :param cb: Callback to register

    The callback is registered when the context is entered and unregistered
    when the context is exited.

    .. versionadded:: 0.8
    """

    stream.register_presence_callback(
        type_,
        from_,
        cb,
    )
    try:
        yield
    finally:
        stream.unregister_presence_callback(
            type_,
            from_,
        )


_Undefined = object()


def stanza_filter(filter_, func, order=_Undefined):
    """
    This is a deprecated alias of
    :meth:`aioxmpp.callbacks.Filter.context_register`.

    .. versionadded:: 0.8

    .. deprecated:: 0.9
    """
    if order is not _Undefined:
        return filter_.context_register(func, order)
    else:
        return filter_.context_register(func)
