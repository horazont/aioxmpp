import aioxmpp

from framework import Example, exec_example


class SendMessage(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "recipient",
            type=jid,
            help="Recipient JID"
        )

        self.argparse.add_argument(
            "message",
            nargs="?",
            default="Hello World!",
            help="Message to send (default: Hello World!)",
        )

    async def run_simple_example(self):
        # compose a message
        msg = aioxmpp.stanza.Message(
            to=self.args.recipient,
            type_=aioxmpp.MessageType.CHAT,
        )

        # [None] is for "no XML language tag"
        msg.body[None] = self.args.message

        print("sending message ...")
        await self.client.stream.send_and_wait_for_sent(
            msg
        )
        print("message sent!")


if __name__ == "__main__":
    exec_example(SendMessage())
