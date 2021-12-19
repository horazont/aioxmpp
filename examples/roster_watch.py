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
import functools

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

        print("--- END OF INITIAL ROSTER ---")

    def _on_entry_changed(self, what, item):
        print(what.upper(), "item:")
        self._print_item(item)

    def make_simple_client(self):
        client = super().make_simple_client()
        self.roster = client.summon(aioxmpp.RosterClient)
        self.roster.on_initial_roster_received.connect(
            self._on_initial_roster,
        )
        self.roster.on_entry_added.connect(
            functools.partial(self._on_entry_changed, "added")
        )
        self.roster.on_entry_name_changed.connect(
            functools.partial(self._on_entry_changed, "name changed")
        )
        self.roster.on_entry_subscription_state_changed.connect(
            functools.partial(self._on_entry_changed, "subscription changed")
        )

        return client

    async def run_simple_example(self):
        await self.sigint_event.wait()

    async def run_example(self):
        self.sigint_event = self.make_sigint_event()
        await super().run_example()


if __name__ == "__main__":
    exec_example(Roster())
