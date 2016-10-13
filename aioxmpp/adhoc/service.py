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
import logging

import aioxmpp.disco
import aioxmpp.service

from aioxmpp.utils import namespaces

from . import xso as adhoc_xso


_logger = logging.getLogger(__name__)


class SessionError(RuntimeError):
    pass


class AdHocClient(aioxmpp.service.Service):
    ORDER_AFTER = [aioxmpp.disco.DiscoClient]

    @asyncio.coroutine
    def get_commands(self, peer_jid):
        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = yield from disco.query_items(
            peer_jid,
            node=namespaces.xep0050_commands,
        )
        return response.items

    @asyncio.coroutine
    def supports_commands(self, peer_jid):
        disco = self.dependencies[aioxmpp.disco.DiscoClient]
        response = yield from disco.query_info(
            peer_jid,
        )

        return namespaces.xep0050_commands in response.features


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
    as context manager *or* call :meth:`start`.

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
        one of the :class:`CommandStatus` enumeration values.

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

    @asyncio.coroutine
    def start(self):
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

        self._response = yield from self._stream.send_iq_and_wait_for_reply(
            request,
        )

        return self._response.first_payload

    @asyncio.coroutine
    def proceed(self, *,
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
            self._response = \
                yield from self._stream.send_iq_and_wait_for_reply(
                    request,
                )
        except (aioxmpp.errors.XMPPModifyError,
                aioxmpp.errors.XMPPCancelError) as exc:
            if isinstance(exc.application_defined_condition,
                          (adhoc_xso.BadSessionID,
                           adhoc_xso.SessionExpired)):
                yield from self.close()
                raise SessionError(exc.text)
            if isinstance(exc, aioxmpp.errors.XMPPCancelError):
                yield from self.close()
            raise

        return self._response.first_payload

    @asyncio.coroutine
    def close(self):
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
                yield from self._stream.send_iq_and_wait_for_reply(
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
