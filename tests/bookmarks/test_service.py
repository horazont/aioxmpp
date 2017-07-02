########################################################################
# File name: test_service.py
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
import io
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.private_xml
import aioxmpp.xso

import aioxmpp.bookmarks

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine
)

TEST_JID1 = aioxmpp.JID.fromstr("foo@bar.baz")
TEST_JID2 = aioxmpp.JID.fromstr("bar@bar.baz")

class TestBookmarkClient(unittest.TestCase):

    def test_is_service(self):
        self.assertTrue(issubclass(
            aioxmpp.bookmarks.BookmarkClient,
            aioxmpp.service.Service
        ))

    def test_after_private_xml(self):
        self.assertIn(
            aioxmpp.private_xml.PrivateXMLService,
            aioxmpp.bookmarks.BookmarkClient.ORDER_AFTER
        )

    def setUp(self):
        self.cc = make_connected_client()
        self.private_xml = aioxmpp.private_xml.PrivateXMLService(self.cc)
        self.s = aioxmpp.bookmarks.BookmarkClient(self.cc, dependencies={
            aioxmpp.private_xml.PrivateXMLService: self.private_xml
        })

    def tearDown(self):
        del self.cc
        del self.private_xml
        del self.s

    def test__get_bookmarks(self):
        with unittest.mock.patch.object(
                self.private_xml,
                "get_private_xml",
                new=CoroutineMock()) as get_private_xml_mock:
            get_private_xml_mock.return_value.bookmarks = \
                unittest.mock.sentinel.result
            res = run_coroutine(self.s._get_bookmarks())

        self.assertIs(res, unittest.mock.sentinel.result)
        self.assertEqual(
            len(get_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = get_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.bookmarks.Storage)
        self.assertEqual(len(arg.bookmarks), 0)

    def test__set_bookmarks(self):
        bookmarks = []
        bookmarks.append(
            aioxmpp.bookmarks.Conference(
                "Coven", aioxmpp.JID.fromstr("coven@example.com")),
        )
        bookmarks.append(
            aioxmpp.bookmarks.URL(
                "Interesting",
                "http://example.com/"),
        )

        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            run_coroutine(self.s._set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = set_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertEqual(arg.bookmarks, bookmarks)

    def test_set_bookmarks_failure(self):
        bookmarks = unittest.mock.sentinel.something_else
        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            with self.assertRaisesRegex(
                    TypeError,
                    "can only assign an iterable$"):
                run_coroutine(self.s.set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            0
        )

    def test_sync(self):
        on_added = unittest.mock.Mock()
        on_added.return_value = None
        on_removed = unittest.mock.Mock()
        on_removed.return_value = None
        on_changed = unittest.mock.Mock()
        on_changed.return_value = None

        self.s.on_bookmark_added.connect(on_added)
        self.s.on_bookmark_removed.connect(on_removed)
        self.s.on_bookmark_changed.connect(on_changed)

        with unittest.mock.patch.object(
                self.private_xml,
                "get_private_xml",
                new=CoroutineMock()) as get_private_xml_mock:
            get_private_xml_mock.return_value = aioxmpp.bookmarks.Storage()
            get_private_xml_mock.return_value.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=aioxmpp.JID.fromstr("foo@bar.baz"),
                    name="foo",
                    nick="quux"
                )
            )

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            get_private_xml_mock.return_value = aioxmpp.bookmarks.Storage()
            get_private_xml_mock.return_value.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quux"
                )
            )
            get_private_xml_mock.return_value.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quuux"
                )
            )

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            get_private_xml_mock.return_value = aioxmpp.bookmarks.Storage()
            get_private_xml_mock.return_value.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quux"
                )
            )

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            get_private_xml_mock.return_value = aioxmpp.bookmarks.Storage()
            get_private_xml_mock.return_value.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=aioxmpp.JID.fromstr("foo@bar.baz"),
                    name="foo",
                    nick="quuux"
                )
            )

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

        self.assertEqual(
            len(on_added.mock_calls), 2
        )

        self.assertEqual(
            len(on_removed.mock_calls), 1
        )

        self.assertEqual(
            len(on_changed.mock_calls), 1
        )


    def test_add_bookmark(self):
        pass

    def test_add_bookmark_already_present(self):
        pass

    def test_remove_bookmark(self):
        pass

    def test_remove_bookmark_already_gone(self):
        pass

    def test_update_bookmark(self):
        pass

