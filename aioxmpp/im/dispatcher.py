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
import asyncio
import enum

import aioxmpp.callbacks
import aioxmpp.carbons
import aioxmpp.service
import aioxmpp.stream


class MessageSource(enum.Enum):
    STREAM = 0
    CARBONS = 1


class IMDispatcher(aioxmpp.service.Service):
    """
    Dispatches messages, taking into account carbons.

    .. function:: message_filter(message, peer, sent, source)

       A message was received or sent.

       :param message: Message stanza
       :type message: :class:`aioxmpp.Message`
       :param peer: The peer from/to which the stanza was received/sent
       :type peer: :class:`aioxmpp.JID`
       :param sent: Whether the mesasge was sent or received.
       :type sent: :class:`bool`
       :param source: The source of the message.
       :type source: :class:`MessageSource`

       `message` is the message stanza which was sent or received.

       `peer` is the JID of the peer involved in the message. If the message
       was sent, this is the :attr:`~.StanzaBase.to` and otherwise it is the
       :attr:`~.StanzaBase.from_` attribute of the stanza.

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

        aioxmpp.carbons.CarbonsClient,
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self.message_filter = aioxmpp.callbacks.Filter()
        self.presence_filter = aioxmpp.callbacks.Filter()

    @aioxmpp.service.depsignal(
        aioxmpp.node.Client,
        "before_stream_established")
    async def enable_carbons(self, *args):
        carbons = self.dependencies[aioxmpp.carbons.CarbonsClient]
        try:
            await carbons.enable()
        except (RuntimeError, aioxmpp.errors.XMPPError):
            self.logger.info(
                "remote server does not support message carbons"
            )
        else:
            self.logger.info(
                "message carbons enabled successfully"
            )
        return True

    @aioxmpp.service.depsignal(
        aioxmpp.stream.StanzaStream,
        "on_message_received")
    def dispatch_message(self, message, *,
                         sent=False,
                         source=MessageSource.STREAM):
        if message.xep0280_received is not None:
            if (message.from_ is not None and
                    message.from_ != self.client.local_jid.bare()):
                return
            message = message.xep0280_received.stanza
            source = MessageSource.CARBONS
        elif message.xep0280_sent is not None:
            if (message.from_ is not None and
                    message.from_ != self.client.local_jid.bare()):
                return
            message = message.xep0280_sent.stanza
            sent = True
            source = MessageSource.CARBONS

        peer = message.to if sent else message.from_

        filtered = self.message_filter.filter(
            message,
            peer,
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
