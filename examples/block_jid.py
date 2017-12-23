#!/usr/bin/env python3
########################################################################
# File name: block_jid.py
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
import sys

import aioxmpp.disco
import aioxmpp.blocking
import aioxmpp.xso

from framework import Example, exec_example


class BlockJID(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--add",
            dest="jids_to_block",
            default=[],
            action="append",
            type=jid,
            metavar="JID",
            help="JID to block (can be specified multiple times)",
        )

        self.argparse.add_argument(
            "--remove",
            dest="jids_to_unblock",
            default=[],
            action="append",
            type=jid,
            metavar="JID",
            help="JID to unblock (can be specified multiple times)",
        )

        self.argparse.add_argument(
            "-l", "--list",
            action="store_true",
            default=False,
            dest="show_list",
            help="If given, prints the block list at the end of the operation",
        )

    def configure(self):
        super().configure()

        if not (self.args.jids_to_block or
                self.args.show_list or
                self.args.jids_to_unblock):
            print("nothing to do!", file=sys.stderr)
            print("specify --add and/or --remove and/or --list",
                  file=sys.stderr)
            sys.exit(1)

    def make_simple_client(self):
        client = super().make_simple_client()
        self.blocking = client.summon(aioxmpp.BlockingClient)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        # we are polite and ask the server whether it actually supports the
        # XEP-0191 block list protocol
        disco = self.client.summon(aioxmpp.DiscoClient)
        server_info = yield from disco.query_info(
            self.client.local_jid.replace(
                resource=None,
                localpart=None,
            )
        )

        if "urn:xmpp:blocking" not in server_info.features:
            print("server does not support block lists!", file=sys.stderr)
            sys.exit(2)

        # now that we are sure that the server supports it, we can send
        # requests.

        if self.args.jids_to_block:
            yield from self.blocking.block_jids(self.args.jids_to_block)
        else:
            print("nothing to block")

        if self.args.jids_to_unblock:
            yield from self.blocking.unblock_jids(self.args.jids_to_unblock)
        else:
            print("nothing to unblock")

        if self.args.show_list:
            # print all the items; again, .items is a list of JIDs
            print("current block list:")
            for item in sorted(self.blocking.blocklist):
                print("\t", item, sep="")


if __name__ == "__main__":
    exec_example(BlockJID())
