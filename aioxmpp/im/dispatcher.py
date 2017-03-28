########################################################################
# File name: dispatcher.py
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
import enum

import aioxmpp.callbacks
import aioxmpp.service
import aioxmpp.stream


class MessageSource(enum.Enum):
    STREAM = 0
    CARBONS = 1


class IMDispatcher(aioxmpp.service.Service):
    """
    Dispatches messages, taking into account carbons.

    .. signal:: on_message(message, sent, source)

       A message was received or sent.

       :param message: Message stanza
       :type message: :class:`aioxmpp.Message`
       :param sent: Whether the mesasge was sent or received.
       :type sent: :class:`bool`
       :param source: The source of the message.
       :type source: :class:`MessageSource`

       `message` is the message stanza which was sent or received.

       If `sent` is true, the message was sent from this resource *or* another
       resource of the same account, if Message Carbons are enabled.

       `source` indicates how the message was sent or received. It may be one
       of the values of the :class:`MessageSource` enumeration.

    """

    ORDER_AFTER = [
        # we want to be loaded after the SimplePresenceDispatcher to ensure
        # that PresenceClient has updated its data structures before the
        # dispatch_presence handler runs.
        # this helps one-to-one conversations a lot, because they can simply
        # re-use the PresenceClient state
        aioxmpp.dispatcher.SimplePresenceDispatcher,
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self.message_filter = aioxmpp.callbacks.Filter()
        self.presence_filter = aioxmpp.callbacks.Filter()

    @aioxmpp.service.depsignal(
        aioxmpp.stream.StanzaStream,
        "on_message_received")
    def dispatch_message(self, message, *,
                         sent=False,
                         source=MessageSource.STREAM):
        filtered = self.message_filter.filter(
            message,
            sent,
            source,
        )

        if filtered is not None:
            self.logger.debug(
                "message was not processed by any IM handler: %s",
                filtered,
            )

    @aioxmpp.service.depsignal(
        aioxmpp.stream.StanzaStream,
        "on_presence_received")
    def dispatch_presence(self, presence, *, sent=False):
        filtered = self.presence_filter.filter(
            presence,
            presence.from_,
            sent,
        )

        if filtered is not None:
            self.logger.debug(
                "presence was not processed by any IM handler: %s",
                filtered,
            )
