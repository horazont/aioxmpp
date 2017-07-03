########################################################################
# File name: test_xso.py
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
import unittest

import aioxmpp.structs
import aioxmpp.bookmarks.xso as bookmark_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

EXAMPLE_JID1 = aioxmpp.JID.fromstr("coven@conference.shakespeare.lit")
EXAMPLE_JID2 = aioxmpp.JID.fromstr("open_field@conference.shakespeare.lit")


class TestNamespace(unittest.TestCase):

    def test_namespace(self):
        self.assertEqual(namespaces.xep0048, "storage:bookmarks")


class TestStorage(unittest.TestCase):

    def test_is_xso(self):
        self.assertTrue(issubclass(bookmark_xso.Storage, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            bookmark_xso.Storage.TAG,
            (namespaces.xep0048, "storage")
        )


class TestConference(unittest.TestCase):

    def test_is_xso(self):
        self.assertTrue(issubclass(bookmark_xso.Conference, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            bookmark_xso.Conference.TAG,
            (namespaces.xep0048, "conference")
        )

    def test_init(self):
        conference = bookmark_xso.Conference("Coven", EXAMPLE_JID1)
        self.assertEqual(conference.name, "Coven")
        self.assertEqual(conference.jid, EXAMPLE_JID1)
        self.assertEqual(conference.autojoin, False)
        self.assertEqual(conference.nick, None)
        self.assertEqual(conference.password, None)

        conference = bookmark_xso.Conference(
            "Coven", EXAMPLE_JID1,
            autojoin=True, nick="First Witch",
            password="h3c473"
        )
        self.assertEqual(conference.name, "Coven")
        self.assertEqual(conference.jid, EXAMPLE_JID1)
        self.assertEqual(conference.autojoin, True)
        self.assertEqual(conference.nick, "First Witch")
        self.assertEqual(conference.password, "h3c473")

    def test_eq(self):
        conf = bookmark_xso.Conference("Coven", EXAMPLE_JID1)
        conf1 = bookmark_xso.Conference("Coven", EXAMPLE_JID1)
        conf2 = bookmark_xso.Conference(
            "Coven1", EXAMPLE_JID1,
            autojoin=True, nick="First Witch",
            password="h3c473"
        )
        conf3 = bookmark_xso.Conference(
            "Coven", EXAMPLE_JID2,
            autojoin=True, nick="First Witch",
            password="h3c473"
        )
        conf4 = bookmark_xso.Conference(
            "Coven", EXAMPLE_JID1,
            nick="First Witch",
            password="h3c473"
        )
        conf5 = bookmark_xso.Conference(
            "Coven", EXAMPLE_JID1,
            autojoin=True,
            password="h3c473"
        )
        conf6 = bookmark_xso.Conference(
            "Coven", EXAMPLE_JID1,
            autojoin=True, nick="First Witch"
        )
        url = bookmark_xso.URL(
            "Coven", "xmpp://coven@conference.shakespeare.lit"
        )
        self.assertEqual(conf, conf)
        self.assertEqual(conf, conf1)
        self.assertNotEqual(conf, conf2)
        self.assertNotEqual(conf, conf3)
        self.assertNotEqual(conf, conf4)
        self.assertNotEqual(conf, conf5)
        self.assertNotEqual(conf, conf6)
        self.assertNotEqual(conf, url)


class TestURL(unittest.TestCase):

    def test_is_xso(self):
        self.assertTrue(issubclass(bookmark_xso.URL, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            bookmark_xso.URL.TAG,
            (namespaces.xep0048, "url")
        )

    def test_init(self):
        url = bookmark_xso.URL("Url1", "http://example.com")
        self.assertEqual(url.name, "Url1")
        self.assertEqual(url.url, "http://example.com")

    def test_eq(self):
        url = bookmark_xso.URL("Url", "http://example.com")
        url1 = bookmark_xso.URL("Url", "http://example.com")
        url2 = bookmark_xso.URL("Url1", "http://example.com")
        url3 = bookmark_xso.URL("Url", "http://example.com/foo")
        conf = bookmark_xso.Conference("Coven", EXAMPLE_JID1)

        self.assertEqual(url, url)
        self.assertEqual(url, url1)
        self.assertNotEqual(url, url2)
        self.assertNotEqual(url, url3)
        self.assertNotEqual(url, conf)


@bookmark_xso.as_bookmark_class
class CustomBookmark(bookmark_xso.Bookmark):
    TAG = ("urn:example:bookmark", "bookmark")

    def __init__(self, name, contents):
        self.name = name
        self.contents = contents

    name = aioxmpp.xso.Attr("name")
    contents = aioxmpp.xso.Attr("contents")

    @property
    def primary(self):
        return self.contents

    @property
    def secondary(self):
        return (self.name,)


class TestCustomBookmark(unittest.TestCase):

    def test_registered(self):
        self.assertIn(
            CustomBookmark, bookmark_xso.Storage.bookmarks._classes
        )

    def test_non_Bookmarks_fail(self):
        with self.assertRaises(TypeError):

            @bookmark_xso.as_bookmark_class
            class CustomBookmark(aioxmpp.xso.XSO):
                TAG = ("urn:example:bookmark", "bookmark")

                def __init__(self, name, contents):
                    self.name = name
                    self.contents = contents

                name = aioxmpp.xso.Attr("name")
                contents = aioxmpp.xso.Attr("contents")

                @property
                def primary(self):
                    return self.contents

                @property
                def secondary(self):
                    return (self.name,)
