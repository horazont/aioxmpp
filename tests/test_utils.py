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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio
import unittest
import unittest.mock
import sys

import aioxmpp.utils as utils

from aioxmpp.testutils import (
    CoroutineMock,
    run_coroutine,
)


class TestNamespaces(unittest.TestCase):
    def test_aioxmpp(self):
        self.assertEqual(
            utils.namespaces.aioxmpp_internal,
            "https://zombofant.net/xmlns/aioxmpp#internal"
        )


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
        with unittest.mock.patch("asyncio.async") as async_:
            self.cm.__enter__()

        async_.assert_called_with(self.started_coro)
        self.assertFalse(async_().cancel.mock_calls)

    def test_exit_cancels_coroutine(self):
        with unittest.mock.patch("asyncio.async") as async_:
            self.cm.__enter__()
            self.cm.__exit__(None, None, None)

        async_().cancel.assert_called_with()

    def test_exit_with_exc_cancels_coroutine_and_propagates(self):
        try:
            raise ValueError()
        except:
            exc_info = sys.exc_info()

        with unittest.mock.patch("asyncio.async") as async_:
            self.cm.__enter__()
            result = self.cm.__exit__(*exc_info)

        self.assertFalse(result)
        async_().cancel.assert_called_with()

    @asyncio.coroutine
    def _long_wrapper(self):
        with self.cm:
            yield from asyncio.sleep(0.1)

    def test_logs_nothing_when_coroutine_terminates_normally(self):
        run_coroutine(self._long_wrapper())
        self.assertFalse(self.logger.mock_calls)

    def test_logs_error_when_coroutine_raises(self):
        @asyncio.coroutine
        def failing():
            raise ValueError()

        self.cm = utils.background_task(failing(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.error.assert_called_with(
            "background task failed: %r",
            unittest.mock.ANY,
            exc_info=True,
        )

    def test_logs_debug_when_coroutine_cancelled(self):
        @asyncio.coroutine
        def too_long():
            yield from asyncio.sleep(10)

        self.cm = utils.background_task(too_long(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.debug.assert_called_with(
            "background task terminated by CM exit: %r",
            unittest.mock.ANY,
        )

    def test_logs_info_when_coroutine_returns_value(self):
        @asyncio.coroutine
        def something():
            return unittest.mock.sentinel.result

        self.cm = utils.background_task(something(), self.logger)
        run_coroutine(self._long_wrapper())

        self.logger.info.assert_called_with(
            "background task (%r) returned a value: %r",
            unittest.mock.ANY,
            unittest.mock.sentinel.result,
        )
