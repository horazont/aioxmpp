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
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service

from aioxmpp.utils import namespaces

from . import xso as blocking_xso


class BlockingClient(service.Service):
    """
    A :class:`~aioxmpp.service.Service` implementing :xep:`Blocking
    Command <191>`.

    This service maintains the list of blocked JIDs and allows
    manipulating the blocklist.

    Attribute:

    .. autoattribute:: blocklist

    Signals:

    .. signal:: on_initial_blocklist_received(blocklist)

       Fires when the initial blocklist was received from the server.

       :param blocklist: the initial blocklist
       :type blocklist: :class:`~collections.abc.Set` of :class:`~aioxmpp.JID`

    .. signal:: on_jids_blocked(blocked_jids)

       Fires when additional JIDs are blocked.

       :param blocked_jids: the newly blocked JIDs
       :type blocked_jids: :class:`~collections.abc.Set`
           of :class:`~aioxmpp.JID`

    .. signal:: on_jids_blocked(blocked_jids)

       Fires when JIDs are unblocked.

       :param unblocked_jids: the now unblocked JIDs
       :type unblocked_jids: :class:`~collections.abc.Set`
           of :class:`~aioxmpp.JID`

    Coroutine methods:

    .. automethod:: block_jids

    .. automethod:: unblock_jids

    .. automethod:: unblock_all
    """
    ORDER_AFTER = [aioxmpp.DiscoClient]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._blocklist = None
        self._lock = asyncio.Lock()
        self._disco = self.dependencies[aioxmpp.DiscoClient]

    on_jids_blocked = callbacks.Signal()
    on_jids_unblocked = callbacks.Signal()
    on_initial_blocklist_received = callbacks.Signal()

    async def _check_for_blocking(self):
        server_info = await self._disco.query_info(
            self.client.local_jid.replace(
                resource=None,
                localpart=None,
            )
        )

        if namespaces.xep0191 not in server_info.features:
            self._blocklist = None
            raise RuntimeError("server does not support blocklists!")

    @service.depsignal(aioxmpp.Client, "before_stream_established")
    async def _get_initial_blocklist(self):
        try:
            await self._check_for_blocking()
        except RuntimeError:
            self.logger.info(
                "server does not support block lists, skipping initial fetch"
            )
            return True

        if self._blocklist is None:
            async with self._lock:
                iq = aioxmpp.IQ(
                    type_=aioxmpp.IQType.GET,
                    payload=blocking_xso.BlockList(),
                )
                result = await self.client.send(iq)
                self._blocklist = frozenset(result.items)
            self.on_initial_blocklist_received(self._blocklist)

        return True

    @property
    def blocklist(self):
        """
        :class:`~collections.abc.Set` of JIDs blocked by the account.
        """
        return self._blocklist

    async def block_jids(self, jids_to_block):
        """
        Add the JIDs in the sequence `jids_to_block` to the client's
        blocklist.
        """
        await self._check_for_blocking()

        if not jids_to_block:
            return

        cmd = blocking_xso.BlockCommand(jids_to_block)
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=cmd,
        )
        await self.client.send(iq)

    async def unblock_jids(self, jids_to_unblock):
        """
        Remove the JIDs in the sequence `jids_to_block` from the
        client's blocklist.
        """
        await self._check_for_blocking()

        if not jids_to_unblock:
            return

        cmd = blocking_xso.UnblockCommand(jids_to_unblock)
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=cmd,
        )
        await self.client.send(iq)

    async def unblock_all(self):
        """
        Unblock all JIDs currently blocked.
        """
        await self._check_for_blocking()

        cmd = blocking_xso.UnblockCommand()
        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=cmd,
        )
        await self.client.send(iq)

    @service.iq_handler(aioxmpp.IQType.SET, blocking_xso.BlockCommand)
    async def handle_block_push(self, block_command):
        diff = ()
        async with self._lock:
            if self._blocklist is None:
                # this means the stream was destroyed while we were waiting for
                # the lock/while the handler was enqueued for scheduling, or
                # the server is buggy and sends pushes before we fetched the
                # blocklist
                return

            if (block_command.from_ is None or
                    block_command.from_ == self.client.local_jid.bare() or
                    # WORKAROUND: ejabberd#2287
                    block_command.from_ == self.client.local_jid):
                diff = frozenset(block_command.payload.items)
                self._blocklist |= diff
            else:
                self.logger.debug(
                    "received block push from unauthorized JID: %s",
                    block_command.from_,
                )

        if diff:
            self.on_jids_blocked(diff)

    @service.iq_handler(aioxmpp.IQType.SET, blocking_xso.UnblockCommand)
    async def handle_unblock_push(self, unblock_command):
        diff = ()
        async with self._lock:
            if self._blocklist is None:
                # this means the stream was destroyed while we were waiting for
                # the lock/while the handler was enqueued for scheduling, or
                # the server is buggy and sends pushes before we fetched the
                # blocklist
                return

            if (unblock_command.from_ is None or
                    unblock_command.from_ == self.client.local_jid.bare() or
                    # WORKAROUND: ejabberd#2287
                    unblock_command.from_ == self.client.local_jid):
                if not unblock_command.payload.items:
                    diff = frozenset(self._blocklist)
                    self._blocklist = frozenset()
                else:
                    diff = frozenset(unblock_command.payload.items)
                    self._blocklist -= diff
            else:
                self.logger.debug(
                    "received unblock push from unauthorized JID: %s",
                    unblock_command.from_,
                )
        if diff:
            self.on_jids_unblocked(diff)

    @service.depsignal(aioxmpp.stream.StanzaStream,
                       "on_stream_destroyed")
    def handle_stream_destroyed(self, reason):
        self._blocklist = None
