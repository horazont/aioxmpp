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

Interfaces
==========

.. autoclass:: MessageTracker

.. autoclass:: MessageState

"""
from enum import Enum

import aioxmpp.callbacks
import aioxmpp.statemachine
import aioxmpp.stream as stream


class MessageState(Enum):
    """
    Enumeration of possible states for :class:`MessageTracker`. These states
    are used to inform using code about the delivery state of a message. See
    :class:`MessageTracker` for details.

    .. attribute:: ABORTED

       The message has been aborted or dropped in the :class:`~.StanzaStream`
       queues. See :class:`~.StanzaToken` and :attr:`MessageTracker.token`.

       This is a final state.

    .. attribute:: ERROR

       An error reply stanza has been received for the stanza which was sent.

       This is, in most cases, a final state.

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
    :class:`~.StanzaToken`), the other implementation can use e.g. :xep:`184` to
    determine delivery at the target and so on.

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
        :attr:`response` is also overriden with the new value, no matter if the
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

        If the tracker is already :meth:`close`\ -d, :class:`RuntimeError` is
        raised. This check happens *before* a test is made whether the
        transition is valid.

        This method is part of the "protected" interface.
        """
        if self._closed:
            raise RuntimeError("message tracker is closed")

        # reject some transitions as documented
        if     (self._state == MessageState.ABORTED or
                self._state == MessageState.ERROR or
                new_state == MessageState.IN_TRANSIT or
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
