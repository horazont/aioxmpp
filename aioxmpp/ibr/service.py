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


@asyncio.coroutine
def get_registration_fields(xmlstream,
                            timeout=60,
                            ):
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

    reply = yield from aioxmpp.protocol.send_and_wait_for(xmlstream,
                                                          [iq],
                                                          [aioxmpp.IQ],
                                                          timeout=timeout)
    return reply.payload


@asyncio.coroutine
def register(query_xso,
             xmlstream,
             timeout=60,
             ):
    """
    Create a new account on the server.

    :param query_xso: XSO with the information needed for the registration.
    :type query_xso: :class:`xso.Query`

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

    yield from aioxmpp.protocol.send_and_wait_for(xmlstream,
                                                  [iq],
                                                  [aioxmpp.IQ],
                                                  timeout=timeout)


def get_used_fields(payload):
    """
    Get a list containing the names of the fields that are used in the
    xso.Query.

    :param payload: Query object o be
    :type payload: :class:`xso.Query`
    :return: :attr:`list`
    """
    return [a for a in dir(payload)
            if isinstance(getattr(payload, a), str) and
            not a.startswith('__')]


def get_query_xso(username, password, aux_fields=None):
    """
    Get an xso.Query object with the info provided in he parameters.

    :param username: Username of the query
    :type username: :class:`str`
    :param password: Password of the query.
    :type password: :class:`str`
    :param aux_fields: Auxiliary fields in case additional info is needed.
    :type aux_fields: :class:`dict`
    :return: :class:`xso.Query`
    """
    query = xso.Query()
    query.username = username
    query.password = password

    if aux_fields is not None:
        for key, value in aux_fields.items():
            setattr(query, key, value)

    return query


class RegistrationService(Service):
    """
    Service implementing XMPP In-Band Registration(:xep:`0077`).

    This 'service' implements the possibility for an entity to register with a
    XMPP server, cancel an existing registration, or change a password.

    .. automethod:: get_client_info

    .. automethod:: change_pass

    .. automethod:: cancel_registration

    .. automethod:: get_registration_fields

    .. automethod:: register

    """

    @asyncio.coroutine
    def get_client_info(self):
        """
        A query is sent to the server to obtain the client's data stored at the
        server.

        :return: :class:`xso.Query`
        """
        iq = aioxmpp.IQ(
            to=self.client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.GET,
            payload=xso.Query()
        )

        reply = (yield from self.client.send(iq))
        return reply

    @asyncio.coroutine
    def change_pass(self,
                    new_pass,
                    old_pass=None):
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
            payload=xso.Query()
        )

        iq.payload.username = self.client.local_jid.localpart
        iq.payload.password = new_pass

        if old_pass:
            iq.payload.old_password = old_pass

        yield from self.client.send(iq)

    @asyncio.coroutine
    def cancel_registration(self):
        """
        Cancels the currents client's account with the server.

        Even if the cancelation is succesful, this method will raise an
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
        yield from self.client.send(iq)
