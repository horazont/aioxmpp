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
import logging
from aioxmpp.service import Service
from . import xso


logger = logging.getLogger(__name__)


async def get_registration_fields(xmlstream, timeout=60):
    """
    A query is sent to the server to obtain the fields that need to be
    filled to register with the server.

    :param xmlstream: Specifies the stream connected to the server where
                      the account will be created.
    :type xmlstream: :class:`aioxmpp.protocol.XMLStream`

    :param timeout: Maximum time in seconds to wait for an IQ response, or
                    :data:`None` to disable the timeout.
    :type timeout: :class:`~numbers.Real` or :data:`None`

    :return: :attr:`list`
    """

    iq = aioxmpp.IQ(
        to=aioxmpp.JID.fromstr(xmlstream._to),
        type_=aioxmpp.IQType.GET,
        payload=xso.Query()
    )
    iq.autoset_id()

    reply = await aioxmpp.protocol.send_and_wait_for(
        xmlstream,
        [iq],
        [aioxmpp.IQ],
        timeout=timeout
    )
    return reply.payload


async def register(xmlstream, query_xso, timeout=60):
    """
    Create a new account on the server.

    :param query_xso: XSO with the information needed for the registration.
    :type query_xso: :class:`~aioxmpp.ibr.Query`

    :param xmlstream: Specifies the stream connected to the server where
                      the account will be created.
    :type xmlstream: :class:`aioxmpp.protocol.XMLStream`

    :param timeout: Maximum time in seconds to wait for an IQ response, or
                    :data:`None` to disable the timeout.
    :type timeout: :class:`~numbers.Real` or :data:`None`
    """
    iq = aioxmpp.IQ(
        to=aioxmpp.JID.fromstr(xmlstream._to),
        type_=aioxmpp.IQType.SET,
        payload=query_xso
    )
    iq.autoset_id()

    await aioxmpp.protocol.send_and_wait_for(
        xmlstream,
        [iq],
        [aioxmpp.IQ],
        timeout=timeout
    )


def get_used_fields(payload):
    """
    Get a list containing the names of the fields that are used in the
    xso.Query.

    :param payload: Query object o be
    :type payload: :class:`~aioxmpp.ibr.Query`
    :return: :attr:`list`
    """
    return [
        tag
        for tag, descriptor in payload.CHILD_MAP.items()
        if descriptor.__get__(payload, type(payload)) is not None
    ]


class RegistrationService(Service):
    """
    Service implementing the XMPP In-Band Registration(:xep:`0077`)
    use cases for registered entities.

    This service allows an already registered and authenticated entity
    to request information about the registration, cancel an existing
    registration, or change a password.

    .. automethod:: get_client_info

    .. automethod:: change_pass

    .. automethod:: cancel_registration

    """

    async def get_client_info(self):
        """
        A query is sent to the server to obtain the client's data stored at the
        server.

        :return: :class:`~aioxmpp.ibr.Query`
        """
        iq = aioxmpp.IQ(
            to=self.client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.GET,
            payload=xso.Query()
        )

        reply = await self.client.send(iq)
        return reply

    async def change_pass(self, new_pass):
        """
        Change the client password for 'new_pass'.

        :param new_pass: New password of the client.
        :type new_pass: :class:`str`

        :param old_pass: Old password of the client.
        :type old_pass: :class:`str`

        """
        iq = aioxmpp.IQ(
            to=self.client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.SET,
            payload=xso.Query(self.client.local_jid.localpart, new_pass)
        )

        await self.client.send(iq)

    async def cancel_registration(self):
        """
        Cancels the currents client's account with the server.

        Even if the cancellation is successful, this method will raise an
        exception due to he account no longer exists for the server, so the
        client will fail.
        To continue with the execution, this method should be surrounded by a
        try/except statement.
        """
        iq = aioxmpp.IQ(
            to=self.client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.SET,
            payload=xso.Query()
        )

        iq.payload.remove = True
        await self.client.send(iq)
