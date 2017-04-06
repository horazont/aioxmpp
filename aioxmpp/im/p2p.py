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
)

from .dispatcher import IMDispatcher, MessageSource

from .service import ConversationService


class Member(AbstractConversationMember):
    def __init__(self, peer_jid, is_self):
        super().__init__(peer_jid, is_self)

    @property
    def direct_jid(self):
        return self._conversation_jid


class Conversation(AbstractConversation):
    def __init__(self, service, peer_jid, parent=None):
        super().__init__(service, parent=parent)
        self.__peer_jid = peer_jid
        self.__members = (
            Member(self._client.local_jid, True),
            Member(peer_jid, False),
        )

    def _handle_message(self, msg, peer, sent, source):
        if sent:
            member = self.__members[0]
        else:
            member = self.__members[1]

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
        msg.to = self.__peer_jid
        self.on_message(msg, self.me, MessageSource.STREAM)
        return self._client.stream.enqueue(msg)

    @asyncio.coroutine
    def send_message_tracked(self, msg):
        raise self._not_implemented_error("message tracking")

    @asyncio.coroutine
    def leave(self):
        yield from super().leave()


class Service(AbstractConversationService, aioxmpp.service.Service):
    """
    Manage one-to-one conversations.

    This service manages one-to-one conversations, including private
    conversations running in the framework of a multi-user chat. In those
    cases, the respective multi-user chat conversation service requests a
    conversation from this service to use.

    For each bare JID, there can either be a single conversation for the bare
    JID or zero or more conversations for full JIDs. Mixing conversations to
    bare and full JIDs of the same bare JID is not allowed, because it is
    ambiguous.

    If bare JIDs are used, the conversation is assumed to be between

    .. note::

       This service does *not* automatically create new conversations when
       messages which cannot be mapped to any conversation are incoming. This
       is handled by the :class:`AutoOneToOneConversationService` service. The
       reason for this is that it must have a lower priority than multi-user
       chat services so that those are able to handle those messages if they
       belong to a new private multi-user chat conversation.

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

    def _make_conversation(self, peer_jid):
        result = Conversation(self, peer_jid, parent=None)
        self._conversationmap[peer_jid] = result
        print("_make_conversation", peer_jid)
        self.on_conversation_new(result)
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

        if     ((msg.type_ == aioxmpp.MessageType.CHAT or
                 msg.type_ == aioxmpp.MessageType.NORMAL) and
                msg.body):
            if existing is None:
                existing = self._make_conversation(peer.bare())

            existing._handle_message(msg, peer, sent, source)
            return None

        return msg

    @asyncio.coroutine
    def get_conversation(self, peer_jid, *, current_jid=None):
        """
        Get or create a new one-to-one conversation with a peer.

        :param peer_jid: The JID of the peer to converse with.
        :type peer_jid: :class:`aioxmpp.JID`
        :param current_jid: The current JID to lock the conversation to (see
                            :rfc:`6121`).
        :type current_jid: :class:`aioxmpp.JID`

        `peer_jid` must be a full or bare JID.
        """
        try:
            return self._conversationmap[peer_jid]
        except KeyError:
            pass
        return self._make_conversation(peer_jid)

    def _conversation_left(self, conv):
        del self._conversationmap[conv.peer_jid]
        self.on_conversation_left(conv)
