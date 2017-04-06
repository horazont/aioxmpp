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
import functools

import aioxmpp.callbacks
import aioxmpp.service


class ConversationService(aioxmpp.service.Service):
    """
    Central place where all :class:`.im.conversation.AbstractConversation`
    subclass instances are collected.

    It provides discoverability of all existing conversations (in no particular
    order) and signals on addition and removal of active conversations. This is
    useful for front ends to track conversations globally without needing to
    know about the specific conversation providers.

    .. signal:: on_conversation_added(conversation)

       A new conversation has been added.

       :param conversation: The conversation which was added.
       :type conversation: :class:`~.im.conversation.AbstractConversation`

       This signal is fired when a new conversation is added by a
       :term:`Conversation Implementation`.

       .. note::

          If you are looking for a "on_conversation_removed" event or similar,
          there is none. You should use the
          :meth:`.AbstractConversation.on_exit` event of the `conversation`.

    .. autoattribute:: conversations

    For :term:`Conversation Implementations <Conversation Implementation>`, the
    following methods are intended; they should not be used by applications.

    .. automethod:: _add_conversation

    """

    on_conversation_added = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._conversations = []

    @property
    def conversations(self):
        """
        Return an iterable of conversations in which the local client is
        participating.
        """
        return self._conversations

    def _handle_conversation_exit(self, conv, *args, **kwargs):
        self._conversations.remove(conv)

    def _add_conversation(self, conversation):
        """
        Add the conversation and fire the :meth:`on_conversation_added` event.

        :param conversation: The conversation object to add.
        :type conversation: :class:`~.AbstractConversation`

        The conversation is added to the internal list of conversations which
        can be queried at :attr:`conversations`. The
        :meth:`on_conversation_added` event is fired.

        In addition, the :class:`ConversationService` subscribes to the
        :meth:`~.AbstractConversation.on_exit` event to remove the conversation
        from the list automatically. There is no need to remove a conversation
        from the list explicitly.
        """
        self.on_conversation_added(conversation)
        conversation.on_exit.connect(
            functools.partial(
                self._handle_conversation_exit,
                conversation
            ),
        )
        self._conversations.append(conversation)
