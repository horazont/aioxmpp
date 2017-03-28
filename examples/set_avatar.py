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
import sys

import aioxmpp
import aioxmpp.avatar

from framework import Example, exec_example


class Avatar(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        group = self.argparse.add_mutually_exclusive_group(required=True)

        group.add_argument(
            "--set-avatar", nargs=1, metavar="AVATAR_FILE",
            help="set the avatar to content of the supplied PNG file."
        )

        group.add_argument(
            "--wipe-avatar",
            action="store_true",
            default=False,
            help="set the avatar to no avatar."
        )

    def configure(self):
        super().configure()
        self.avatar_file = self.args.avatar_file
        self.wipe_avatar = self.args.wipe_avatar

    def make_simple_client(self):
        client = super().make_simple_client()
        self.avatar = client.summon(aioxmpp.avatar.AvatarServer)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        if self.avatar_file is not None:
            with open(self.avatar_file, "rb") as f:
                image_data = f.read()

            avatar_set = aioxmpp.avatar.AvatarSet()
            avatar_set.add_avatar_image("image/png", image_bytes=image_data)

            yield from self.avatar.publish_avatar_set(avatar_set)

        elif self.wipe_avatar:
            yield from self.avatar.disable_avatar()

    @asyncio.coroutine
    def run_example(self):
        yield from super().run_example()

if __name__ == "__main__":
    exec_example(Avatar())
