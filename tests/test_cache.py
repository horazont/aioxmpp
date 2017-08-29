########################################################################
# File name: test_cache.py
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
import collections.abc
import unittest

import aioxmpp.cache as cache


class TestLRUDict(unittest.TestCase):
    def setUp(self):
        self.d = cache.LRUDict()

    def tearDown(self):
        del self.d

    def test_is_mutable_mapping(self):
        self.assertIsInstance(
            self.d,
            collections.abc.MutableMapping,
        )

    def test_default_maxsize(self):
        self.assertEqual(
            self.d.maxsize,
            1,
        )

    def test_store_and_retrieve(self):
        key = object()
        value = object()
        self.d[key] = value

        result = self.d[key]
        self.assertEqual(result, value)

    def test_raise_KeyError_for_unknown_key(self):
        key = object()

        with self.assertRaises(KeyError):
            self.d[key]

        value = object()
        self.d[key] = value

        with self.assertRaises(KeyError):
            self.d[object()]

    def test_store_multiple(self):
        size = 3
        self.d.maxsize = size
        keys = [object() for i in range(size)]
        values = [object() for i in range(size)]

        for i, (k, v) in enumerate(zip(keys, values)):
            self.assertEqual(
                len(self.d),
                i,
            )

            self.d[k] = v
            self.assertEqual(
                self.d[k],
                v,
            )

            self.assertEqual(
                len(self.d),
                i + 1,
            )

        for k, v in zip(keys, values):
            self.assertEqual(
                self.d[k],
                v,
            )

    def test_iter_iterates_over_keys(self):
        size = 3
        self.d.maxsize = size
        keys = [object() for i in range(size)]
        values = [object() for i in range(size)]

        for k, v in zip(keys, values):
            self.d[k] = v
            self.assertEqual(
                self.d[k],
                v,
            )

        self.assertSetEqual(
            set(self.d),
            set(keys),
        )

    def test_maxsize_can_be_written(self):
        self.d.maxsize = 4
        self.assertEqual(self.d.maxsize, 4)

    def test_maxsize_rejects_non_positive_integers(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            self.d.maxsize = 0

        with self.assertRaisesRegex(ValueError, "must be positive"):
            self.d.maxsize = -1

    def test_maxsize_accepts_None(self):
        self.d.maxsize = None
        self.assertIsNone(self.d.maxsize)

    def test_fetch_does_not_create_ghost_keys(self):
        with self.assertRaises(KeyError):
            self.d[object()]
        self.d[object()] = object()

        # "ghost key": if one part of the data structure (the "last used") is
        # updated before the check for existance of the key is made
        # in this case, the second store would raise because there is a key
        # in the "last used" data structure which isn’t in the main data
        # structure
        self.d[object()] = object()

    def test_lru_purge_when_decreasing_maxsize(self):
        size = 4
        self.d.maxsize = size
        keys = [object() for i in range(size)]
        values = [object() for i in range(size)]

        for k, v in zip(keys, values):
            self.d[k] = v
            self.assertEqual(
                self.d[k],
                v,
            )

        # keys have now been fetached in insertion order
        # reducing maxsize by one should remove first key, but not the others

        self.d.maxsize = size - 1

        with self.assertRaises(KeyError):
            self.d[keys[0]]

        # we now fetch the second key, so that the third is purged instead of
        # the second when we reduce maxsize again

        self.d[keys[1]]

        self.d.maxsize = size - 2

        with self.assertRaises(KeyError):
            self.d[keys[2]]

        self.assertEqual(
            self.d[keys[1]],
            values[1]
        )

        # reducing the size to 1 should leave only the third key

        self.d.maxsize = 1

        self.assertEqual(
            self.d[keys[1]],
            values[1]
        )

        for i in [0, 2, 3]:
            with self.assertRaises(KeyError):
                self.d[keys[i]]

    def test_lru_purge_when_storing(self):
        size = 4
        self.d.maxsize = size
        keys = [object() for i in range(size + 2)]
        values = [object() for i in range(size + 2)]

        for k, v in zip(keys[:size], values[:size]):
            self.d[k] = v
            self.assertEqual(
                self.d[k],
                v,
            )

        # keys have now been fetached in insertion order
        # reducing maxsize by one should remove first key, but not the others

        self.d[keys[size]] = values[size]

        with self.assertRaises(KeyError):
            self.d[keys[0]]

        # we now fetch the second key, so that the third is purged instead of
        # the second when we reduce maxsize again

        self.d[keys[2]]

        self.d[keys[size + 1]] = values[size + 1]

        with self.assertRaises(KeyError):
            self.d[keys[1]]

        self.assertEqual(
            self.d[keys[2]],
            values[2]
        )

        for i in [0, 1]:
            with self.assertRaises(KeyError, msg=i):
                self.d[keys[i]]

        for i in [2, 3, 4, 5]:
            self.assertEqual(
                self.d[keys[i]],
                values[i],
            )

    def test_expire_removes_from_cache(self):
        key = object()
        value = object()
        self.d[key] = value

        del self.d[key]

        with self.assertRaises(KeyError):
            self.d[key]

        self.d[object()] = value
        self.d[object()] = value
