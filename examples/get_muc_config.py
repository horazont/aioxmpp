########################################################################
# File name: get_muc_config.py
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
import configparser

import aioxmpp.muc
import aioxmpp.muc.xso

from framework import Example, exec_example


class ServerInfo(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--muc",
            type=jid,
            default=None,
            help="JID of the muc to query"
        )

    def configure(self):
        super().configure()

        self.muc_jid = self.args.muc
        if self.muc_jid is None:
            try:
                self.muc_jid = aioxmpp.JID.fromstr(
                    self.config.get("muc_config", "muc_jid")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.muc_jid = aioxmpp.JID.fromstr(
                    input("MUC JID> ")
                )

    def make_simple_client(self):
        client = super().make_simple_client()
        client.summon(aioxmpp.MUCClient)
        return client

    async def run_simple_example(self):
        config = await self.client.summon(
            aioxmpp.MUCClient
        ).get_room_config(
            self.muc_jid
        )
        form = aioxmpp.muc.xso.ConfigurationForm.from_xso(config)

        print("name:", form.roomname.value)
        print("description:", form.roomdesc.value)

        print("moderated?", form.moderatedroom.value)

        print("members only?", form.membersonly.value)

        print("persistent?", form.persistentroom.value)


if __name__ == "__main__":
    exec_example(ServerInfo())
