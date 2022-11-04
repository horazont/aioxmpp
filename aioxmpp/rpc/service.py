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
import collections

import aioxmpp.callbacks
import aioxmpp.disco
import aioxmpp.service
import aioxmpp.stanza
import aioxmpp.structs

from aioxmpp.utils import namespaces

from . import xso as rpc_xso

class RPCClient(aioxmpp.service.Service):
    """
    Access other entities :xep:`0009` RPC methods.

    This service provides helpers to conveniently access and execute :xep:`0009`
    RPC methods.

    .. automethod:: supports_rpc
    .. automethod:: call_method
    """

    ORDER_AFTER = [aioxmpp.disco.DiscoClient]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

    async def supports_rpc(self, peer_jid):
        """
        Detect whether a peer supports :xep:`0009` RPC.

        :param peer_jid: JID of the peer to query
        :type peer_jid: :class:`aioxmpp.JID`
        :rtype: :class:`bool`
        :return: True if the peer supports the RPC protocol, false
                 otherwise.

        Note that the fact that a peer supports the protocol does not imply
        that it offers any methods.
        """

        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = await disco.query_info(
            peer_jid,
        )

        return namespaces.xep0009 in response.features

    async def call_method(self, jid, payload):
        """
        Send a call request to peer.

        :param jid: JID of the peer to run the method at.
        :type jid: :class:`~aioxmpp.JID`
        :param stanza: Stanza to send.
        :type payload: :class:`xso.Query`
        :rtype: :class:`xso`
        :return: Server method response.

        Sends a RPC method call. The execution response is returned.
        """
        iq = aioxmpp.IQ(
            to=jid, 
            type_=aioxmpp.structs.IQType.SET,
            payload=payload
        )
        
        response = await self.client.send(iq)

        return response

MethodEntry = collections.namedtuple(
    "MethodEntry",
    [
        "handler",
        "method_name",
        "is_allowed",
    ]
)

class MethodEntry(aioxmpp.disco.StaticNode):
    def __init__(self, handler, method_name=None, is_allowed=None):
        self._handler = handler
        self._method_name = method_name
        self._is_allowed = is_allowed

    @property
    def method_name(self):
        return self._method_name

    @property
    def handler(self):
        return self._handler

    @property
    def is_allowed(self):
        return self._is_allowed

    def is_allowed_for(self, *args, **kwargs):
        if self._is_allowed is None:
            return True
        return self._is_allowed(*args, **kwargs)


class RPCServer(aioxmpp.service.Service, aioxmpp.disco.Node):
    """
    Support for serving RPC method calls.

    .. automethod:: register_method

    .. automethod:: unregister_method
    """

    ORDER_AFTER = [aioxmpp.disco.DiscoServer]

    disco_node = aioxmpp.disco.mount_as_node(
        "http://jabber.org/protocol/rpc"
    )
    disco_feature = aioxmpp.disco.register_feature(
        "http://jabber.org/protocol/rpc"
    )

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self.register_identity(
            "automation", "rpc",
        )

        self._disco = self.dependencies[aioxmpp.disco.DiscoServer]

        self._methods = {}

    @aioxmpp.service.iq_handler(aioxmpp.IQType.SET,
                                rpc_xso.Query)
    async def _handle_method_call(self, stanza):
        payload = stanza.payload.payload
        if not isinstance(payload, rpc_xso.MethodCall):
            return

        try:
            method = self._methods[payload.methodName.name]
        except KeyError:
            raise aioxmpp.errors.XMPPCancelError(
                aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND,
                text="no such method: {!r}".format(
                    payload.methodName.name
                )
            )

        if not method.is_allowed_for(stanza.from_):
            raise aioxmpp.errors.XMPPCancelError(
                aioxmpp.errors.ErrorCondition.FORBIDDEN,
            )

        response = method.handler(stanza)

        return response

    def register_method(self, handler, method_name, is_allowed=None):
        """
        Register a handler for method calls.

        :param handler: Coroutine function to run to get the response for a
                        request.
        :type node: :class:`function`
        :param method_name: Human-readable name of the method
        :type name: :class:`str`
        :param is_allowed: A predicate which determines whether the method is
                           allowed for a given peer.
        :type is_allowed: function or :data:`None`

        When a request for the method is received, `handler` is invoked.

        If `is_allowed` is not :data:`None`, it is invoked whenever a method
        request is received. The :class:`aioxmpp.JID` of the requester is 
        passed as positional argument to `is_allowed`. If `is_allowed` returns
        false, attempts to execute it are rejected with ``<forbidden/>`` without
        calling `handler`.

        If `is_allowed` is :data:`None`, the method is always visible and
        allowed.
        """
        method = MethodEntry(
            handler, 
            method_name, 
            is_allowed=is_allowed
        )
        self._methods[method_name] = method

    def unregister_method(self, method_name):
        """
        Unregister a method previously registered.

        :param node: Name of the method.
        :type node: :class:`str`
        """
        if method_name not in self._methods.keys():
            raise KeyError("Not registered method: {}".format(method_name))
        
        del self._methods[method_name]