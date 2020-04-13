########################################################################
# File name: list_presence.py
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

from datetime import timedelta

import aioxmpp.presence

from framework import Example, exec_example


class PresenceCollector:
    def __init__(self, done_timeout=timedelta(seconds=1)):
        self.presences = []
        self.done_future = asyncio.Future()
        self.done_timeout = done_timeout
        self._reset_timer()

    def _reset_timer(self):
        self._done_task = asyncio.ensure_future(
            asyncio.sleep(self.done_timeout.total_seconds())
        )
        self._done_task.add_done_callback(self._sleep_done)

    def _sleep_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            return
        self.done_future.set_result(self.presences)

    def add_presence(self, pres):
        self.presences.append(pres)
        self._done_task.cancel()
        self._reset_timer()


class ListPresence(Example):
    def make_simple_client(self):
        client = super().make_simple_client()
        self.collector = PresenceCollector()
        client.stream.register_presence_callback(
            aioxmpp.PresenceType.AVAILABLE,
            None,
            self.collector.add_presence,
        )
        client.stream.register_presence_callback(
            aioxmpp.PresenceType.UNAVAILABLE,
            None,
            self.collector.add_presence,
        )

        return client

    async def run_simple_example(self):
        print("collecting presences... ")
        self.presences = await self.collector.done_future

    async def run_example(self):
        await super().run_example()

        print("found presences:")
        for i, pres in enumerate(self.presences):
            print("presence {}".format(i))
            print("  peer: {}".format(pres.from_))
            print("  type: {}".format(pres.type_))
            print("  show: {}".format(pres.show))
            print("  status: ")
            for lang, text in pres.status.items():
                print("    (lang={}) {!r}".format(
                    lang,
                    text))


if __name__ == "__main__":
    exec_example(ListPresence())
