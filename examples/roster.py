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

    async def run_simple_example(self):
        done, pending = await asyncio.wait(
            [
                self.sigint_event.wait(),
                self.done_event.wait()
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for fut in pending:
            fut.cancel()

    async def run_example(self):
        self.sigint_event = self.make_sigint_event()
        await super().run_example()


if __name__ == "__main__":
    exec_example(Roster())
