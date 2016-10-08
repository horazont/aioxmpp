import asyncio

import aioxmpp

from framework import Example, exec_example


class EchoBot(Example):
    def message_received(self, msg):
        if msg.type_ != aioxmpp.MessageType.CHAT:
            return

        if not msg.body:
            # do not reflect anything without a body
            return

        # we could also use reply = msg.make_reply() instead
        reply = aioxmpp.Message(
            type_=msg.type_,
            to=msg.from_,
        )

        # make_reply() would not set the body though
        reply.body.update(msg.body)

        self.client.stream.enqueue_stanza(reply)

    async def run_simple_example(self):
        stop_event = self.make_sigint_event()

        self.client.stream.register_message_callback(
            aioxmpp.MessageType.CHAT,
            None,
            self.message_received,
        )
        print("echoing... (press Ctrl-C or send SIGTERM to stop)")
        await stop_event.wait()

if __name__ == "__main__":
    exec_example(EchoBot())
