########################################################################
# File name: p2p.py
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

import aioxmpp.service

from .conversation import (
    AbstractConversationMember,
    AbstractConversation,
    AbstractConversationService,
    ConversationFeature,
)

from .dispatcher import IMDispatcher, MessageSource

from .service import ConversationService


class Member(AbstractConversationMember):
    """
    Member of a one-on-one conversation.

    .. autoattribute:: direct_jid

    """

    def __init__(self, peer_jid, is_self):
        super().__init__(peer_jid, is_self)

    @property
    def direct_jid(self):
        """
        The JID of the peer.
        """

        return self._conversation_jid

    @property
    def uid(self) -> bytes:
        return b"xmpp:" + str(self._conversation_jid.bare()).encode("utf-8")


class Conversation(AbstractConversation):
    """
    Implementation of :class:`~.im.conversation.AbstractConversation` for
    one-on-one conversations.

    .. seealso::

        :class:`.im.conversation.AbstractConversation`
          for documentation on the interface implemented by this class.
    """

    def __init__(self, service, peer_jid, parent=None):
        super().__init__(service, parent=parent)
        self.__peer_jid = peer_jid
        self.__members = (
            Member(self._client.local_jid, True),
            Member(peer_jid, False),
        )

    @property
    def features(self):
        return (
            frozenset([ConversationFeature.SEND_MESSAGE,
                       ConversationFeature.LEAVE]) |
            super().features
        )

    def _handle_message(self, msg, peer, sent, source):
        if sent:
            member = self.__members[0]
        else:
            member = self.__members[1]

        self._service.logger.debug("emitting on_message for %s",
                                   self.__peer_jid)
        self.on_message(msg, member, source)

    @property
    def jid(self):
        return self.__peer_jid

    @property
    def members(self):
        return self.__members

    @property
    def me(self):
        return self.__members[0]

    def send_message(self, msg):
        msg.autoset_id()
        msg.to = self.__peer_jid
        self.on_message(msg, self.me, MessageSource.STREAM)
        return self._client.enqueue(msg)

    async def send_message_tracked(self, msg):
        raise self._not_implemented_error("message tracking")

    async def leave(self):
        self._service._conversation_left(self)


class Service(AbstractConversationService, aioxmpp.service.Service):
    """
    Manage one-to-one conversations.

    .. seealso::

        :class:`~.AbstractConversationService`
            for useful common signals

    This service manages one-to-one conversations, including private
    conversations running in the framework of a multi-user chat. In those
    cases, the respective multi-user chat conversation service requests a
    conversation from this service to use.

    For each bare JID, there can either be a single conversation for the bare
    JID or zero or more conversations for full JIDs. Mixing conversations to
    bare and full JIDs of the same bare JID is not allowed, because it is
    ambiguous.

    This service creates conversations if it detects them as one-on-one
    conversations. Subscribe to
    :meth:`aioxmpp.im.ConversationService.on_conversation_added` to be notified
    about new conversations being auto-created.

    .. automethod:: get_conversation
    """

    ORDER_AFTER = [
        ConversationService,
        IMDispatcher,
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._conversationmap = {}
        self.on_conversation_new.connect(
            self.dependencies[ConversationService]._add_conversation
        )

    def _make_conversation(self, peer_jid, spontaneous):
        self.logger.debug("creating new conversation for %s (spontaneous=%s)",
                          peer_jid, spontaneous)
        result = Conversation(self, peer_jid, parent=None)
        self._conversationmap[peer_jid] = result
        if spontaneous:
            self.on_spontaneous_conversation(result)
        self.on_conversation_new(result)
        result.on_enter()
        self.logger.debug("new conversation for %s set up and events emitted",
                          peer_jid)
        return result

    @aioxmpp.service.depfilter(IMDispatcher, "message_filter")
    def _filter_message(self, msg, peer, sent, source):
        try:
            existing = self._conversationmap[peer]
        except KeyError:
            try:
                existing = self._conversationmap[peer.bare()]
            except KeyError:
                existing = None

        if (existing is None and
                (msg.type_ == aioxmpp.MessageType.CHAT or
                 msg.type_ == aioxmpp.MessageType.NORMAL) and
                msg.body):
            conversation_jid = peer.bare()
            if msg.xep0045_muc_user is not None:
                conversation_jid = peer
            existing = self._make_conversation(conversation_jid, True)

        if existing is not None:
            existing._handle_message(msg, peer, sent, source)
            return None

        return msg

    def get_conversation(self, peer_jid, *, current_jid=None):
        """
        Get or create a new one-to-one conversation with a peer.

        :param peer_jid: The JID of the peer to converse with.
        :type peer_jid: :class:`aioxmpp.JID`
        :param current_jid: The current JID to lock the conversation to (see
                            :rfc:`6121`).
        :type current_jid: :class:`aioxmpp.JID`
        :rtype: :class:`Conversation`
        :return: The new or existing conversation with the peer.

        `peer_jid` must be a full or bare JID. See the :class:`Service`
        documentation for details.

        .. versionchanged:: 0.10

            In 0.9, this was a coroutine. Sorry.
        """

        try:
            return self._conversationmap[peer_jid]
        except KeyError:
            pass
        return self._make_conversation(peer_jid, False)

    def _conversation_left(self, conv):
        del self._conversationmap[conv.jid]
