########################################################################
# File name: service.py
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
import asyncio
import functools
import uuid

from datetime import datetime
from enum import Enum

import aioxmpp.callbacks
import aioxmpp.disco
import aioxmpp.forms
import aioxmpp.service
import aioxmpp.stanza
import aioxmpp.structs
import aioxmpp.tracking
import aioxmpp.im.conversation
import aioxmpp.im.dispatcher
import aioxmpp.im.p2p
import aioxmpp.im.service
import aioxmpp.utils

from aioxmpp.utils import namespaces

from . import self_ping
from . import xso as muc_xso


def _extract_one_pair(body):
    """
    Extract one language-text pair from a :class:`~.LanguageMap`.

    This is used for tracking.
    """
    if not body:
        return None, None

    try:
        return None, body[None]
    except KeyError:
        return min(body.items(), key=lambda x: x[0])


class LeaveMode(Enum):
    """
    The different reasons for a user to leave or be removed from MUC.

    .. attribute:: DISCONNECTED

       The local client disconnected. This only occurs in events referring to
       the local entity.

    .. attribute:: SYSTEM_SHUTDOWN

       The remote server shut down.

    .. attribute:: NORMAL

       The leave was initiated by the occupant themselves and was not a kick or
       ban.

    .. attribute:: KICKED

       The user was kicked from the room.

    .. attribute:: AFFILIATION_CHANGE

       Changes in the affiliation of the user caused them to be removed.

    .. attribute:: MODERATION_CHANGE

       Changes in the moderation settings of the room caused the user to be
       removed.

    .. attribute:: BANNED

       The user was banned from the room.

    .. attribute:: ERROR

        The user was removed due to an error when communicating with the client
        or the users server.

        Not all servers support this. If not supported by the server, one will
        typically see a :attr:`KICKED` status code with an appropriate
        :attr:`~.Presence.status` message.

        .. versionadded:: 0.10
    """

    DISCONNECTED = -2
    SYSTEM_SHUTDOWN = -1
    NORMAL = 0
    KICKED = 1
    AFFILIATION_CHANGE = 3
    MODERATION_CHANGE = 4
    BANNED = 5
    ERROR = 6


class _OccupantDiffClass(Enum):
    UNIMPORTANT = 0
    NICK_CHANGED = 1
    LEFT = 2


class Occupant(aioxmpp.im.conversation.AbstractConversationMember):
    """
    A tracking object to track a single occupant in a :class:`Room`.

    .. seealso::

        :class:`~.AbstractConversationMember`
            for additional notes on some of the pre-defined attributes.

    .. autoattribute:: direct_jid

    .. autoattribute:: conversation_jid

    .. autoattribute:: uid

    .. autoattribute:: nick

    .. attribute:: presence_state

       The :class:`~.PresenceState` of the occupant.

    .. attribute:: presence_status

       The :class:`~.LanguageMap` holding the presence status text of the
       occupant.

    .. attribute:: affiliation

       The affiliation of the occupant with the room. This may be :data:`None`
       with faulty MUC implementations.

    .. attribute:: role

       The current role of the occupant within the room. This may be
       :data:`None` with faulty MUC implementations.

    """

    def __init__(self,
                 occupantjid,
                 is_self,
                 presence_state=aioxmpp.structs.PresenceState(available=True),
                 presence_status={},
                 affiliation=None,
                 role=None,
                 jid=None):
        super().__init__(occupantjid, is_self)
        self.presence_state = presence_state
        self.presence_status = aioxmpp.structs.LanguageMap(presence_status)
        self.affiliation = affiliation
        self.role = role
        self._direct_jid = jid
        if jid is None:
            self._uid = b"urn:uuid:" + uuid.uuid4().bytes
        else:
            self._set_uid_from_direct_jid(self._direct_jid)

            if not self._direct_jid.is_bare:
                raise ValueError("the jid argument must be a bare JID")

    def _set_uid_from_direct_jid(self, jid):
        self._uid = b"xmpp:" + str(jid.bare()).encode("utf-8")

    @property
    def direct_jid(self):
        """
        The real :class:`~aioxmpp.JID` of the occupant.

        If the MUC is anonymous and we do not have the permission to see the
        real JIDs of occupants, this is :data:`None`.
        """
        return self._direct_jid

    @property
    def nick(self):
        """
        The nickname of the occupant.
        """
        return self.conversation_jid.resource

    @property
    def uid(self):
        """
        This is either a random identifier if the real JID of the occupant is
        not known, or an identifier derived from the real JID of the occupant.

        Note that as per the semantics of the :attr:`uid`, users **must** treat
        it as opaque.

        .. seealso::

            :class:`~aioxmpp.im.conversation.AbstractConversationMember.uid`
                Documentation of the attribute on the base class, with
                additional information on semantics.
        """
        return self._uid

    @classmethod
    def from_presence(cls, presence, is_self):
        try:
            item = presence.xep0045_muc_user.items[0]
        except (AttributeError, IndexError):
            affiliation = None
            if presence.type_ == aioxmpp.structs.PresenceType.UNAVAILABLE:
                role = "none"  # unavailable must be the "none" role
            else:
                role = None
            jid = None
        else:
            affiliation = item.affiliation
            role = item.role
            jid = item.bare_jid

        return cls(
            occupantjid=presence.from_,
            is_self=is_self,
            presence_state=aioxmpp.structs.PresenceState.from_stanza(presence),
            presence_status=aioxmpp.structs.LanguageMap(presence.status),
            affiliation=affiliation,
            role=role,
            jid=jid,
        )

    def update(self, other):
        if self.conversation_jid != other.conversation_jid:
            raise ValueError("occupant JID mismatch")
        self.presence_state = other.presence_state
        self.presence_status.clear()
        self.presence_status.update(other.presence_status)
        self.affiliation = other.affiliation or self.affiliation
        self.role = other.role or self.role
        if self._direct_jid is None and other.direct_jid is not None:
            self._set_uid_from_direct_jid(other.direct_jid)
        self._direct_jid = other.direct_jid or self._direct_jid

    def __repr__(self):
        return "<{}.{} occupantjid={!r} uid={!r} jid={!r}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self._conversation_jid,
            self._uid,
            self._direct_jid,
        )


class RoomState(Enum):
    """
    Enumeration which describes the state a :class:`~.muc.Room` is in.

    .. attribute:: JOIN_PRESENCE

        The room is in the process of being joined and the presence state
        transfer is going on.

    .. attribute:: HISTORY

        Presence state transfer has happened, but the room subject has not
        been received yet. This is where history replay messages are
        received.

        When entering this state, :attr:`~.muc.Room.muc_active` becomes true.

    .. attribute:: ACTIVE

        The join has completed, including history replay and receiving the
        subject.

    .. attribute:: DISCONNECTED

        The MUC is suspended or disconnected. If the MUC is disconnected,
        :attr:`~.muc.Room.muc_joined` will be false, too.
    """

    JOIN_PRESENCE = 0
    HISTORY = 1
    ACTIVE = 2
    DISCONNECTED = 3


class ServiceMember(aioxmpp.im.conversation.AbstractConversationMember):
    """
    A :class:`~aioxmpp.im.conversation.AbstractConversationMember` which
    represents a MUC service.

    .. versionadded:: 0.10

    Objects of this instance are used for the :attr:`Room.service_member`
    property of rooms.

    Aside from the mandatory conversation member attributes, the following
    attributes for compatibility with :class:`Occupant` are provided:

    .. autoattribute:: nick

    .. attribute:: presence_state
        :annotation: aioxmpp.structs.PresenceState(False)

        The presence state of the service. Always unavailable.

    .. attribute:: presence_status
        :annotation: {}

        The presence status of the service as :class:`~.LanguageMap`. Always
        empty.

    .. attribute:: affiliation
        :annotation: None

        The affiliation of the service. Always :data:`None`.

    .. attribute:: role
        :annotation: None

        The role of the service. Always :data:`None`.
    """

    def __init__(self, muc_address):
        super().__init__(muc_address, False)
        self.presence_state = aioxmpp.structs.PresenceState(False)
        self.presence_status = aioxmpp.structs.LanguageMap()
        self.affiliation = None
        self.role = None
        self._uid = b"xmpp:" + str(muc_address).encode("utf-8")

    @property
    def direct_jid(self):
        return self.conversation_jid

    @property
    def nick(self):
        return None

    @property
    def uid(self) -> bytes:
        return self._uid


