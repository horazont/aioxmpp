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

from datetime import datetime, timedelta
from enum import Enum

import aioxmpp.callbacks
import aioxmpp.forms
import aioxmpp.service
import aioxmpp.stanza
import aioxmpp.structs
import aioxmpp.tracking
import aioxmpp.im.conversation
import aioxmpp.im.dispatcher
import aioxmpp.im.p2p
import aioxmpp.im.service

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
    """

    DISCONNECTED = -2
    SYSTEM_SHUTDOWN = -1
    NORMAL = 0
    KICKED = 1
    AFFILIATION_CHANGE = 3
    MODERATION_CHANGE = 4
    BANNED = 5


class _OccupantDiffClass(Enum):
    UNIMPORTANT = 0
    NICK_CHANGED = 1
    LEFT = 2


class Occupant(aioxmpp.im.conversation.AbstractConversationMember):
    """
    A tracking object to track a single occupant in a :class:`Room`.

    .. autoattribute:: direct_jid

    .. autoattribute:: conversation_jid

    .. autoattribute:: nick

    .. attribute:: presence_state

       The :class:`~.PresenceState` of the occupant.

    .. attribute:: presence_status

       The :class:`~.LanguageMap` holding the presence status text of the
       occupant.

    .. attribute:: affiliation

       The affiliation of the occupant with the room.

    .. attribute:: role

       The current role of the occupant within the room.

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

    @classmethod
    def from_presence(cls, presence, is_self):
        try:
            item = presence.xep0045_muc_user.items[0]
        except (AttributeError, IndexError):
            affiliation = None
            role = None
            jid = None
        else:
            affiliation = item.affiliation
            role = item.role
            jid = item.jid

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
        self.affiliation = other.affiliation
        self.role = other.role
        self._direct_jid = other.direct_jid


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

    These properties are specific to MUC:

    .. autoattribute:: muc_active

    .. autoattribute:: muc_joined

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

    .. signal:: on_enter(presence, occupant, **kwargs)

       Emits when the initial room :class:`~.Presence` stanza for the
       local JID is received. This means that the join to the room is complete;
       the message history and subject are not transferred yet though.

       The `occupant` argument refers to the :class:`Occupant` which will be
       used to track the local user.

    .. signal:: on_message(msg, member, source, **kwargs)

        A message occured in the conversation.

        :param msg: Message which was received.
        :type msg: :class:`aioxmpp.Message`
        :param member: The member object of the sender.
        :type member: :class:`.AbstractConversationMember`
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

    .. signal:: on_nick_changed(member, old_nick, new_nick, **kwargs)

        The nickname of an occupant has changed

        :param member: The occupant whose nick has changed.
        :type member: :class:`Occupant`
        :param old_nick: The old nickname of the member.
        :type old_nick: :class:`str` or :data:`None`
        :param new_nick: The new nickname of the member.
        :type new_nick: :class:`str`

        The new nickname is already set in the `member` object. Both `old_nick`
        and `new_nick` are not :data:`None`.

        .. seealso::

            :meth:`.AbstractConversation.on_nick_changed` for the full
            specification.

    .. signal:: on_topic_changed(member, new_topic, *, muc_nick=None, **kwargs)

        The topic of the conversation has changed.

        :param member: The member object who changed the topic.
        :type member: :class:`Occupant` or :data:`None`
        :param new_topic: The new topic of the conversation.
        :type new_topic: :class:`.LanguageMap`
        :param muc_nick: The nickname of the occupant who changed the topic.
        :type muc_nick: :class:`str`

        The `member` is matched by nickname. It is possible that the member is
        not in the room at the time the topic chagne is received (for example
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

        When this signal is called, the `member` has already been removed from
        the :attr:`members`.

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

    .. signal:: on_exit(*, muc_leave_mode=None, muc_actor=None, muc_reason=None, **kwargs)

        Emits when the unavailable :class:`~.Presence` stanza for the
        local JID is received.

        :param muc_leave_mode: The cause of the removal.
        :type muc_leave_mode: :class:`LeaveMode` member
        :param muc_actor: The actor object if available.
        :type muc_actor: :class:`~.xso.UserActor`
        :param muc_reason: The reason for the cause, as given by the actor.
        :type muc_reason: :class:`str`

    The following signals inform users about state changes related to **other**
    occupants in the chat room. Note that different events may fire for the
    same presence stanza. A common example is a ban, which triggers
    :meth:`on_affiliation_change` (as the occupants affiliation is set to
    ``"outcast"``) and then :meth:`on_leave` (with :attr:`LeaveMode.BANNED`
    `mode`).

    .. signal:: on_muc_affiliation_changed(member, *, muc_actor=None, muc_reason=None, **kwargs)

       Emits when the affiliation of a `member` with the room changes.

       `occupant` is the :class:`Occupant` instance tracking the occupant whose
       affiliation changed.

       There may be `actor` and/or `reason` keyword arguments which provide
       details on who triggered the change in affiliation and for what reason.

    .. signal:: on_muc_role_changed(member, *, muc_actor=None, muc_reason=None, **kwargs)

       Emits when the role of an `occupant` in the room changes.

       `occupant` is the :class:`Occupant` instance tracking the occupant whose
       role changed.

       There may be `actor` and/or `reason` keyword arguments which provide
       details on who triggered the change in role and for what reason.

    """

    on_message = aioxmpp.callbacks.Signal()

    # this occupant state events
    on_enter = aioxmpp.callbacks.Signal()
    on_muc_suspend = aioxmpp.callbacks.Signal()
    on_muc_resume = aioxmpp.callbacks.Signal()
    on_exit = aioxmpp.callbacks.Signal()

    # other occupant state events
    on_join = aioxmpp.callbacks.Signal()
    on_leave = aioxmpp.callbacks.Signal()
    on_presence_changed = aioxmpp.callbacks.Signal()
    on_muc_affiliation_changed = aioxmpp.callbacks.Signal()
    on_nick_changed = aioxmpp.callbacks.Signal()
    on_muc_role_changed = aioxmpp.callbacks.Signal()

    # room state events
    on_topic_changed = aioxmpp.callbacks.Signal()

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
        self.muc_autorejoin = False
        self.muc_password = None

    @property
    def service(self):
        return self._service

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
        }

    def _suspend(self):
        self.on_muc_suspend()
        self._active = False

    def _disconnect(self):
        if not self._joined:
            return
        self.on_exit(
            muc_leave_mode=LeaveMode.DISCONNECTED
        )
        self._joined = False
        self._active = False

    def _resume(self):
        self._this_occupant = None
        self._occupant_info = {}
        self._active = False
        self.on_muc_resume()

    def _match_tracker(self, message):
        try:
            tracker = self._tracking_by_id[message.id_]
        except KeyError:
            if (self._this_occupant is not None and
                    message.from_ == self._this_occupant.conversation_jid):
                key = _extract_one_pair(message.body)
                try:
                    trackers = self._tracking_by_body[key]
                except KeyError:
                    trackers = None
            else:
                trackers = None

            if not trackers:
                tracker = None
            else:
                tracker = trackers[0]

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

        if not sent:
            if self._match_tracker(message):
                return

        if (self._this_occupant and
                self._this_occupant._conversation_jid == message.from_):
            occupant = self._this_occupant
        else:
            occupant = self._occupant_info.get(message.from_, None)

        if not message.body and message.subject:
            self._subject = aioxmpp.structs.LanguageMap(message.subject)
            self._subject_setter = message.from_.resource

            self.on_topic_changed(
                occupant,
                self._subject,
                muc_nick=message.from_.resource,
            )

        elif message.body:
            self.on_message(
                message,
                occupant,
                source,
            )

    def _diff_presence(self, stanza, info, existing):
        if (not info.presence_state.available and
                303 in stanza.xep0045_muc_user.status_codes):
            return (
                _OccupantDiffClass.NICK_CHANGED,
                (
                    stanza.xep0045_muc_user.items[0].nick,
                )
            )

        result = (_OccupantDiffClass.UNIMPORTANT, None)
        to_emit = []

        if not info.presence_state.available:
            status_codes = stanza.xep0045_muc_user.status_codes
            mode = LeaveMode.NORMAL
            try:
                reason = stanza.xep0045_muc_user.items[0].reason
                actor = stanza.xep0045_muc_user.items[0].actor
            except IndexError:
                reason = None
                actor = None

            if 307 in status_codes:
                mode = LeaveMode.KICKED
            elif 301 in status_codes:
                mode = LeaveMode.BANNED
            elif 321 in status_codes:
                mode = LeaveMode.AFFILIATION_CHANGE
            elif 322 in status_codes:
                mode = LeaveMode.MODERATION_CHANGE
            elif 332 in status_codes:
                mode = LeaveMode.SYSTEM_SHUTDOWN

            result = (
                _OccupantDiffClass.LEFT,
                (
                    mode,
                    actor,
                    reason,
                )
            )
        elif   (existing.presence_state != info.presence_state or
                existing.presence_status != info.presence_status):
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
                    "actor": stanza.xep0045_muc_user.items[0].actor,
                    "reason": stanza.xep0045_muc_user.items[0].reason,
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
                    "actor": stanza.xep0045_muc_user.items[0].actor,
                    "reason": stanza.xep0045_muc_user.items[0].reason,
                },
            ))

        if to_emit:
            existing.update(info)
            for signal, args, kwargs in to_emit:
                signal(*args, **kwargs)

        return result

    def _handle_self_presence(self, stanza):
        info = Occupant.from_presence(stanza, True)

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
            self.on_enter(stanza, info)
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
            self.on_exit(muc_leave_mode=mode,
                         muc_actor=actor,
                         muc_reason=reason)
            self._joined = False
            self._active = False

    def _inbound_muc_user_presence(self, stanza):
        self._service.logger.debug("%s: inbound muc user presence %r",
                                   self._mucjid,
                                   stanza)

        if (110 in stanza.xep0045_muc_user.status_codes or
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
            self.on_leave(existing,
                          muc_leave_mode=mode,
                          muc_actor=actor,
                          muc_reason=reason)
            del self._occupant_info[existing.conversation_jid]

    @asyncio.coroutine
    def send_message(self, msg):
        """
        Send a message to the MUC.

        :param msg: The message to send.
        :type msg: :class:`aioxmpp.Message`

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
        yield from self.service.client.stream.send(msg)
        self.on_message(
            msg,
            self._this_occupant,
            aioxmpp.im.dispatcher.MessageSource.STREAM
        )

    def _tracker_closed(self, tracker):
        try:
            id_key, body_key = self._tracking_metadata[tracker]
        except KeyError:
            return
        self._tracking_by_id.pop(id_key, None)
        self._tracking_by_body.pop(body_key, None)

    @asyncio.coroutine
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
        token = yield from tracking_svc.send_tracked(msg, tracker)
        return token, tracker

    @asyncio.coroutine
    def set_nick(self, new_nick):
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
        yield from self._service.client.stream.send(
            stanza
        )

    @asyncio.coroutine
    def kick(self, member, reason=None):
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
        yield from self.muc_set_role(
            member.nick,
            "none",
            reason=reason
        )

    @asyncio.coroutine
    def muc_set_role(self, nick, role, *, reason=None):
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

        yield from self.service.client.stream.send(
            iq
        )

    @asyncio.coroutine
    def ban(self, member, reason=None, *, request_kick=True):
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

        yield from self.muc_set_affiliation(
            member.direct_jid,
            "outcast",
            reason=reason
        )

    @asyncio.coroutine
    def muc_set_affiliation(self, jid, affiliation, *, reason=None):
        """
        Convenience wrapper around :meth:`.MUCClient.set_affiliation`. See
        there for details, and consider its `mucjid` argument to be set to
        :attr:`mucjid`.
        """
        return (yield from self.service.set_affiliation(
            self._mucjid,
            jid, affiliation,
            reason=reason))

    @asyncio.coroutine
    def set_topic(self, new_topic):
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

        yield from self.service.client.stream.send(msg)

    @asyncio.coroutine
    def leave(self):
        """
        Leave the MUC.
        """
        fut = self.on_exit.future()

        def cb(**kwargs):
            fut.set_result(None)
            return True  # disconnect

        self.on_exit.connect(cb)

        presence = aioxmpp.stanza.Presence(
            type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
            to=self._mucjid
        )
        yield from self.service.client.stream.send(presence)

        yield from fut

    @asyncio.coroutine
    def muc_request_voice(self):
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

        yield from self.service.client.stream.send(msg)


def _connect_to_signal(signal, func):
    return signal, signal.connect(func)


class MUCClient(aioxmpp.service.Service):
    """
    :term:`Conversation Implementation` for Multi-User Chats (:xep:`45`).

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

    .. automethod:: set_affiliation

    .. automethod:: set_room_config

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.muc.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.

    .. versionchanged:: 0.9

        This class was completely remodeled in 0.9 to conform with the
        :class:`aioxmpp.im` interface.

    """

    ORDER_AFTER = [
        aioxmpp.im.dispatcher.IMDispatcher,
        aioxmpp.im.service.ConversationService,
        aioxmpp.tracking.BasicTrackingService,
    ]

    ORDER_BEFORE = [
        aioxmpp.im.p2p.Service,
    ]

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
        self.client.stream.enqueue(presence)

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

    def _pending_join_done(self, mucjid, fut):
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
            self.client.stream.enqueue(unjoin)

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

    def _inbound_muc_presence(self, stanza):
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
        if stanza.xep0045_muc is not None:
            self._inbound_muc_presence(stanza)
            return None
        return stanza

    @aioxmpp.service.depfilter(
        aioxmpp.im.dispatcher.IMDispatcher,
        "message_filter")
    def _handle_message(self, message, peer, sent, source):
        if (source == aioxmpp.im.dispatcher.MessageSource.CARBONS
                and message.xep0045_muc_user):
            return None

        mucjid = peer.bare()
        try:
            muc = self._joined_mucs[mucjid]
        except KeyError:
            return message

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

    def get_muc(self, mucjid):
        try:
            return self._joined_mucs[mucjid]
        except KeyError:
            return self._pending_mucs[mucjid][0]

    @asyncio.coroutine
    def _shutdown(self):
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
        before yielding next (e.g. in a non-deferred event handler to the :meth:`~.ConversationService.on_conversation_added` signal), to avoid
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
        room.on_enter.connect(
            self._pending_on_enter,
        )

        fut = asyncio.Future()
        fut.add_done_callback(functools.partial(
            self._pending_join_done,
            mucjid
        ))
        self._pending_mucs[mucjid] = room, fut, nick, history

        if self.client.established:
            self._send_join_presence(mucjid, history, nick, password)

        self.dependencies[
            aioxmpp.im.service.ConversationService
        ]._add_conversation(room)

        return room, fut

    @asyncio.coroutine
    def set_affiliation(self, mucjid, jid, affiliation, *, reason=None):
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

        yield from self.client.stream.send(
            iq
        )

    @asyncio.coroutine
    def get_room_config(self, mucjid):
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

        return (yield from self.client.stream.send(
            iq
        )).form

    @asyncio.coroutine
    def set_room_config(self, mucjid, data):
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

        yield from self.client.stream.send(
            iq,
        )
