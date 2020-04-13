########################################################################
# File name: test_e2e.py
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

import aioxmpp.bookmarks

from aioxmpp.e2etest import (
    blocking_timed,
    TestCase,
)


class TestBookmarks(TestCase):
    @blocking_timed
    async def setUp(self):
        self.client = await self.provisioner.get_connected_client(
            services=[aioxmpp.BookmarkClient]
        )

        self.s = self.client.summon(aioxmpp.BookmarkClient)

    @blocking_timed
    async def test_store_and_retrieve(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        await self.s.add_bookmark(bookmark)

        bookmarks = await self.s.get_bookmarks()
        self.assertIn(bookmark, bookmarks)
        self.assertIsNot(bookmark, bookmarks[0])

    @blocking_timed
    async def test_add_event(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        added_future = asyncio.Future()

        def handler(bookmark):
            added_future.set_result(bookmark)
            return True  # disconnect

        self.s.on_bookmark_added.connect(handler)

        await self.s.add_bookmark(bookmark)

        self.assertTrue(added_future.done())
        self.assertEqual(added_future.result(), bookmark)
        self.assertIsNot(added_future.result(), bookmark)

    @blocking_timed
    async def test_store_and_remove(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        await self.s.add_bookmark(bookmark)

        await self.s.discard_bookmark(bookmark)

        bookmarks = await self.s.get_bookmarks()
        self.assertNotIn(bookmark, bookmarks)

    @blocking_timed
    async def test_remove_event(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        await self.s.add_bookmark(bookmark)

        removed_future = asyncio.Future()

        def handler(bookmark):
            removed_future.set_result(bookmark)
            return True  # disconnect

        self.s.on_bookmark_removed.connect(handler)

        await self.s.discard_bookmark(bookmark)

        self.assertTrue(removed_future.done())
        self.assertEqual(removed_future.result(), bookmark)
        self.assertIsNot(removed_future.result(), bookmark)

    @blocking_timed
    async def test_store_and_update(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        await self.s.add_bookmark(bookmark)

        updated_bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit"),
            nick="firstwitch",
            autojoin=True,
        )

        await self.s.update_bookmark(bookmark, updated_bookmark)

        bookmarks = await self.s.get_bookmarks()
        self.assertNotIn(bookmark, bookmarks)
        self.assertIn(updated_bookmark, bookmarks)

    @blocking_timed
    async def test_change_event(self):
        bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit")
        )

        await self.s.add_bookmark(bookmark)

        changed_future = asyncio.Future()

        def handler(old, new):
            changed_future.set_result((old, new))
            return True  # disconnect

        self.s.on_bookmark_changed.connect(handler)

        updated_bookmark = aioxmpp.bookmarks.Conference(
            "Coven",
            aioxmpp.JID.fromstr("coven@chat.shakespeare.lit"),
            nick="firstwitch",
            autojoin=True,
        )

        await self.s.update_bookmark(bookmark, updated_bookmark)

        self.assertTrue(changed_future.done())
        old, new = changed_future.result()

        self.assertEqual(old, bookmark)
        self.assertEqual(new, updated_bookmark)
