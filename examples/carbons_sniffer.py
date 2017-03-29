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
        if     (message.from_ != self.client.local_jid.bare() and
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


    @asyncio.coroutine
    def run_example(self):
        self.stop_event = self.make_sigint_event()
        yield from super().run_example()

    @asyncio.coroutine
    def run_simple_example(self):
        filterchain = self.client.stream.app_inbound_message_filter
        with filterchain.context_register(self._message_filter):
            print("enabling carbons")
            yield from self.carbons.enable()
            print("carbons enabled! sniffing ... (hit Ctrl+C to stop)")

            yield from self.stop_event.wait()


if __name__ == "__main__":
    exec_example(CarbonsSniffer())
