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
    """
    Represent different possible modes for sending an invitation.

    .. attribute:: DIRECT

       The invitation is sent directly to the invitee, without going through a
       service specific to the conversation.

    .. attribute:: MEDIATED

       The invitation is sent indirectly through a service which is providing
       the conversation. Advantages of using this mode include most notably
       that the service can automatically add the invitee to the list of
       allowed participants in configurations where such restrictions exist (or
       deny the request if the inviter does not have the permissions to do so).
    """

    DIRECT = 0
    MEDIATED = 1


class ConversationFeature(enum.Enum):
    """
    Represent individual features of a :term:`Conversation` of a
    :term:`Conversation Implementation`.

    .. seealso::

       The :attr:`.AbstractConversation.features` provides a set of features
       offered by a specific :term:`Conversation`.

    .. attribute:: BAN

       Allows use of :meth:`~.AbstractConversation.ban`.

    .. attribute:: BAN_WITH_KICK

       Explicit support for setting the `request_kick` argument to :data:`True`
       in :meth:`~.AbstractConversation.ban`.

    .. attribute:: INVITE

       Allows use of :meth:`~.AbstractConversation.invite`.

    .. attribute:: INVITE_DIRECT

       Explicit support for the :attr:`~.InviteMode.DIRECT` invite mode when
       calling :meth:`~.AbstractConversation.invite`.

    .. attribute:: INVITE_DIRECT_CONFIGURE

       Explicit support for configuring the conversation to allow the invitee
       to join when using :attr:`~.InviteMode.DIRECT` with
       :meth:`~.AbstractConversation.invite`.

    .. attribute:: INVITE_MEDIATED

       Explicit support for the :attr:`~.InviteMode.MEDIATED` invite mode when
       calling :meth:`~.AbstractConversation.invite`.

    .. attribute:: INVITE_UPGRADE

       Explicit support and requirement for `allow_upgrade` when
       calling :meth:`~.AbstractConversation.invite`.

    .. attribute:: KICK

       Allows use of :meth:`~.AbstractConversation.kick`.

    .. attribute:: LEAVE

       Allows use of :meth:`~.AbstractConversation.leave`.

    .. attribute:: SEND_MESSAGE

       Allows use of :meth:`~.AbstractConversation.send_message`.

    .. attribute:: SEND_MESSAGE_TRACKED

       Allows use of :meth:`~.AbstractConversation.send_message_tracked`.

    .. attribute:: SET_NICK

       Allows use of :meth:`~.AbstractConversation.set_nick`.

    .. attribute:: SET_NICK_OF_OTHERS

       Explicit support for changing the nickname of other members when calling
       :meth:`~.AbstractConversation.set_nick`.

    .. attribute:: SET_TOPIC

       Allows use of :meth:`~.AbstractConversation.set_topic`.

    """

    BAN = 'ban'
    BAN_WITH_KICK = 'ban-with-kick'
    INVITE = 'invite'
    INVITE_DIRECT = 'invite-direct'
    INVITE_DIRECT_CONFIGURE = 'invite-direct-configure'
    INVITE_MEDIATED = 'invite-mediated'
    INVITE_UPGRADE = 'invite-upgrade'
    KICK = 'kick'
    LEAVE = 'leave'
    SEND_MESSAGE = 'send-message'
    SEND_MESSAGE_TRACKED = 'send-message-tracked'
    SET_TOPIC = 'set-topic'
    SET_NICK = 'set-nick'
    SET_NICK_OF_OTHERS = 'set-nick-of-others'


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
    """
    Represent a member in a :class:`~.AbstractConversation`.

    While all :term:`implementations <Conversation Implementation>` will have
    their own additional attributes, the following attributes must exist on
    all subclasses:

    .. autoattribute:: conversation_jid

    .. autoattribute:: direct_jid

    .. autoattribute:: is_self

    .. autoattribute:: uid
    """

    def __init__(self,
                 conversation_jid,
                 is_self):
        super().__init__()
        self._conversation_jid = conversation_jid
        self._is_self = is_self

    @property
    def direct_jid(self):
        """
        If available, this is the :class:`~aioxmpp.JID` address of the member
        for direct contact, outside of the conversation. It is independent of
        the conversation itself.

        If not available, this attribute reads as :data:`None`.
        """
        return None

    @property
    def conversation_jid(self):
        """
        The :class:`~aioxmpp.JID` of the conversation member relative to the
        conversation.
        """
        return self._conversation_jid

    @property
    def is_self(self):
        """
        True if the member refers to ourselves in the conversation, false
        otherwise.
        """
        return self._is_self

    @abc.abstractproperty
    def uid(self) -> bytes:
        """
        This is a unique ID for the occupant. It can be used across sessions
        and restarts to assert equality between occupants. It is guaranteed
        to be equal if and only if the entity is the same (up to a uncertainty
        caused by the limited length of the unique ID, somewhere in the order
        of ``2**(-120)``).

        The identifier is always a :class:`bytes` and **must** be treated as
        opaque by users. The only guarantee which is given is that its length
        will be less than 4096 bytes.
        """


