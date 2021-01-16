########################################################################
# File name: carbons_sniffer.py
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

from framework import Example, exec_example


class CarbonsSniffer(Example):
    def make_simple_client(self):
        client = super().make_simple_client()
        self.carbons = client.summon(aioxmpp.CarbonsClient)
        return client

    def _format_message(self, message):
        parts = []
        parts.append(str(message))
        if message.body:
            parts.append("text: {}".format(message.body))
        else:
            parts.append("other")

        return "; ".join(parts)

    def _message_filter(self, message):
        if (message.from_ != self.client.local_jid.bare() and
                message.from_ is not None):
            return

        if message.xep0280_sent is not None:
            print("SENT: {}".format(self._format_message(
                message.xep0280_sent.stanza
            )))

        elif message.xep0280_received is not None:
            print("RECV: {}".format(self._format_message(
                message.xep0280_received.stanza
            )))

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    async def run_simple_example(self):
        filterchain = self.client.stream.app_inbound_message_filter
        with filterchain.context_register(self._message_filter):
            print("enabling carbons")
            await self.carbons.enable()
            print("carbons enabled! sniffing ... (hit Ctrl+C to stop)")

            await self.stop_event.wait()


if __name__ == "__main__":
    exec_example(CarbonsSniffer())
