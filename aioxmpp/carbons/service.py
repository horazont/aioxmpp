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

import aioxmpp.service

from aioxmpp.utils import namespaces

from . import xso as carbons_xso


class CarbonsClient(aioxmpp.service.Service):
    """
    Provide an interface to enable and disable Message Carbons on the server
    side.

    .. note::

       This service deliberately does not provide a way to actually obtain sent
       or received carbonated messages.

       The common way for a service to do this would be a stanza filter (see
       :class:`aioxmpp.stream.StanzaStream`); however, in general the use and
       further distribution of carbonated messages highly depends on the
       application: it does, for example, not make sense to simply unwrap
       carbonated messages.

    .. automethod:: enable

    .. automethod:: disable
    """

    ORDER_AFTER = [
        aioxmpp.DiscoClient,
    ]

    async def _check_for_feature(self):
        disco_client = self.dependencies[aioxmpp.DiscoClient]
        info = await disco_client.query_info(
            self.client.local_jid.replace(
                localpart=None,
                resource=None,
            )
        )

        if namespaces.xep0280_carbons_2 not in info.features:
            raise RuntimeError(
                "Message Carbons ({}) are not supported by the server".format(
                    namespaces.xep0280_carbons_2
                )
            )

    async def enable(self):
        """
        Enable message carbons.

        :raises RuntimeError: if the server does not support message carbons.
        :raises aioxmpp.XMPPError: if the server responded with an error to the
                                   request.
        :raises: as specified in :meth:`aioxmpp.Client.send`
        """
        await self._check_for_feature()

        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=carbons_xso.Enable()
        )

        await self.client.send(iq)

    async def disable(self):
        """
        Disable message carbons.

        :raises RuntimeError: if the server does not support message carbons.
        :raises aioxmpp.XMPPError: if the server responded with an error to the
                                   request.
        :raises: as specified in :meth:`aioxmpp.Client.send`
        """
        await self._check_for_feature()

        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=carbons_xso.Disable()
        )

        await self.client.send(iq)
