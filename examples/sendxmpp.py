import argparse
import asyncio
import os

import aioxmpp


async def main(from_jid, to_jid, password, message):
    client = aioxmpp.PresenceManagedClient(
        aioxmpp.JID.fromstr(from_jid),
        aioxmpp.make_security_layer(password),
    )

    async with client.connected() as stream:
        msg = aioxmpp.Message(
            to=aioxmpp.JID.fromstr(to_jid),
            type_=aioxmpp.MessageType.CHAT,
        )
        msg.body[None] = message
        await stream.send(msg)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("from_")
    parser.add_argument("to")
    parser.add_argument("message")

    args = parser.parse_args()

    password = os.environ["SENDXMPP_PASSWORD"]

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(args.from_, args.to, password, args.message))
    finally:
        loop.close()
