########################################################################
# File name: presence_info.py
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
import pathlib

import aioxmpp.disco
import aioxmpp.entitycaps
import aioxmpp.presence

from framework import Example, exec_example


class PresenceInfo(Example):
    def prepare_argparse(self):
        super().prepare_argparse()
        self.argparse.add_argument(
            "--system-capsdb",
            type=pathlib.Path,
            default=None,
            metavar="DIR",
            help="Path to the capsdb",
        )
        self.argparse.add_argument(
            "--user-capsdb",
            metavar="DIR",
            type=pathlib.Path,
            default=pathlib.Path().cwd() / "user_hashes",
            help="Path to the user capsdb (defaults to user_hashes/)",
        )

        self.argparse.epilog = """
        Point --system-capsdb to a directory containing the capsdb
        (<https://github.com/xnyhps/capsdb>) to speed up fetching of
        capabilities of peers.
        """

    @asyncio.coroutine
    def _show_info(self, full_jid):
        info = yield from self.disco.query_info(full_jid)
        print("{}:".format(full_jid))
        print("  features:")
        for feature in info.features:
            print("    {!r}".format(feature))

        print("  identities:")
        identities = list(info.identities)

        def identity_key(identity):
            return identity.category, identity.type_

        identities.sort(key=identity_key)

        for (category, type_), identities in (
                itertools.groupby(info.identities, identity_key)):
            print("    category={!r} type={!r}".format(category, type_))
            subidentities = list(identities)
            subidentities.sort(key=lambda ident: ident.lang)
            for identity in subidentities:
                print("      [{}] {!r}".format(identity.lang, identity.name))

    def _on_available(self, full_jid, stanza):
        asyncio.ensure_future(self._show_info(full_jid))

    def make_simple_client(self):
        client = super().make_simple_client()
        self.disco = client.summon(aioxmpp.DiscoClient)
        self.caps = client.summon(aioxmpp.EntityCapsService)

        if self.args.system_capsdb:
            self.caps.cache.set_system_db_path(self.args.system_capsdb)
        self.caps.cache.set_user_db_path(self.args.user_capsdb)

        self.presence = client.summon(aioxmpp.PresenceService)
        self.presence.on_available.connect(
            self._on_available
        )

        return client

    @asyncio.coroutine
    def run_simple_example(self):
        for i in range(5, 0, -1):
            print("going to wait {} more seconds for further "
                  "presence".format(i))
            yield from asyncio.sleep(1)


if __name__ == "__main__":
    exec_example(PresenceInfo())
