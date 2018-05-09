########################################################################
# File name: test_statemachine.py
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
import functools
import unittest

from enum import Enum

import aioxmpp.statemachine as statemachine

from aioxmpp.testutils import run_coroutine


@functools.total_ordering
class States(Enum):
    STATE1 = 1
    STATE2 = 2
    STATE3 = 3
    STATE4 = 4

    def __lt__(self, other):
        return self.value < other.value


class TestOrderedStateSkipped(unittest.TestCase):
    def test_is_value_error(self):
        self.assertTrue(issubclass(
            statemachine.OrderedStateSkipped,
            ValueError
        ))

    def test_init(self):
        exc = statemachine.OrderedStateSkipped(States.STATE1)
        self.assertRegex(
            str(exc),
            r"state [^ ]+ has been skipped"
        )
        self.assertIs(exc.skipped_state, States.STATE1)


class TestOrderedStateMachine(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.osm = statemachine.OrderedStateMachine(
            States.STATE1,
            loop=self.loop)

    def tearDown(self):
        del self.osm
        del self.loop

    def test_init(self):
        osm = statemachine.OrderedStateMachine(
            States.STATE1)
        self.assertEqual(
            States.STATE1,
            osm.state
        )

    def test_init_rejects_unordered_state_type(self):
        class OtherStates(Enum):
            FOO = 1
            BAR = 2

        with self.assertRaisesRegex(TypeError,
                                    "states must be ordered"):
            statemachine.OrderedStateMachine(OtherStates.FOO)

    def test_wait_for_at_least(self):
        state_tasks = {
            state: asyncio.ensure_future(self.osm.wait_for_at_least(state),
                                 loop=self.loop)
            for state in States
        }

        run_coroutine(asyncio.sleep(0))

        self.osm.state = States.STATE3

        run_coroutine(asyncio.sleep(0.01))

        for state, task in state_tasks.items():
            if state <= States.STATE3:
                self.assertTrue(task.done(), state)
                self.assertIsNone(task.result())
            else:
                self.assertFalse(task.done(), state)

    def test_wait_for_at_least_checks_current_state(self):
        state_tasks = {
            state: asyncio.ensure_future(self.osm.wait_for_at_least(state),
                                 loop=self.loop)
            for state in States
        }

        self.osm.state = States.STATE3

        run_coroutine(asyncio.sleep(0))

        for state, task in state_tasks.items():
            if state <= States.STATE3:
                self.assertTrue(task.done(), state)
                self.assertIsNone(task.result())
            else:
                self.assertFalse(task.done(), state)

    def test_wait_for_at_least_can_be_cancelled(self):
        state_tasks = {
            state: asyncio.ensure_future(self.osm.wait_for_at_least(state),
                                 loop=self.loop)
            for state in States
        }

        run_coroutine(asyncio.sleep(0))

        for task in state_tasks.values():
            task.cancel()

        run_coroutine(asyncio.sleep(0))

        self.osm.state = States.STATE3

        run_coroutine(asyncio.sleep(0))

    def test_state_rejects_rewinding(self):
        self.osm.state = States.STATE2
        with self.assertRaisesRegex(
                ValueError,
                "cannot rewind OrderedStateMachine"):
            self.osm.state = States.STATE1
        self.osm.state = States.STATE2

    def test_wait_for(self):
        state_tasks = {
            state: asyncio.ensure_future(self.osm.wait_for(state),
                                 loop=self.loop)
            for state in States
        }

        run_coroutine(asyncio.sleep(0))

        self.osm.state = States.STATE3

        run_coroutine(asyncio.sleep(0.01))

        for state, task in state_tasks.items():
            # STATE1 triggers immediately, it is the current state when the
            # coroutine is called
            if state in [States.STATE3, States.STATE1]:
                self.assertTrue(task.done(), state)
                self.assertIsNone(task.result())
            elif state < States.STATE3:
                self.assertTrue(task.done(), state)
                self.assertIsInstance(
                    task.exception(),
                    statemachine.OrderedStateSkipped,
                    state
                )
            else:
                self.assertFalse(task.done(), state)

    def test_wait_for_checks_immediately(self):
        state_tasks = {
            state: asyncio.ensure_future(self.osm.wait_for(state),
                                 loop=self.loop)
            for state in States
        }

        self.osm.state = States.STATE3

        run_coroutine(asyncio.sleep(0.01))

        for state, task in state_tasks.items():
            if state == States.STATE3:
                self.assertTrue(task.done(), state)
                self.assertIsNone(task.result())
            elif state < States.STATE3:
                self.assertTrue(task.done(), state)
                self.assertIsInstance(
                    task.exception(),
                    statemachine.OrderedStateSkipped,
                    state
                )
            else:
                self.assertFalse(task.done(), state)

    def test_rewind_allows_going_back(self):
        self.osm.state = States.STATE3
        self.osm.rewind(States.STATE2)
        self.assertEqual(
            States.STATE2,
            self.osm.state
        )

    def test_rewind_rejects_going_forward(self):
        self.osm.state = States.STATE3
        with self.assertRaisesRegex(ValueError,
                                    "cannot forward using rewind"):
            self.osm.rewind(States.STATE4)

    def test_wait_for_at_least_fails_if_state_is_unreachable(self):
        self.osm.state
