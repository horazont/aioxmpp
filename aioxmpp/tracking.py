########################################################################
# File name: tracking.py
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
:mod:`~aioxmpp.tracking` --- Interfaces for high-level message tracking
#######################################################################

This submodule provides interfaces for tracking messages to the recipient. The
actual tracking is not implemented here.

.. versionadded:: 0.5

   This module was added in version 0.5.

.. versionchanged:: 0.9

   This module was completely rewritten in 0.9.

.. seealso::

   Method :meth:`~.muc.Room.send_tracked_message`
     implements tracking for messages sent through a MUC.

.. _api-tracking-memory:

General Remarks about Tracking and Memory Consumption
=====================================================


Tracking stanzas costs memory. There are basically two options on how to
implement the management of additional information:

1. Either the tracking stops when the :class:`MessageTracker` is released (i.e.
   the last reference to it gets collected).

2. Or the tracking is stopped explicitly by the user.

Option (1) has the appeal that users (applications) do not have to worry about
properly releasing the tracking objects. However, it has the downside that
applications have to keep the :class:`MessageeTracker` instance around.
Remember that connecting to callbacks of an object is *not* enough to keep it
alive.

Option (2) is somewhat like file objects work: in theory, you have to close
them explicitly and manually: if you do not, there is no guarantee when the
file is actually closed. It is thus a somewhat known Python idiom, and also is
more explicit. And it doesn’t break callbacks.

The implementation of :class:`MessageTracker` uses **Option 2**. So you have to
:meth:`MessageTracker.close` all :class:`MessageTracker` objects to ensure that
all tracking resources associated with it are released; this stops any tracking
which is still in progress.

It is strongly recommended that you close message trackers after a timeout. You
can use :meth:`MessageTracker.set_timeout` for that, or manually call
:meth:`MessageTracker.close` as desired.

Tracking implementations
========================

.. autoclass:: BasicTrackingService

Interfaces
==========

.. autoclass:: MessageTracker

.. autoclass:: MessageState