class Room(aioxmpp.im.conversation.AbstractConversation):
    """
    :term:`Conversation` representing a single :xep:`45` Multi-User Chat.

    .. note::

        This is an implementation of :class:`~.AbstractConversation`. The
        members which do not carry the ``muc_`` prefix usually have more
        extensive documentation there. This documentation here only provides
        a short synopsis for those members plus the changes with respect to
        the base interface.

    .. versionchanged:: 0.9

        In 0.9, the :class:`Room` interface was re-designed to match
        :class:`~.AbstractConversation`.

    The following properties are provided:

    .. autoattribute:: features

    .. autoattribute:: jid

    .. autoattribute:: me

    .. autoattribute:: members

    .. autoattribute:: service_member

    These properties are specific to MUC:

    .. autoattribute:: muc_active

    .. autoattribute:: muc_joined

    .. autoattribute:: muc_state

    .. autoattribute:: muc_subject

    .. autoattribute:: muc_subject_setter

    .. attribute:: muc_autorejoin

       A boolean flag indicating whether this MUC is supposed to be
       automatically rejoined when the stream it is used gets destroyed and
       re-estabished.

    .. attribute:: muc_password

       The password to use when (re-)joining. If :attr:`autorejoin` is
       :data:`None`, this can be cleared after :meth:`on_enter` has been
       emitted.

    The following methods and properties provide interaction with the MUC
    itself:

    .. automethod:: ban

    .. automethod:: kick

    .. automethod:: leave

    .. automethod:: send_message

    .. automethod:: send_message_tracked

    .. automethod:: set_nick

    .. automethod:: set_topic

    .. automethod:: muc_request_voice

    .. automethod:: muc_set_role

    .. automethod:: muc_set_affiliation

    The interface provides signals for most of the rooms events. The following
    keyword arguments are used at several signal handlers (which is also noted
    at their respective documentation):

    `muc_actor` = :data:`None`
       The :class:`~.xso.UserActor` instance of the corresponding
       :class:`~.xso.UserExt`, describing which other occupant caused the
       event.

       Note that the `muc_actor` is in fact not a :class:`~.Occupant`.

    `muc_reason` = :data:`None`
       The reason text in the corresponding :class:`~.xso.UserExt`, which
       gives more information on why an action was triggered.

    .. note::

       Signal handlers attached to any of the signals below **must** accept
       arbitrary keyword arguments for forward compatibility. For details see
       the documentation on :class:`~.AbstractConversation`.

    .. signal:: on_enter(**kwargs)

        Emits when the initial room :class:`~.Presence` stanza for the
        local JID is received. This means that the join to the room is
        complete; the message history and subject are not transferred yet
        though.

        .. seealso::

            :meth:`on_muc_enter`
                is an extended version of this signal which contains additional
                MUC-specific information.

        .. versionchanged:: 0.10

            The :meth:`on_enter` signal does not receive any arguments anymore
            to make MUC comply with the :class:`AbstractConversation` spec.

    .. signal:: on_muc_enter(presence, occupant, *, muc_status_codes=set(), **kwargs)

        This is an extended version of :meth:`on_enter` which adds MUC-specific
        arguments.

        :param presence: The initial presence stanza.
        :param occupant: The :class:`Occupant` which will be used to track the
            local user.
        :param muc_status_codes: The set of status codes received in the
            initial join.
        :type muc_status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        .. versionadded:: 0.10

    .. signal:: on_message(msg, member, source, **kwargs)

        A message occurred in the conversation.

        :param msg: Message which was received.
        :type msg: :class:`aioxmpp.Message`
        :param member: The member object of the sender.
        :type member: :class:`.Occupant`
        :param source: How the message was acquired
        :type source: :class:`~.MessageSource`

        The notable specialities about MUCs compared to the base specification
        at :meth:`.AbstractConversation.on_message` are:

        * Carbons do not happen for MUC messages.
        * MUC Private Messages are not handled here; see :class:`MUCClient` for
          MUC PM details.
        * MUCs reflect messages; to make this as easy to handle as possible,
          reflected messages are **not** emitted via the :meth:`on_message`
          event **if and only if** they were sent with tracking (see
          :meth:`send_message_tracked`) and they were detected as reflection.

          See :meth:`send_message_tracked` for details and caveats on the
          tracking implementation.

        When **history replay** happens, since joins and leaves are not part of
        the history, it is not always possible to reason about the identity of
        the sender of a history message. To avoid possible spoofing attacks,
        the following caveats apply to the :class:`~.Occupant` objects handed
        as `member` during history replay:

        * Two identical :class:`~.Occupant` objects are only used *iff* the
          nickname *and* the actual address of the entity are equal. This
          implies that unless this client has the permission to see JIDs of
          occupants of the MUC, all :class:`~.Occupant` objects during history
          replay will be different instances.
        * If the nickname and the actual address of a message from history
          match, the current :class:`~.Occupant` object for the respective
          occupant is used.
        * :class:`~.Occupant` objects which are created for history replay are
          never part of :attr:`members`. They are only used to convey the
          information passed in the messages from the history replay, which
          would otherwise be inaccessible.

        .. seealso::

            :meth:`.AbstractConversation.on_message` for the full
            specification.

    .. signal:: on_presence_changed(member, resource, presence, **kwargs)

        The presence state of an occupant has changed.

        :param member: The member object of the affected member.
        :type member: :class:`Occupant`
        :param resource: The resource of the member which changed presence.
        :type resource: :class:`str` or :data:`None`
        :param presence: The presence stanza
        :type presence: :class:`aioxmpp.Presence`

        `resource` is always :data:`None` for MUCs and unavailable presence
        implies that the occupant left the room. In this case, only
        :meth:`on_leave` is emitted.

        .. seealso::

            :meth:`.AbstractConversation.on_presence_changed` for the full
            specification.

    .. signal:: on_nick_changed(member, old_nick, new_nick, *, muc_status_codes=set(), **kwargs)

        The nickname of an occupant has changed

        :param member: The occupant whose nick has changed.
        :type member: :class:`Occupant`
        :param old_nick: The old nickname of the member.
        :type old_nick: :class:`str` or :data:`None`
        :param new_nick: The new nickname of the member.
        :type new_nick: :class:`str`
        :param muc_status_codes: The set of status codes received in the leave
            notification.
        :type muc_status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        The new nickname is already set in the `member` object. Both `old_nick`
        and `new_nick` are not :data:`None`.

        .. seealso::

            :meth:`.AbstractConversation.on_nick_changed` for the full
            specification.

        .. versionchanged:: 0.10

            The `muc_status_codes` argument was added.

    .. signal:: on_topic_changed(member, new_topic, *, muc_nick=None, **kwargs)

        The topic of the conversation has changed.

        :param member: The member object who changed the topic.
        :type member: :class:`Occupant` or :data:`None`
        :param new_topic: The new topic of the conversation.
        :type new_topic: :class:`.LanguageMap`
        :param muc_nick: The nickname of the occupant who changed the topic.
        :type muc_nick: :class:`str`

        The `member` is matched by nickname. It is possible that the member is
        not in the room at the time the topic change is received (for example
        on a join).

        `muc_nick` is always the nickname of the entity who changed the topic.
        If the entity is currently not joined or has changed nick since the
        topic was set, `member` will be :data:`None`, but `muc_nick` is still
        the nickname of the actor.

        .. note::

            :meth:`on_topic_changed` is emitted during join, iff a topic is set
            in the MUC.

    .. signal:: on_join(member, **kwargs)

        A new occupant has joined the MUC.

        :param member: The member object of the new member.
        :type member: :class:`Occupant`

        When this signal is called, the `member` is already included in the
        :attr:`members`.

    .. signal:: on_leave(member, *, muc_leave_mode=None, muc_actor=None, muc_reason=None, **kwargs)

        An occupant has left the conversation.

        :param member: The member object of the previous occupant.
        :type member: :class:`Occupant`
        :param muc_leave_mode: The cause of the removal.
        :type muc_leave_mode: :class:`LeaveMode` member
        :param muc_actor: The actor object if available.
        :type muc_actor: :class:`~.xso.UserActor`
        :param muc_reason: The reason for the cause, as given by the actor.
        :type muc_reason: :class:`str`
        :param muc_status_codes: The set of status codes received in the leave
            notification.
        :type muc_status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        When this signal is called, the `member` has already been removed from
        the :attr:`members`.

        .. versionchanged:: 0.10

            The `muc_status_codes` argument was added.

    .. signal:: on_muc_suspend()

        Emits when the stream used by this MUC gets destroyed (see
        :meth:`~.node.Client.on_stream_destroyed`) and the MUC is configured to
        automatically rejoin the user when the stream is re-established.

    .. signal:: on_muc_resume()

        Emits when the MUC is about to be rejoined on a new stream. This can be
        used by implementations to clear their MUC state, as it is emitted
        *before* any events like presence are emitted.

        The internal state of :class:`Room` is cleared before :meth:`on_resume`
        is emitted, which implies that presence events will be emitted for all
        occupants on re-join, independent on their presence before the
        connection was lost.

        Note that on a rejoin, all presence is re-emitted.

    .. signal:: on_muc_role_request(form, submission_future)

        Emits when an unprivileged occupant requests a role change and the
        MUC service wants this occupant to approve or deny it.

        :param form: The approval form as presented by the service.
        :type form: :class:`~.VoiceRequestForm`
        :param submission_future: A future to which the form to submit must
            be sent.
        :type submission_future: :class:`asyncio.Future`

        To decide on a role change request, a handler of this signal must
        fill in the form and set the form as a result of the
        `submission_future`.

        Once the result is set, the reply is sent by the MUC service
        automatically.

        It is required for signal handlers to check whether the
        `submission_future` is already done before processing the form (as it
        is possible that multiple handlers are connected to this signal).

    .. signal:: on_exit(*, muc_leave_mode=None, muc_actor=None, muc_reason=None, muc_status_codes=set(), **kwargs)

        Emits when the unavailable :class:`~.Presence` stanza for the
        local JID is received.

        :param muc_leave_mode: The cause of the removal.
        :type muc_leave_mode: :class:`LeaveMode` member
        :param muc_actor: The actor object if available.
        :type muc_actor: :class:`~.xso.UserActor`
        :param muc_reason: The reason for the cause, as given by the actor.
        :type muc_reason: :class:`str`
        :param muc_status_codes: The set of status codes received in the leave
            notification.
        :type muc_status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        .. note::

            The keyword arguments `muc_actor`, `muc_reason` and
            `muc_status_codes` are not always given. Be sure to default them
            accordingly.

        .. versionchanged:: 0.10

            The `muc_status_codes` argument was added.

    .. signal:: on_muc_stale(**kwargs)

        Emits when the :attr:`muc_hard_timeout` expires.

        This signal is emitted only up to once for each pause in data
        reception. As long as data is received often enough, the timeout will
        not trigger. When the timeout triggers due to silence, the signal is
        emitted once, and not again until after data has been received for the
        next time.

        This signal is only informational. It does not imply that the MUC is
        unreachable or that the local occupant has been removed from the MUC,
        but it is very likely that no messages can currently be sent or
        received.

        It is not clear whether messages are being lost.

        A prominent example on when this condition can occur is highlighted in
        the specification for the feature this is built on (:xep:`0410`).
        Often, the MUC service is on a remote domain, which means that there
        are at least two network connections involved, sometimes three (c2s,
        s2s, and from the remote server to the MUC component).

        When the s2s connection (for example) fails in certain ways, it is
        possible that no error replies are generated by any party; stanzas are
        essentially blackholed. When the network connection resumes, it depends
        on the exact failure mode whether the occupant is still in the room and
        which messages (if any) which were sent in the meantime will have been
        delivered to any participant.

        After :meth:`on_muc_stale` emits, exactly one of the following will
        happen, given infinite time:

        - :meth:`on_muc_fresh` is emitted, which means that connectivity to
          the MUC has been re-confirmed.

        - :meth:`on_muc_suspend` is emitted, which means that the local client
          has disconnected (but autorejoin is enabled).

        - :meth:`on_exit` is emitted, which means that the client has been
          removed from the MUC or the local client has disconnected (and
          autorejoin is disabled).

        The aliveness checks are only enabled after presence synchronisation
        has begun.

    .. signal:: on_muc_fresh(**kwargs)

        Emits after :meth:`on_muc_stale` when connectivity is re-confirmed.

        See :meth:`on_muc_stale` for details.

    The following signals inform users about state changes related to **other**
    occupants in the chat room. Note that different events may fire for the
    same presence stanza. A common example is a ban, which triggers
    :meth:`on_affiliation_change` (as the occupants affiliation is set to
    ``"outcast"``) and then :meth:`on_leave` (with :attr:`LeaveMode.BANNED`
    `mode`).

    .. signal:: on_muc_affiliation_changed(member, *, actor=None, reason=None, status_codes=set(), **kwargs)

        Emits when the affiliation of a `member` with the room changes.

        :param occupant: The member of the room.
        :type occupant: :class:`Occupant`
        :param actor: The actor object if available.
        :type actor: :class:`~.xso.UserActor`
        :param reason: The reason for the change, as given by the actor.
        :type reason: :class:`str`
        :param status_codes: The set of status codes received in the change
            notification.
        :type status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        `occupant` is the :class:`Occupant` instance tracking the occupant
        whose affiliation changed.

        .. versionchanged:: 0.10

            The `status_codes` argument was added.

    .. signal:: on_muc_role_changed(member, *, actor=None, reason=None, status_codes=set(), **kwargs)

        Emits when the role of an `occupant` in the room changes.

        :param occupant: The member of the room.
        :type occupant: :class:`Occupant`
        :param actor: The actor object if available.
        :type actor: :class:`~.xso.UserActor`
        :param reason: The reason for the change, as given by the actor.
        :type reason: :class:`str`
        :param status_codes: The set of status codes received in the change
            notification.
        :type status_codes: :class:`~.abc.Set` of :class:`int` or
            :class:`~.StatusCode`

        `occupant` is the :class:`Occupant` instance tracking the occupant
        whose role changed.

        .. versionchanged:: 0.10

            The `status_codes` argument was added.

    Timeout control:

    .. seealso::

        :ref:`api-aioxmpp.muc-self-ping-logic`

    .. attribute:: muc_soft_timeout

        The soft timeout of the MUC aliveness timeout logic as
        :class:`datetime.timedelta`.

        .. versionadded:: 0.11

    .. attribute:: muc_hard_timeout

        The hard timeout of the MUC aliveness timeout logic as
        :class:`datetime.timedelta`.

        .. versionadded:: 0.11

    .. attribute:: muc_ping_interval

        The interval at which pings are sent after the soft timeout expires as
        :class:`datetime.timedelta`.

        .. warning::

            Please see the notes on :attr:`muc_ping_timeout`
            when changing the value of :attr:`muc_ping_timeout` or
            :attr:`muc_ping_interval`.

        .. versionadded:: 0.11

    .. attribute:: muc_ping_timeout

        The maximum time to wait for a ping reply for each individual ping as
        :class:`datetime.timedelta`.

        .. warning::

            Pings are continued to be sent even when other pings are already
            in-flight. This means that up to
            ``math.ceil(muc_ping_timeout / muc_ping_interval)`` pings are
            in-flight at the same time. Each ping which is in-flight
            unfortunately requires a small amount of memory and an entry in a
            map which associates the stanza ID with the handler/future for the
            reply.

        .. versionadded:: 0.11

    .. seealso::

        :ref:`api-aioxmpp.muc-self-ping-logic`

    """  # NOQA: E501
    # this occupant state events
    on_muc_suspend = aioxmpp.callbacks.Signal()
    on_muc_resume = aioxmpp.callbacks.Signal()
    on_muc_enter = aioxmpp.callbacks.Signal()
    on_muc_stale = aioxmpp.callbacks.Signal()
    on_muc_fresh = aioxmpp.callbacks.Signal()

    # other occupant state events
    on_muc_affiliation_changed = aioxmpp.callbacks.Signal()
    on_muc_role_changed = aioxmpp.callbacks.Signal()

    # approval requests
    on_muc_role_request = aioxmpp.callbacks.Signal()

    def __init__(self, service, mucjid):
        super().__init__(service)
        self._mucjid = mucjid
        self._occupant_info = {}
        self._subject = aioxmpp.structs.LanguageMap()
        self._subject_setter = None
        self._joined = False
        self._active = False
        self._this_occupant = None
        self._tracking_by_id = {}
        self._tracking_metadata = {}
        self._tracking_by_body = {}
        self._state = RoomState.JOIN_PRESENCE
        self._history_replay_occupants = {}
        self._service_member = ServiceMember(mucjid)
        self.muc_autorejoin = False
        self.muc_password = None
        self._monitor = self_ping.MUCMonitor(
            mucjid,
            service.client,
            self._monitor_stale,
            self._monitor_fresh,
            self._monitor_exited,
            self._service.logger.getChild("MUCMonitor"),
        )

    @property
    def service(self):
        return self._service

    @property
    def muc_state(self):
        """
        The state the MUC is in. This is one of the
        :class:`~.muc.RoomState` enumeration values. See there for
        documentation on the meaning.

        This state is more detailed than :attr:`muc_active`.
        """
        return self._state

    @property
    def muc_active(self):
        """
        A boolean attribute indicating whether the connection to the MUC is
        currently live.

        This becomes true when :attr:`joined` first becomes true. It becomes
        false whenever the connection to the MUC is interrupted in a way which
        requires re-joining the MUC (this implies that if stream management is
        being used, active does not become false on temporary connection
        interruptions).
        """
        return self._active

    @property
    def muc_joined(self):
        """
        This attribute becomes true when :meth:`on_enter` is first emitted and
        stays true until :meth:`on_exit` is emitted.

        When it becomes false, the :class:`Room` is removed from the
        bookkeeping of the :class:`.MUCClient` to which it belongs and is thus
        dead.
        """
        return self._joined

    @property
    def muc_subject(self):
        """
        The current subject of the MUC, as :class:`~.structs.LanguageMap`.
        """
        return self._subject

    @property
    def muc_subject_setter(self):
        """
        The nick name of the entity who set the subject.
        """
        return self._subject_setter

    @property
    def me(self):
        """
        A :class:`Occupant` instance which tracks the local user. This is
        :data:`None` until :meth:`on_enter` is emitted; it is never set to
        :data:`None` again, but the identity of the object changes on each
        :meth:`on_enter`.
        """
        return self._this_occupant

    @property
    def jid(self):
        """
        The (bare) :class:`aioxmpp.JID` of the MUC which this :class:`Room`
        tracks.
        """
        return self._mucjid

    @property
    def members(self):
        """
        A copy of the list of occupants. The local user is always the first
        item in the list, unless the :meth:`on_enter` has not fired yet.
        """

        if self._this_occupant is not None:
            items = [self._this_occupant]
        else:
            items = []
        items += list(self._occupant_info.values())
        return items

    @property
    def service_member(self):
        """
        A :class:`ServiceMember` object which represents the MUC service
        itself.

        This is used when messages from the MUC service are received.

        .. seealso::

            :attr:`~aioxmpp.im.conversation.AbstractConversation.service_member`
                For more documentation on the semantics of
                :attr:`~.service_member`.

        .. versionadded:: 0.10
        """
        return self._service_member

    @property
    def features(self):
        """
        The set of features supported by this MUC. This may vary depending on
        features exported by the MUC service, so be sure to check this for each
        individual MUC.
        """

        return {
            aioxmpp.im.conversation.ConversationFeature.BAN,
            aioxmpp.im.conversation.ConversationFeature.BAN_WITH_KICK,
            aioxmpp.im.conversation.ConversationFeature.KICK,
            aioxmpp.im.conversation.ConversationFeature.SEND_MESSAGE,
            aioxmpp.im.conversation.ConversationFeature.SEND_MESSAGE_TRACKED,
            aioxmpp.im.conversation.ConversationFeature.SET_TOPIC,
            aioxmpp.im.conversation.ConversationFeature.SET_NICK,
            aioxmpp.im.conversation.ConversationFeature.INVITE,
            aioxmpp.im.conversation.ConversationFeature.INVITE_DIRECT,
        }

    muc_soft_timeout = aioxmpp.utils.proxy_property(
        "_monitor",
        "soft_timeout",
    )

    muc_hard_timeout = aioxmpp.utils.proxy_property(
        "_monitor",
        "hard_timeout",
    )

    muc_ping_timeout = aioxmpp.utils.proxy_property(
        "_monitor",
        "ping_timeout",
    )

    muc_ping_interval = aioxmpp.utils.proxy_property(
        "_monitor",
        "ping_interval",
    )

    def _enter_active_state(self):
        self._state = RoomState.ACTIVE
        self._history_replay_occupants.clear()

    def _suspend(self):
        self._monitor.disable()
        self.on_muc_suspend()
        self._active = False
        self._state = RoomState.DISCONNECTED
        self._history_replay_occupants.clear()

    def _disconnect(self):
        if not self._joined:
            return
        self._monitor.disable()
        self.on_exit(
            muc_leave_mode=LeaveMode.DISCONNECTED
        )
        self._joined = False
        self._active = False
        self._state = RoomState.DISCONNECTED
        self._history_replay_occupants.clear()

    def _resume(self):
        self._this_occupant = None
        self._occupant_info = {}
        self._active = False
        self._state = RoomState.JOIN_PRESENCE
        self.on_muc_resume()

    def _monitor_stale(self):
        self.on_muc_stale()

    def _monitor_fresh(self):
        self.on_muc_fresh()

    def _monitor_exited(self):
        if self.muc_autorejoin:
            self._service._cycle(self)
        else:
            self._disconnect()

    def _match_tracker(self, message):
        try:
            tracker = self._tracking_by_id[message.id_]
        except KeyError:
            if (self._this_occupant is not None and
                    message.from_ == self._this_occupant.conversation_jid):
                key = _extract_one_pair(message.body)
                self._service.logger.debug("trying to match by body: %r",
                                           key)
                try:
                    trackers = self._tracking_by_body[key]
                except KeyError:
                    alt_key = (None, key[1])
                    try:
                        trackers = self._tracking_by_body[alt_key]
                    except KeyError:
                        trackers = None
                else:
                    self._service.logger.debug("found tracker by body")
            else:
                self._service.logger.debug(
                    "can’t match by body because of sender mismatch"
                )
                trackers = None

            if not trackers:
                tracker = None
            else:
                tracker = trackers[0]
        else:
            self._service.logger.debug("found tracker by ID")

        if tracker is None:
            return False

        id_key, body_key = self._tracking_metadata.pop(tracker)
        del self._tracking_by_id[id_key]

        # remove tracker from list and delete list map entry if empty
        trackers = self._tracking_by_body[body_key]
        del trackers[0]
        if not trackers:
            del self._tracking_by_body[body_key]

        try:
            tracker._set_state(
                aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
                message,
            )
        except ValueError:
            # this can happen if another implementation was faster with
            # changing the state than we were.
            pass

        return True

    def _handle_message(self, message, peer, sent, source):
        self._service.logger.debug("%s: inbound message %r",
                                   self._mucjid,
                                   message)

        self._monitor.enable()
        self._monitor.reset()

        if self._state == RoomState.HISTORY and not message.xep0203_delay:
            # WORKAROUND: prosody#1053; AFFECTS: <= 0.9.12, <= 0.10
            self._service.logger.debug(
                "%s: received un-delayed message during history replay: "
                "assuming that server is buggy and replay is over.",
                self._mucjid,
            )
            self._enter_active_state()

        if not sent:
            if self._match_tracker(message):
                return

        if (self._this_occupant and
                self._this_occupant._conversation_jid == message.from_):
            occupant = self._this_occupant
        else:
            if message.from_.resource is None:
                occupant = self._service_member
            else:
                occupant = self._occupant_info.get(message.from_, None)

            if (self._state == RoomState.HISTORY and
                    not sent and
                    message.from_.resource is not None):
                if (message.xep0045_muc_user and
                        message.xep0045_muc_user.items):
                    item = message.xep0045_muc_user.items[0]
                    jid = item.bare_jid
                    affiliation = item.affiliation or None
                    role = item.role or None
                else:
                    jid = None
                    affiliation = None
                    role = None

                occupant = self._history_replay_occupants.get(jid, occupant)

                if (not occupant or
                        occupant.direct_jid is None or
                        occupant.direct_jid != jid):
                    occupant = Occupant(message.from_, False,
                                        presence_state=aioxmpp.PresenceState(),
                                        jid=jid,
                                        affiliation=affiliation,
                                        role=role)
                    if jid is not None:
                        self._history_replay_occupants[jid] = occupant
            elif occupant is None:
                occupant = Occupant(message.from_, False,
                                    presence_state=aioxmpp.PresenceState())

        if not message.body and message.subject:
            self._subject = aioxmpp.structs.LanguageMap(message.subject)
            self._subject_setter = message.from_.resource

            self.on_topic_changed(
                occupant,
                self._subject,
                muc_nick=message.from_.resource,
            )

            self._enter_active_state()

        elif message.body:
            if occupant is not None and occupant == self._this_occupant:
                tracker = aioxmpp.tracking.MessageTracker()
                tracker._set_state(
                    aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT
                )
                tracker.close()
            else:
                tracker = None
            self.on_message(
                message,
                occupant,
                source,
                tracker=tracker,
            )

    def _diff_presence(self, stanza, info, existing):
        if (not info.presence_state.available and
                muc_xso.StatusCode.NICKNAME_CHANGE in
                stanza.xep0045_muc_user.status_codes):
            return (
                _OccupantDiffClass.NICK_CHANGED,
                (
                    stanza.xep0045_muc_user.items[0].nick,
                )
            )

        result = (_OccupantDiffClass.UNIMPORTANT, None)
        to_emit = []

        try:
            reason = stanza.xep0045_muc_user.items[0].reason
            actor = stanza.xep0045_muc_user.items[0].actor
        except IndexError:
            reason = None
            actor = None

        if not info.presence_state.available:
            status_codes = stanza.xep0045_muc_user.status_codes
            mode = LeaveMode.NORMAL

            if muc_xso.StatusCode.REMOVED_ERROR in status_codes:
                mode = LeaveMode.ERROR
            elif muc_xso.StatusCode.REMOVED_KICKED in status_codes:
                mode = LeaveMode.KICKED
            elif muc_xso.StatusCode.REMOVED_BANNED in status_codes:
                mode = LeaveMode.BANNED
            elif muc_xso.StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
                mode = LeaveMode.AFFILIATION_CHANGE
            elif (muc_xso.StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY
                  in status_codes):
                mode = LeaveMode.MODERATION_CHANGE
            elif muc_xso.StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
                mode = LeaveMode.SYSTEM_SHUTDOWN

            result = (
                _OccupantDiffClass.LEFT,
                (
                    mode,
                    actor,
                    reason,
                )
            )
        else:
            to_emit.append((self.on_presence_changed,
                            (existing, None, stanza),
                            {}))

        if existing.role != info.role:
            to_emit.append((
                self.on_muc_role_changed,
                (
                    stanza,
                    existing,
                ),
                {
                    "actor": actor,
                    "reason": reason,
                    "status_codes": stanza.xep0045_muc_user.status_codes,
                },
            ))

        if existing.affiliation != info.affiliation:
            to_emit.append((
                self.on_muc_affiliation_changed,
                (
                    stanza,
                    existing,
                ),
                {
                    "actor": actor,
                    "reason": reason,
                    "status_codes": stanza.xep0045_muc_user.status_codes,
                },
            ))

        if to_emit:
            existing.update(info)
            for signal, args, kwargs in to_emit:
                signal(*args, **kwargs)

        return result

    def _handle_self_presence(self, stanza):
        info = Occupant.from_presence(stanza, True)

        self._monitor.ping_address = stanza.from_

        if not self._active:
            if stanza.type_ == aioxmpp.structs.PresenceType.UNAVAILABLE:
                self._service.logger.debug(
                    "%s: not active, and received unavailable ... "
                    "is this a reconnect?",
                    self._mucjid,
                )
                return

            self._service.logger.debug("%s: not active, configuring",
                                       self._mucjid)
            self._this_occupant = info
            self._joined = True
            self._active = True
            self._state = RoomState.HISTORY
            self.on_muc_enter(
                stanza, info,
                muc_status_codes=frozenset(
                    stanza.xep0045_muc_user.status_codes
                )
            )
            self.on_enter()
            return

        existing = self._this_occupant
        mode, data = self._diff_presence(stanza, info, existing)
        if mode == _OccupantDiffClass.NICK_CHANGED:
            new_nick, = data
            old_nick = existing.nick
            self._service.logger.debug("%s: nick changed: %r -> %r",
                                       self._mucjid,
                                       old_nick,
                                       new_nick)
            existing._conversation_jid = existing.conversation_jid.replace(
                resource=new_nick
            )
            self.on_nick_changed(existing, old_nick, new_nick)
        elif mode == _OccupantDiffClass.LEFT:
            mode, actor, reason = data
            self._service.logger.debug("%s: we left the MUC. reason=%r",
                                       self._mucjid,
                                       reason)
            existing.update(info)
            self._monitor.disable()
            self.on_exit(muc_leave_mode=mode,
                         muc_actor=actor,
                         muc_reason=reason,
                         muc_status_codes=stanza.xep0045_muc_user.status_codes)
            self._joined = False
            self._active = False

    def _inbound_muc_user_presence(self, stanza):
        self._service.logger.debug("%s: inbound muc user presence %r",
                                   self._mucjid,
                                   stanza)

        self._monitor.enable()
        self._monitor.reset()

        if stanza.from_.is_bare:
            self._service.logger.debug(
                "received muc user presence from bare JID %s. ignoring.",
                stanza.from_,
            )
            return

        if self._state == RoomState.HISTORY:
            # WORKAROUND: prosody#1053; AFFECTS: <= 0.9.12, <= 0.10
            self._service.logger.debug(
                "%s: received presence during history replay: "
                "assuming that server is buggy and replay is over.",
                self._mucjid,
            )
            self._enter_active_state()

        if (muc_xso.StatusCode.SELF in stanza.xep0045_muc_user.status_codes or
                (self._this_occupant is not None and
                 self._this_occupant.conversation_jid == stanza.from_)):
            self._service.logger.debug("%s: is self-presence",
                                       self._mucjid)
            self._handle_self_presence(stanza)
            return

        info = Occupant.from_presence(stanza, False)
        try:
            existing = self._occupant_info[info.conversation_jid]
        except KeyError:
            if stanza.type_ == aioxmpp.structs.PresenceType.UNAVAILABLE:
                self._service.logger.debug(
                    "received unavailable presence from unknown occupant %r."
                    " ignoring.",
                    stanza.from_,
                )
                return
            self._occupant_info[info.conversation_jid] = info
            self.on_join(info)
            return

        mode, data = self._diff_presence(stanza, info, existing)
        if mode == _OccupantDiffClass.NICK_CHANGED:
            new_nick, = data
            old_nick = existing.nick
            del self._occupant_info[existing.conversation_jid]
            existing._conversation_jid = existing.conversation_jid.replace(
                resource=new_nick
            )
            self._occupant_info[existing.conversation_jid] = existing
            self.on_nick_changed(existing, old_nick, new_nick)
        elif mode == _OccupantDiffClass.LEFT:
            mode, actor, reason = data
            existing.update(info)
            self.on_leave(
                existing,
                muc_leave_mode=mode,
                muc_actor=actor,
                muc_reason=reason,
                muc_status_codes=stanza.xep0045_muc_user.status_codes
            )
            del self._occupant_info[existing.conversation_jid]

    def _handle_role_request(self, form):
        def submit(fut):
            data_xso = fut.result()
            msg = aioxmpp.Message(
                to=self.jid,
                type_=aioxmpp.MessageType.NORMAL,
            )
            msg.xep0004_data.append(data_xso)
            self._service.client.enqueue(msg)

        fut = asyncio.Future()
        fut.add_done_callback(submit)
        self.on_muc_role_request(form, fut)

    def send_message(self, msg):
        """
        Send a message to the MUC.

        :param msg: The message to send.
        :type msg: :class:`aioxmpp.Message`
        :return: The stanza token of the message.
        :rtype: :class:`~aioxmpp.stream.StanzaToken`

        There is no need to set the address attributes or the type of the
        message correctly; those will be overridden by this method to conform
        to the requirements of a message to the MUC. Other attributes are left
        untouched (except that :meth:`~.StanzaBase.autoset_id` is called) and
        can be used as desired for the message.

        .. seealso::

            :meth:`.AbstractConversation.send_message` for the full interface
            specification.
        """
        msg.type_ = aioxmpp.MessageType.GROUPCHAT
        msg.to = self._mucjid
        # see https://mail.jabber.org/pipermail/standards/2017-January/032048.html  # NOQA
        # for a full discussion on the rationale for this.
        # TL;DR: we want to help entities to discover that a message is related
        # to a MUC.
        msg.xep0045_muc_user = muc_xso.UserExt()
        result = self.service.client.enqueue(msg)
        return result

    def _tracker_closed(self, tracker):
        try:
            id_key, body_key = self._tracking_metadata[tracker]
        except KeyError:
            return
        self._tracking_by_id.pop(id_key, None)
        self._tracking_by_body.pop(body_key, None)

    def send_message_tracked(self, msg):
        """
        Send a message to the MUC with tracking.

        :param msg: The message to send.
        :type msg: :class:`aioxmpp.Message`

        .. warning::

            Please read :ref:`api-tracking-memory`. This is especially relevant
            for MUCs because tracking is not guaranteed to work due to how
            :xep:`45` is written. It will work in many cases, probably in all
            cases you test during development, but it may fail to work for some
            individual messages and it may fail to work consistently for some
            services. See the implementation details below for reasons.

        The message is tracked and is considered
        :attr:`~.MessageState.DELIVERED_TO_RECIPIENT` when it is reflected back
        to us by the MUC service. The reflected message is then available in
        the :attr:`~.MessageTracker.response` attribute.

        .. note::

            Two things:

            1. The MUC service may change the contents of the message. An
               example of this is the Prosody developer MUC which replaces
               messages with more than a few lines with a pastebin link.
            2. Reflected messages which are caught by tracking are not emitted
               through :meth:`on_message`.

        There is no need to set the address attributes or the type of the
        message correctly; those will be overridden by this method to conform
        to the requirements of a message to the MUC. Other attributes are left
        untouched (except that :meth:`~.StanzaBase.autoset_id` is called) and
        can be used as desired for the message.

        .. warning::

            Using :meth:`send_message_tracked` before :meth:`on_join` has
            emitted will cause the `member` object in the resulting
            :meth:`on_message` event to be :data:`None` (the message will be
            delivered just fine).

            Using :meth:`send_message_tracked` before history replay is over
            will cause the :meth:`on_message` event to be emitted during
            history replay, even though everyone else in the MUC will -- of
            course -- only see the message after the history.

            :meth:`send_message` is not affected by these quirks.

        .. seealso::

            :meth:`.AbstractConversation.send_message_tracked` for the full
            interface specification.

        **Implementation details:** Currently, we try to detect reflected
        messages using two different criteria. First, if we see a message with
        the same message ID (note that message IDs contain 120 bits of entropy)
        as the message we sent, we consider it as the reflection. As some MUC
        services re-write the message ID in the reflection, as a fallback, we
        also consider messages which originate from the correct sender and have
        the correct body a reflection.

        Obviously, this fails consistently in MUCs which re-write the body and
        re-write the ID and randomly if the MUC always re-writes the ID but
        only sometimes the body.
        """
        msg.type_ = aioxmpp.MessageType.GROUPCHAT
        msg.to = self._mucjid
        # see https://mail.jabber.org/pipermail/standards/2017-January/032048.html  # NOQA
        # for a full discussion on the rationale for this.
        # TL;DR: we want to help entities to discover that a message is related
        # to a MUC.
        msg.xep0045_muc_user = muc_xso.UserExt()
        msg.autoset_id()
        tracking_svc = self.service.dependencies[
            aioxmpp.tracking.BasicTrackingService
        ]
        tracker = aioxmpp.tracking.MessageTracker()
        id_key = msg.id_
        body_key = _extract_one_pair(msg.body)
        self._tracking_by_id[id_key] = tracker
        self._tracking_metadata[tracker] = (
            id_key,
            body_key,
        )
        self._tracking_by_body.setdefault(
            body_key,
            []
        ).append(tracker)
        tracker.on_closed.connect(functools.partial(
            self._tracker_closed,
            tracker,
        ))
        token = tracking_svc.send_tracked(msg, tracker)
        self.on_message(
            msg,
            self._this_occupant,
            aioxmpp.im.dispatcher.MessageSource.STREAM,
            tracker=tracker,
        )
        return token, tracker

    async def set_nick(self, new_nick):
        """
        Change the nick name of the occupant.

        :param new_nick: New nickname to use
        :type new_nick: :class:`str`

        This sends the request to change the nickname and waits for the request
        to be sent over the stream.

        The nick change may or may not happen, or the service may modify the
        nickname; observe the :meth:`on_nick_change` event.

        .. seealso::

            :meth:`.AbstractConversation.set_nick` for the full interface
            specification.
        """

        stanza = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.AVAILABLE,
            to=self._mucjid.replace(resource=new_nick),
        )
        await self._service.client.send(
            stanza
        )

    async def kick(self, member, reason=None):
        """
        Kick an occupant from the MUC.

        :param member: The member to kick.
        :type member: :class:`Occupant`
        :param reason: A reason to show to the members of the conversation
            including the kicked member.
        :type reason: :class:`str`
        :raises aioxmpp.errors.XMPPError: if the server returned an error for
                                          the kick command.

        .. seealso::

            :meth:`.AbstractConversation.kick` for the full interface
            specification.
        """
        await self.muc_set_role(
            member.nick,
            "none",
            reason=reason
        )

    async def muc_set_role(self, nick, role, *, reason=None):
        """
        Change the role of an occupant.

        :param nick: The nickname of the occupant whose role shall be changed.
        :type nick: :class:`str`
        :param role: The new role for the occupant.
        :type role: :class:`str`
        :param reason: An optional reason to show to the occupant (and all
            others).

        Change the role of an occupant, identified by their `nick`, to the
        given new `role`. Optionally, a `reason` for the role change can be
        provided.

        Setting the different roles require different privilegues of the local
        user. The details can be checked in :xep:`0045` and are enforced solely
        by the server, not local code.

        The coroutine returns when the role change has been acknowledged by the
        server. If the server returns an error, an appropriate
        :class:`aioxmpp.errors.XMPPError` subclass is raised.
        """

        if nick is None:
            raise ValueError("nick must not be None")

        if role is None:
            raise ValueError("role must not be None")

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=self._mucjid
        )

        iq.payload = muc_xso.AdminQuery(
            items=[
                muc_xso.AdminItem(nick=nick,
                                  reason=reason,
                                  role=role)
            ]
        )

        await self.service.client.send(iq)

    async def ban(self, member, reason=None, *, request_kick=True):
        """
        Ban an occupant from re-joining the MUC.

        :param member: The occupant to ban.
        :type member: :class:`Occupant`
        :param reason: A reason to show to the members of the conversation
            including the banned member.
        :type reason: :class:`str`
        :param request_kick: A flag indicating that the member should be
            removed from the conversation immediately, too.
        :type request_kick: :class:`bool`

        `request_kick` is supported by MUC, but setting it to false has no
        effect: banned members are always immediately kicked.

        .. seealso::

            :meth:`.AbstractConversation.ban` for the full interface
            specification.
        """
        if member.direct_jid is None:
            raise ValueError(
                "cannot ban members whose direct JID is not "
                "known")

        await self.muc_set_affiliation(
            member.direct_jid,
            "outcast",
            reason=reason
        )

    async def muc_set_affiliation(self, jid, affiliation, *, reason=None):
        """
        Convenience wrapper around :meth:`.MUCClient.set_affiliation`. See
        there for details, and consider its `mucjid` argument to be set to
        :attr:`mucjid`.
        """
        return await self.service.set_affiliation(
            self._mucjid,
            jid, affiliation,
            reason=reason
        )

    async def set_topic(self, new_topic):
        """
        Change the (possibly publicly) visible topic of the conversation.

        :param new_topic: The new topic for the conversation.
        :type new_topic: :class:`str`

        Request to set the subject to `new_topic`. `new_topic` must be a
        mapping which maps :class:`~.structs.LanguageTag` tags to strings;
        :data:`None` is a valid key.
        """

        msg = aioxmpp.stanza.Message(
            type_=aioxmpp.structs.MessageType.GROUPCHAT,
            to=self._mucjid
        )
        msg.subject.update(new_topic)

        await self.service.client.send(msg)

    async def leave(self):
        """
        Leave the MUC.
        """
        fut = self.on_exit.future()

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            to=self._mucjid
        )
        await self.service.client.send(presence)

        await fut

    async def muc_request_voice(self):
        """
        Request voice (participant role) in the room and wait for the request
        to be sent.

        The participant role allows occupants to send messages while the room
        is in moderated mode.

        There is no guarantee that the request will be granted. To detect that
        voice has been granted, observe the :meth:`on_role_change` signal.

        .. versionadded:: 0.8
        """

        msg = aioxmpp.Message(
            to=self._mucjid,
            type_=aioxmpp.MessageType.NORMAL
        )

        data = aioxmpp.forms.Data(
            aioxmpp.forms.DataType.SUBMIT,
        )

        data.fields.append(
            aioxmpp.forms.Field(
                type_=aioxmpp.forms.FieldType.HIDDEN,
                var="FORM_TYPE",
                values=["http://jabber.org/protocol/muc#request"],
            ),
        )
        data.fields.append(
            aioxmpp.forms.Field(
                type_=aioxmpp.forms.FieldType.LIST_SINGLE,
                var="muc#role",
                values=["participant"],
            )
        )

        msg.xep0004_data.append(data)

        await self.service.client.send(msg)

    async def invite(self, address, text=None, *,
                     mode=aioxmpp.im.InviteMode.DIRECT,
                     allow_upgrade=False):
        if mode == aioxmpp.im.InviteMode.DIRECT:
            msg = aioxmpp.Message(
                type_=aioxmpp.MessageType.NORMAL,
                to=address.bare(),
            )
            msg.xep0249_direct_invite = muc_xso.DirectInvite(
                self.jid,
                reason=text,
            )

            return self.service.client.enqueue(msg), self
        if mode == aioxmpp.im.InviteMode.MEDIATED:
            invite = muc_xso.Invite()
            invite.to = address
            invite.reason = text

            msg = aioxmpp.Message(
                type_=aioxmpp.MessageType.NORMAL,
                to=self.jid,
            )
            msg.xep0045_muc_user = muc_xso.UserExt()
            msg.xep0045_muc_user.invites.append(invite)

            return self.service.client.enqueue(msg), self


