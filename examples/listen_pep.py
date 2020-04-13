########################################################################
# File name: listen_pep.py
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
import itertools
import io
import pathlib

import aioxmpp.disco
import aioxmpp.entitycaps
import aioxmpp.presence
import aioxmpp.xso

from framework import Example, exec_example


class ListenPEP(Example):
    def prepare_argparse(self):
        super().prepare_argparse()
        self.argparse.add_argument(
            "--namespace",
            dest="namespaces",
            default=[],
            action="append",
            metavar="PEP-NAMESPACE",
            help="PEP namespace to listen for (omit the +notify!). May be "
            "given multiple times."
        )

    def configure(self):
        super().configure()
        self.pep_namespaces = self.args.namespaces

    def _on_item_published(self, jid, node, item, message=None):
        buf = io.BytesIO()
        aioxmpp.xml.write_single_xso(item, buf)
        print(jid, node, buf.getvalue().decode("utf-8"))

    def make_simple_client(self):
        client = super().make_simple_client()
        self.caps = client.summon(aioxmpp.EntityCapsService)
        self.pep = client.summon(aioxmpp.PEPClient)

        self.claims = []
        for ns in self.pep_namespaces:
            claim = self.pep.claim_pep_node(
                ns,
                notify=True,
            )
            claim.on_item_publish.connect(self._on_item_published)
            self.claims.append(claim)

        return client

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    async def run_simple_example(self):
        await self.stop_event.wait()


if __name__ == "__main__":
    exec_example(ListenPEP())
