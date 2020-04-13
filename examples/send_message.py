########################################################################
# File name: send_message.py
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
        await self.client.send(msg)
        print("message sent!")


if __name__ == "__main__":
    exec_example(SendMessage())
