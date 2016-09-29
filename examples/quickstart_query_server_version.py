import asyncio
import getpass

try:
    import readline  # NOQA
except ImportError:
    pass

import aioxmpp
import aioxmpp.xso as xso

namespace = "jabber:iq:version"


@aioxmpp.IQ.as_payload_class
class Query(xso.XSO):
    TAG = (namespace, "query")

    name = xso.ChildText(
        (namespace, "name"),
        default=None,
    )

    version = xso.ChildText(
        (namespace, "version"),
        default=None,
    )

    os = xso.ChildText(
        (namespace, "os"),
        default=None,
    )


async def main(local_jid, password):
    client = aioxmpp.PresenceManagedClient(
        local_jid,
        aioxmpp.make_security_layer(password)
    )

    peer_jid = local_jid.bare().replace(localpart=None)

    async with client.connected() as stream:
        iq = aioxmpp.IQ(
            type_="get",
            payload=Query(),
            to=peer_jid,
        )

        print("sending query to {}".format(peer_jid))
        reply = await stream.send_iq_and_wait_for_reply(iq)
        print("got response! logging off...")

    print("    name: {!r}".format(reply.name))
    print("    version: {!r}".format(reply.version))
    print("    os: {!r}".format(reply.os))


if __name__ == "__main__":
    local_jid = aioxmpp.JID.fromstr(input("local JID> "))
    password = getpass.getpass()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(local_jid, password))
    loop.close()
