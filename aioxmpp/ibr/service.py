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

from . import xso


logger = logging.getLogger(__name__)


class RegistrationService:
    """
    Service implementing XMPP In-Band Registration(:xep:`0077`).

    This service implements the response to XMPP Pings and provides a method
    to send pings.

    This class doesn't inherit from the Service class because here are methods
    that can't have a connected client in order to run. For example, a new
    account should sent the needed stanza without being authenticated,
    otherwise it would make no sense.

    .. automethod:: get_client_info

    .. automethod:: change_pass

    .. automethod:: cancel_registration

    .. automethod:: get_registration_fields

    .. automethod:: register

    """

    @asyncio.coroutine
    def get_client_info(self, client):
        """
        A query is sent to the server o obtain the client's data stored at the
        server.

        :param client: Client from which the query is sent.
        :type client: :class:`aioxmpp.Client`

        :return: IQ response :attr:`~.IQ.payload` or :data:`None`
        """
        iq = aioxmpp.IQ(
            to=client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.GET,
            payload=xso.Query()
        )

        return (yield from client.send(iq))

    @asyncio.coroutine
    def change_pass(self,
                    client,
                    new_pass,
                    aux_fields=None):
        """
        Change the client password for 'new_pass'.

        :param client: Client who wants to change the password.
        :type client: :class:`aioxmpp.Client`

        :param new_pass: New password of the client.
        :type new_pass: :class:`str`

        :param aux_fields: Auxiliary fields in case additional info is needed.
        :type aux_fields: :class:`dict`

        :return:`None`

        If the query fails for whatever reason, it will raise an exception
        from inside client.send(iq).
        """
        iq = aioxmpp.IQ(
            to=client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.SET,
            payload=xso.Query()
        )

        iq.payload.username = client.local_jid.localpart
        iq.payload.password = new_pass

        if aux_fields is not None:
            for key, value in aux_fields.items():
                setattr(iq.payload, key, value)
        yield from client.send(iq)

    @asyncio.coroutine
    def cancel_registration(self, client):
        """
        Cancels the currents client's account with the server.

        :param client: Client who wants to cancel.
        :type client: :class:`aioxmpp.Client`

        :return:`None`

        Even if the cancelation is succesful, this method will raise an
        exception due to he account no longer exists for the server, so the
        client will fail.
        To continue with the execution, this method should be surrounded by a
        try/except statement.
        """
        iq = aioxmpp.IQ(
            to=client.local_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.SET,
            payload=xso.Query()
        )

        iq.payload.remove = True
        yield from client.send(iq)

    @staticmethod
    @asyncio.coroutine
    def connect_and_send(iq, loop, metadata, peer_jid, timeout):
        options = list((
            yield from aioxmpp.discover_connectors(
                peer_jid.domain, loop=loop
            )
        ))
        for host, port, conn in options:
            transport, xmlstream, features = yield from conn.connect(
                loop,
                metadata,
                peer_jid.domain,
                host,
                port,
                timeout,
                base_logger=logger
            )
            reply = yield from aioxmpp.send_and_wait_for(
                xmlstream, [iq], [aioxmpp.IQ]
            )
        return reply

    @asyncio.coroutine
    def get_registration_fields(self,
                                peer_jid,
                                timeout=60,
                                no_verify=True
                                ):
        """
        A query is sent to the server to obtain the fields that need to be
        filled to register with the server.

        :param peer_jid: Server where he query will be sent.
        :type peer_jid: :class:`aioxmpp.JID`

        :param timeout: Maximum time in seconds to wait for an IQ response, or
                        :data:`None` to disable the timeout.
        :type timeout: :class:`~numbers.Real` or :data:`None`

        :param no_verify: Specifies whether the server's TLS is verified.
        :type no_verify: :class:`aioxmpp.JID`

        :return: :attr:`list`
        """
        iq = aioxmpp.IQ(
            to=peer_jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.GET,
            payload=xso.Query()
        )
        iq.autoset_id()

        loop = asyncio.get_event_loop()
        metadata = aioxmpp.make_security_layer('', no_verify=no_verify)

        try:
            reply = yield from self.connect_and_send(iq, loop, metadata, peer_jid, timeout)

            return [a for a in dir(reply.payload)
                    if isinstance(getattr(reply.payload, a), str) and
                    not a.startswith('__')]
        except Exception as exc:
            raise exc

    @asyncio.coroutine
    def register(self,
                 jid,
                 password,
                 aux_fields=None,
                 timeout=60,
                 no_verify=True
                 ):
        """
        Create a new account on the server.

        :param jid: Server where he account will be created wih the username
                    of the account.
        :type jid: :class:`aioxmpp.JID`

        :param password: Password of the new account.
        :type password: :class:`str`

        :param aux_fields: Auxiliary fields in case additional info is needed.
        :type aux_fields: :class:`dict`

        :param timeout: Maximum time in seconds to wait for an IQ response, or
                        :data:`None` to disable the timeout.
        :type timeout: :class:`~numbers.Real` or :data:`None`

        :param no_verify: Specifies whether the server's TLS is verified.
        :type no_verify: :class:`aioxmpp.JID`

        :return: :attr:`list`
        """
        iq = aioxmpp.IQ(
            to=jid.bare().replace(localpart=None),
            type_=aioxmpp.IQType.SET,
            payload=xso.Query()
        )
        iq.autoset_id()

        iq.payload.username = jid.localpart
        iq.payload.password = password

        if aux_fields is not None:
            for key, value in aux_fields.items():
                setattr(iq.payload, key, value)

        loop = asyncio.get_event_loop()
        metadata = aioxmpp.make_security_layer(password, no_verify=no_verify)

        try:
            reply = yield from self.connect_and_send(iq, loop, metadata, jid, timeout)
            return reply
        except Exception as exc:
            raise exc
