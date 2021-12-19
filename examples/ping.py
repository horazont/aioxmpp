########################################################################
# File name: entity_info.py
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
import aioxmpp.forms

from framework import Example, exec_example


class Ping(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "target_entity",
            default=None,
            nargs="*",
            type=jid,
            help="Entities to ping",
        )

    async def run_simple_example(self):
        tasks = [
            asyncio.wait_for(aioxmpp.ping.ping(self.client, target), timeout=60)
            for target in self.args.target_entity
        ]
        for addr, result in zip(self.args.target_entity, await asyncio.gather(*tasks, return_exceptions=True)):
            print(addr, result)


if __name__ == "__main__":
    exec_example(Ping())
