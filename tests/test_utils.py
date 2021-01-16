########################################################################
# File name: test_utils.py
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
import types
import sys
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp.errors as errors
import aioxmpp.utils as utils

from aioxmpp.testutils import (
    CoroutineMock,
    get_timeout,
    run_coroutine,
    make_listener,
)


class Testnamespaces(unittest.TestCase):
    def test_aioxmpp(self):
        self.assertEqual(
            utils.namespaces.aioxmpp_internal,
            "https://zombofant.net/xmlns/aioxmpp#internal"
        )

    def test_namespaces_is_Namespaces_instance(self):
        self.assertIsInstance(
            utils.namespaces,
            utils.Namespaces
        )


class TestNamespaces(unittest.TestCase):
    def setUp(self):
        self.namespaces = utils.Namespaces()
        self.namespaces.aioxmpp_internal = \
            "https://zombofant.net/xmlns/aioxmpp#internal"

    def tearDown(self):
        del self.namespaces

    def test_aioxmpp(self):
        self.assertEqual(
            self.namespaces.aioxmpp_internal,
            "https://zombofant.net/xmlns/aioxmpp#internal"
        )

    def test_inconsistent_rebinding_errors(self):
        with self.assertRaisesRegex(ValueError,
                                    "^inconsistent namespace redefinition$"):
            self.namespaces.aioxmpp_internal = "fnord"

    def test_allow_consistent_rebinding(self):
        self.namespaces.aioxmpp_internal = \
            "https://zombofant.net/xmlns/aioxmpp#internal"

    def test_deleting_is_prohibited(self):
        with self.assertRaisesRegex(AttributeError,
                                    "^deleting short-hands is prohibited$"):
            del self.namespaces.aioxmpp_internal

    def test_namespace_redefinition_errors(self):
        with self.assertRaisesRegex(
                ValueError,
                "^namespace https://zombofant.net/xmlns/aioxmpp#internal"
                " already defined as aioxmpp_internal$"):
            self.namespaces.aioxmpp_internal_clash = \
                "https://zombofant.net/xmlns/aioxmpp#internal"


