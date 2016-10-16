########################################################################
# File name: list_adhoc_commands.py
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

import aioxmpp.adhoc

from framework import Example, exec_example


class ListAdhocCommands(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "peer_jid",
            nargs="?",
            metavar="JID",
            default=None,
            help="Entity to ask for ad-hoc commands. Must be a full jid,"
            " defaults to the domain of the local JID (asking the server)"
        )

    def configure(self):
        super().configure()

        self.adhoc_peer_jid = (
            self.args.peer_jid or
            self.g_jid.replace(resource=None, localpart=None)
        )

    @asyncio.coroutine
    def run_simple_example(self):
        adhoc = self.client.summon(aioxmpp.adhoc.AdHocClient)
        for item in (yield from adhoc.get_commands(self.adhoc_peer_jid)):
            print("{}: {}".format(
                item.node,
                item.name
            ))


if __name__ == "__main__":
    exec_example(ListAdhocCommands())
