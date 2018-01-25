########################################################################
# File name: get_vcard.py
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

import lxml

import aioxmpp
import aioxmpp.vcard as vcard

from framework import Example, exec_example


class VCard(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--remote-jid",
            type=jid,
            help="the jid of which to retrieve the avatar"
        )

    def configure(self):
        super().configure()

        self.remote_jid = self.args.remote_jid
        if self.remote_jid is None:
            try:
                self.remote_jid = aioxmpp.JID.fromstr(
                    self.config.get("vcard", "remote_jid")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.remote_jid = aioxmpp.JID.fromstr(
                    input("Remote JID> ")
                )

    def make_simple_client(self):
        client = super().make_simple_client()
        self.vcard = client.summon(aioxmpp.vcard.VCardService)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        vcard = yield from self.vcard.get_vcard(
            self.remote_jid
        )


        es = lxml.etree.tostring(vcard.elements, pretty_print=True,
                                 encoding="utf-8")
        print(es.decode("utf-8"))

    @asyncio.coroutine
    def run_example(self):
        yield from super().run_example()

if __name__ == "__main__":
    exec_example(VCard())
