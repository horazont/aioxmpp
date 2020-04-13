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
# import base64
import collections
import logging
import random

# from datetime import timedelta

import aioxmpp.disco
import aioxmpp.errors
import aioxmpp.disco.xso as disco_xso
import aioxmpp.service
import aioxmpp.structs

from aioxmpp.utils import namespaces

from . import xso as adhoc_xso


_logger = logging.getLogger(__name__)
_rng = random.SystemRandom()


class SessionError(RuntimeError):
    pass


class ClientCancelledError(SessionError):
    pass


class AdHocClient(aioxmpp.service.Service):
    """
    Access other entities :xep:`50` Ad-Hoc commands.

    This service provides helpers to conveniently access and execute :xep:`50`
    Ad-Hoc commands.

    .. automethod:: supports_commands

    .. automethod:: get_commands

    .. automethod:: get_command_info

    .. automethod:: execute
    """

    ORDER_AFTER = [aioxmpp.disco.DiscoClient]

    async def get_commands(self, peer_jid):
        """
        Return the list of commands offered by the peer.

        :param peer_jid: JID of the peer to query
        :type peer_jid: :class:`~aioxmpp.JID`
        :rtype: :class:`list` of :class:`~.disco.xso.Item`
        :return: List of command items

        In the returned list, each :class:`~.disco.xso.Item` represents one
        command supported by the peer. The :attr:`~.disco.xso.Item.node`
        attribute is the identifier of the command which can be used with
        :meth:`get_command_info` and :meth:`execute`.
        """

        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = await disco.query_items(
            peer_jid,
            node=namespaces.xep0050_commands,
        )
        return response.items

    async def get_command_info(self, peer_jid, command_name):
        """
        Obtain information about a command.

        :param peer_jid: JID of the peer to query
        :type peer_jid: :class:`~aioxmpp.JID`
        :param command_name: Node name of the command
        :type command_name: :class:`str`
        :rtype: :class:`~.disco.xso.InfoQuery`
        :return: Service discovery information about the command

        Sends a service discovery query to the service discovery node of the
        command. The returned object contains information about the command,
        such as the namespaces used by its implementation (generally the
        :xep:`4` data forms namespace) and possibly localisations of the
        commands name.

        The `command_name` can be obtained by inspecting the listing from
        :meth:`get_commands` or from well-known command names as defined for
        example in :xep:`133`.
        """

        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = await disco.query_info(
            peer_jid,
            node=command_name,
        )
        return response

    async def supports_commands(self, peer_jid):
        """
        Detect whether a peer supports :xep:`50` Ad-Hoc commands.

        :param peer_jid: JID of the peer to query
        :type peer_jid: :class:`aioxmpp.JID`
        :rtype: :class:`bool`
        :return: True if the peer supports the Ad-Hoc commands protocol, false
                 otherwise.

        Note that the fact that a peer supports the protocol does not imply
        that it offers any commands.
        """

        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = await disco.query_info(
            peer_jid,
        )

        return namespaces.xep0050_commands in response.features

    async def execute(self, peer_jid, command_name):
        """
        Start execution of a command with a peer.

        :param peer_jid: JID of the peer to start the command at.
        :type peer_jid: :class:`~aioxmpp.JID`
        :param command_name: Node name of the command to execute.
        :type command_name: :class:`str`
        :rtype: :class:`~.adhoc.service.ClientSession`
        :return: A started command execution session.

        Initialises a client session and starts execution of the command. The
        session is returned.

        This may raise any exception which may be raised by
        :meth:`~.adhoc.service.ClientSession.start`.
        """

        session = ClientSession(
            self.client.stream,
            peer_jid,
            command_name,
        )
        await session.start()
        return session


CommandEntry = collections.namedtuple(
    "CommandEntry",
    [
        "name",
        "is_allowed",
        "handler",
        "features",
    ]
)


class CommandEntry(aioxmpp.disco.StaticNode):
    def __init__(self, name, handler, features=set(), is_allowed=None):
        super().__init__()
        if isinstance(name, str):
            self.__name = aioxmpp.structs.LanguageMap({None: name})
        else:
            self.__name = aioxmpp.structs.LanguageMap(name)
        self.__handler = handler

        features = set(features) | {namespaces.xep0050_commands}
        for feature in features:
            self.register_feature(feature)

        self.__is_allowed = is_allowed

        self.register_identity(
            "automation",
            "command-node",
            names=self.__name
        )

    @property
    def name(self):
        return self.__name

    @property
    def handler(self):
        return self.__handler

    @property
    def is_allowed(self):
        return self.__is_allowed

    def is_allowed_for(self, *args, **kwargs):
        if self.__is_allowed is None:
            return True
        return self.__is_allowed(*args, **kwargs)

    def iter_identities(self, stanza):
        if not self.is_allowed_for(stanza.from_):
            return iter([])
        return super().iter_identities(stanza)