class AbstractConversation(metaclass=abc.ABCMeta):
    """
    Interface for a conversation.

    .. note::

       All signals may receive additional keyword arguments depending on the
       specific subclass implementing them. Handlers connected to the signals
       **must** support arbitrary keyword arguments.

       To support future extensions to the base specification, subclasses must
       prefix all keyword argument names with a common, short prefix which ends
       with an underscore. For example, a MUC implementation could use
       ``muc_presence``.

       Future extensions to the base class will use either names without
       underscores or the ``base_`` prefix.

    .. note::

       In the same spirit, methods defined on subclasses should use the same
       prefix. However, the base class does not guarantee that it won’t use
       names with underscores in future extensions.

       To prevent collisions, subclasses should avoid the use of prefixes which
       are verbs in the english language.

    Signals:

    .. note::

        The `member` argument common to many signals is never :data:`None` and
        always an instance of a subclass of
        :class:`~.AbstractConversationMember`. However, the `member` may not be
        part of the :attr:`members` of the conversation. For example, it may be
        the :attr:`service_member` object which is never part of
        :attr:`members`. Other cases where a non-member is passed as `member`
        may exist depending on the conversation subclass.

    .. signal:: on_message(msg, member, source, tracker=None, **kwargs)

       A message occurred in the conversation.

       :param msg: Message which was received.
       :type msg: :class:`aioxmpp.Message`
       :param member: The member object of the sender.
       :type member: :class:`.AbstractConversationMember`
       :param source: How the message was acquired
       :type source: :class:`~.MessageSource`
       :param tracker: A message tracker which tracks an outbound message.
       :type tracker: :class:`aioxmpp.tracking.MessageTracker`

       This signal is emitted on the following events:

       * A message was sent to the conversation and delivered directly to us.
         This is the classic case of "a message was received". In this case,
         `source` is :attr:`~.MessageSource.STREAM` and `member` is the
         :class:`~.AbstractConversationMember` of the originator.

       * A message was sent from this client. This is the classic case of "a
         message was sent". In this case, `source` is
         :attr:`~.MessageSource.STREAM` and `member` refers to ourselves.

       * A carbon-copy of a message received by another resource of our account
         which belongs to this conversation was received. `source` is
         :attr:`~.MessageSource.CARBONS` and `member` is the
         :class:`~.AbstractConversationMember` of the originator.

       * A carbon-copy of a message sent by another resource of our account was
         sent to this conversation. In this case, `source` is
         :attr:`~.MessageSource.CARBONS` and `member` refers to ourselves.

       Often, you don’t need to distinguish between carbon-copied and
       non-carbon-copied messages.

       All messages which are not handled otherwise (and for example dispatched
       as :meth:`on_state_changed` signals) are dispatched to this event. This
       may include messages not understood and/or which carry no textual
       payload.

       `tracker` is set only for messages sent by the local member. If a
       message is sent from the client without tracking, `tracker` is
       :data:`None`; otherwise, the `tracker` is always set, even for messages
       sent by other clients. It depends on the conversation implementation as
       well as timing in which state a tracker is at the time the event is
       emitted.

    .. signal:: on_state_changed(member, new_state, msg, **kwargs)

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

    .. signal:: on_presence_changed(member, resource, presence, **kwargs)

       The presence state of a member has changed.

       :param member: The member object of the affected member.
       :type member: :class:`~.AbstractConversationMember`
       :param resource: The resource of the member which changed presence.
       :type resource: :class:`str` or :data:`None`
       :param presence: The presence stanza
       :type presence: :class:`aioxmpp.Presence`

       If the `presence` stanza affects multiple resources, `resource` holds
       the affected resource and the event is emitted once per affected
       resource.

       However, the `presence` stanza affects only a single resource,
       `resource` is :data:`None`; the affected resource can be extracted from
       the :attr:`~.StanzaBase.from_` of the `presence` stanza in that case.
       This is to help implementations to know whether a bunch of resources was
       shot offline by a single presence (`resource` is not :data:`None`), e.g.
       due to an error or whether a single resource went offline by itself.
       Implementations may want to only show the former case.

       .. note::

          In some implementations, unavailable presence implies that a
          participant leaves the room, in which case :meth:`on_leave` is
          emitted instead.

    .. signal:: on_nick_changed(member, old_nick, new_nick, **kwargs)

       The nickname of a member has changed

       :param member: The member object of the member whose nick has changed.
       :type member: :class:`~.AbstractConversationMember`
       :param old_nick: The old nickname of the member.
       :type old_nick: :class:`str` or :data:`None`
       :param new_nick: The new nickname of the member.
       :type new_nick: :class:`str`

       The new nickname is already set in the `member` object, if the `member`
       object has an accessor for the nickname.

       In some cases, `old_nick` may be :data:`None`. These cases include those
       where it is not trivial for the protocol to actually determine the old
       nickname or where no nickname was set before.

    .. signal:: on_topic_changed(member, new_topic, **kwargs)

        The topic of the conversation has changed.

        :param member: The member object who changed the topic.
        :type member: :class:`~.AbstractConversationMember`
        :param new_topic: The new topic of the conversation.
        :type new_topic: :class:`.LanguageMap`

    .. signal:: on_uid_changed(member, old_uid, **kwargs)

        This rare signal notifies that the
        :attr:`~.AbstractConversationMember.uid` of a member has changed.

        :param member: The member object for which the UID has changed.
        :type member: :class:`~.AbstractConversationMember`
        :param old_uid: The old UID of the member.
        :type old_uid: :class:`bytes`

        The new uid is already available at the members
        :attr:`~.AbstractConversationMember.uid` attribute.

        This signal can only fire for multi-user conversations where the
        visibility of identifying information changes. In many cases, it will
        be irrelevant for the application, but for some use-cases it might be
        important to be able to re-write historical messages to use the new
        uid.

    .. signal:: on_enter()

        The conversation was entered.

        This event is emitted up to once for a :class:`AbstractConversation`.

        One of :meth:`on_enter` and :meth:`on_failure` is emitted exactly
        once for each :class:`AbstractConversation` instance.

        .. seealso::

            :func:`aioxmpp.callbacks.first_signal` can be used nicely to await
            the completion of entering a conversation::

                conv = ... # let this be your conversation
                await first_signal(conv.on_enter, conv.on_failure)
                # await first_signal() will either return None (success) or
                # raise the exception passed to :meth:`on_failure`.

        .. note::

            This and :meth:`on_failure` are the only signals which **must not**
            receive keyword arguments, so that they continue to work with
            :attr:`.AdHocSignal.AUTO_FUTURE` and
            :func:`~.callbacks.first_signal`.

        .. versionadded:: 0.10

    .. signal:: on_failure(exc)

        The conversation could not be entered.

        :param exc: The exception which caused the operation to fail.
        :type exc: :class:`Exception`

        Often, `exc` will be a :class:`aioxmpp.errors.XMPPError` indicating
        an error emitted from an involved server, such as permission problems,
        conflicts or non-existent peers.

        This signal can only be emitted instead of :meth:`on_enter` and not
        after the room has been entered. If the conversation is terminated
        due to a remote cause at a later point, :meth:`on_exit` is used.

        One of :meth:`on_enter` and :meth:`on_failure` is emitted exactly
        once for each :class:`AbstractConversation` instance.

        .. note::

            This and :meth:`on_failure` are the only signals which **must not**
            receive keyword arguments, so that they continue to work with
            :attr:`.AdHocSignal.AUTO_FUTURE` and
            :func:`~.callbacks.first_signal`.

        .. versionadded:: 0.10

    .. signal:: on_join(member, **kwargs)

       A new member has joined the conversation.

       :param member: The member object of the new member.
       :type member: :class:`~.AbstractConversationMember`

       When this signal is called, the `member` is already included in the
       :attr:`members`.

    .. signal:: on_leave(member, **kwargs)

       A member has left the conversation.

       :param member: The member object of the previous member.
       :type member: :class:`~.AbstractConversationMember`

       When this signal is called, the `member` has already been removed from
       the :attr:`members`.

    .. signal:: on_exit(**kwargs)

       The local user has left the conversation.

       When this signal fires, the conversation is defunct in the sense that it
       cannot be used to send messages anymore. A new conversation needs to be
       started.

    Properties:

    .. autoattribute:: features

    .. autoattribute:: jid

    .. autoattribute:: members

    .. autoattribute:: me

    .. autoattribute:: service_member

    Methods:

    .. note::

       See :attr:`features` for discovery of support for individual methods at
       a given conversation instance.

    .. automethod:: ban

    .. automethod:: invite

    .. automethod:: kick

    .. automethod:: leave

    .. automethod:: send_message

    .. automethod:: send_message_tracked

    .. automethod:: set_nick

    .. automethod:: set_topic

    Interface solely for subclasses:

    .. attribute:: _client

       The `client` as passed to the constructor.

    """

    on_message = aioxmpp.callbacks.Signal()
    on_state_changed = aioxmpp.callbacks.Signal()
    on_presence_changed = aioxmpp.callbacks.Signal()
    on_join = aioxmpp.callbacks.Signal()
    on_leave = aioxmpp.callbacks.Signal()
    on_exit = aioxmpp.callbacks.Signal()
    on_failed = aioxmpp.callbacks.Signal()
    on_nick_changed = aioxmpp.callbacks.Signal()
    on_enter = aioxmpp.callbacks.Signal()
    on_failure = aioxmpp.callbacks.Signal()
    on_topic_changed = aioxmpp.callbacks.Signal()

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

    @abc.abstractproperty
    def jid(self):
        """
        The address of the conversation.
        """

    @property
    def service_member(self):
        """
        The member representing the service on which the conversation is
        hosted, if available.

        This is never included in :attr:`members`. It may be used as member
        argument in events to make it clear that the message originates from
        the service and not an unknown occupant.

        This may be :data:`None`.

        .. versionadded:: 0.10
        """

    @property
    def features(self):
        """
        A set of features supported by this :term:`Conversation`.

        The members of the set are usually drawn from the
        :class:`~.ConversationFeature` :mod:`enumeration <enum>`;
        :term:`Conversation  Implementations <Conversation Implementation>` are
        free to add custom elements from other enumerations to this set.

        Unless stated otherwise, the methods of :class:`~.AbstractConversation`
        and its subclasses always may throw one of the following exceptions,
        **unless** support for those methods is explicitly stated with an
        appropriate :class:`~.ConversationFeature` member in the
        :attr:`features`.

        * :class:`NotImplementedError` if the :term:`Conversation
          Implementation` does not support the method at all.
        * :class:`RuntimeError` if the server does not support the method.
        * :class:`aioxmpp.XMPPCancelError` with ``feature-not-implemented``
          condition.

        *If* support for the method is claimed in :attr:`features`, these
        exceptions **must not** be raised (for the given reason; of course, a
        method may still raise an :class:`aioxmpp.XMPPCancelError` due for
        other conditions such as ``item-not-found``).
        """
        return frozenset()

    def send_message(self, body):
        """
        Send a message to the conversation.

        :param msg: The message to send.
        :type msg: :class:`aioxmpp.Message`
        :return: The stanza token obtained from sending.
        :rtype: :class:`~aioxmpp.stream.StanzaToken`

        The default implementation simply calls :meth:`send_message_tracked`
        and immediately cancels the tracking object, returning only the stanza
        token.

        There is no need to provide proper address attributes on `msg`.
        Implementations will override those attributes with the values
        appropriate for the conversation. Some implementations may allow the
        user to choose a :attr:`~aioxmpp.Message.type_`, but others may simply
        stamp it over.

        Subclasses may override this method with a more specialised
        implementation. Subclasses which do not provide tracked message sending
        **must** override this method to provide untracked message sending.

        .. seealso::

           The corresponding feature is
           :attr:`.ConversationFeature.SEND_MESSAGE`. See :attr:`features` for
           details.

        """
        token, tracker = self.send_message_tracked(body)
        tracker.cancel()
        return token

    @abc.abstractmethod
    def send_message_tracked(self, msg, *, timeout=None):
        """
        Send a message to the conversation with tracking.

        :param msg: The message to send.
        :type msg: :class:`aioxmpp.Message`
        :param timeout: Timeout for the tracking.
        :type timeout: :class:`numbers.RealNumber`, :class:`datetime.timedelta`
                       or :data:`None`
        :raise NotImplementedError: if tracking is not implemented
        :return: The stanza token obtained from sending and the
            :class:`aioxmpp.tracking.MessageTracker` tracking the delivery.
        :rtype: :class:`~aioxmpp.stream.StanzaToken`,
            :class:`~aioxmpp.tracking.MessageTracker`

        There is no need to provide proper address attributes on `msg`.
        Implementations will override those attributes with the values
        appropriate for the conversation. Some implementations may allow the
        user to choose a :attr:`~aioxmpp.Message.type_`, but others may simply
        stamp it over.

        Tracking may not be supported by all implementations, and the degree of
        support varies with implementation. Please check the documentation
        of the respective subclass.

        `timeout` is the number of seconds (or a :class:`datetime.timedelta`
        object which defines the timespan) after which the tracking expires and
        is closed if no response has been received in the mean time. If
        `timeout` is set to :data:`None`, the tracking never expires.

        .. warning::

            Read :ref:`api-tracking-memory`.

        .. seealso::

           The corresponding feature is
           :attr:`.ConversationFeature.SEND_MESSAGE_TRACKED`. See
           :attr:`features` for details.

        """

    async def kick(self, member, reason=None):
        """
        Kick a member from the conversation.

        :param member: The member to kick.
        :param reason: A reason to show to the members of the conversation
            including the kicked member.
        :type reason: :class:`str`
        :raises aioxmpp.errors.XMPPError: if the server returned an error for
                                          the kick command.

        .. seealso::

           The corresponding feature is
           :attr:`.ConversationFeature.KICK`. See :attr:`features` for details.
        """
        raise self._not_implemented_error("kicking members")

    async def ban(self, member, reason=None, *, request_kick=True):
        """
        Ban a member from re-joining the conversation.

        :param member: The member to ban.
        :param reason: A reason to show to the members of the conversation
            including the banned member.
        :type reason: :class:`str`
        :param request_kick: A flag indicating that the member should be
            removed from the conversation immediately, too.
        :type request_kick: :class:`bool`

        If `request_kick` is true, the implementation attempts to kick the
        member from the conversation, too, if that does not happen
        automatically. There is no guarantee that the member is not removed
        from the conversation even if `request_kick` is false.

        Additional features:

        :attr:`~.ConversationFeature.BAN_WITH_KICK`
           If `request_kick` is true, the member is kicked from the
           conversation.

        .. seealso::

           The corresponding feature for this method is
           :attr:`.ConversationFeature.BAN`. See :attr:`features` for details
           on the semantics of features.
        """
        raise self._not_implemented_error("banning members")

    async def invite(self, address, text=None, *,
                     mode=InviteMode.DIRECT,
                     allow_upgrade=False):
        """
        Invite another entity to the conversation.

        :param address: The address of the entity to invite.
        :type address: :class:`aioxmpp.JID`
        :param text: A reason/accompanying text for the invitation.
        :param mode: The invitation mode to use.
        :type mode: :class:`~.im.InviteMode`
        :param allow_upgrade: Whether to allow creating a new conversation to
            satisfy the invitation.
        :type allow_upgrade: :class:`bool`
        :raises NotImplementedError: if the requested `mode` is not supported
        :raises ValueError: if `allow_upgrade` is false, but a new conversation
            is required.
        :return: The stanza token for the invitation and the possibly new
            conversation object
        :rtype: tuple of :class:`~.StanzaToken` and
            :class:`~.AbstractConversation`

        .. note::

            Even though this is a coroutine, it returns a stanza token. The
            coroutine-ness may be needed to generate the invitation in the
            first place. Sending the actual invitation is done non-blockingly
            and the stanza token for that is returned. To wait until the
            invitation has been sent, unpack the stanza token from the result
            and await it.

        Return the new conversation object to use. In many cases, this will
        simply be the current conversation object, but in some cases (e.g. when
        someone is invited to a one-on-one conversation), a new conversation
        must be created and used.

        If `allow_upgrade` is false and a new conversation would be needed to
        invite an entity, :class:`ValueError` is raised.

        Additional features:

        :attr:`~.ConversationFeature.INVITE_DIRECT`
           Support for :attr:`~.im.InviteMode.DIRECT` mode.

        :attr:`~.ConversationFeature.INVITE_DIRECT_CONFIGURE`
           If a direct invitation is used, the conversation will be configured
           to allow the invitee to join before the invitation is sent. This may
           fail with a :class:`aioxmpp.errors.XMPPError`, in which case the
           error is re-raised and the invitation not sent.

        :attr:`~.ConversationFeature.INVITE_MEDIATED`
           Support for :attr:`~.im.InviteMode.MEDIATED` mode.

        :attr:`~.ConversationFeature.INVITE_UPGRADE`
           If `allow_upgrade` is :data:`True`, an upgrade will be performed and
           a new conversation is returned. If `allow_upgrade` is :data:`False`,
           the invite will fail.

        .. seealso::

           The corresponding feature for this method is
           :attr:`.ConversationFeature.INVITE`. See :attr:`features` for
           details on the semantics of features.
        """
        raise self._not_implemented_error("inviting entities")

    async def set_nick(self, new_nickname):
        """
        Change our nickname.

        :param new_nickname: The new nickname for the member.
        :type new_nickname: :class:`str`
        :raises ValueError: if the nickname is not a valid nickname

        Sends the request to change the nickname and waits for the request to
        be sent.

        There is no guarantee that the nickname change will actually be
        applied; listen to the :meth:`on_nick_changed` event.

        Implementations may provide a different method which provides more
        feedback.

        .. seealso::

           The corresponding feature for this method is
           :attr:`.ConversationFeature.SET_NICK`. See :attr:`features` for
           details on the semantics of features.

        """
        raise self._not_implemented_error("changing the nickname")

    async def set_topic(self, new_topic):
        """
        Change the (possibly publicly) visible topic of the conversation.

        :param new_topic: The new topic for the conversation.
        :type new_topic: :class:`str`

        Sends the request to change the topic and waits for the request to
        be sent.

        There is no guarantee that the topic change will actually be
        applied; listen to the :meth:`on_topic_chagned` event.

        Implementations may provide a different method which provides more
        feedback.

        .. seealso::

           The corresponding feature for this method is
           :attr:`.ConversationFeature.SET_TOPIC`. See :attr:`features` for
           details on the semantics of features.


        """
        raise self._not_implemented_error("changing the topic")

    async def leave(self):
        """
        Leave the conversation.

        .. seealso::

           The corresponding feature is
           :attr:`.ConversationFeature.LEAVE`. See :attr:`features` for
           details.
        """


