########################################################################
# File name: pubsub_watch.py
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

import aioxmpp
import aioxmpp.pubsub
import aioxmpp.xml

from framework import Example, exec_example


class PubSubWatch(Example):
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

    @asyncio.coroutine
    def run_example(self):
        self.stop_event = self.make_sigint_event()
        yield from super().run_example()

    def _on_item_published(self, jid, node, item, *, message=None):
        print("PUBLISHED: {}".format(item.id_))

    def _on_item_retracted(self, jid, node, id_, *, message=None):
        print("RETRACTED: {}".format(id_))

    @asyncio.coroutine
    def run_simple_example(self):
        pubsub = self.client.summon(aioxmpp.PubSubClient)
        pubsub.on_item_published.connect(self._on_item_published)
        pubsub.on_item_retracted.connect(self._on_item_retracted)
        subid = (yield from pubsub.subscribe(
            self.args.target_entity,
            node=self.args.target_node,
        )).payload.subid
        print("SUBSCRIBED: subid={!r}".format(subid))
        try:
            yield from self.stop_event.wait()
        finally:
            yield from pubsub.unsubscribe(
                self.args.target_entity,
                node=self.args.target_node,
                subid=subid,
            )


if __name__ == "__main__":
    exec_example(PubSubWatch())
