########################################################################
# File name: set_avatar.py
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

import aioxmpp
import aioxmpp.avatar

from framework import Example, exec_example


class Avatar(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        self.argparse.add_argument(
            "muc_jid",
            type=aioxmpp.JID.fromstr,
        )

        self.argparse.add_argument(
            "--mime-type",
            default="image/png",
        )

        group = self.argparse.add_mutually_exclusive_group(required=True)

        group.add_argument(
            "--set-avatar", nargs=1, metavar="AVATAR_FILE",
            help="set the avatar to content of the supplied file."
        )

        group.add_argument(
            "--wipe-avatar",
            action="store_true",
            default=False,
            help="set the avatar to no avatar."
        )

    def configure(self):
        super().configure()
        if self.args.set_avatar:
            self.avatar_file, = self.args.set_avatar
        else:
            self.avatar_file = None
        self.wipe_avatar = self.args.wipe_avatar
        self.target_jid = self.args.muc_jid
        self.mime_type = self.args.mime_type

    def make_simple_client(self):
        client = super().make_simple_client()
        self.vcard = client.summon(aioxmpp.vcard.VCardService)
        return client

    async def run_simple_example(self):
        vcard = await self.vcard.get_vcard(jid=self.target_jid)
        vcard.clear_photo_data()
        if self.avatar_file is not None:
            with open(self.avatar_file, "rb") as f:
                image_data = f.read()

            vcard = await self.vcard.get_vcard(jid=self.target_jid)
            vcard.set_photo_data(self.mime_type, image_data)
            await self.vcard.set_vcard(vcard, jid=self.target_jid)

        elif self.wipe_avatar:
            await self.vcard.set_vcard(vcard, jid=self.target_jid)

    async def run_example(self):
        await super().run_example()


if __name__ == "__main__":
    exec_example(Avatar())
