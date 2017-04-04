########################################################################
# File name: retrieve_avatar.py
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

import aioxmpp
import aioxmpp.avatar

from framework import Example, exec_example


class Avatar(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "output_file",
            help="the file the retrieved avatar image will be written to."
        )

        self.argparse.add_argument(
            "--remote-jid",
            type=jid,
            help="the jid of which to retrieve the avatar"
        )

    def configure(self):
        super().configure()

        self.output_file = self.args.output_file
        self.remote_jid = self.args.remote_jid
        if self.remote_jid is None:
            try:
                self.remote_jid = aioxmpp.JID.fromstr(
                    self.config.get("avatar", "remote_jid")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.remote_jid = aioxmpp.JID.fromstr(
                    input("Remote JID> ")
                )

    def make_simple_client(self):
        client = super().make_simple_client()
        self.avatar = client.summon(aioxmpp.avatar.AvatarClient)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        metadata = yield from self.avatar.get_avatar_metadata(
            self.remote_jid
        )

        for metadatum in metadata["image/png"]:
            if metadatum.has_image_data_in_pubsub:
                image = yield from metadatum.get_image_bytes()
                with open(self.output_file, "wb") as avatar_image:
                    avatar_image.write(image)
                return

        print("retrieving avatar failed: no avatar in pubsub")

    @asyncio.coroutine
    def run_example(self):
        yield from super().run_example()

if __name__ == "__main__":
    exec_example(Avatar())
