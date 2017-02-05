########################################################################
# File name: test_tasks.py
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
import contextlib
import unittest
import unittest.mock

import aioxmpp.tasks as tasks

from aioxmpp.testutils import CoroutineMock


@asyncio.coroutine
def _infinite_loop():
    while True:
        yield from asyncio.sleep(1)


class TestTaskPool(unittest.TestCase):
    def setUp(self):
        self.p = tasks.TaskPool()

    def tearDown(self):
        del self.p

    def test_defaults(self):
        self.assertIsNone(self.p.get_limit(()))
        self.assertIsNone(self.p.default_limit)

    def test_max_tasks_sets_limit_on_empty_tuple(self):
        p = tasks.TaskPool(max_tasks=10)
        self.assertEqual(
            p.get_limit(()),
            10,
        )

    def test_set_limit(self):
        self.p.set_limit(("foo", "bar"), 2)
        self.assertEqual(self.p.get_limit(("foo", "bar")), 2)
        self.assertIsNone(self.p.get_limit(()))
        self.assertIsNone(self.p.get_limit(("fnord",)))
        self.assertIsNone(self.p.get_limit(("foo",)))

    def test_set_limit_is_idempotent(self):
        self.p.set_limit(("foo", "bar"), 2)
        self.p.set_limit(("foo", "bar"), 2)
        self.assertEqual(self.p.get_limit(("foo", "bar")), 2)

    def test_clear_limit(self):
        self.p.set_limit(("foo", "bar"), 2)
        self.p.clear_limit(("foo", "bar"))
        self.assertIsNone(self.p.get_limit(("foo", "bar")))

    def test_clear_limit_is_idempotent(self):
        self.p.set_limit(("foo", "bar"), 2)
        self.p.clear_limit(("foo", "bar"))
        self.p.clear_limit(("foo", "bar"))
        self.assertIsNone(self.p.get_limit(("foo", "bar")))

    def test_set_limit_with_none_behaves_like_clear_limit(self):
        self.p.set_limit(("foo", "bar"), 2)
        self.p.set_limit(("foo", "bar"), None)
        self.assertIsNone(self.p.get_limit(("foo", "bar")))
        self.p.clear_limit(("foo", "bar"))
        self.assertIsNone(self.p.get_limit(("foo", "bar")))

    def test_empty_groups_have_zero_tasks(self):
        self.assertEqual(self.p.get_task_count(()), 0)
        self.assertEqual(self.p.get_task_count(("foo",)), 0)
        self.assertEqual(self.p.get_task_count(("foo", "bar")), 0)

    def test_spawn_starts_coroutine_and_returns_task(self):
        coro_fun = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            async_ = stack.enter_context(
                unittest.mock.patch(
                    "asyncio.async"
                )
            )

            result = self.p.spawn(
                set(), coro_fun, 1, 2, groups="foo", coro_fun="bar"
            )

        coro_fun.assert_called_once_with(
            1, 2,
            groups="foo",
            coro_fun="bar",
        )

        async_.assert_called_once_with(
            coro_fun()
        )

        self.assertEqual(
            result,
            async_()
        )

    def test_spawn_accounting(self):
        coro_fun = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            async_ = stack.enter_context(
                unittest.mock.patch(
                    "asyncio.async"
                )
            )

            result = self.p.spawn(
                set(), coro_fun, 1, 2, groups="foo", coro_fun="bar"
            )

        coro_fun.assert_called_once_with(
            1, 2,
            groups="foo",
            coro_fun="bar",
        )

        async_.assert_called_once_with(
            coro_fun()
        )

        self.assertEqual(
            result,
            async_()
        )

    def test_spawn_respects_global_limit(self):
        self.p.set_limit((), 0)
        coro_fun = unittest.mock.Mock()

        with self.assertRaisesRegex(
                RuntimeError,
                "maximum number of tasks in group '\(\)' exhausted"):
            self.p.spawn(set(), coro_fun)