def _connect_to_signal(signal, func):
    return signal, signal.connect(func)


class MUCClient(aioxmpp.im.conversation.AbstractConversationService,
                aioxmpp.service.Service):
    """
    :term:`Conversation Implementation` for Multi-User Chats (:xep:`45`).

    .. seealso::

        :class:`~.AbstractConversationService`
            for useful common signals

    This service provides access to Multi-User Chats using the
    conversation interface defined by :mod:`aioxmpp.im`.

    Client service implementing the a Multi-User Chat client. By loading it
    into a client, it is possible to join multi-user chats and implement
    interaction with them.

    Private Messages into the MUC are not handled by this service. They are
    handled by the normal :class:`.p2p.Service`.

    .. automethod:: join

    Manage rooms:

    .. automethod:: get_room_config

    .. automethod:: set_room_config

    .. automethod:: get_affiliated

    .. automethod:: set_affiliation

    Global events:

    .. signal:: on_muc_invitation(stanza, muc_address, inviter_address, mode, *, password=None, reason=None, **kwargs)

        Emits when a MUC invitation has been received.

        .. versionadded:: 0.10

        :param stanza: The stanza containing the invitation.
        :type stanza: :class:`aioxmpp.Message`
        :param muc_address: The address of the MUC to which the invitation
            points.
        :type muc_address: :class:`aioxmpp.JID`
        :param inviter_address: The address of the inviter.
        :type inviter_address: :class:`aioxmpp.JID` or :data:`None`
        :param mode: The type of the invitation.
        :type mode: :class:`.im.InviteMode`
        :param password: Password for the MUC.
        :type password: :class:`str` or :data:`None`
        :param reason: Text accompanying the invitation.
        :type reason: :class:`str` or :data:`None`

        The format of the `inviter_address` depends on the `mode`:

        :attr:`~.im.InviteMode.DIRECT`
            For direct invitations, the `inviter_address` is the full or bare
            JID of the entity which sent the invitation. Usually, this will
            be a full JID of a users client.

        :attr:`~.im.InviteMode.MEDIATED`
            For mediated invitations, the `inviter_address` is either the
            occupant JID of the inviting occupant or the real bare or full JID
            of the occupant (:xep:`45` leaves it up to the service to decide).
            May also be :data:`None`.

        .. warning::

            Neither invitation type is perfect and has issues. Mediated invites
            can easily be spoofed by MUCs (both their intent and the inviter
            address) and might be used by spam rooms to trick users into
            joining. Direct invites may not reach the recipient due to local
            policy, but they allow proper sender attribution.

            `inviter_address` values which are not an occupant JID should not
            be trusted for mediated invites!

            How to deal with this is a policy decision which :mod:`aioxmpp`
            can not make for your application.

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.muc.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.

    .. versionchanged:: 0.9

        This class was completely remodeled in 0.9 to conform with the
        :class:`aioxmpp.im` interface.

    .. versionchanged:: 0.10

        This class now conforms to the :class:`~.AbstractConversationService`
        interface.

    """  # NOQA: E501

    ORDER_AFTER = [
        aioxmpp.im.dispatcher.IMDispatcher,
        aioxmpp.im.service.ConversationService,
        aioxmpp.tracking.BasicTrackingService,
        aioxmpp.DiscoServer,
    ]

    ORDER_BEFORE = [
        aioxmpp.im.p2p.Service,
    ]

    on_muc_invitation = aioxmpp.callbacks.Signal()

    direct_invite_feature = aioxmpp.disco.register_feature(
        namespaces.xep0249_conference,
    )

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._pending_mucs = {}
        self._joined_mucs = {}

    def _send_join_presence(self, mucjid, history, nick, password):
        presence = aioxmpp.stanza.Presence()
        presence.to = mucjid.replace(resource=nick)
        presence.xep0045_muc = muc_xso.GenericExt()
        presence.xep0045_muc.password = password
        presence.xep0045_muc.history = history
        self.client.enqueue(presence)

    @aioxmpp.service.depsignal(aioxmpp.Client, "on_stream_established")
    def _stream_established(self):
        self.logger.debug("stream established, (re-)connecting to %d mucs",
                          len(self._pending_mucs))

        for muc, fut, nick, history in self._pending_mucs.values():
            if muc.muc_joined:
                self.logger.debug("%s: resuming", muc.jid)
                muc._resume()
            self.logger.debug("%s: sending join presence", muc.jid)
            self._send_join_presence(muc.jid, history, nick, muc.muc_password)

    @aioxmpp.service.depsignal(aioxmpp.Client, "on_stream_destroyed")
    def _stream_destroyed(self):
        self.logger.debug(
            "stream destroyed, preparing autorejoin and cleaning up the others"
        )

        new_pending = {}
        for muc, fut, *more in self._pending_mucs.values():
            if not muc.muc_autorejoin:
                self.logger.debug(
                    "%s: pending without autorejoin -> ConnectionError",
                    muc.jid
                )
                fut.set_exception(ConnectionError())
            else:
                self.logger.debug(
                    "%s: pending with autorejoin -> keeping",
                    muc.jid
                )
                new_pending[muc.jid] = (muc, fut) + tuple(more)
        self._pending_mucs = new_pending

        for muc in list(self._joined_mucs.values()):
            if muc.muc_autorejoin:
                self.logger.debug(
                    "%s: connected with autorejoin, suspending and adding to "
                    "pending",
                    muc.jid
                )
                muc._suspend()
                self._pending_mucs[muc.jid] = (
                    muc, None, muc.me.nick, muc_xso.History(
                        since=datetime.utcnow()
                    )
                )
            else:
                self.logger.debug(
                    "%s: connected with autorejoin, disconnecting",
                    muc.jid
                )
                muc._disconnect()

        self.logger.debug("state now: pending=%r, joined=%r",
                          self._pending_mucs,
                          self._joined_mucs)

    def _pending_join_done(self, mucjid, room, fut):
        try:
            fut.result()
        except (Exception, asyncio.CancelledError) as exc:
            room.on_failure(exc)

        if fut.cancelled():
            try:
                del self._pending_mucs[mucjid]
            except KeyError:
                pass
            unjoin = aioxmpp.stanza.Presence(
                to=mucjid,
                type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            )
            unjoin.xep0045_muc = muc_xso.GenericExt()
            self.client.enqueue(unjoin)

    def _pending_on_enter(self, presence, occupant, **kwargs):
        mucjid = presence.from_.bare()
        try:
            pending, fut, *_ = self._pending_mucs.pop(mucjid)
        except KeyError:
            pass  # huh
        else:
            self.logger.debug("%s: pending -> joined",
                              mucjid)
            if fut is not None:
                fut.set_result(None)
            self._joined_mucs[mucjid] = pending

    def _inbound_muc_user_presence(self, stanza):
        mucjid = stanza.from_.bare()

        try:
            muc = self._joined_mucs[mucjid]
        except KeyError:
            try:
                muc, *_ = self._pending_mucs[mucjid]
            except KeyError:
                return
        muc._inbound_muc_user_presence(stanza)

    def _inbound_presence_error(self, stanza):
        mucjid = stanza.from_.bare()
        try:
            pending, fut, *_ = self._pending_mucs.pop(mucjid)
        except KeyError:
            pass
        else:
            fut.set_exception(stanza.error.to_exception())

    @aioxmpp.service.depfilter(
        aioxmpp.im.dispatcher.IMDispatcher,
        "presence_filter")
    def _handle_presence(self, stanza, peer, sent):
        if sent:
            return stanza

        if stanza.xep0045_muc_user is not None:
            self._inbound_muc_user_presence(stanza)
            return None
        if stanza.type_ == aioxmpp.structs.PresenceType.ERROR:
            self._inbound_presence_error(stanza)
            return None
        return stanza

    @aioxmpp.service.depfilter(
        aioxmpp.im.dispatcher.IMDispatcher,
        "message_filter")
    def _handle_message(self, message, peer, sent, source):
        if message.xep0045_muc_user and message.xep0045_muc_user.invites:
            if sent:
                return None

            invite = message.xep0045_muc_user.invites[0]
            if invite.to:
                # outbound mediated invite -- we should never be receiving this
                # with sent=False
                self.logger.debug(
                    "received outbound mediated invite?! dropping"
                )
                return None

            # mediated invitation
            self.on_muc_invitation(
                message,
                message.from_.bare(),
                invite.from_,
                aioxmpp.im.InviteMode.MEDIATED,
                password=invite.password,
                reason=invite.reason,
            )
            return None

        if message.xep0249_direct_invite:
            if sent:
                return None

            invite = message.xep0249_direct_invite
            try:
                jid = invite.jid
            except AttributeError:
                self.logger.debug(
                    "received direct invitation without destination JID; "
                    "dropping",
                )
                return None

            self.on_muc_invitation(
                message,
                jid,
                message.from_,
                aioxmpp.im.InviteMode.DIRECT,
                password=invite.password,
                reason=invite.reason,
            )
            return None

        if (source == aioxmpp.im.dispatcher.MessageSource.CARBONS
                and message.xep0045_muc_user):
            return None

        mucjid = peer.bare()
        try:
            muc = self._joined_mucs[mucjid]
        except KeyError:
            return message

        if (message.type_ == aioxmpp.MessageType.NORMAL and not sent and
                peer == mucjid):
            for form in message.xep0004_data:
                if form.get_form_type() != muc_xso.VoiceRequestForm.FORM_TYPE:
                    continue
                form_obj = muc_xso.VoiceRequestForm.from_xso(form)
                muc._handle_role_request(form_obj)
                return None

        if message.type_ != aioxmpp.MessageType.GROUPCHAT:
            if muc is not None:
                if source == aioxmpp.im.dispatcher.MessageSource.CARBONS:
                    return None
                # tag so that p2p.Service knows what to do
                message.xep0045_muc_user = muc_xso.UserExt()
            return message

        muc._handle_message(
            message, peer, sent, source
        )

    def _muc_exited(self, muc, *args, **kwargs):
        try:
            del self._joined_mucs[muc.jid]
        except KeyError:
            _, fut, *_ = self._pending_mucs.pop(muc.jid)
            if not fut.done():
                fut.set_result(None)

    def _cycle(self, room: Room):
        try:
            room, fut, nick, history = self._pending_mucs[room.jid]
        except KeyError:
            # the muc is already joined
            nick = room.me.nick
            # we do not request history for cycle operations; there is no way
            # to determine the right amount. this could be changed in the
            # future.
            history = muc_xso.History()
            history.maxchars = 0
            history.maxstanzas = 0

        unjoin = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            to=room.jid.replace(resource=nick),
        )
        unjoin.xep0045_muc = muc_xso.GenericExt()

        self.client.enqueue(unjoin)
        room._suspend()
        room._resume()

        self._send_join_presence(
            room.jid,
            history,
            nick,
            room.muc_password,
        )

    def get_muc(self, mucjid):
        try:
            return self._joined_mucs[mucjid]
        except KeyError:
            return self._pending_mucs[mucjid][0]

    async def _shutdown(self):
        for muc, fut, *_ in self._pending_mucs.values():
            muc._disconnect()
            fut.set_exception(ConnectionError())
        self._pending_mucs.clear()

        for muc in list(self._joined_mucs.values()):
            muc._disconnect()
        self._joined_mucs.clear()

    def join(self, mucjid, nick, *,
             password=None, history=None, autorejoin=True):
        """
        Join a multi-user chat and create a conversation for it.

        :param mucjid: The bare JID of the room to join.
        :type mucjid: :class:`~aioxmpp.JID`.
        :param nick: The nickname to use in the room.
        :type nick: :class:`str`
        :param password: The password to join the room, if required.
        :type password: :class:`str`
        :param history: Specification for how much and which history to fetch.
        :type history: :class:`.xso.History`
        :param autorejoin: Flag to indicate that the MUC should be
            automatically rejoined after a disconnect.
        :type autorejoin: :class:`bool`
        :raises ValueError: if the MUC JID is invalid.
        :return: The :term:`Conversation` and a future on the join.
        :rtype: tuple of :class:`~.Room` and :class:`asyncio.Future`.

        Join a multi-user chat at `mucjid` with `nick`. Return a :class:`Room`
        instance which is used to track the MUC locally and a
        :class:`aioxmpp.Future` which becomes done when the join succeeded
        (with a :data:`None` value) or failed (with an exception).

        In addition, the :meth:`~.ConversationService.on_conversation_added`
        signal is emitted immediately with the new :class:`Room`.

        It is recommended to attach the desired signals to the :class:`Room`
        before yielding next (e.g. in a non-deferred event handler to the
        :meth:`~.ConversationService.on_conversation_added` signal), to avoid
        races with the server. It is guaranteed that no signals are emitted
        before the next yield, and thus, it is safe to attach the signals right
        after :meth:`join` returned. (This is also the reason why :meth:`join`
        is not a coroutine, but instead returns the room and a future to wait
        for.)

        Any other interaction with the room must go through the :class:`Room`
        instance.

        If the multi-user chat at `mucjid` is already or currently being
        joined, the existing :class:`Room` and future is returned. The `nick`
        and other options for the new join are ignored.

        If the `mucjid` is not a bare JID, :class:`ValueError` is raised.

        `password` may be a string used as password for the MUC. It will be
        remembered and stored at the returned :class:`Room` instance.

        `history` may be a :class:`History` instance to request a specific
        amount of history; otherwise, the server will return a default amount
        of history.

        If `autorejoin` is true, the MUC will be re-joined after the stream has
        been destroyed and re-established. In that case, the service will
        request history since the stream destruction and ignore the `history`
        object passed here.

        If the stream is currently not established, the join is deferred until
        the stream is established.
        """
        if history is not None and not isinstance(history, muc_xso.History):
            raise TypeError("history must be {!s}, got {!r}".format(
                muc_xso.History.__name__,
                history))

        if not mucjid.is_bare:
            raise ValueError("MUC JID must be bare")

        try:
            room, fut, *_ = self._pending_mucs[mucjid]
        except KeyError:
            pass
        else:
            return room, fut

        try:
            room = self._joined_mucs[mucjid]
        except KeyError:
            pass
        else:
            fut = asyncio.Future()
            fut.set_result(None)
            return room, fut

        room = Room(self, mucjid)
        room.muc_autorejoin = autorejoin
        room.muc_password = password
        room.on_exit.connect(
            functools.partial(
                self._muc_exited,
                room
            )
        )
        room.on_muc_enter.connect(
            self._pending_on_enter,
        )

        fut = asyncio.Future()
        fut.add_done_callback(functools.partial(
            self._pending_join_done,
            mucjid,
            room,
        ))
        self._pending_mucs[mucjid] = room, fut, nick, history

        if self.client.established:
            self._send_join_presence(mucjid, history, nick, password)

        self.on_conversation_new(room)
        self.dependencies[
            aioxmpp.im.service.ConversationService
        ]._add_conversation(room)

        return room, fut

    async def get_affiliated(self, mucjid, affiliation):
        """
        Retrieve the list of JIDs with the given affiliation with a MUC.

        :param mucjid: The bare JID identifying the MUC.
        :type mucjid: :class:`~aioxmpp.JID`
        :param affiliation: The affiliation level to query.
        :type affiliation: :class:`str`
        :raises: :class:`aioxmpp.errors.XMPPAuthError` if the client does not
            have sufficient privileges to query affiliations of the given
            level.
        :return: Collection of JIDs with the given affiliation.
        """
        req = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.GET,
            to=mucjid,
        )
        req.payload = muc_xso.AdminQuery(
            items=[
                muc_xso.AdminItem(affiliation=affiliation),
            ]
        )

        resp = await self.client.send(req)
        return [
            item.jid
            for item in resp.items
        ]

    async def set_affiliation(self, mucjid, jid, affiliation, *, reason=None):
        """
        Change the affiliation of an entity with a MUC.

        :param mucjid: The bare JID identifying the MUC.
        :type mucjid: :class:`~aioxmpp.JID`
        :param jid: The bare JID of the entity whose affiliation shall be
            changed.
        :type jid: :class:`~aioxmpp.JID`
        :param affiliation: The new affiliation for the entity.
        :type affiliation: :class:`str`
        :param reason: Optional reason for the affiliation change.
        :type reason: :class:`str` or :data:`None`

        Change the affiliation of the given `jid` with the MUC identified by
        the bare `mucjid` to the given new `affiliation`. Optionally, a
        `reason` can be given.

        If you are joined in the MUC, :meth:`Room.muc_set_affiliation` may be
        more convenient, but it is possible to modify the affiliations of a MUC
        without being joined, given sufficient privilegues.

        Setting the different affiliations require different privilegues of the
        local user. The details can be checked in :xep:`0045` and are enforced
        solely by the server, not local code.

        The coroutine returns when the change in affiliation has been
        acknowledged by the server. If the server returns an error, an
        appropriate :class:`aioxmpp.errors.XMPPError` subclass is raised.
        """

        if mucjid is None or not mucjid.is_bare:
            raise ValueError("mucjid must be bare JID")

        if jid is None:
            raise ValueError("jid must not be None")

        if affiliation is None:
            raise ValueError("affiliation must not be None")

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=mucjid
        )

        iq.payload = muc_xso.AdminQuery(
            items=[
                muc_xso.AdminItem(jid=jid,
                                  reason=reason,
                                  affiliation=affiliation)
            ]
        )

        await self.client.send(iq)

    async def get_room_config(self, mucjid):
        """
        Query and return the room configuration form for the given MUC.

        :param mucjid: JID of the room to query
        :type mucjid: bare :class:`~.JID`
        :return: data form template for the room configuration
        :rtype: :class:`aioxmpp.forms.Data`

        .. seealso::

           :class:`~.ConfigurationForm`
              for a form template to work with the returned form

        .. versionadded:: 0.7
        """

        if mucjid is None or not mucjid.is_bare:
            raise ValueError("mucjid must be bare JID")

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.GET,
            to=mucjid,
            payload=muc_xso.OwnerQuery(),
        )

        return (await self.client.send(iq)).form

    async def set_room_config(self, mucjid, data):
        """
        Set the room configuration using a :xep:`4` data form.

        :param mucjid: JID of the room to query
        :type mucjid: bare :class:`~.JID`
        :param data: Filled-out configuration form
        :type data: :class:`aioxmpp.forms.Data`

        .. seealso::

           :class:`~.ConfigurationForm`
              for a form template to generate the required form

        A sensible workflow to, for example, set a room to be moderated, could
        be this::

          form = aioxmpp.muc.ConfigurationForm.from_xso(
              (await muc_service.get_room_config(mucjid))
          )
          form.moderatedroom = True
          await muc_service.set_rooom_config(mucjid, form.render_reply())

        .. versionadded:: 0.7
        """

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=mucjid,
            payload=muc_xso.OwnerQuery(form=data),
        )

        await self.client.send(iq)
