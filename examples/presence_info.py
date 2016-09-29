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

    async def _show_info(self, full_jid):
        info = await self.disco.query_info(full_jid)
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
        self.disco = client.summon(aioxmpp.disco.Service)
        self.caps = client.summon(aioxmpp.entitycaps.Service)

        if self.args.system_capsdb:
            self.caps.cache.set_system_db_path(self.args.system_capsdb)
        self.caps.cache.set_user_db_path(self.args.user_capsdb)

        self.presence = client.summon(aioxmpp.presence.Service)
        self.presence.on_available.connect(
            self._on_available
        )

        return client

    async def run_simple_example(self):
        for i in range(5, 0, -1):
            print("going to wait {} more seconds for further "
                  "presence".format(i))
            await asyncio.sleep(1)


if __name__ == "__main__":
    exec_example(PresenceInfo())
