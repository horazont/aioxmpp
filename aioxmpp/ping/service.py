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
    async def handle_ping(self, request):
        return ping_xso.Ping()

    async def ping(self, peer):
        """
        Wrapper around :func:`aioxmpp.ping.ping`.

        **When to use this wrapper vs. the global function:** Using this method
        has the side effect that the application will start to respond to
        :xep:`199` pings. While this is not a security issue per se (as
        responding to :xep:`199` pings only changes the format of the reply,
        not the fact that a reply is sent from the client), it may not be
        desirable under all circumstances.

        So especially when developing a Service which does not *require* that
        the application replies to pings (for example, when implementing a
        stream or group chat aliveness check), it is preferable to use the
        global function.

        When implementing an application where it is desirable to reply to
        pings, using this wrapper is fine.

        In general, aioxmpp services should avoid depending on this service.

        (The decision essentially boils down to "summon this service or not?",
        and it is not a decision aioxmpp should make for the application unless
        necessary for compliance.)

        .. versionchanged:: 0.11

            Converted to a shim wrapper.
        """
        return await ping(self.client, peer)


async def ping(client, peer):
    """
    Ping a peer.

    :param peer: The peer to ping.
    :type peer: :class:`aioxmpp.JID`
    :raises aioxmpp.errors.XMPPError: as received

    Send a :xep:`199` ping IQ to `peer` and wait for the reply.

    This is a low-level version of :meth:`aioxmpp.PingService.ping`.

    **When to use this function vs. the service method:** See
    :meth:`aioxmpp.PingService.ping`.

    .. note::

        If the peer does not support :xep:`199`, they will respond with
        a ``cancel`` ``service-unavailable`` error. However, some
        implementations return a ``cancel`` ``feature-not-implemented``
        error instead. Callers should be prepared for the
        :class:`aioxmpp.XMPPCancelError` exceptions in those cases.

    .. versionchanged:: 0.11

        Extracted this helper from :class:`aioxmpp.PingService`.
    """

    iq = aioxmpp.IQ(
        to=peer,
        type_=aioxmpp.IQType.GET,
        payload=ping_xso.Ping()
    )

    await client.send(iq)
