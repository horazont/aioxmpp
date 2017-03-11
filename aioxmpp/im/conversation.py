########################################################################
# File name: conversation.py
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
import abc
import asyncio
import enum

import aioxmpp.callbacks


class InviteMode(enum.Enum):
    DIRECT = 0
    MEDIATED = 1


# class AbstractConversationMember(metaclass=abc.ABCMeta):
#     """
#     Interface for a member in a conversation.

#     The JIDs of a member can be either bare or full. Both bare and full JIDs
#     can be used with the :class:`aioxmpp.PresenceClient` service to look up the
#     presence information.

#     .. autoattribute:: direct_jid

#     .. autoattribute:: conversation_jid

#     .. autoattribute:: root_conversation

#     .. automethod:: get_direct_conversation
#     """

#     @abc.abstractproperty
#     def direct_jid(self):
#         """
#         A :class:`aioxmpp.JID` which can be used to directly communicate with
#         the member.

#         May be :data:`None` if the direct JID is not known or has not been
#         explicitly requested for the conversation.
#         """

#     @abc.abstractproperty
#     def conversation_jid(self):
#         """
#         A :class:`~aioxmpp.JID` which can be used to communicate with the
#         member in the context of the conversation.
#         """

#     @abc.abstractproperty
#     def root_conversation(self):
#         """
#         The root conversation to which this member belongs.
#         """

#     def _not_implemented_error(self, what):
#         return NotImplementedError(
#             "{} not supported for this type of conversation".format(what)
#         )

#     @asyncio.coroutine
#     def get_direct_conversation(self, *, prefer_direct=True):
#         """
#         Create or get and return a direct conversation with this member.

#         :param prefer_direct: Control which JID is used to start the
#                               conversation.
#         :type prefer_direct: :class:`bool`
#         :raises NotImplementedError: if a direct conversation is not supported
#                                      for the type of conversation to which the
#                                      member belongs.
#         :return: New or existing conversation with the conversation member.
#         :rtype: :class:`.AbstractConversation`

#         This may not be available for all conversation implementations. If it
#         is not available, :class:`NotImplementedError` is raised.
#         """
#         raise self._not_implemented_error("direct conversation")


class ConversationState(enum.Enum):
    """
    State of a conversation.

    .. note::

       The members of this enumeration closely mirror the states of :xep:`85`,
       with the addition of the internal :attr:`PENDING` state. The reason is
       that :xep:`85` is a Final Standard and is state-of-the-art for
       conversation states in XMPP.

    .. attribute:: PENDING

       The conversation has been created, possibly automatically, and the
       application has not yet set the conversation state.

    .. attribute:: ACTIVE

       .. epigraph::

          User accepts an initial content message, sends a content message,
          gives focus to the chat session interface (perhaps after being
          inactive), or is otherwise paying attention to the conversation.

          -- from :xep:`85`

    .. attribute:: INACTIVE

       .. epigraph::

          User has not interacted with the chat session interface for an
          intermediate period of time (e.g., 2 minutes).

          -- from :xep:`85`

    .. attribute:: GONE

       .. epigraph::

          User has not interacted with the chat session interface, system, or
          device for a relatively long period of time (e.g., 10 minutes).

          -- from :xep:`85`

    .. attribute:: COMPOSING

       .. epigraph::

          User is actively interacting with a message input interface specific
          to this chat session (e.g., by typing in the input area of a chat
          window).

          -- from :xep:`85`

    .. attribute:: PAUSED

       .. epigraph::

          User was composing but has not interacted with the message input
          interface for a short period of time (e.g., 30 seconds).

          -- from :xep:`85`

    When any of the above states is entered, a notification is sent out to the
    participants of the conversation.
    """

    PENDING = 0
    ACTIVE = 1
    INACTIVE = 2
    GONE = 3
    COMPOSING = 4
    PAUSED = 5


class AbstractConversationMember(metaclass=abc.ABCMeta):
    def __init__(self,
                 conversation_jid,
                 is_self):
        super().__init__()
        self._conversation_jid = conversation_jid
        self._is_self = is_self

    @property
    def direct_jid(self):
        return None

    @property
    def conversation_jid(self):
        return self._conversation_jid

    @property
    def is_self(self):
        return self._is_self


