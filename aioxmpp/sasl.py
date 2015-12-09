"""
:mod:`~aioxmpp.sasl` -- SASL helpers
####################################

This module is used to implement SASL in :mod:`aioxmpp.security_layer`. It
provides a state machine for use by the different SASL mechanisms and
implementations of some SASL mechansims.

It provides an XMPP adaptor for :mod:`aiosasl`.

.. autoclass:: SASLXMPPInterface

The XSOs for SASL authentication can be found in :mod:`aioxmpp.nonza`.

"""

import asyncio
import logging

import aiosasl

from . import errors, protocol, nonza

logger = logging.getLogger(__name__)


class SASLXMPPInterface(aiosasl.SASLInterface):
    def __init__(self, xmlstream):
        super().__init__()
        self.xmlstream = xmlstream
        self.timeout = None

    @asyncio.coroutine
    def _send_sasl_node_and_wait_for(self, node):
        node = yield from protocol.send_and_wait_for(
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

    @asyncio.coroutine
    def initiate(self, mechanism, payload=None):
        return (yield from self._send_sasl_node_and_wait_for(
            nonza.SASLAuth(mechanism=mechanism,
                           payload=payload)))

    @asyncio.coroutine
    def respond(self, payload):
        return (yield from self._send_sasl_node_and_wait_for(
            nonza.SASLResponse(payload=payload)
        ))

    @asyncio.coroutine
    def abort(self):
        try:
            next_state, payload = yield from self._send_sasl_node_and_wait_for(
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
