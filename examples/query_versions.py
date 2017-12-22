########################################################################
# File name: query_versions.py
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
import argparse
import asyncio
import itertools
import sys

import aioxmpp
import aioxmpp.disco
import aioxmpp.errors
import aioxmpp.version
import aioxmpp.xso

from framework import Example, exec_example


if not hasattr(asyncio, "ensure_future"):
    asyncio.ensure_future = getattr(asyncio, "async")


class SoftwareVersions(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        self.argparse.add_argument(
            "--timeout",
            type=float,
            help="Maximum time (in seconds) to wait for a response "
            "(default: 20s)",
            default=20,
        )

        group = self.argparse.add_mutually_exclusive_group(required=True)

        group.add_argument(
            "-f", "--from-file",
            type=argparse.FileType("r"),
            dest="from_file",
            help="Read the JIDs from a file, one line per JID.",
            default=None,
        )

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        group.add_argument(
            "-t", "--targets",
            nargs="+",
            dest="jids",
            help="The JIDs to query as command-line arguments",
            default=[],
            type=jid,
        )

    def configure(self):
        super().configure()

        self.jids = list(self.args.jids)
        if self.args.from_file:
            with self.args.from_file as f:
                for line in f:
                    self.jids.append(aioxmpp.JID.fromstr(line[:-1]))

        self.timeout = self.args.timeout

    @asyncio.coroutine
    def run_example(self):
        self.stop_event = self.make_sigint_event()
        yield from super().run_example()

    def format_version(self, version_xso):
        return "name={!r} version={!r} os={!r}".format(
            version_xso.name,
            version_xso.version,
            version_xso.os,
        )

    @asyncio.coroutine
    def run_simple_example(self):
        tasks = []
        stream = self.client.stream
        for jid in self.jids:
            tasks.append(
                asyncio.ensure_future(aioxmpp.version.query_version(
                    stream,
                    jid,
                ))
            )

        gather_task = asyncio.ensure_future(
            asyncio.wait(
                tasks,
                return_when=asyncio.ALL_COMPLETED,
            )
        )

        cancel_fut = asyncio.ensure_future(self.stop_event.wait())

        yield from asyncio.wait(
            [
                gather_task,
                cancel_fut,
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for target, fut in zip(self.jids, tasks):
            if not fut.done():
                fut.cancel()
                continue

            if fut.exception():
                print("{} failed: {}".format(target, fut.exception()),
                      file=sys.stderr)
                continue

            print("{}: {}".format(target, self.format_version(fut.result())))

        if not cancel_fut.done():
            cancel_fut.cancel()


if __name__ == "__main__":
    exec_example(SoftwareVersions())
