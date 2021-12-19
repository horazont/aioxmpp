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

from . import xso as vcard_xso


class VCardService(service.Service):
    """
    Service for handling vcard-temp.

    .. automethod:: get_vcard

    .. automethod:: set_vcard
    """

    async def get_vcard(self, jid=None):
        """
        Get the vCard stored for the jid `jid`. If `jid` is
        :data:`None` get the vCard of the connected entity.

        :param jid: the object to retrieve.
        :returns: the stored vCard.

        We mask a :class:`XMPPCancelError` in case it is
        ``feature-not-implemented`` or ``item-not-found`` and return
        an empty vCard, since this can be understood to be semantically
        equivalent.
        """

        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.GET,
            to=jid,
            payload=vcard_xso.VCard(),
        )

        try:
            return await self.client.send(iq)
        except aioxmpp.XMPPCancelError as e:
            if e.condition in (
                    aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED,
                    aioxmpp.ErrorCondition.ITEM_NOT_FOUND):
                return vcard_xso.VCard()
            else:
                raise

    async def set_vcard(self, vcard, jid=None):
        """
        Store the vCard `vcard` for the connected entity.

        :param vcard: the vCard to store.

        .. note::

           `vcard` should always be derived from the result of
           `get_vcard` to preserve the elements of the vcard the
           client does not modify.

        .. warning::

           It is in the responsibility of the user to supply valid
           vcard data as per :xep:`0054`.
        """
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=vcard,
            to=jid,
        )
        await self.client.send(iq)
