########################################################################
# File name: get_bookmarks_raw.py
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

import lxml.etree

import aioxmpp
import aioxmpp.private_xml as private_xml
import aioxmpp.xso as xso

from framework import Example, exec_example

class Storage(xso.XSO):
    TAG = ("storage:bookmarks", "storage")

class GetBookmarksRaw(Example):

    def make_simple_client(self):
        client = super().make_simple_client()
        self.avatar = client.summon(private_xml.PrivateXMLService)
        return client

    @asyncio.coroutine
    def run_simple_example(self):
        res = yield from self.avatar.get_private_xml(
            Storage()
        )
        for item in res.unregistered_payload:
            print(lxml.etree.tostring(item, pretty_print=True).decode("utf-8"))

    @asyncio.coroutine
    def run_example(self):
        yield from super().run_example()

if __name__ == "__main__":
    exec_example(GetBookmarksRaw())