class AdHocServer(aioxmpp.service.Service, aioxmpp.disco.Node):
    """
    Support for serving Ad-Hoc commands.

    .. .. automethod:: register_stateful_command

    .. automethod:: register_stateless_command

    .. automethod:: unregister_command
    """

    ORDER_AFTER = [aioxmpp.disco.DiscoServer]

    disco_node = aioxmpp.disco.mount_as_node(
        "http://jabber.org/protocol/commands"
    )
    disco_feature = aioxmpp.disco.register_feature(
        "http://jabber.org/protocol/commands"
    )

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self.register_identity(
            "automation", "command-list",
        )

        self._commands = {}
        self._disco = self.dependencies[aioxmpp.disco.DiscoServer]

    @aioxmpp.service.iq_handler(aioxmpp.IQType.SET,
                                adhoc_xso.Command)
    async def _handle_command(self, stanza):
        try:
            info = self._commands[stanza.payload.node]
        except KeyError:
            raise aioxmpp.errors.XMPPCancelError(
                aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND,
                text="no such command: {!r}".format(
                    stanza.payload.node
                )
            )

        if not info.is_allowed_for(stanza.from_):
            raise aioxmpp.errors.XMPPCancelError(
                aioxmpp.errors.ErrorCondition.FORBIDDEN,
            )

        return await info.handler(stanza)

    def iter_items(self, stanza):
        local_jid = self.client.local_jid
        languages = [
            aioxmpp.structs.LanguageRange.fromstr("en"),
        ]

        if stanza.lang is not None:
            languages.insert(0, aioxmpp.structs.LanguageRange.fromstr(
                str(stanza.lang)
            ))

        for node, info in self._commands.items():
            if not info.is_allowed_for(stanza.from_):
                continue
            yield disco_xso.Item(
                local_jid,
                name=info.name.lookup(languages),
                node=node,
            )

    def register_stateless_command(self, node, name, handler, *,
                                   is_allowed=None,
                                   features={namespaces.xep0004_data}):
        """
        Register a handler for a stateless command.

        :param node: Name of the command (``node`` in the service discovery
                     list).
        :type node: :class:`str`
        :param name: Human-readable name of the command
        :type name: :class:`str` or :class:`~.LanguageMap`
        :param handler: Coroutine function to run to get the response for a
                        request.
        :param is_allowed: A predicate which determines whether the command is
                           shown and allowed for a given peer.
        :type is_allowed: function or :data:`None`
        :param features: Set of features to announce for the command
        :type features: :class:`set` of :class:`str`

        When a request for the command is received, `handler` is invoked. The
        semantics of `handler` are the same as for
        :meth:`~.StanzaStream.register_iq_request_handler`. It must produce a
        valid :class:`~.adhoc.xso.Command` response payload.

        If `is_allowed` is not :data:`None`, it is invoked whenever a command
        listing is generated and whenever a command request is received. The
        :class:`aioxmpp.JID` of the requester is passed as positional argument
        to `is_allowed`. If `is_allowed` returns false, the command is not
        included in the list and attempts to execute it are rejected with
        ``<forbidden/>`` without calling `handler`.

        If `is_allowed` is :data:`None`, the command is always visible and
        allowed.

        The `features` are returned on a service discovery info request for the
        command node. By default, the :xep:`4` (Data Forms) namespace is
        included, but this can be overridden by passing a different set without
        that feature to `features`.
        """

        info = CommandEntry(
            name,
            handler,
            is_allowed=is_allowed,
            features=features,
        )
        self._commands[node] = info
        self._disco.mount_node(
            node,
            info,
        )

    def unregister_command(self, node):
        """
        Unregister a command previously registered.

        :param node: Name of the command (``node`` in the service discovery
                     list).
        :type node: :class:`str`
        """


