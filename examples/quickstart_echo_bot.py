########################################################################
# File name: quickstart_echo_bot.py
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
import getpass

try:
    import readline  # NOQA
except ImportError:
    pass

import aioxmpp


async def main(local_jid, password):
    client = aioxmpp.PresenceManagedClient(
        local_jid,
        aioxmpp.make_security_layer(password)
    )

    def message_received(msg):
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

        client.enqueue(reply)

    message_dispatcher = client.summon(
        aioxmpp.dispatcher.SimpleMessageDispatcher
    )
    message_dispatcher.register_callback(
        aioxmpp.MessageType.CHAT,
        None,
        message_received,
    )

    async with client.connected():
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    local_jid = aioxmpp.JID.fromstr(input("local JID> "))
    password = getpass.getpass()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(local_jid, password))
    loop.close()
