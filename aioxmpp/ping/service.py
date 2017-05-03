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

import aioxmpp.disco
import aioxmpp.service
import aioxmpp.structs

from aioxmpp.utils import namespaces

from . import xso as ping_xso


class PingService(aioxmpp.service.Service):
    """
    Service implementing XMPP Ping (:xep:`199`).

    This service implements the response to XMPP Pings and provides a method
    to send pings.

    .. automethod:: ping
    """

    ORDER_AFTER = [
        aioxmpp.disco.DiscoServer,
    ]

    _ping_feature = aioxmpp.disco.register_feature(
        namespaces.xep0199_ping
    )

    @aioxmpp.service.iq_handler(aioxmpp.structs.IQType.GET, ping_xso.Ping)
    @asyncio.coroutine
    def handle_ping(self, request):
        return ping_xso.Ping()

    @asyncio.coroutine
    def ping(self, peer):
        """
        Ping a peer.

        :param peer: The peer to ping.
        :type peer: :class:`aioxmpp.JID`
        :raises aioxmpp.errors.XMPPError: as received

        Send a :xep:`199` ping IQ to `peer` and wait for the reply.

        .. note::

            If the peer does not support :xep:`199`, they will respond with
            a ``cancel`` ``service-unavailable`` error. However, some
            implementations return a ``cancel`` ``feature-not-implemented``
            error instead. Callers should be prepared for the
            :class:`aioxmpp.XMPPCancelError` exceptions in those cases.
        """

        iq = aioxmpp.IQ(
            to=peer,
            type_=aioxmpp.IQType.GET,
            payload=ping_xso.Ping()
        )

        yield from self.client.stream.send(iq)