class AbstractConversation(metaclass=abc.ABCMeta):
    """
    Interface for a conversation.

    Signals:

    .. signal:: on_message_received(msg, member)

       A message has been received within the conversation.

       :param msg: Message which was received.
       :type msg: :class:`aioxmpp.Message`
       :param member: The member object of the sender.
       :type member: :class:`.AbstractConversationMember`

    .. signal:: on_state_changed(member, new_state, msg)

       The conversation state of a member has changed.

       :param member: The member object of the member whose state changed.
       :type member: :class:`.AbstractConversationMember`
       :param new_state: The new conversation state of the member.
       :type new_state: :class:`~.ConversationState`
       :param msg: The stanza which conveyed the state change.
       :type msg: :class:`aioxmpp.Message`

       This signal also fires for state changes of the local occupant. The
       exact point at which this signal fires for the local occupant is
       determined by the implementation.

    Properties:

    .. autoattribute:: members

    .. autoattribute:: me

    Methods:

    .. automethod:: send_message

    .. automethod:: send_message_tracked

    .. automethod:: kick

    .. automethod:: ban

    .. automethod:: invite

    .. automethod:: set_topic

    .. automethod:: leave

    Interface solely for subclasses:

    .. attribute:: _client

       The `client` as passed to the constructor.

    """

    on_message_received = aioxmpp.callbacks.Signal()
    on_state_changed = aioxmpp.callbacks.Signal()

    def __init__(self, service, parent=None, **kwargs):
        super().__init__(**kwargs)
        self._service = service
        self._client = service.client
        self.__parent = parent

    def _not_implemented_error(self, what):
        return NotImplementedError(
            "{} not supported for this type of conversation".format(what)
        )

    @property
    def parent(self):
        """
        The conversation to which this conversation belongs. Read-only.

        When the parent is closed, the sub-conversations are also closed.
        """
        return self.__parent

    @abc.abstractproperty
    def members(self):
        """
        An iterable of members of this conversation.
        """

    @abc.abstractproperty
    def me(self):
        """
        The member representing the local member.
        """

    @asyncio.coroutine
    def send_message(self, body):
        """
        Send a message to the conversation.

        :param body: The message body.

        The default implementation simply calls :meth:`send_message_tracked`
        and immediately cancels the tracking object.

        Subclasses may override this method with a more specialised
        implementation. Subclasses which do not provide tracked message sending
        **must** override this method to provide untracked message sending.
        """
        tracker = yield from self.send_message_tracked(body)
        tracker.cancel()

    @abc.abstractmethod
    @asyncio.coroutine
    def send_message_tracked(self, body, *, timeout=None):
        """
        Send a message to the conversation with tracking.

        :param body: The message body.
        :param timeout: Timeout for the tracking.
        :type timeout: :class:`numbers.RealNumber`, :class:`datetime.timedelta`
                       or :data:`None`
        :raise NotImplementedError: if tracking is not implemented

        Tracking may not be supported by all implementations, and the degree of
        support varies with implementation. Please check the documentation
        of the respective subclass.

        `timeout` is the number of seconds (or a :class:`datetime.timedelta`
        object which defines the timespan) after which the tracking expires and
        enters :attr:`.tracking.MessageState.TIMED_OUT` state if no response
        has been received in the mean time. If `timeout` is set to
        :data:`None`, the tracking never expires.

        .. warning::

           Active tracking objects consume memory for storing the state. It is
           advisable to either set a `timeout` or
           :meth:`.tracking.MessageTracker.cancel` the tracking from the
           application at some point to prevent degration of performance and
           running out of memory.

        """

    @asyncio.coroutine
    def kick(self, member):
        """
        Kick a member from a conversation.
        """
        raise self._not_implemented_error("kicking occupants")

    @asyncio.coroutine
    def ban(self, member, *, request_kick=True):
        """
        Ban a member from re-joining a conversation.

        If `request_kick` is :data:`True`, it is ensured that the member is
        kicked from the conversation, too.
        """
        raise self._not_implemented_error("banning members")

    @asyncio.coroutine
    def invite(self, jid, *,
               preferred_mode=InviteMode.DIRECT,
               allow_upgrade=False):
        """
        Invite another entity to the conversation.

        Return the new conversation object to use. In many cases, this will
        simply be the current conversation object, but in some cases (e.g. when
        someone is invited to a one-on-one conversation), a new conversation
        must be created and used.

        If `allow_upgrade` is false and a new conversation would be needed to
        invite an entity, :class:`ValueError` is raised.
        """
        raise self._not_implemented_error("inviting entities")

    @asyncio.coroutine
    def set_topic(self, new_topic):
        """
        Change the (possibly publicly) visible topic of the conversation.
        """
        raise self._not_implemented_error("changing the topic")

    @abc.abstractmethod
    @asyncio.coroutine
    def leave(self):
        """
        Leave the conversation.

        The base implementation calls
        :meth:`.AbstractConversationService._conversation_left` and must be
        called after all other preconditions for a leave have completed.
        """
        self._service._conversation_left(self)


class AbstractConversationService(metaclass=abc.ABCMeta):
    on_conversation_new = aioxmpp.callbacks.Signal()
    on_conversation_left = aioxmpp.callbacks.Signal()

    @abc.abstractmethod
    def _conversation_left(self, c):
        """
        Called by :class:`AbstractConversation` after the conversation has been
        left by the client.
        """
