########################################################################
# File name: register.py
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
    import readline
except ImportError:
    pass

import aioxmpp
import aioxmpp.ibr as ibr


async def register(jid, password):
    metadata = aioxmpp.make_security_layer(None)
    _, stream, features = await aioxmpp.node.connect_xmlstream(jid, metadata)

    query = ibr.Query(jid.localpart, password)
    await ibr.register(stream, query)
    print("Registered")


if __name__ == "__main__":
    local_jid = aioxmpp.JID.fromstr(input("local JID> "))
    password = getpass.getpass()

    loop = asyncio.get_event_loop()

    loop.run_until_complete(register(local_jid, password))
