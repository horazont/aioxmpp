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

        client.stream.enqueue_stanza(reply)

    client.stream.register_message_callback(
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