"""
import asyncio
import functools

from datetime import timedelta
from enum import Enum

import aioxmpp.callbacks
import aioxmpp.service


class MessageState(Enum):
    """
    Enumeration of possible states for :class:`MessageTracker`. These states
    are used to inform using code about the delivery state of a message. See
    :class:`MessageTracker` for details.

    .. versionchanged:: 0.10

        The :attr:`ERROR` state is no longer final. Tracking implementations
        may now trump an error state with another state in some cases.

        An example would be :xep:`184` message delivery receipts which can
        for sure attest an :attr:`DELIVERED_TO_RECIPIENT` state. This is more
        useful than an error reply.

    .. attribute:: ABORTED

       The message has been aborted or dropped in the :class:`~.StanzaStream`
       queues. See :class:`~.StanzaToken` and :attr:`MessageTracker.token`.

       This is a final state.

    .. attribute:: ERROR

       An error reply stanza has been received for the stanza which was sent.

       This is, in most cases, a final state, but transitions to
       :attr:`DELIVERED_TO_RECIPIENT` and :attr:`SEEN_BY_RECIPIENT` are
       allowed.

    .. attribute:: IN_TRANSIT

       The message is still queued for sending or has been sent to the peer
       server without stream management.

       Depending on the tracking implementation, this may be a final state.

    .. attribute:: DELIVERED_TO_SERVER

       The message has been delivered to the server and the server acked the
       delivery using stream management.

       Depending on the tracking implementation, this may be a final state.

    .. attribute:: DELIVERED_TO_RECIPIENT

       The message has been delivered to the recipient.

       Depending on the tracking implementation, this may be a final state.

    .. attribute:: SEEN_BY_RECIPIENT

       The recipient has marked the message as seen or read. This is a final
       state.

    """

    IN_TRANSIT = 0
    ABORTED = 1
    ERROR = 2
    DELIVERED_TO_SERVER = 3
    DELIVERED_TO_RECIPIENT = 4
    SEEN_BY_RECIPIENT = 5


class MessageTracker:
    """
    This is the high-level equivalent of the :class:`~.StanzaToken`.

    This structure is used by different tracking implementations. The interface
    of this class is split in two parts:

    1. The public interface for use by applications.
    2. The "protected" interface for use by tracking implementations.

    :class:`MessageTracker` objects are designed to be drivable from multiple
    tracking implementations at once. The idea is that different tracking
    implementations can cover different parts of the path a stanza takes: one
    can cover the path to the server (by hooking into the events of a
    :class:`~.StanzaToken`), the other implementation can use e.g. :xep:`184`
    to determine delivery at the target and so on.

    Methods and attributes from the "protected" interface are marked by a
    leading underscore.

    .. autoattribute:: state

    .. autoattribute:: response

    .. autoattribute:: closed

    .. signal:: on_state_changed(new_state, response=None)

       Emits when a new state is entered.

       :param new_state: The new state of the tracker.
       :type new_state: :class:`~.MessageState` member
       :param response: A stanza related to the state.
       :type response: :class:`~.StanzaBase` or :data:`None`

       The is *not* emitted when the tracker is closed.

    .. signal:: on_closed()

       Emits when the tracker is closed.

    .. automethod:: close

    .. automethod:: set_timeout

    "Protected" interface:

    .. automethod:: _set_state

    """

    on_closed = aioxmpp.callbacks.Signal()
    on_state_changed = aioxmpp.callbacks.Signal()

    def __init__(self):
        super().__init__()
        self._state = MessageState.IN_TRANSIT
        self._response = None
        self._closed = False

    @property
    def state(self):
        """
        The current state of the tracking. Read-only.
        """
        return self._state

    @property
    def response(self):
        """
        A stanza which is relevant to the current state. For
        :attr:`.MessageState.ERROR`, this will generally be a
        :class:`.MessageType.ERROR` stanza. For other states, this is either
        :data:`None` or another stanza depending on the tracking
        implementation.
        """
        return self._response

    @property
    def closed(self):
        """
        Boolean indicator whether the tracker is closed.

        .. seealso::

           :meth:`close` for details.
        """
        return self._closed

    def close(self):
        """
        Close the tracking, clear all references to the tracker and release all
        tracking-related resources.

        This operation is idempotent. It does not change the :attr:`state`, but
        :attr:`closed` turns :data:`True`.

        The :meth:`on_closed` event is only fired on the first call to
        :meth:`close`.
        """
        if self._closed:
            return
        self._closed = True
        self.on_closed()

    def set_timeout(self, timeout):
        """
        Automatically close the tracker after `timeout` has elapsed.

        :param timeout: The timeout after which the tracker is closed
                        automatically.
        :type timeout: :class:`numbers.Real` or :class:`datetime.timedelta`

        If the `timeout` is not a :class:`datetime.timedelta` instance, it is
        assumed to be given as seconds.

        The timeout cannot be cancelled after it has been set. It starts at the
        very moment :meth:`set_timeout` is called.
        """
        loop = asyncio.get_event_loop()

        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()

        loop.call_later(timeout, self.close)

    # "Protected" Interface

    def _set_state(self, new_state, response=None):
        """
        Set the state of the tracker.

        :param new_state: The new state of the tracker.
        :type new_state: :class:`~.MessageState` member
        :param response: A stanza related to the new state.
        :type response: :class:`~.StanzaBase` or :data:`None`
        :raise ValueError: if a forbidden state transition is attempted.
        :raise RuntimeError: if the tracker is closed.

        The state of the tracker is set to the `new_state`. The
        :attr:`response` is also overridden with the new value, no matter if the
        new or old value is :data:`None` or not. The :meth:`on_state_changed`
        event is emitted.

        The following transitions are forbidden and attempting to perform them
        will raise :class:`ValueError`:

        * any state -> :attr:`~.MessageState.IN_TRANSIT`
        * :attr:`~.MessageState.DELIVERED_TO_RECIPIENT` ->
          :attr:`~.MessageState.DELIVERED_TO_SERVER`
        * :attr:`~.MessageState.SEEN_BY_RECIPIENT` ->
          :attr:`~.MessageState.DELIVERED_TO_RECIPIENT`
        * :attr:`~.MessageState.SEEN_BY_RECIPIENT` ->
          :attr:`~.MessageState.DELIVERED_TO_SERVER`
        * :attr:`~.MessageState.ABORTED` -> any state
        * :attr:`~.MessageState.ERROR` -> any state

        If the tracker is already :meth:`close`\\ -d, :class:`RuntimeError` is
        raised. This check happens *before* a test is made whether the
        transition is valid.

        This method is part of the "protected" interface.
        """
        if self._closed:
            raise RuntimeError("message tracker is closed")

        # reject some transitions as documented
        if (self._state == MessageState.ABORTED or
                new_state == MessageState.IN_TRANSIT or
                (self._state == MessageState.ERROR and
                 new_state == MessageState.DELIVERED_TO_SERVER) or
                (self._state == MessageState.ERROR and
                 new_state == MessageState.ABORTED) or
                (self._state == MessageState.DELIVERED_TO_RECIPIENT and
                 new_state == MessageState.DELIVERED_TO_SERVER) or
                (self._state == MessageState.SEEN_BY_RECIPIENT and
                 new_state == MessageState.DELIVERED_TO_SERVER) or
                (self._state == MessageState.SEEN_BY_RECIPIENT and
                 new_state == MessageState.DELIVERED_TO_RECIPIENT)):
            raise ValueError(
                "message tracker transition from {} to {} not allowed".format(
                    self._state,
                    new_state
                )
            )

        self._state = new_state
        self._response = response
        self.on_state_changed(self._state, self._response)


class BasicTrackingService(aioxmpp.service.Service):
    """
    Error handling and :class:`~.StanzaToken`\\ -based tracking for messages.

    This service provides the most basic tracking of message stanzas. It can be
    combined with other forms of tracking.

    Specifically, the stanza is tracked using the means of
    :class:`~.StanzaToken`, that is, until it is acknowledged by the server. In
    addition, error stanzas in reply to the message are also tracked (but they
    do not override states occurring after
    :attr:`~.MessageState.DELIVERED_TO_SERVER`).

    Tracking stanzas:

    .. automethod:: send_tracked

    .. automethod:: attach_tracker
    """

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._trackers = {}

    @aioxmpp.service.inbound_message_filter
    def _inbound_message_filter(self, message):
        try:
            if message.type_ != aioxmpp.MessageType.ERROR:
                return message
        except AttributeError:
            return message

        try:
            key = message.from_.bare(), message.id_
        except AttributeError:
            return message

        try:
            tracker = self._trackers.pop(key)
        except KeyError:
            return message

        if tracker.state == MessageState.DELIVERED_TO_RECIPIENT:
            return
        if tracker.state == MessageState.SEEN_BY_RECIPIENT:
            return
        tracker._set_state(MessageState.ERROR, message)

    def _tracker_closed(self, key):
        self._trackers.pop(key, None)

    def _stanza_sent(self, tracker, token, fut):
        # FIXME: look into whether this is correct, and if it is, document why:
        #
        # - CancelledError does not lead to ABORTED
        # - why it makes sense to channel all *other* exceptions into
        #   ABORTED state
        try:
            fut.result()
        except asyncio.CancelledError:
            return
        except:  # NOQA: E722
            next_state = MessageState.ABORTED
        else:
            next_state = MessageState.DELIVERED_TO_SERVER
        try:
            tracker._set_state(next_state)
        except ValueError:
            pass

    def send_tracked(self, stanza, tracker):
        """
        Send a message stanza with tracking.

        :param stanza: Message stanza to send.
        :type stanza: :class:`aioxmpp.Message`
        :param tracker: Message tracker to use.
        :type tracker: :class:`~.MessageTracker`
        :rtype: :class:`~.StanzaToken`
        :return: The token used to send the stanza.

        If `tracker` is :data:`None`, a new :class:`~.MessageTracker` is
        created.

        This configures tracking for the stanza as if by calling
        :meth:`attach_tracker` with a `token` and sends the stanza through the
        stream.

        .. seealso::

           :meth:`attach_tracker`
              can be used if the stanza cannot be sent (e.g. because it is a
              carbon-copy) or has already been sent.
        """
        token = self.client.enqueue(stanza)
        self.attach_tracker(stanza, tracker, token)
        return token

    def attach_tracker(self, stanza, tracker=None, token=None):
        """
        Configure tracking for a stanza without sending it.

        :param stanza: Message stanza to send.
        :type stanza: :class:`aioxmpp.Message`
        :param tracker: Message tracker to use.
        :type tracker: :class:`~.MessageTracker` or :data:`None`
        :param token: Optional stanza token for more fine-grained tracking.
        :type token: :class:`~.StanzaToken`
        :rtype: :class:`~.MessageTracker`
        :return: The message tracker.

        If `tracker` is :data:`None`, a new :class:`~.MessageTracker` is
        created.

        If `token` is not :data:`None`, updates to the stanza `token` are
        reflected in the `tracker`.

        If an error reply is received, the tracker will enter
        :class:`~.MessageState.ERROR` and the error will be set as
        :attr:`~.MessageTracker.response`.

        You should use :meth:`send_tracked` if possible. This method however is
        very useful if you need to track carbon copies of sent messages, as a
        stanza token is not available here and re-sending the message to obtain
        one is generally not desirable ☺.
        """
        if tracker is None:
            tracker = MessageTracker()
        stanza.autoset_id()
        key = stanza.to.bare(), stanza.id_
        self._trackers[key] = tracker
        tracker.on_closed.connect(
            functools.partial(self._tracker_closed, key)
        )
        if token is not None:
            token.future.add_done_callback(
                functools.partial(
                    self._stanza_sent,
                    tracker,
                    token,
                )
            )
        return tracker
