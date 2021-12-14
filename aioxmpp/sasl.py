########################################################################
# File name: sasl.py
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
"""
:mod:`~aioxmpp.sasl` -- SASL helpers
####################################

This module is used to implement SASL in :mod:`aioxmpp.security_layer`. It
provides a state machine for use by the different SASL mechanisms and
implementations of some SASL mechanisms.

It provides an XMPP adaptor for :mod:`aiosasl`.

.. autoclass:: SASLXMPPInterface

The XSOs for SASL authentication can be found in :mod:`aioxmpp.nonza`.

"""

import asyncio
import logging

import aiosasl

from . import protocol, nonza

logger = logging.getLogger(__name__)


class SASLXMPPInterface(aiosasl.SASLInterface):
    def __init__(self, xmlstream):
        super().__init__()
        self.xmlstream = xmlstream
        self.timeout = None

    async def _send_sasl_node_and_wait_for(self, node):
        node = await protocol.send_and_wait_for(
            self.xmlstream,
            [node],
            [
                nonza.SASLChallenge,
                nonza.SASLFailure,
                nonza.SASLSuccess
            ],
            timeout=self.timeout
        )

        state = node.TAG[1]

        if state == "failure":
            xmpp_error = node.condition[1]
            text = node.text
            raise aiosasl.SASLFailure(xmpp_error, text=text)

        if hasattr(node, "payload"):
            payload = node.payload
        else:
            payload = None

        return state, payload

    async def initiate(self, mechanism, payload=None):
        with self.xmlstream.mute():
            return await self._send_sasl_node_and_wait_for(
                nonza.SASLAuth(mechanism=mechanism,
                               payload=payload))

    async def respond(self, payload):
        with self.xmlstream.mute():
            return await self._send_sasl_node_and_wait_for(
                nonza.SASLResponse(payload=payload)
            )

    async def abort(self):
        try:
            next_state, payload = await self._send_sasl_node_and_wait_for(
                nonza.SASLAbort()
            )
        except aiosasl.SASLFailure as err:
            self._state = "failure"
            if err.opaque_error != "aborted":
                raise
            return "failure", None
        else:
            raise aiosasl.SASLFailure(
                "aborted",
                text="unexpected non-failure after abort: "
                "{}".format(self._state)
            )
