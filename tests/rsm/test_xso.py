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
import unittest.mock

import aioxmpp.xso as xso

import aioxmpp.rsm.xso as rsm_xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_rsm(self):
        self.assertEqual(
            namespaces.xep0059_rsm,
            "http://jabber.org/protocol/rsm"
        )


class Test_RangeLimitBase(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rsm_xso._RangeLimitBase,
            xso.XSO,
        ))

    def test_value(self):
        self.assertIsInstance(
            rsm_xso._RangeLimitBase.value,
            xso.Text,
        )

    def test_init_default(self):
        l = rsm_xso._RangeLimitBase()
        self.assertIsNone(l.value)

    def test_init(self):
        l = rsm_xso._RangeLimitBase("foo")
        self.assertEqual(l.value, "foo")


class TestAfter(unittest.TestCase):
    def test_is_range_limit(self):
        self.assertTrue(issubclass(
            rsm_xso.After,
            rsm_xso._RangeLimitBase,
        ))

    def test_tag(self):
        self.assertEqual(
            rsm_xso.After.TAG,
            (namespaces.xep0059_rsm, "after"),
        )


class TestFirst(unittest.TestCase):
    def test_is_range_limit(self):
        self.assertTrue(issubclass(
            rsm_xso.First,
            rsm_xso._RangeLimitBase,
        ))

    def test_tag(self):
        self.assertEqual(
            rsm_xso.First.TAG,
            (namespaces.xep0059_rsm, "first"),
        )

    def test_index(self):
        self.assertIsInstance(
            rsm_xso.First.index,
            xso.Attr,
        )
        self.assertEqual(
            rsm_xso.First.index.tag,
            (None, "index"),
        )
        self.assertIsInstance(
            rsm_xso.First.index.type_,
            xso.Integer,
        )
        self.assertIsNone(rsm_xso.First.index.default)


class TestLast(unittest.TestCase):
    def test_is_range_limit(self):
        self.assertTrue(issubclass(
            rsm_xso.Last,
            rsm_xso._RangeLimitBase,
        ))

    def test_tag(self):
        self.assertEqual(
            rsm_xso.Last.TAG,
            (namespaces.xep0059_rsm, "last"),
        )


class TestBefore(unittest.TestCase):
    def test_is_range_limit(self):
        self.assertTrue(issubclass(
            rsm_xso.Before,
            rsm_xso._RangeLimitBase,
        ))

    def test_tag(self):
        self.assertEqual(
            rsm_xso.Before.TAG,
            (namespaces.xep0059_rsm, "before"),
        )


