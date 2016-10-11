########################################################################
# File name: roster.py
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

import aioxmpp.roster

from framework import Example, exec_example


class Roster(Example):
    def _print_item(self, item):
        print("  entry {}:".format(item.jid))
        print("    name={!r}".format(item.name))
        print("    subscription={!r}".format(item.subscription))
        print("    ask={!r}".format(item.ask))
        print("    approved={!r}".format(item.approved))

    def _on_initial_roster(self):
        for group, items in self.roster.groups.items():
            print("group {}:".format(group))
            for item in items:
                self._print_item(item)

        print("ungrouped items:")
        for item in self.roster.items.values():
            if not item.groups:
                self._print_item(item)

        self.done_event.set()

    def make_simple_client(self):
        client = super().make_simple_client()
        self.roster = client.summon(aioxmpp.roster.Service)
        self.roster.on_initial_roster_received.connect(
            self._on_initial_roster,
        )
        self.done_event = asyncio.Event()

        return client

    @asyncio.coroutine
    def run_simple_example(self):
        done, pending = yield from asyncio.wait(
            [
                self.sigint_event.wait(),
                self.done_event.wait()
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for fut in pending:
            fut.cancel()

    @asyncio.coroutine
    def run_example(self):
        self.sigint_event = self.make_sigint_event()
        yield from super().run_example()


if __name__ == "__main__":
    exec_example(Roster())
