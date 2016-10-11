########################################################################
# File name: quickstart_query_server_version.py
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
