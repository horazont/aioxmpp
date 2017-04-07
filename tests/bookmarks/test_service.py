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

import lxml.etree
import lxml.sax

import aioxmpp
import aioxmpp.private_xml
import aioxmpp.xso

import aioxmpp.bookmarks

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine
)

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

    def test_get_bookmarks(self):
        with unittest.mock.patch.object(
                self.private_xml,
                "get_private_xml",
                new=CoroutineMock()) as get_private_xml_mock:
            get_private_xml_mock.return_value = unittest.mock.sentinel.result
            res = run_coroutine(self.s.get_bookmarks())

        self.assertIs(res, unittest.mock.sentinel.result)
        self.assertEqual(
            len(get_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = get_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.bookmarks.Storage)
        self.assertEqual(len(arg.bookmarks), 0)

    def test_set_bookmarks(self):
        bookmarks = aioxmpp.bookmarks.Storage()
        bookmarks.bookmarks.append(
            aioxmpp.bookmarks.Conference(
                "Coven", aioxmpp.JID.fromstr("coven@example.com")),
        )
        bookmarks.bookmarks.append(
            aioxmpp.bookmarks.URL(
                "Interesting",
                "http://example.com/"),
        )

        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            run_coroutine(self.s.set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = set_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertIs(arg, bookmarks)

    def test_set_bookmarks_failure(self):
        bookmarks = unittest.mock.sentinel.something_else
        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            with self.assertRaisesRegex(
                    TypeError,
                    "^set_bookmarks only accepts bookmark.Storage objects$"):
                run_coroutine(self.s.set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            0
        )
