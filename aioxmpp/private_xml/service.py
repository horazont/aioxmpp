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

import aioxmpp
import aioxmpp.service as service

from . import xso as private_xml_xso


class PrivateXMLService(service.Service):
    """
    Service for handling server side private XML storage.

    .. automethod:: get_private_xml

    .. automethod:: set_private_xml
    """

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

    async def get_private_xml(self, query_xso):
        """
        Get the private XML data for the element `query_xso` from the
        server.

        :param query_xso: the object to retrieve.
        :returns: the stored private XML data.

        `query_xso` *must* serialize to an empty XML node of the
        wanted namespace and type and *must* be registered as private
        XML :class:`~private_xml_xso.Query` payload.

        """
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.GET,
            payload=private_xml_xso.Query(query_xso)
        )
        return await self.client.send(iq)

    async def set_private_xml(self, xso):
        """
        Store the serialization of `xso` on the server as the private XML
        data for the namespace of `xso`.

        :param xso: the XSO whose serialization is send as private XML data.
        """
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=private_xml_xso.Query(xso)
        )
        await self.client.send(iq)
