########################################################################
# File name: entity_items.py
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
import itertools

import aioxmpp.disco

from framework import Example, exec_example


class EntityItems(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "target_entity",
            type=jid
        )

        self.argparse.add_argument(
            "target_node",
            default=None,
            nargs="?",
        )

    async def run_simple_example(self):
        disco = self.client.summon(aioxmpp.DiscoClient)
        try:
            items = await disco.query_items(
                self.args.target_entity,
                node=self.args.target_node,
                timeout=10
            )
        except Exception as exc:
            print("could not get info: ")
            print("{}: {}".format(type(exc).__name__, exc))
            raise

        print("items:")
        for item in items.items:
            print("  jid={}  node={!r}  name={!r}".format(item.jid, item.node, item.name))


if __name__ == "__main__":
    exec_example(EntityItems())
