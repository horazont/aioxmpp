########################################################################
# File name: statemachine.py
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
"""
:mod:`~aioxmpp.statemachine` -- Utils for implementing a state machine
######################################################################

.. autoclass:: OrderedStateMachine

.. autoclass:: OrderedStateSkipped

"""
import asyncio


class OrderedStateSkipped(ValueError):
    """
    This exception signals that a state has been skipped in a
    :class:`OrderedStateMachine` and cannot be waited for anymore.

    .. attribute:: skipped_state

       The state which a routine attempted to wait for and which cannot be
       reached by the state machine anymore.

    """

    def __init__(self, skipped_state):
        super().__init__("state {} has been skipped".format(skipped_state))
        self.skipped_state = skipped_state


class OrderedStateMachine:
    """
    :class:`OrderedStateMachine` provides facilities to implement a state
    machine. Besides storing the state, it provides coroutines which allow to
    wait for a specific state.

    The state machine uses `initial_state` as initial state. States used by
    :class:`OrderedStateMachine` must be ordered; a sanity check is performed
    by checking if the `initial_state` is less than itself. If that check
    fails, :class:`TypeError` is raised.

    Reading and manipulating the state:

    .. autoattribute:: state

    .. automethod:: rewind

    Waiting for specific states:

    .. automethod:: wait_for

    .. automethod:: wait_for_at_least
    """
    def __init__(self, initial_state, *, loop=None):
        try:
            initial_state < initial_state
        except (TypeError, AttributeError):
            raise TypeError("states must be ordered")

        self._state = initial_state
        self._least_waiters = []
        self._exact_waiters = []
        self.loop = loop if loop is not None else asyncio.get_event_loop()

    @property
    def state(self):
        """
        The current state of the state machine. Writing to this attribute
        advances the state of the state machine.

        Attempting to change the state to a state which is *less* than the
        current state will result in a :class:`ValueError` exception; an
        :class:`OrderedStateMachine` can only move forwards.

        Any coroutines waiting for a specific state to be reached will be woken
        up appropriately, see the specific methods for details.
        """
        return self._state

    @state.setter
    def state(self, new_state):
        if new_state < self._state:
            raise ValueError("cannot rewind OrderedStateMachine "
                             "({} < {})".format(
                                 new_state, self._state))
        self._state = new_state

        new_waiters = []
        for least_state, fut in self._least_waiters:
            if fut.done():
                continue
            if not (new_state < least_state):
                fut.set_result(None)
                continue
            new_waiters.append((least_state, fut))
        self._least_waiters[:] = new_waiters

        new_waiters = []
        for expected_state, fut in self._exact_waiters:
            if fut.done():
                continue
            if expected_state == new_state:
                fut.set_result(None)
                continue
            if expected_state < new_state:
                fut.set_exception(OrderedStateSkipped(expected_state))
                continue
            new_waiters.append((expected_state, fut))
        self._exact_waiters[:] = new_waiters

    def rewind(self, new_state):
        """
        Rewind can be used as an exceptional way to roll back the state of a
        :class:`OrderedStateMachine`.

        Rewinding is not the usual use case for an
        :class:`OrderedStateMachine`. Usually, if the current state `A` is
        greater than any given state `B`, it is assumed that state `B` cannot
        be reached anymore (which makes :meth:`wait_for` raise).

        It may make sense to go backwards though, and in cases where the
        ability to go backwards is sensible even if routines which previously
        attempted to wait for the state you are going backwards to failed,
        using a :class:`OrderedStateMachine` is still a good idea.
        """
        if new_state > self._state:
            raise ValueError("cannot forward using rewind "
                             "({} > {})".format(new_state, self._state))
        self._state = new_state

    async def wait_for(self, new_state):
        """
        Wait for an exact state `new_state` to be reached by the state
        machine.

        If the state is skipped, that is, if a state which is greater than
        `new_state` is written to :attr:`state`, the coroutine raises
        :class:`OrderedStateSkipped` exception as it is not possible anymore
        that it can return successfully (see :attr:`state`).
        """
        if self._state == new_state:
            return

        if self._state > new_state:
            raise OrderedStateSkipped(new_state)

        fut = asyncio.Future(loop=self.loop)
        self._exact_waiters.append((new_state, fut))
        await fut

    async def wait_for_at_least(self, new_state):
        """
        Wait for a state to be entered which is greater than or equal to
        `new_state` and return.
        """
        if not (self._state < new_state):
            return

        fut = asyncio.Future(loop=self.loop)
        self._least_waiters.append((new_state, fut))
        await fut
