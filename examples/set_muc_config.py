########################################################################
# File name: set_muc_config.py
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
# General Public License for more details.
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

        self.argparse.set_defaults(
            moderated=None,
            persistent=None,
            membersonly=None,
        )

        mutex = self.argparse.add_mutually_exclusive_group()
        mutex.add_argument(
            "--set-moderated",
            dest="moderated",
            action="store_true",
            help="Set the room to be moderated",
        )
        mutex.add_argument(
            "--clear-moderated",
            dest="moderated",
            action="store_false",
            help="Set the room to be unmoderated",
        )

        mutex = self.argparse.add_mutually_exclusive_group()
        mutex.add_argument(
            "--set-persistent",
            dest="persistent",
            action="store_true",
            help="Set the room to be persistent",
        )
        mutex.add_argument(
            "--clear-persistent",
            dest="persistent",
            action="store_false",
            help="Set the room to be not persistent",
        )

        mutex = self.argparse.add_mutually_exclusive_group()
        mutex.add_argument(
            "--set-members-only",
            dest="membersonly",
            action="store_true",
            help="Set the room to be members only",
        )
        mutex.add_argument(
            "--clear-members-only",
            dest="membersonly",
            action="store_false",
            help="Set the room to be joinable by everyone",
        )

        self.argparse.add_argument(
            "--description",
            dest="description",
            default=None,
            help="Change the natural-language room description"
        )

        self.argparse.add_argument(
            "--name",
            dest="name",
            default=None,
            help="Change the natural-language room name"
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
        client.summon(aioxmpp.muc.Service)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        muc = self.client.summon(aioxmpp.muc.Service)

        config = yield from muc.get_room_config(
            self.muc_jid
        )
        form = aioxmpp.muc.xso.ConfigurationForm.from_xso(config)

        if self.args.membersonly is not None:
            form.membersonly.value = self.args.membersonly

        if self.args.persistent is not None:
            form.persistent.value = self.args.persistent

        if self.args.moderated is not None:
            form.moderatedroom.value = self.args.moderated

        if self.args.description is not None:
            form.roomdesc.value = self.args.description

        if self.args.name is not None:
            form.roomname.value = self.args.name

        yield from muc.set_room_config(
            self.muc_jid,
            form.render_reply()
        )


if __name__ == "__main__":
    exec_example(ServerInfo())
