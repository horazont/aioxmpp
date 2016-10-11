########################################################################
# File name: server_info.py
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
import itertools

import aioxmpp.disco

from framework import Example, exec_example


class ServerInfo(Example):
    async def run_simple_example(self):
        disco = self.client.summon(aioxmpp.disco.Service)
        try:
            info = await disco.query_info(
                self.g_jid.replace(resource=None, localpart=None),
                timeout=10
            )
        except Exception as exc:
            print("could not get info: ")
            print("{}: {}".format(type(exc).__name__, exc))
            raise

        print("features:")
        for feature in info.features:
            print("  {!r}".format(feature))

        print("identities:")
        identities = list(info.identities)

        def identity_key(ident):
            return (ident.category, ident.type_)

        identities.sort(key=identity_key)
        for (category, type_), identities in (
                itertools.groupby(info.identities, identity_key)):
            print("  category={!r} type={!r}".format(category, type_))
            subidentities = list(identities)
            subidentities.sort(key=lambda ident: ident.lang)
            for identity in subidentities:
                print("    [{}] {!r}".format(identity.lang, identity.name))


if __name__ == "__main__":
    exec_example(ServerInfo())
