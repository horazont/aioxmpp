########################################################################
# File name: test_xmltestutils.py
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
import unittest

from aioxmpp.utils import etree

from aioxmpp.xmltestutils import XMLTestCase, element_path


class TestTestUtils(unittest.TestCase):
    def test_element_path(self):
        el = etree.fromstring("<foo><bar><baz /></bar>"
                              "<subfoo />"
                              "<bar><baz /></bar></foo>")
        baz1 = el[0][0]
        subfoo = el[1]
        baz2 = el[2][0]

        self.assertEqual(
            "/foo",
            element_path(el))
        self.assertEqual(
            "/foo/bar[0]/baz[0]",
            element_path(baz1))
        self.assertEqual(
            "/foo/subfoo[0]",
            element_path(subfoo))
        self.assertEqual(
            "/foo/bar[1]/baz[0]",
            element_path(baz2))


class TestXMLTestCase(XMLTestCase):
    def test_assertSubtreeEqual_tag(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<bar />")

        with self.assertRaisesRegex(AssertionError, "tag mismatch"):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_key_missing(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo />")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_attr_surplus_key(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo />")
        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_allow_surplus(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<foo a='1'/>")
        self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_attr_value_mismatch(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo a='2'/>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_attr_value_mismatch_allow_surplus(self):
        t1 = etree.fromstring("<foo a='1'/>")
        t2 = etree.fromstring("<foo a='1' b='2'/>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_attr=True)

    def test_assertSubtreeEqual_missing_child(self):
        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo />")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_surplus_child(self):
        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo><bar/><bar/></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_allow_surplus_child(self):
        t1 = etree.fromstring("<foo />")
        t2 = etree.fromstring("<foo><bar/></foo>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_children=True)

        t1 = etree.fromstring("<foo><bar/></foo>")
        t2 = etree.fromstring("<foo><bar/><bar/><fnord /></foo>")

        self.assertSubtreeEqual(t1, t2, ignore_surplus_children=True)

    def test_assertSubtreeEqual_allow_relative_reordering(self):
        t1 = etree.fromstring("<foo><bar/><baz/></foo>")
        t2 = etree.fromstring("<foo><baz/><bar/></foo>")

        self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_forbid_reordering_of_same(self):
        t1 = etree.fromstring("<foo><bar a='1' /><bar a='2' /></foo>")
        t2 = etree.fromstring("<foo><bar a='2' /><bar a='1' /></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_strict_ordering(self):
        t1 = etree.fromstring("<foo><bar/><baz/></foo>")
        t2 = etree.fromstring("<foo><baz/><bar/></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, strict_ordering=True)

    def test_assertSubtreeEqual_text(self):
        t1 = etree.fromstring("<foo>text1</foo>")
        t2 = etree.fromstring("<foo>text2</foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_text_including_tails(self):
        t1 = etree.fromstring("<foo>t<a/>ext1</foo>")
        t2 = etree.fromstring("<foo>te<a/>xt1</foo>")

        self.assertSubtreeEqual(t1, t2)

    def test_assertSubtreeEqual_text_no_join_text_parts(self):
        t1 = etree.fromstring("<foo>t<a/>ext1</foo>")
        t2 = etree.fromstring("<foo>te<a/>xt1</foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, join_text_parts=False)

    def test_assertSubtreeEqual_text_no_join_text_parts_is_strict(self):
        t1 = etree.fromstring("<foo><a/>text1</foo>")
        t2 = etree.fromstring("<foo>text1<a/></foo>")

        with self.assertRaises(AssertionError):
            self.assertSubtreeEqual(t1, t2, join_text_parts=False)
