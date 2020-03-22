########################################################################
# File name: test_self_ping.py
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
import logging
import random
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp.callbacks
import aioxmpp.errors
import aioxmpp.utils
import aioxmpp.muc.self_ping as self_ping

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
    get_timeout,
)


class Test_apply_jitter(unittest.TestCase):
    def test_uses_and_scales_random_upper_end(self):
        v = random.random() * 100

        with contextlib.ExitStack() as stack:
            random_ = stack.enter_context(unittest.mock.patch(
                "random.random"
            ))

            random_.return_value = 1.

            result = self_ping._apply_jitter(
                v,
                0.2,
            )

        self.assertEqual(result, v * 1.2)

    def test_uses_and_scales_random_lower_end(self):
        v = random.random() * 100

        with contextlib.ExitStack() as stack:
            random_ = stack.enter_context(unittest.mock.patch(
                "random.random"
            ))

            random_.return_value = 0.

            result = self_ping._apply_jitter(
                v,
                0.2,
            )

        self.assertEqual(result, v * 0.8)


class TestMUCPinger(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.listener = unittest.mock.Mock()
        self.loop = asyncio.get_event_loop()
        self.logger = logging.getLogger(".".join([type(self).__module__,
                                                  type(self).__qualname__]))
        self.p = self_ping.MUCPinger(
            unittest.mock.sentinel.ping_address,
            self.cc,
            self.listener.on_fresh,
            self.listener.on_exited,
            self.logger,
            self.loop,
        )

        def no_jitter(v, amplitude):
            return v

        self.jitter_mock = unittest.mock.Mock(side_effect=no_jitter)

        self.jitter_patch = unittest.mock.patch(
            "aioxmpp.muc.self_ping._apply_jitter",
            new=self.jitter_mock,
        )
        self.jitter_patch.start()

    def tearDown(self):
        self.p.stop()
        self.jitter_patch.stop()
        del self.p

    def _require_task_running(self):
        self.assertIsNotNone(self.p._task)
        if self.p._task.done():
            # if done, try to fetch the result, this’ll re-raise the exception
            self.p._task.result()
        self.assertFalse(self.p._task.done())

    def test_emits_no_events_on_construction(self):
        self.assertSequenceEqual(self.listener.mock_calls, [])

    def test_start_starts_the_pinger_coroutine(self):
        with contextlib.ExitStack() as stack:
            ensure_future = stack.enter_context(unittest.mock.patch(
                "asyncio.ensure_future",
            ))
            stack.enter_context(unittest.mock.patch.object(
                self.p,
                "_pinger",
                new=unittest.mock.Mock(
                    return_value=unittest.mock.sentinel.pinger_coro,
                ),
            ))

            self.p.start()

        ensure_future.assert_called_once_with(
            unittest.mock.sentinel.pinger_coro,
            loop=self.loop,
        )

    def test_stop_cancels_pinger_task(self):
        task = unittest.mock.Mock(["cancel"])

        with contextlib.ExitStack() as stack:
            ensure_future = stack.enter_context(unittest.mock.patch(
                "asyncio.ensure_future",
                return_value=task,
            ))
            stack.enter_context(unittest.mock.patch.object(
                self.p,
                "_pinger",
                new=unittest.mock.Mock(
                    return_value=unittest.mock.sentinel.pinger_coro,
                ),
            ))

            self.p.start()

        task.cancel.assert_not_called()

        self.p.stop()
        task.cancel.assert_called_once_with()

    def test_stop_does_not_cancel_task_twice(self):
        task = unittest.mock.Mock(["cancel"])

        with contextlib.ExitStack() as stack:
            ensure_future = stack.enter_context(unittest.mock.patch(
                "asyncio.ensure_future",
                return_value=task,
            ))
            stack.enter_context(unittest.mock.patch.object(
                self.p,
                "_pinger",
                new=unittest.mock.Mock(
                    return_value=unittest.mock.sentinel.pinger_coro,
                ),
            ))

            self.p.start()

        task.cancel.assert_not_called()

        self.p.stop()
        task.cancel.assert_called_once_with()
        task.cancel.reset_mock()

        self.p.stop()
        task.cancel.assert_not_called()

    def test_start_cancels_existing_task_before_starting(self):
        task = unittest.mock.Mock(["cancel"])

        def check_task(*args, **kwargs):
            task.cancel.assert_called_once_with()
            return unittest.mock.Mock(["cancel"])

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.p,
                "_pinger",
                new=unittest.mock.Mock(
                    return_value=unittest.mock.sentinel.pinger_coro,
                ),
            ))

            stack.enter_context(unittest.mock.patch(
                "asyncio.ensure_future",
                return_value=task,
            ))

            self.p.start()

            ensure_future = stack.enter_context(unittest.mock.patch(
                "asyncio.ensure_future",
                side_effect=check_task,
            ))

            self.p.start()

        ensure_future.assert_called_once_with(
            unittest.mock.sentinel.pinger_coro,
            loop=self.loop,
        )

    def test_pinger_emits_ping_right_away(self):
        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(0))
            self._require_task_running()

        ping.assert_called_once_with(
            self.cc,
            unittest.mock.sentinel.ping_address,
        )

    def test_pinger_emits_ping_every_ping_interval(self):
        timeout = get_timeout(0.1)

        self.p.ping_interval = timedelta(seconds=timeout)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(timeout / 2))

            for i in range(5):
                self._require_task_running()
                ping.assert_called_once_with(
                    self.cc,
                    unittest.mock.sentinel.ping_address
                )
                ping.reset_mock()
                run_coroutine(asyncio.sleep(timeout))

    def test_pinger_uses_jitter_to_calculate_next(self):
        timeout = get_timeout(0.1)

        self.p.ping_interval = timedelta(seconds=timeout)
        self.jitter_mock.return_value = timeout*2
        self.jitter_mock.side_effect = None

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(timeout / 2))

            self._require_task_running()
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address
            )
            ping.reset_mock()

            run_coroutine(asyncio.sleep(timeout * 2))

            self._require_task_running()
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address
            )
            ping.reset_mock()

    def test_pinger_cancels_after_ping_timeout(self):
        interval = get_timeout(0.1)
        timeout = get_timeout(0.4)

        futures = []

        def ping_func(*args, **kwargs):
            fut = asyncio.Future()
            futures.append(fut)
            return fut

        self.p.ping_interval = timedelta(seconds=interval)
        self.p.ping_timeout = timedelta(seconds=timeout)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=unittest.mock.Mock(
                    side_effect=ping_func,
                ),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(interval / 2))

            # we check that, at any time, at most four futures
            # (timeout/interval) are not cancelled
            for i in range(10):
                self._require_task_running()
                ping.assert_called_once_with(
                    self.cc,
                    unittest.mock.sentinel.ping_address
                )
                ping.reset_mock()
                self.assertLessEqual(
                    sum(not fut.done() for fut in futures),
                    4,
                )
                run_coroutine(asyncio.sleep(interval))

    def test_pinger_cancels_futures_on_cancel(self):
        interval = get_timeout(0.1)

        futures = []

        def ping(*args, **kwargs):
            fut = asyncio.Future()
            futures.append(fut)
            return fut

        self.p.ping_interval = timedelta(seconds=interval)
        self.p.ping_timeout = timedelta(seconds=interval*10)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=unittest.mock.Mock(
                    side_effect=ping,
                ),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(interval / 2))

            # we check that, at any time, at most four futures
            # (timeout/interval) are not cancelled
            for i in range(5):
                self._require_task_running()
                run_coroutine(asyncio.sleep(interval))

        self.p.stop()
        run_coroutine(asyncio.sleep(interval / 2))

        self.assertTrue(all(fut.done() for fut in futures))

    def test_pinger_picks_up_on_address_change(self):
        interval = get_timeout(0.1)

        self.p.ping_interval = timedelta(seconds=interval)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(interval / 2))

            self._require_task_running()
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address
            )
            ping.reset_mock()

            self.p.ping_address = unittest.mock.sentinel.ping_address2
            run_coroutine(asyncio.sleep(interval))
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address2,
            )

    def test_pinger_picks_up_on_interval_change(self):
        interval = get_timeout(0.1)
        interval2 = get_timeout(0.3)

        self.p.ping_interval = timedelta(seconds=interval)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(interval / 2))

            self._require_task_running()
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address
            )
            ping.reset_mock()

            self.p.ping_interval = timedelta(seconds=interval2)

            import time
            run_coroutine(asyncio.sleep(interval2))
            self._require_task_running()
            print(time.monotonic(), "slept")
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address,
            )
            ping.reset_mock()

    def test_pinger_picks_up_on_timeout_change(self):
        interval = get_timeout(0.3)
        timeout = get_timeout(0.3)

        futures = []

        def ping_func(*args, **kwargs):
            fut = asyncio.Future()
            futures.append(fut)
            return fut

        self.p.ping_interval = timedelta(seconds=interval)
        self.p.ping_timeout = timedelta(seconds=interval*10)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=unittest.mock.Mock(
                    side_effect=ping_func,
                ),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(interval / 2))

            self._require_task_running()
            ping.assert_called_once_with(
                self.cc,
                unittest.mock.sentinel.ping_address
            )
            ping.reset_mock()

            self.p.ping_timeout = timedelta(seconds=timeout)

            run_coroutine(asyncio.sleep(interval))
            self._require_task_running()

            self.assertEqual(len(futures), 2)

            run_coroutine(asyncio.sleep(interval))
            self._require_task_running()

            self.assertEqual(len(futures), 3)

            run_coroutine(asyncio.sleep(interval / 2))

        self.assertFalse(futures[0].done())
        self.assertTrue(futures[1].done())
        self.assertTrue(futures[2].done())

    def test_pinger_calls__interpret_result_for_finished_pings(self):
        interval = get_timeout(0.1)
        timeout = get_timeout(0.16)

        modes = [
            False,
            None,
            RuntimeError(),
        ]

        futures = []
        mode_i = 0

        def ping_func(*args, **kwargs):
            def make_fut():
                fut = asyncio.Future()
                futures.append(fut)
                return fut

            nonlocal mode_i

            mode = modes[mode_i]
            mode_i += 1

            fut = make_fut()
            if mode is None:
                fut.set_result(unittest.mock.sentinel.some_result)
            elif mode is False:
                pass
            else:
                fut.set_exception(mode)
            return fut

        self.p.ping_interval = timedelta(seconds=interval)
        self.p.ping_timeout = timedelta(seconds=timeout)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=unittest.mock.Mock(
                    side_effect=ping_func,
                ),
            ))

            _interpret_result = stack.enter_context(unittest.mock.patch.object(
                self.p,
                "_interpret_result"
            ))

            self.p.start()

            logging.debug("test: sleeping for %s", interval / 2)
            run_coroutine(asyncio.sleep(interval / 2))
            # t_interval = 0.025 / 0.05, t_timeout = 0.025 / 0.08
            self.assertEqual(len(futures), 1)
            self.assertFalse(futures[0].done())

            logging.debug("test: sleeping for %s", interval * 0.6)
            run_coroutine(asyncio.sleep(interval * 0.6))
            # t_interval = 0.005 / 0.05, t_timeout = 0.055 / 0.08
            self.assertEqual(len(futures), 2)
            self.assertFalse(futures[0].done())
            self.assertTrue(futures[1].done())

            logging.debug("test: verifying")
            _interpret_result.assert_called_once_with(unittest.mock.ANY)
            _, (fut, ), _ = _interpret_result.mock_calls[0]
            self.assertEqual(fut.result(), futures[1].result())
            _interpret_result.reset_mock()

            logging.debug("test: sleeping for %s", interval * 0.6)
            run_coroutine(asyncio.sleep(interval * 0.6))
            # t_interval = 0.035 / 0.05, t_timeout = 0.085 / 0.08
            self.assertEqual(len(futures), 2)
            self.assertTrue(futures[0].done())
            self.assertTrue(futures[1].done())

            _interpret_result.assert_called_once_with(unittest.mock.ANY)
            _, (fut, ), _ = _interpret_result.mock_calls[0]
            self.assertEqual(len(futures), 2)
            self.assertTrue(futures[0].cancelled())
            self.assertTrue(futures[0].done())
            self.assertIsInstance(fut.exception(), asyncio.TimeoutError)
            _interpret_result.reset_mock()

            run_coroutine(asyncio.sleep(interval * 0.8))
            # t_interval = 0.025 / 0.05
            self.assertEqual(len(futures), 3)
            self.assertTrue(futures[2].done())

            _interpret_result.assert_called_once_with(unittest.mock.ANY)
            _, (fut, ), _ = _interpret_result.mock_calls[0]
            self.assertIs(fut.exception(), futures[2].exception())
            self.assertIsNotNone(fut.exception())
            _interpret_result.reset_mock()

    def test__interpret_result_emits_on_fresh_for_None_result(self):
        fut = asyncio.Future()
        fut.set_result(None)

        self.p._interpret_result(fut)

        self.listener.on_fresh.assert_called_once_with()
        self.listener.on_exited.assert_not_called()

    def test__interpret_result_emits_on_fresh_for_service_unavailable_error(self):  # NOQA
        for type_ in [aioxmpp.errors.XMPPCancelError,
                      aioxmpp.errors.XMPPWaitError,
                      aioxmpp.errors.XMPPAuthError,
                      aioxmpp.errors.XMPPModifyError]:
            fut = asyncio.Future()
            fut.set_exception(
                type_(aioxmpp.errors.ErrorCondition.SERVICE_UNAVAILABLE)
            )

            self.p._interpret_result(fut)

            self.listener.on_fresh.assert_called_once_with()
            self.listener.on_exited.assert_not_called()
            self.listener.on_fresh.reset_mock()

    def test__interpret_result_emits_on_fresh_for_feature_not_implemented_error(self):  # NOQA
        for type_ in [aioxmpp.errors.XMPPCancelError,
                      aioxmpp.errors.XMPPWaitError,
                      aioxmpp.errors.XMPPAuthError,
                      aioxmpp.errors.XMPPModifyError]:
            fut = asyncio.Future()
            fut.set_exception(
                type_(aioxmpp.errors.ErrorCondition.FEATURE_NOT_IMPLEMENTED)
            )

            self.p._interpret_result(fut)

            self.listener.on_fresh.assert_called_once_with()
            self.listener.on_exited.assert_not_called()
            self.listener.on_fresh.reset_mock()

    def test__interpret_result_emits_nothing_for_item_not_found_error(self):
        for type_ in [aioxmpp.errors.XMPPCancelError,
                      aioxmpp.errors.XMPPWaitError,
                      aioxmpp.errors.XMPPAuthError,
                      aioxmpp.errors.XMPPModifyError]:
            fut = asyncio.Future()
            fut.set_exception(
                type_(aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND)
            )

            self.p._interpret_result(fut)

            self.listener.on_fresh.assert_not_called()
            self.listener.on_exited.assert_not_called()

    def test__interpret_result_emits_nothing_for_timeout(self):
        fut = asyncio.Future()
        fut.set_exception(
            asyncio.TimeoutError()
        )

        self.p._interpret_result(fut)

        self.listener.on_fresh.assert_not_called()
        self.listener.on_exited.assert_not_called()

    def test__interpret_result_emits_on_exited_for_other_xmpp_error(self):
        for type_ in [aioxmpp.errors.XMPPCancelError,
                      aioxmpp.errors.XMPPWaitError,
                      aioxmpp.errors.XMPPAuthError,
                      aioxmpp.errors.XMPPModifyError]:
            exc = type_(aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND)

            fut = asyncio.Future()
            fut.set_exception(exc)

            with unittest.mock.patch.object(
                    aioxmpp.errors.XMPPError, "condition",
                    new=unittest.mock.sentinel.condition):
                self.p._interpret_result(fut)

            self.listener.on_fresh.assert_not_called()
            self.listener.on_exited.assert_called_once_with()
            self.listener.on_exited.reset_mock()

    def test__interpret_result_emits_nothing_for_other_exceptions(self):
        class FooException(Exception):
            pass

        fut = asyncio.Future()
        fut.set_exception(FooException())

        self.p._interpret_result(fut)

        self.listener.on_fresh.assert_not_called()
        self.listener.on_exited.assert_not_called()

    def test_pinger_skips_ping_emission_if_client_is_suspended(self):
        timeout = get_timeout(0.1)

        self.assertFalse(self.cc.suspended)

        self.p.ping_interval = timedelta(seconds=timeout)

        with contextlib.ExitStack() as stack:
            ping = stack.enter_context(unittest.mock.patch(
                "aioxmpp.ping.ping",
                new=CoroutineMock(),
            ))

            self.p.start()

            run_coroutine(asyncio.sleep(timeout / 2))

            for i in range(2):
                self._require_task_running()
                ping.assert_called_once_with(
                    self.cc,
                    unittest.mock.sentinel.ping_address
                )
                ping.reset_mock()
                # we need to change the suspended flag here, because the next
                # sleep covers the next ping sending
                if i == 1:
                    self.cc.suspended = True
                run_coroutine(asyncio.sleep(timeout))

            for i in range(2):
                print(i)
                self._require_task_running()
                ping.assert_not_called()
                if i == 1:
                    self.cc.suspended = False

    def test_rejects_float_for_ping_interval(self):
        with self.assertRaises(TypeError):
            self.p.ping_interval = 1.

    def test_rejects_float_for_ping_timeout(self):
        with self.assertRaises(TypeError):
            self.p.ping_timeout = 1.


class TestMUCMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = unittest.mock.Mock(spec=aioxmpp.utils.AlivenessMonitor)
        self.pinger = unittest.mock.Mock(spec=self_ping.MUCPinger)
        self.pinger.ping_address = unittest.mock.sentinel.null_address
        self.pinger.ping_timeout = unittest.mock.sentinel.null_tiemout
        self.pinger.ping_interval = unittest.mock.sentinel.null_interval
        self.listener = unittest.mock.Mock()
        self.cc = make_connected_client()
        loop = asyncio.get_event_loop()
        self.logger = logging.getLogger(".".join([type(self).__module__,
                                                  type(self).__qualname__]))

        with contextlib.ExitStack() as stack:
            AlivenessMonitor = stack.enter_context(unittest.mock.patch(
                "aioxmpp.utils.AlivenessMonitor",
                return_value=self.monitor,
            ))

            MUCPinger = stack.enter_context(unittest.mock.patch(
                "aioxmpp.muc.self_ping.MUCPinger",
                return_value=self.pinger,
            ))

            self.m = self_ping.MUCMonitor(
                unittest.mock.sentinel.ping_address,
                self.cc,
                self.listener.on_stale,
                self.listener.on_fresh,
                self.listener.on_exited,
                logger=self.logger,
                loop=loop,
            )

        AlivenessMonitor.assert_called_once_with(loop)
        MUCPinger.assert_called_once_with(
            unittest.mock.sentinel.ping_address,
            self.cc,
            self.m._pinger_fresh_detected,
            self.m._pinger_exited_detected,
            self.logger,
            loop,
        )

        self.assertSequenceEqual(self.pinger.mock_calls, [])

    def tearDown(self):
        del self.m
        del self.monitor

    def test_connects_to_monitor_signals(self):
        self.monitor.on_deadtime_hard_limit_tripped.connect\
            .assert_called_once_with(
                self.m._hard_limit_tripped
            )

        self.monitor.on_deadtime_soft_limit_tripped.connect\
            .assert_called_once_with(
                self.m._soft_limit_tripped
            )

    def test_stale_inits_to_false(self):
        self.assertFalse(self.m.is_stale)

    def test_stale_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.m.is_stale = False

    def test_initialises_monitor_timeouts_to_None(self):
        self.assertIsNone(self.monitor.deadtime_soft_limit)
        self.assertIsNone(self.monitor.deadtime_hard_limit)

    def test_initialises_timeouts(self):
        self.assertEqual(self.m.soft_timeout, timedelta(minutes=13))
        self.assertEqual(self.m.hard_timeout, timedelta(minutes=15))

    def test_ping_address_inits_to_init_value(self):
        self.assertEqual(
            self.m.ping_address,
            unittest.mock.sentinel.ping_address,
        )

    def test_ping_address_is_writable(self):
        self.m.ping_address = unittest.mock.sentinel.foo
        self.assertEqual(
            self.m.ping_address,
            unittest.mock.sentinel.foo
        )

    def test_emits_no_events_on_construction(self):
        self.listener.on_fresh.assert_not_called()
        self.listener.on_stale.assert_not_called()
        self.listener.on_exited.assert_not_called()

    def test__mark_stale_emits_on_stale_if_not_stale(self):
        self.assertFalse(self.m.is_stale)

        self.m._mark_stale()

        self.listener.on_stale.assert_called_once_with()

    def test__mark_stale_does_not_emit_emits_on_stale_if_stale(self):
        self.m._mark_stale()
        self.listener.on_stale.reset_mock()
        self.assertTrue(self.m.is_stale)

        self.m._mark_stale()

        self.listener.on_stale.assert_not_called()

    def test__mark_stale_changes_is_stale(self):
        self.assertFalse(self.m.is_stale)

        self.m._mark_stale()

        self.assertTrue(self.m.is_stale)

    def test__mark_fresh_does_nothing_if_not_stale(self):
        self.assertFalse(self.m.is_stale)

        self.m._mark_fresh()

        self.assertFalse(self.m.is_stale)
        self.listener.on_stale.assert_not_called()
        self.listener.on_fresh.assert_not_called()

    def test__mark_fresh_clears_stale_flag(self):
        self.m._mark_stale()
        self.assertTrue(self.m.is_stale)

        self.m._mark_fresh()

        self.assertFalse(self.m.is_stale)

    def test__mark_fresh_emits_on_fresh_if_stale(self):
        self.m._mark_stale()
        self.assertTrue(self.m.is_stale)

        self.m._mark_fresh()

        self.listener.on_fresh.assert_called_once_with()

    def test__enable_monitor_notifies_and_configures_monitor(self):
        self.m.soft_timeout = timedelta(seconds=2)
        self.m.hard_timeout = timedelta(seconds=5)

        # the timeouts must not be set before notify_received to prevent
        # spurious triggers
        def check_timeouts():
            self.assertIsNone(self.monitor.deadtime_soft_limit)
            self.assertIsNone(self.monitor.deadtime_hard_limit)

        self.monitor.notify_received.side_effect = check_timeouts

        self.m._enable_monitor()

        self.monitor.notify_received.assert_called_once_with()
        self.assertEqual(self.monitor.deadtime_soft_limit, self.m.soft_timeout)
        self.assertEqual(self.monitor.deadtime_hard_limit, self.m.hard_timeout)

    def test__disable_monitor_notifies_and_deconfigures_monitor(self):
        self.m.soft_timeout = timedelta(seconds=2)
        self.m.hard_timeout = timedelta(seconds=5)
        self.m._enable_monitor()
        self.monitor.notify_received.reset_mock()

        # the timeouts must not be set before notify_received to prevent
        # spurious triggers
        def check_timeouts():
            self.assertEqual(self.monitor.deadtime_soft_limit,
                             self.m.soft_timeout)
            self.assertEqual(self.monitor.deadtime_hard_limit,
                             self.m.hard_timeout)

        self.monitor.notify_received.side_effect = check_timeouts

        self.m._disable_monitor()

        self.monitor.notify_received.assert_called_once_with()
        self.assertIsNone(self.monitor.deadtime_soft_limit)
        self.assertIsNone(self.monitor.deadtime_hard_limit)

    def test__hard_limit_tripped_calls__mark_stale(self):
        with contextlib.ExitStack() as stack:
            _mark_stale = stack.enter_context(unittest.mock.patch.object(
                self.m,
                "_mark_stale",
            ))

            self.m._hard_limit_tripped()

        _mark_stale.assert_called_once_with()

    def test__soft_limit_starts_pinger(self):
        self.m._soft_limit_tripped()
        self.pinger.start.assert_called_once_with()

    def test__pinger_fresh_detected_stops_pinger(self):
        self.m._pinger_fresh_detected()
        self.pinger.stop.assert_called_once_with()

    def test__pinger_fresh_detected_resets_aliveness_monitor(self):
        self.m._pinger_fresh_detected()
        self.monitor.notify_received.assert_called_once_with()

    def test__pinger_fresh_detected_calls__mark_fresh(self):
        with contextlib.ExitStack() as stack:
            _mark_fresh = stack.enter_context(unittest.mock.patch.object(
                self.m,
                "_mark_fresh",
            ))

            self.m._pinger_fresh_detected()

        _mark_fresh.assert_called_once_with()

    def test__pinger_exited_detected_stops_pinger(self):
        self.m._pinger_exited_detected()
        self.pinger.stop.assert_called_once_with()

    def test__pinger_exited_emits_on_exited(self):
        self.m._pinger_exited_detected()
        self.listener.on_exited.assert_called_once_with()

    def test_reset_cancels_pinger(self):
        self.m.reset()
        self.pinger.stop.assert_called_once_with()

    def test_reset_notifies_monitor(self):
        self.m.reset()
        self.monitor.notify_received.assert_called_once_with()

    def test_reset_marks_fresh(self):
        with unittest.mock.patch.object(self.m, "_mark_fresh") as _mark_fresh:
            self.m.reset()

        _mark_fresh.assert_called_once_with()

    def test_enable_enables_monitor(self):
        with unittest.mock.patch.object(
                self.m,
                "_enable_monitor") as _enable_monitor:
            self.m.enable()

        _enable_monitor.assert_called_once_with()

    def test_enable_clears_stale_state_without_event(self):
        self.m._mark_stale()
        self.listener.reset_mock()
        self.assertTrue(self.m.is_stale)

        self.m.enable()

        self.assertFalse(self.m.is_stale)
        self.listener.on_fresh.assert_not_called()

    def test_disable_disables_monitor(self):
        with unittest.mock.patch.object(
                self.m,
                "_disable_monitor") as _disable_monitor:
            self.m.disable()

        _disable_monitor.assert_called_once_with()

    def test_disable_stops_pinger(self):
        self.m.disable()
        self.pinger.stop.assert_called_once_with()

    def test_does_not_forward_timeout_writes_to_monitor_when_disabled(self):
        self.m.soft_timeout = timedelta(seconds=2)
        self.m.hard_timeout = timedelta(seconds=5)

        self.assertIsNone(self.monitor.deadtime_soft_limit)
        self.assertIsNone(self.monitor.deadtime_hard_limit)

    def test_writes_to_timeouts_can_be_read_immediately(self):
        self.m.soft_timeout = timedelta(seconds=2)

        self.assertEqual(self.m.soft_timeout,
                         timedelta(seconds=2))

    def test_forwards_timeout_writes_to_monitor_when_enabled(self):
        self.m._enable_monitor()

        self.assertNotEqual(self.monitor.deadtime_soft_limit,
                            timedelta(seconds=2))
        self.assertNotEqual(self.monitor.deadtime_hard_limit,
                            timedelta(seconds=5))

        self.m.soft_timeout = timedelta(seconds=2)
        self.m.hard_timeout = timedelta(seconds=5)

        self.assertEqual(self.monitor.deadtime_soft_limit,
                         timedelta(seconds=2))
        self.assertEqual(self.monitor.deadtime_hard_limit,
                         timedelta(seconds=5))

    def test_forwards_ping_address_writes_to_pinger(self):
        self.m.ping_address = unittest.mock.sentinel.foo

        self.assertEqual(self.pinger.ping_address, unittest.mock.sentinel.foo)

    def test_forwards_ping_timeout_writes_to_pinger(self):
        self.m.ping_timeout = unittest.mock.sentinel.foo

        self.assertEqual(self.pinger.ping_timeout, unittest.mock.sentinel.foo)

    def test_forwards_ping_interval_writes_to_pinger(self):
        self.m.ping_interval = unittest.mock.sentinel.foo

        self.assertEqual(self.pinger.ping_interval, unittest.mock.sentinel.foo)

    def test_enable_does_not_modify_state_if_already_enabled(self):
        self.m.enable()
        self.m._mark_stale()
        self.assertTrue(self.m.is_stale)

        with unittest.mock.patch.object(self.m,
                                        "_enable_monitor") as _enable_monitor:
            self.m.enable()

        _enable_monitor.assert_not_called()
        self.assertTrue(self.m.is_stale)

    def test_enable_modifies_state_after_disable(self):
        self.m.enable()
        self.m._mark_stale()
        self.m.disable()
        self.assertTrue(self.m.is_stale)

        with unittest.mock.patch.object(self.m,
                                        "_enable_monitor") as _enable_monitor:
            self.m.enable()

        _enable_monitor.assert_called_once_with()
        self.assertFalse(self.m.is_stale)

    def test_rejects_float_for_soft_timeout(self):
        with self.assertRaises(TypeError):
            self.m.soft_timeout = 1.

    def test_rejects_float_for_hard_timeout(self):
        with self.assertRaises(TypeError):
            self.m.hard_timeout = 1.
