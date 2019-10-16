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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio

import aioxmpp
import aioxmpp.im.dispatcher

from framework import Example, exec_example


class EchoBot(Example):
    def message_received(self, msg, peer, sent, source):
        if sent:  # ignore mesasges we sent
            return msg

        if msg.type_ != aioxmpp.MessageType.CHAT:
            return msg

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

        self.client.enqueue(reply)

    def make_simple_client(self):
        client = super().make_simple_client()
        self.dispatcher = client.summon(
            aioxmpp.im.dispatcher.IMDispatcher
        )
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        stop_event = self.make_sigint_event()

        self.dispatcher.message_filter.register(
            self.message_received,
            0,
        )

        print("echoing... (press Ctrl-C or send SIGTERM to stop)")
        yield from stop_event.wait()


if __name__ == "__main__":
    exec_example(EchoBot())
