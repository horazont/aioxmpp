import asyncio

import aioxmpp.service

import aioxmpp.stanza as stanza

from . import xso as roster_xso


class Service(aioxmpp.service.Service):
    def __init__(self, client):
        super().__init__(client)

        self._bse_token = client.before_stream_established.connect(
            self._request_initial_roster
        )

    @asyncio.coroutine
    def _request_initial_roster(self):
        iq = stanza.IQ(type_="get")
        iq.payload = roster_xso.Query()

        response = yield from self.client.stream.send_iq_and_wait_for_reply(
            iq,
            timeout=self.client.negotiation_timeout.total_seconds()
        )