class AbstractConversationService(metaclass=abc.ABCMeta):
    """
    Abstract base class for
    :term:`Conversation Services <Conversation Service>`.

    Useful implementations:

    .. autosummary::

        aioxmpp.im.p2p.Service
        aioxmpp.muc.MUCClient

    In general, conversation services should provide a method (*not* a
    coroutine method) to start a conversation using the service. That method
    should return the fresh :class:`~.AbstractConversation` object immediately
    and start possibly needed background tasks to actually initiate the
    conversation. The caller should use the
    :meth:`~.AbstractConversation.on_enter` and
    :meth:`~.AbstractConversation.on_failure` signals to be notified of the
    result of the join operation.

    Signals:

    .. signal:: on_conversation_new(conversation)

        Fires when a new conversation is created in the service.

        :param conversation: The new conversation.
        :type conversation: :class:`AbstractConversation`

        .. seealso::

            :meth:`.ConversationService.on_conversation_added`
                is a signal shared among all :term:`Conversation
                Implementations <Conversation Implementation>` which gets
                emitted whenever a new conversation is added. If you need all
                conversations, that is the signal to listen for.

    .. signal:: on_spontaneous_conversation(conversation)

        Like :meth:`on_conversation_new`, but is only emitted for conversations
        which are created without local interaction.

        :param conversation: The new conversation.
        :type conversation: :class:`AbstractConversation`

        .. versionadded:: 0.10

    """

    on_conversation_new = aioxmpp.callbacks.Signal()
    on_spontaneous_conversation = aioxmpp.callbacks.Signal()
