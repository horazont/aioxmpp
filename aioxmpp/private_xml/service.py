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

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

    @asyncio.coroutine
    def get_private_xml(self, query_xso):
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.GET,
            payload=private_xml_xso.Query(query_xso)
        )
        return (yield from self.client.stream.send(iq))

    @asyncio.coroutine
    def set_private_xml(self, xso):
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=private_xml_xso.Query(xso)
        )
        yield from self.client.stream.send(iq)