class TestResultSetMetadata(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rsm_xso.ResultSetMetadata,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            rsm_xso.ResultSetMetadata.TAG,
            (namespaces.xep0059_rsm, "set"),
        )

    def test_before(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.before,
            xso.Child,
        )
        self.assertSetEqual(
            rsm_xso.ResultSetMetadata.before._classes,
            {
                rsm_xso.Before,
            }
        )

    def test_after(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.after,
            xso.Child,
        )
        self.assertSetEqual(
            rsm_xso.ResultSetMetadata.after._classes,
            {
                rsm_xso.After,
            }
        )

    def test_first(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.first,
            xso.Child,
        )
        self.assertSetEqual(
            rsm_xso.ResultSetMetadata.first._classes,
            {
                rsm_xso.First,
            }
        )

    def test_last(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.last,
            xso.Child,
        )
        self.assertSetEqual(
            rsm_xso.ResultSetMetadata.last._classes,
            {
                rsm_xso.Last,
            }
        )

    def test_count(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.count,
            xso.ChildText,
        )
        self.assertEqual(
            rsm_xso.ResultSetMetadata.count.tag,
            (namespaces.xep0059_rsm, "count"),
        )
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.count.type_,
            xso.Integer,
        )
        self.assertIsNone(rsm_xso.ResultSetMetadata.count.default)

    def test_index(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.index,
            xso.ChildText,
        )
        self.assertEqual(
            rsm_xso.ResultSetMetadata.index.tag,
            (namespaces.xep0059_rsm, "index"),
        )
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.index.type_,
            xso.Integer,
        )
        self.assertIsNone(rsm_xso.ResultSetMetadata.index.default)

    def test_max(self):
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.max_,
            xso.ChildText,
        )
        self.assertEqual(
            rsm_xso.ResultSetMetadata.max_.tag,
            (namespaces.xep0059_rsm, "max"),
        )
        self.assertIsInstance(
            rsm_xso.ResultSetMetadata.max_.type_,
            xso.Integer,
        )
        self.assertIsNone(rsm_xso.ResultSetMetadata.max_.default)

    def test_init(self):
        rsm = rsm_xso.ResultSetMetadata()
        self.assertIsNone(rsm.first)
        self.assertIsNone(rsm.last)
        self.assertIsNone(rsm.after)
        self.assertIsNone(rsm.before)
        self.assertIsNone(rsm.count)
        self.assertIsNone(rsm.max_)
        self.assertIsNone(rsm.index)

    def test_fetch_page(self):
        rsm = rsm_xso.ResultSetMetadata.fetch_page(10)
        self.assertEqual(rsm.index, 10)
        self.assertIsNone(rsm.max_)

    def test_fetch_page_with_count(self):
        rsm = rsm_xso.ResultSetMetadata.fetch_page(20, max_=100)
        self.assertEqual(rsm.index, 20)
        self.assertEqual(rsm.max_, 100)

    def test_limit_cls(self):
        rsm = rsm_xso.ResultSetMetadata.limit(100)
        self.assertEqual(rsm.max_, 100)

    def test_limit_index_obj(self):
        rsm = rsm_xso.ResultSetMetadata.fetch_page(10)
        new_rsm = rsm.limit(100)
        self.assertIsNot(rsm, new_rsm)
        self.assertEqual(rsm.index, new_rsm.index)
        self.assertEqual(new_rsm.max_, 100)
        self.assertIsNone(rsm.max_)

    def test_limit_before_after_obj(self):
        rsm = rsm_xso.ResultSetMetadata()
        rsm.after = rsm_xso.After()
        rsm.before = rsm_xso.Before()
        new_rsm = rsm.limit(100)
        self.assertIsNot(rsm, new_rsm)
        self.assertIsNot(rsm.before, new_rsm.before)
        self.assertIsNot(rsm.after, new_rsm.after)
        self.assertEqual(rsm.after.value, new_rsm.after.value)
        self.assertEqual(rsm.before.value, new_rsm.before.value)
        self.assertEqual(new_rsm.max_, 100)
        self.assertIsNone(rsm.max_)

    def test_next__obj(self):
        rsm = rsm_xso.ResultSetMetadata()
        rsm.last = unittest.mock.Mock()
        rsm.last.value = "last value"

        new_rsm = rsm.next_page()
        self.assertIsNot(rsm, new_rsm)
        self.assertIsNot(rsm.last, new_rsm.after)
        self.assertEqual(rsm.last.value, new_rsm.after.value)
        self.assertIsNone(new_rsm.max_)

    def test_next__with_max_obj(self):
        rsm = rsm_xso.ResultSetMetadata()
        rsm.last = unittest.mock.Mock()
        rsm.last.value = "last value"

        new_rsm = rsm.next_page(max_=100)
        self.assertIsNot(rsm, new_rsm)
        self.assertIsNot(rsm.last, new_rsm.after)
        self.assertEqual(rsm.last.value, new_rsm.after.value)
        self.assertEqual(new_rsm.max_, 100)

    def test_previous_obj(self):
        rsm = rsm_xso.ResultSetMetadata()
        rsm.first = unittest.mock.Mock()
        rsm.first.value = "first value"

        new_rsm = rsm.previous_page()
        self.assertIsNot(rsm, new_rsm)
        self.assertIsNot(rsm.first, new_rsm.before)
        self.assertEqual(rsm.first.value, new_rsm.before.value)
        self.assertIsNone(new_rsm.max_)

    def test_previous_with_max_obj(self):
        rsm = rsm_xso.ResultSetMetadata()
        rsm.first = unittest.mock.Mock()
        rsm.first.value = "first value"

        new_rsm = rsm.previous_page(max_=100)
        self.assertIsNot(rsm, new_rsm)
        self.assertIsNot(rsm.first, new_rsm.before)
        self.assertEqual(rsm.first.value, new_rsm.before.value)
        self.assertEqual(new_rsm.max_, 100)

    def test_last_cls(self):
        rsm = rsm_xso.ResultSetMetadata.last_page()
        self.assertIsInstance(rsm.before, rsm_xso.Before)
        self.assertIsNone(rsm.before.value)
        self.assertIsNone(rsm.max_)

    def test_last_with_max_cls(self):
        rsm = rsm_xso.ResultSetMetadata.last_page(max_=10)
        self.assertIsInstance(rsm.before, rsm_xso.Before)
        self.assertIsNone(rsm.before.value)
        self.assertEqual(rsm.max_, 10)