class Testbackground_task(unittest.TestCase):
    def setUp(self):
        self.coro = CoroutineMock()
        self.coro.return_value = None
        self.started_coro = self.coro()
        self.logger = unittest.mock.Mock()
        self.cm = utils.background_task(
            self.started_coro,
            self.logger,
        )

    def tearDown(self):
        try:
            self.cm.__exit__(None, None, None)
        except:
            pass
        del self.cm
        del self.logger
        del self.coro

    def test_enter_starts_coroutine(self):
        with unittest.mock.patch("asyncio.ensure_future") as async_:
            self.cm.__enter__()

        async_.assert_called_with(self.started_coro)
        self.assertFalse(async_().cancel.mock_calls)

    def test_exit_cancels_coroutine(self):
        with unittest.mock.patch("asyncio.ensure_future") as async_:
            self.cm.__enter__()
            self.cm.__exit__(None, None, None)

        async_().cancel.assert_called_with()

    def test_exit_with_exc_cancels_coroutine_and_propagates(self):
        try:
            raise ValueError()
        except:
            exc_info = sys.exc_info()

        with unittest.mock.patch("asyncio.ensure_future") as async_:
            self.cm.__enter__()
            result = self.cm.__exit__(*exc_info)

        self.assertFalse(result)
        async_().cancel.assert_called_with()

    async def _long_wrapper(self):
        with self.cm:
            await asyncio.sleep(0.1)

    def test_logs_nothing_when_coroutine_terminates_normally(self):
        run_coroutine(self._long_wrapper())
        self.assertFalse(self.logger.mock_calls)

    def test_logs_error_when_coroutine_raises(self):
        async def failing():
            raise ValueError()

        self.cm = utils.background_task(failing(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.error.assert_called_with(
            "background task failed: %r",
            unittest.mock.ANY,
            exc_info=True,
        )

    def test_logs_debug_when_coroutine_cancelled(self):
        async def too_long():
            await asyncio.sleep(10)

        self.cm = utils.background_task(too_long(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.debug.assert_called_with(
            "background task terminated by CM exit: %r",
            unittest.mock.ANY,
        )

    def test_logs_info_when_coroutine_returns_value(self):
        async def something():
            return unittest.mock.sentinel.result

        self.cm = utils.background_task(something(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.info.assert_called_with(
            "background task (%r) returned a value: %r",
            unittest.mock.ANY,
            unittest.mock.sentinel.result,
        )


class Testmagicmethod(unittest.TestCase):
    def test_invoke_on_class(self):
        m = unittest.mock.Mock()

        class Foo:
            @utils.magicmethod
            def foo(self_or_cls, *args, **kwargs):
                return m(self_or_cls, *args, **kwargs)

        result = Foo.foo(unittest.mock.sentinel.a1,
                         unittest.mock.sentinel.a2,
                         a=unittest.mock.sentinel.a3)

        m.assert_called_once_with(
            Foo,
            unittest.mock.sentinel.a1,
            unittest.mock.sentinel.a2,
            a=unittest.mock.sentinel.a3,
        )

        self.assertEqual(result, m())

    def test_invoke_on_object(self):
        m = unittest.mock.Mock()

        class Foo:
            @utils.magicmethod
            def foo(self_or_cls, *args, **kwargs):
                return m(self_or_cls, *args, **kwargs)

        instance = Foo()
        result = instance.foo(unittest.mock.sentinel.a1,
                              unittest.mock.sentinel.a2,
                              a=unittest.mock.sentinel.a3)

        m.assert_called_once_with(
            instance,
            unittest.mock.sentinel.a1,
            unittest.mock.sentinel.a2,
            a=unittest.mock.sentinel.a3,
        )

        self.assertEqual(result, m())

    def test_instance_method_is_instance_method(self):
        class Foo:
            @utils.magicmethod
            def foo(self_or_cls, *args, **kwargs):
                pass

        self.assertIsInstance(
            Foo().foo,
            types.MethodType
        )

    def test_class_method_is_also_method(self):
        class Foo:
            @utils.magicmethod
            def foo(self_or_cls, *args, **kwargs):
                pass

        self.assertIsInstance(
            Foo.foo,
            types.MethodType
        )

    def test_magicmethod_can_be_overridden(self):
        class Foo:
            @utils.magicmethod
            def foo(self_or_cls, *args, **kwargs):
                pass

        o = Foo()
        o.foo = "bar"
        self.assertEqual(o.foo, "bar")


class Testmkdir_exist_ok(unittest.TestCase):
    def test_successful_mkdir(self):
        p = unittest.mock.Mock()
        utils.mkdir_exist_ok(p)
        self.assertSequenceEqual(
            p.mock_calls,
            [
                unittest.mock.call.mkdir(parents=True),
            ]
        )

    def test_mkdir_exists_but_is_directory(self):
        p = unittest.mock.Mock()
        p.is_dir.return_value = True
        p.mkdir.side_effect = FileExistsError()
        utils.mkdir_exist_ok(p)
        self.assertSequenceEqual(
            p.mock_calls,
            [
                unittest.mock.call.mkdir(parents=True),
                unittest.mock.call.is_dir()
            ]
        )

    def test_mkdir_exists_but_is_not_directory(self):
        p = unittest.mock.Mock()
        p.is_dir.return_value = False
        exc = FileExistsError()
        p.mkdir.side_effect = exc
        with self.assertRaises(FileExistsError) as ctx:
            utils.mkdir_exist_ok(p)

        self.assertIs(ctx.exception, exc)

        self.assertSequenceEqual(
            p.mock_calls,
            [
                unittest.mock.call.mkdir(parents=True),
                unittest.mock.call.is_dir()
            ]
        )


class TestLazyTask(unittest.TestCase):
    def setUp(self):
        self.coro = CoroutineMock()

    def test_yield_from_able(self):
        self.coro.return_value = unittest.mock.sentinel.result

        async def user(fut):
            return await fut

        fut = utils.LazyTask(self.coro)

        result = run_coroutine(user(fut))

        self.assertEqual(result, unittest.mock.sentinel.result)

    def test_run_coroutine_able(self):
        self.coro.return_value = unittest.mock.sentinel.result

        fut = utils.LazyTask(self.coro)

        result = run_coroutine(fut)

        self.assertEqual(result, unittest.mock.sentinel.result)

    def test_async_able(self):
        self.coro.return_value = unittest.mock.sentinel.result

        fut = utils.LazyTask(self.coro)

        result = run_coroutine(asyncio.ensure_future(fut))

        self.assertEqual(result, unittest.mock.sentinel.result)

    def test_runs_only_once_even_if_awaited_concurrently(self):
        self.coro.return_value = unittest.mock.sentinel.result

        fut = utils.LazyTask(self.coro)

        result2 = run_coroutine(asyncio.ensure_future(fut))
        result1 = run_coroutine(fut)

        self.assertEqual(result1, result2)
        self.assertEqual(result1, unittest.mock.sentinel.result)

        self.coro.assert_called_once_with()

    def test_add_done_callback_spawns_task(self):
        fut = utils.LazyTask(self.coro)
        cb = unittest.mock.Mock(["__call__"])

        with unittest.mock.patch("asyncio.ensure_future") as async_:
            fut.add_done_callback(cb)
            async_.assert_called_once_with(unittest.mock.ANY)

    def test_add_done_callback_works(self):
        fut = utils.LazyTask(self.coro)
        cb = unittest.mock.Mock(["__call__"])

        fut.add_done_callback(cb)

        run_coroutine(fut)

        cb.assert_called_once_with(fut)

    def test_is_future(self):
        self.assertTrue(issubclass(
            utils.LazyTask,
            asyncio.Future,
        ))

    def test_passes_args(self):
        self.coro.return_value = unittest.mock.sentinel.result

        fut = utils.LazyTask(
            self.coro,
            unittest.mock.sentinel.a1,
            unittest.mock.sentinel.a2,
            unittest.mock.sentinel.a3,
        )

        result = run_coroutine(fut)

        self.assertEqual(result, unittest.mock.sentinel.result)

        self.coro.assert_called_once_with(
            unittest.mock.sentinel.a1,
            unittest.mock.sentinel.a2,
            unittest.mock.sentinel.a3,
        )


class Testgather_reraise_multi(unittest.TestCase):

    def test_with_empty_list(self):
        self.assertEqual(
            run_coroutine(utils.gather_reraise_multi()),
            []
        )

    def test_with_one_successful_task(self):
        async def foo():
            return True

        self.assertEqual(
            run_coroutine(utils.gather_reraise_multi(foo())),
            [True]
        )

    def test_with_one_failing_task(self):
        async def foo():
            raise RuntimeError

        try:
            run_coroutine(utils.gather_reraise_multi(foo()))
        except errors.GatherError as e:
            self.assertIs(type(e.exceptions[0]), RuntimeError)
        else:
            self.fail()


    def test_with_two_successful_tasks(self):
        async def foo():
            return True

        async def bar():
            return False

        self.assertEqual(
            run_coroutine(utils.gather_reraise_multi(foo(), bar())),
            [True, False]
        )

    def test_with_two_tasks_one_failing(self):
        async def foo():
            raise RuntimeError

        async def bar():
            return False

        try:
            run_coroutine(utils.gather_reraise_multi(foo(), bar()))
        except errors.GatherError as e:
            self.assertIs(type(e.exceptions[0]), RuntimeError)
        else:
            self.fail()

    def test_with_two_tasks_both_failing(self):
        async def foo():
            raise RuntimeError

        async def bar():
            raise Exception

        try:
            run_coroutine(utils.gather_reraise_multi(foo(), bar()))
        except errors.GatherError as e:
            self.assertIs(type(e.exceptions[0]), RuntimeError)
            self.assertIs(type(e.exceptions[1]), Exception)
        else:
            self.fail()


class Test_to_nmtoken(unittest.TestCase):

    def test_unique_integers(self):
        results = set()
        for i in range(2048):
            res = utils.to_nmtoken(i)
            if res in results:
                self.fail("generated tokens not unique")
            results.add(res)

    def test_integers_and_bytes_do_not_collide(self):
        a = utils.to_nmtoken(255)
        b = utils.to_nmtoken(b"\xff")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith(":"))
        self.assertFalse(b.startswith(":"))

    def test_zero_extension(self):
        a = utils.to_nmtoken(b"\xff\x00")
        b = utils.to_nmtoken(b"\xff")
        self.assertNotEqual(a, b)


class TestAlivenessMonitor(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.am = utils.AlivenessMonitor(self.loop)
        self.listener = make_listener(self.am)

    def tearDown(self):
        del self.am
        del self.loop

    def test_defaults(self):
        self.assertIsNone(self.am.deadtime_soft_limit)
        self.assertIsNone(self.am.deadtime_hard_limit)

    def test_soft_limit_settable(self):
        self.am.deadtime_soft_limit = timedelta(seconds=1)

        self.assertEqual(self.am.deadtime_soft_limit, timedelta(seconds=1))

    def test_hard_limit_is_settable(self):
        self.am.deadtime_hard_limit = timedelta(seconds=1)

        self.assertEqual(self.am.deadtime_hard_limit, timedelta(seconds=1))

    def test_soft_limit_trips(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_notify_received_resets_soft_limit_timer(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()

    def test_changing_soft_limit_recaluclates_timer(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()

        self.am.deadtime_soft_limit = dt*1.5

        run_coroutine(asyncio.sleep((dt * 0.5).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_soft_timer_fires_even_without_any_reception(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_hard_limit_trips(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

    def test_notify_received_resets_hard_limit_timer(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

    def test_changing_hard_limit_recaluclates_timer(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        self.am.deadtime_hard_limit = dt*1.5

        run_coroutine(asyncio.sleep((dt * 0.5).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

    def test_hard_timer_fires_even_without_any_reception(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

    def test_both_trip(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.deadtime_hard_limit = dt * 1.5
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt * 0.9).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()
        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.2).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()
        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()

        run_coroutine(asyncio.sleep((dt * 0.4).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()
        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

    def test_changing_soft_limit_may_emit_limit_immediately(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()
        self.am.deadtime_soft_limit = dt

        run_coroutine(asyncio.sleep(0))
        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_changing_soft_limit_does_not_reemit_hard_limit(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()
        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

        self.am.deadtime_soft_limit = dt * 1.5

        run_coroutine(asyncio.sleep(0))
        self.listener.on_deadtime_soft_limit_tripped.assert_not_called()
        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()

    def test_changing_hard_limit_does_not_reemit_soft_limit(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()
        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

        self.am.deadtime_hard_limit = dt * 1.5

        run_coroutine(asyncio.sleep(0))
        self.listener.on_deadtime_hard_limit_tripped.assert_not_called()
        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_soft_limit_can_reemit_after_reception(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_soft_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))

        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()
        self.am.notify_received()
        self.listener.on_deadtime_soft_limit_tripped.reset_mock()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))
        self.listener.on_deadtime_soft_limit_tripped.assert_called_once_with()

    def test_hard_limit_can_reemit_after_reception(self):
        dt = get_timeout(timedelta(seconds=0.1))

        self.am.deadtime_hard_limit = dt
        self.am.notify_received()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))

        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()
        self.am.notify_received()
        self.listener.on_deadtime_hard_limit_tripped.reset_mock()

        run_coroutine(asyncio.sleep((dt*1.1).total_seconds()))
        self.listener.on_deadtime_hard_limit_tripped.assert_called_once_with()


class Testproxy_property(unittest.TestCase):
    def setUp(self):
        self.obj = unittest.mock.Mock(["member"])
        self.obj.member = unittest.mock.Mock(["attr"])
        self.pp = utils.proxy_property("member", "attr")

    def test_forwards_reads(self):
        self.assertEqual(
            self.pp.__get__(self.obj, unittest.mock.sentinel.type_),
            self.obj.member.attr
        )

    def test_forwards_writes(self):
        self.obj.member.attr = unittest.mock.sentinel.old_value

        self.pp.__set__(self.obj, unittest.mock.sentinel.value)

        self.assertEqual(
            self.obj.member.attr,
            unittest.mock.sentinel.value,
        )

    def test_rejects_deletes_by_default(self):
        self.assertTrue(hasattr(self.obj.member, "attr"))

        with self.assertRaisesRegex(AttributeError, "can't delete attribute"):
            self.pp.__delete__(self.obj)

        self.assertTrue(hasattr(self.obj.member, "attr"))

    def test_rejects_writes_if_readonly(self):
        self.obj.member.attr = unittest.mock.sentinel.old_value

        pp = utils.proxy_property("member", "attr", readonly=True)

        with self.assertRaisesRegex(AttributeError, "can't set attribute"):
            pp.__set__(self.obj, unittest.mock.sentinel.value)

        self.assertEqual(
            self.obj.member.attr,
            unittest.mock.sentinel.old_value
        )

    def test_forwards_delete_if_enabled(self):
        self.assertTrue(hasattr(self.obj.member, "attr"))

        pp = utils.proxy_property("member", "attr", allow_delete=True)

        pp.__delete__(self.obj)

        self.assertFalse(hasattr(self.obj.member, "attr"))
