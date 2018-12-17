########################################################################
# File name: test___init__.py
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

import aioxmpp.structs as structs
import aioxmpp.xso.model as xso_model
import aioxmpp.xso as xso


class Testtag_to_str(unittest.TestCase):
    def test_unqualified(self):
        self.assertEqual(
            "foo",
            xso.tag_to_str((None, "foo"))
        )

    def test_with_namespace(self):
        self.assertEqual(
            "{uri:bar}foo",
            xso.tag_to_str(("uri:bar", "foo"))
        )


class Testnormalize_tag(unittest.TestCase):
    def test_unqualified(self):
        self.assertEqual(
            (None, "foo"),
            xso.normalize_tag("foo")
        )

    def test_with_namespace(self):
        self.assertEqual(
            ("uri:bar", "foo"),
            xso.normalize_tag(("uri:bar", "foo"))
        )

    def test_etree_format(self):
        self.assertEqual(
            ("uri:bar", "foo"),
            xso.normalize_tag("{uri:bar}foo")
        )

    def test_validate_etree_format(self):
        with self.assertRaises(ValueError):
            xso.normalize_tag("uri:bar}foo")

    def test_validate_tuple_format(self):
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo",))
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo", "bar", "baz"))
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo", None))
        with self.assertRaises(ValueError):
            xso.normalize_tag((None, None))
        with self.assertRaises(TypeError):
            xso.normalize_tag((1, 2))

    def test_reject_incorrect_types(self):
        with self.assertRaises(TypeError):
            xso.normalize_tag(1)
        with self.assertRaises(TypeError):
            xso.normalize_tag((1, 2))


class TestNO_DEFAULT(unittest.TestCase):
    def test_unequal_to_things(self):
        NO_DEFAULT = xso.NO_DEFAULT
        self.assertFalse(NO_DEFAULT is None)
        self.assertFalse(NO_DEFAULT is True)
        self.assertFalse(NO_DEFAULT is False)
        self.assertFalse(NO_DEFAULT == "")
        self.assertFalse(NO_DEFAULT == "foo")
        self.assertFalse(NO_DEFAULT == 0)
        self.assertFalse(NO_DEFAULT == 123)
        self.assertFalse(NO_DEFAULT == 0.)
        self.assertFalse(NO_DEFAULT == float("nan"))

    def test_equal_to_itself(self):
        self.assertTrue(xso.NO_DEFAULT == xso.NO_DEFAULT)
        self.assertFalse(xso.NO_DEFAULT != xso.NO_DEFAULT)

    def test___bool__raises(self):
        with self.assertRaises(TypeError):
            bool(xso.NO_DEFAULT)

    def test___index__raises(self):
        with self.assertRaises(TypeError):
            int(xso.NO_DEFAULT)

    def test___float__raises(self):
        with self.assertRaises(TypeError):
            float(xso.NO_DEFAULT)

    def test___lt__raises(self):
        with self.assertRaises(TypeError):
            xso.NO_DEFAULT < xso.NO_DEFAULT

    def test___gt__raises(self):
        with self.assertRaises(TypeError):
            xso.NO_DEFAULT > xso.NO_DEFAULT


class TestAbstractTextChild(unittest.TestCase):
    def test_moved(self):
        self.assertTrue(xso.AbstractTextChild,
                        xso_model.AbstractTextChild)
