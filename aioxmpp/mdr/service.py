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
import aioxmpp.disco
import aioxmpp.service
import aioxmpp.tracking

from . import xso


class DeliveryReceiptsService(aioxmpp.service.Service):
    """
    :term:`Tracking Service` which tracks :xep:`184` replies.

    To send a tracked message, use the :meth:`attach_tracker` method before
    sending.

    .. automethod:: attach_tracker
    """

    ORDER_AFTER = [aioxmpp.disco.DiscoServer]

    disco_feature = aioxmpp.disco.register_feature("urn:xmpp:receipts")

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._bare_jid_maps = {}

    @aioxmpp.service.inbound_message_filter
    def _inbound_message_filter(self, stanza):
        recvd = stanza.xep0184_received
        if recvd is not None:
            try:
                tracker = self._bare_jid_maps.pop(
                    (stanza.from_, recvd.message_id)
                )
            except KeyError:
                self.logger.debug(
                    "received unexpected/late/dup <receipt/>. dropping."
                )
            else:
                try:
                    tracker._set_state(
                        aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT
                    )
                except ValueError as exc:
                    self.logger.debug(
                        "failed to update tracker after receipt: %s",
                        exc,
                    )
            return None

        return stanza

    def attach_tracker(self, stanza, tracker=None):
        """
        Return a new tracker or modify one to track the stanza.

        :param stanza: Stanza to track.
        :type stanza: :class:`aioxmpp.Message`
        :param tracker: Existing tracker to attach to.
        :type tracker: :class:`.tracking.MessageTracker`
        :raises ValueError: if the stanza is of type
            :attr:`~aioxmpp.MessageType.ERROR`
        :raises ValueError: if the stanza contains a delivery receipt
        :return: The message tracker for the stanza.
        :rtype: :class:`.tracking.MessageTracker`

        The `stanza` gets a :xep:`184` receipt request attached and internal
        handlers are set up to update the `tracker` state once a confirmation
        is received.

        .. warning::

           See the :ref:`api-tracking-memory`.

        """
        if stanza.xep0184_received is not None:
            raise ValueError(
                "requesting delivery receipts for delivery receipts is not "
                "allowed"
            )
        if stanza.type_ == aioxmpp.MessageType.ERROR:
            raise ValueError(
                "requesting delivery receipts for errors is not supported"
            )

        if tracker is None:
            tracker = aioxmpp.tracking.MessageTracker()

        stanza.xep0184_request_receipt = True
        stanza.autoset_id()
        self._bare_jid_maps[stanza.to, stanza.id_] = tracker
        return tracker


def compose_receipt(message):
    """
    Compose a :xep:`184` delivery receipt for a :class:`~aioxmpp.Message`.

    :param message: The message to compose the receipt for.
    :type message: :class:`~aioxmpp.Message`
    :raises ValueError: if the input message is of type
        :attr:`~aioxmpp.MessageType.ERROR`
    :raises ValueError: if the input message is a message receipt itself
    :return: A message which serves as a receipt for the input message.
    :rtype: :class:`~aioxmpp.Message`
    """

    if message.type_ == aioxmpp.MessageType.ERROR:
        raise ValueError("receipts cannot be generated for error messages")
    if message.xep0184_received:
        raise ValueError("receipts cannot be generated for receipts")
    if message.id_ is None:
        raise ValueError("receipts cannot be generated for id-less messages")

    reply = message.make_reply()
    reply.to = reply.to.bare()
    reply.xep0184_received = xso.Received(message.id_)
    return reply
