########################################################################
# File name: echo_bot.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
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
