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
import io
import unittest
import random

import aioxmpp.cache

from aioxmpp.benchtest import times, timed, record

class TestLRUDict(unittest.TestCase):
    KEY = "aioxmpp.cache", "LRUDict"

    @times(1000)
    def test_random_access(self):
        key = self.KEY + ("random_access",)

        N = 1000

        lru_dict = aioxmpp.cache.LRUDict()
        lru_dict.maxsize = N
        keys = [object() for i in range(N)]
        for i in range(N):
            lru_dict[keys[i]] = object()

        with timed() as t:
            for i in range(N):
                lru_dict[keys[random.randrange(0, N)]]

        record(key, t.elapsed, "s")

    @times(1000)
    def test_inserts(self):
        key = self.KEY + ("inserts",)

        N = 1000

        lru_dict = aioxmpp.cache.LRUDict()
        lru_dict.maxsize = N
        keys = [object() for i in range(N)]
        for i in range(N):
            lru_dict[keys[i]] = object()

        with timed() as t:
            for i in range(N):
                lru_dict[object()] = object()

        record(key, t.elapsed, "s")
