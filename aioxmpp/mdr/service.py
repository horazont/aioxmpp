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


class DeliveryReceiptsService(aioxmpp.service.Service):
    ORDER_AFTER = [aioxmpp.DiscoServer]

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
                tracker._set_state(
                    aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT
                )
            return None

        return stanza

    def attach_tracker(self, stanza, tracker):
        """
        Return a new tracker or modify one to track the stanza.

        :param stanza: Stanza to track.
        :type stanza: :class:`aioxmpp.Message`
        :param tracker: Existing tracker to attach to.
        :type tracker: :class:`.tracking.MessageTracker`
        :return: The message tracker for the stanza.
        :rtype: :class:`.tracking.MessageTracker`

        The `stanza` gets a :xep:`184` reciept request attached and internal
        handlers are set up to update the `tracker` state once a confirmation
        is received.

        .. warning::

           See the :ref:`api-tracking-memory`.

        """
        stanza.xep0184_request_receipt = True
        stanza.autoset_id()
        self._bare_jid_maps[stanza.to, stanza.id_] = tracker
        return tracker