class ClientSession:
    """
    Represent an Ad-Hoc command session on the client side.

    :param stream: The stanza stream over which the session is established.
    :type stream: :class:`~.StanzaStream`
    :param peer_jid: The full JID of the peer to communicate with
    :type peer_jid: :class:`~aioxmpp.JID`
    :param command_name: The command to run
    :type command_name: :class:`str`

    The constructor does not send any stanza, it merely prepares the internal
    state. To start the command itself, use the :class:`ClientSession` object
    as context manager or call :meth:`start`.

    .. note::

       The client session returned by :meth:`.AdHocClient.execute` is already
       started.

    The `command_name` must be one of the :attr:`~.disco.xso.Item.node` values
    as returned by :meth:`.AdHocClient.get_commands`.

    .. automethod:: start

    .. automethod:: proceed

    .. automethod:: close

    The following attributes change depending on the stage of execution of the
    command:

    .. autoattribute:: allowed_actions

    .. autoattribute:: first_payload

    .. autoattribute:: response

    .. autoattribute:: status
    """

    def __init__(self, stream, peer_jid, command_name, *, logger=None):
        super().__init__()
        self._stream = stream
        self._peer_jid = peer_jid
        self._command_name = command_name
        self._logger = logger or _logger

        self._status = None
        self._response = None

    @property
    def status(self):
        """
        The current status of command execution. This is either :data:`None` or
        one of the :class:`~.adhoc.CommandStatus` enumeration values.

        Initially, this attribute is :data:`None`. After calls to
        :meth:`start`, :meth:`proceed` or :meth:`close`, it takes the value of
        the :attr:`~.xso.Command.status` attribute of the response.
        """

        if self._response is not None:
            return self._response.status
        return None

    @property
    def response(self):
        """
        The last :class:`~.xso.Command` received from the peer.

        This is initially (and after :meth:`close`) :data:`None`.
        """

        return self._response

    @property
    def first_payload(self):
        """
        Shorthand to access :attr:`~.xso.Command.first_payload` of the
        :attr:`response`.

        This is initially (and after :meth:`close`) :data:`None`.
        """

        if self._response is not None:
            return self._response.first_payload
        return None

    @property
    def sessionid(self):
        """
        Shorthand to access :attr:`~.xso.Command.sessionid` of the
        :attr:`response`.

        This is initially (and after :meth:`close`) :data:`None`.
        """

        if self._response is not None:
            return self._response.sessionid
        return None

    @property
    def allowed_actions(self):
        """
        Shorthand to access :attr:`~.xso.Actions.allowed_actions` of the
        :attr:`response`.

        If no response has been received yet or if the response specifies no
        set of valid actions, this is the minimal set of allowed actions (
        :attr:`~.ActionType.EXECUTE` and :attr:`~.ActionType.CANCEL`).
        """

        if self._response is not None and self._response.actions is not None:
            return self._response.actions.allowed_actions
        return {adhoc_xso.ActionType.EXECUTE,
                adhoc_xso.ActionType.CANCEL}

    async def start(self):
        """
        Initiate the session by starting to execute the command with the peer.

        :return: The :attr:`~.xso.Command.first_payload` of the response

        This sends an empty command IQ request with the
        :attr:`~.ActionType.EXECUTE` action.

        The :attr:`status`, :attr:`response` and related attributes get updated
        with the newly received values.
        """

        if self._response is not None:
            raise RuntimeError("command execution already started")

        request = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            to=self._peer_jid,
            payload=adhoc_xso.Command(self._command_name),
        )

        self._response = await self._stream.send_iq_and_wait_for_reply(
            request,
        )

        return self._response.first_payload

    async def proceed(self, *,
                      action=adhoc_xso.ActionType.EXECUTE,
                      payload=None):
        """
        Proceed command execution to the next stage.

        :param action: Action type for proceeding
        :type action: :class:`~.ActionTyp`
        :param payload: Payload for the request, or :data:`None`
        :return: The :attr:`~.xso.Command.first_payload` of the response

        `action` must be one of the actions returned by
        :attr:`allowed_actions`. It defaults to :attr:`~.ActionType.EXECUTE`,
        which is (alongside with :attr:`~.ActionType.CANCEL`) always allowed.

        `payload` may be a sequence of XSOs, a single XSO or :data:`None`. If
        it is :data:`None`, the XSOs from the request are re-used. This is
        useful if you modify the payload in-place (e.g. via
        :attr:`first_payload`). Otherwise, the payload on the request is set to
        the `payload` argument; if it is a single XSO, it is wrapped in a
        sequence.

        The :attr:`status`, :attr:`response` and related attributes get updated
        with the newly received values.
        """

        if self._response is None:
            raise RuntimeError("command execution not started yet")

        if action not in self.allowed_actions:
            raise ValueError("action {} not allowed in this stage".format(
                action
            ))

        cmd = adhoc_xso.Command(
            self._command_name,
            action=action,
            payload=self._response.payload if payload is None else payload,
            sessionid=self.sessionid,
        )

        request = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            to=self._peer_jid,
            payload=cmd,
        )

        try:
            self._response = await self._stream.send_iq_and_wait_for_reply(
                request,
            )
        except (aioxmpp.errors.XMPPModifyError,
                aioxmpp.errors.XMPPCancelError) as exc:
            if isinstance(exc.application_defined_condition,
                          (adhoc_xso.BadSessionID,
                           adhoc_xso.SessionExpired)):
                await self.close()
                raise SessionError(exc.text)
            if isinstance(exc, aioxmpp.errors.XMPPCancelError):
                await self.close()
            raise

        return self._response.first_payload

    async def close(self):
        if self._response is None:
            return

        if self.status != adhoc_xso.CommandStatus.COMPLETED:
            request = aioxmpp.IQ(
                type_=aioxmpp.IQType.SET,
                to=self._peer_jid,
                payload=adhoc_xso.Command(
                    self._command_name,
                    sessionid=self.sessionid,
                    action=adhoc_xso.ActionType.CANCEL,
                )
            )

            try:
                await self._stream.send_iq_and_wait_for_reply(
                    request,
                )
            except aioxmpp.errors.StanzaError as exc:
                # we are cancelling only out of courtesy.
                # if something goes wrong here, it’s barely worth logging
                self._logger.debug(
                    "ignored stanza error during close(): %r",
                    exc,
                )

        self._response = None

    async def __aenter__(self):
        if self._response is None:
            await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        await self.close()
