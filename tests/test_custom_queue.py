########################################################################
# File name: test_custom_queue.py
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
import unittest

import aioxmpp.custom_queue as custom_queue

from aioxmpp.testutils import run_coroutine


class TestAsyncDeque(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.q = custom_queue.AsyncDeque(loop=self.loop)

    def test_put_get_cycle_nowait(self):
        self.q.put_nowait(1)
        self.q.put_nowait(2)
        self.q.put_nowait(3)

        self.assertEqual(
            1,
            self.q.get_nowait()
        )
        self.assertEqual(
            2,
            self.q.get_nowait()
        )
        self.assertEqual(
            3,
            self.q.get_nowait()
        )

    def test_putleft_getright_cycle_nowait(self):
        self.q.putleft_nowait(1)
        self.q.putleft_nowait(2)
        self.q.putleft_nowait(3)

        self.assertEqual(
            1,
            self.q.getright_nowait()
        )
        self.assertEqual(
            2,
            self.q.getright_nowait()
        )
        self.assertEqual(
            3,
            self.q.getright_nowait()
        )

    def test_len(self):
        self.assertEqual(0, len(self.q))
        self.q.put_nowait(1)
        self.assertEqual(1, len(self.q))
        self.q.put_nowait(1)
        self.assertEqual(2, len(self.q))
        self.q.get_nowait()
        self.assertEqual(1, len(self.q))

    def test_contains(self):
        self.assertNotIn(1, self.q)
        self.q.put_nowait(1)
        self.assertIn(1, self.q)

    def test_get(self):
        @asyncio.coroutine
        def putter():
            yield from asyncio.sleep(0.001)
            self.q.put_nowait(1)

        _, v = run_coroutine(asyncio.gather(
            putter(),
            self.q.get()
        ))

        self.assertEqual(1, v)

    def test_one_producer_many_consumers(self):
        @asyncio.coroutine
        def putter():
            for i in range(20):
                self.q.put_nowait(i)
                yield from asyncio.sleep(0)

        @asyncio.coroutine
        def getter():
            result = []
            for i in range(4):
                result.append((yield from self.q.get()))
                yield from asyncio.sleep(0)
            return result

        _, vs1, vs2, vs3, vs4, vs5 = run_coroutine(asyncio.gather(
            putter(),
            getter(),
            getter(),
            getter(),
            getter(),
            getter(),
        ))

        self.assertSequenceEqual(
            range(20),
            sorted(vs1 + vs2 + vs3 + vs4 + vs5)
        )

    def test_one_consumer_many_producers(self):
        @asyncio.coroutine
        def putter(n0):
            for i in range(n0, n0 + 4):
                self.q.put_nowait(i)
                yield from asyncio.sleep(0)

        @asyncio.coroutine
        def getter():
            result = []
            for i in range(20):
                result.append((yield from self.q.get()))
                yield from asyncio.sleep(0)
            return result

        _, _, _, _, _, vs = run_coroutine(asyncio.gather(
            putter(0),
            putter(4),
            putter(8),
            putter(12),
            putter(16),
            getter()
        ))

        self.assertSequenceEqual(
            range(20),
            sorted(vs)
        )

    def test_empty(self):
        self.assertTrue(self.q.empty())
        self.q.put_nowait(1)
        self.assertFalse(self.q.empty())
        self.q.get_nowait()
        self.assertTrue(self.q.empty())

    def test_raise_asyncio_QueueEmpty_on_empty_get(self):
        with self.assertRaises(asyncio.QueueEmpty):
            self.q.get_nowait()

        with self.assertRaises(asyncio.QueueEmpty):
            self.q.getright_nowait()

    def test_clear(self):
        self.q.put_nowait(1)
        self.q.put_nowait(2)
        self.q.clear()
        self.assertTrue(self.q.empty())
        with self.assertRaises(asyncio.QueueEmpty):
            self.q.get_nowait()

    def tearDown(self):
        del self.q
        del self.loop
