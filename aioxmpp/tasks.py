########################################################################
# File name: tasks.py
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
:mod:`~aioxmpp.tasks` -- Manage herds of running coroutines
###########################################################

.. autoclass:: TaskPool
"""
import asyncio
import logging


class TaskPool:
    """
    Coroutine worker pool with limits on the maximum number of coroutines.

    :param max_tasks: Maximum number of total coroutines running in the pool.
    :type max_tasks: positive :class:`int` or :data:`None`
    :param logger: Logger to use for diagnostics, defaults to a module-wide
                   logger

    Each coroutine run in the task pool belongs to zero or more groups. Groups
    are identified by their hashable *group key*. The structure of the key is
    not relevant. Groups are created on-demand. Each coroutine is implicitly
    part of the group ``()`` (the empty tuple).

    `max_tasks` is the limit on the group ``()`` (the empty tuple). As every
    coroutine is running in that group, it is the limit on the total number of
    coroutines running in the pool.

    When a coroutine exits (either normally or by an exception or
    cancellation), it is removed from the pool and the counters for running
    coroutines are adapted accordingly.

    Controlling limits on groups:

    .. automethod:: set_limit

    .. automethod:: get_limit

    .. automethod:: get_task_count

    .. automethod:: clear_limit

    Starting and adding coroutines:

    .. automethod:: spawn(group, coro_fun, *args, **kwargs)

    .. automethod:: add
    """

    def __init__(self, *, max_tasks=None, default_limit=None, logger=None):
        super().__init__()
        if logger is None:
            logger = logging.getLogger(__name__)
        self._group_limits = {}
        self._group_tasks = {}
        self.default_limit = default_limit
        self.set_limit((), max_tasks)

    def set_limit(self, group, new_limit):
        """
        Set a new limit on the number of tasks in the `group`.

        :param group: Group key of the group to modify.
        :type group: hashable
        :param new_limit: New limit for the number of tasks running in `group`.
        :type new_limit: non-negative :class:`int` or :data:`None`
        :raise ValueError: if `new_limit` is non-positive

        The limit of tasks for the `group` is set to `new_limit`. If there are
        currently more than `new_limit` tasks running in `group`, those tasks
        will continue to run, however, the creation of new tasks is inhibited
        until the group is below its limit.

        If the limit is set to zero, no new tasks can be spawned in the group
        at all.

        If `new_limit` is negative :class:`ValueError` is raised instead.

        If `new_limit` is :data:`None`, the method behaves as if
        :meth:`clear_limit` was called for `group`.
        """
        if new_limit is None:
            self._group_limits.pop(group, None)
            return

        self._group_limits[group] = new_limit

    def clear_limit(self, group):
        """
        Clear the limit on the number of tasks in the `group`.

        :param group: Group key of the group to modify.
        :type group: hashable

        The limit on the number of tasks in `group` is removed. If the `group`
        currently has no limit, this method has no effect.
        """
        self._group_limits.pop(group, None)

    def get_limit(self, group):
        """
        Return the limit on the number of tasks in the `group`.

        :param group: Group key of the group to query.
        :type group: hashable
        :return: The current limit
        :rtype: :class:`int` or :data:`None`

        If the `group` currently has no limit set, :data:`None` is returned.
        Otherwise, the maximum number of tasks which are allowed to run in the
        `group` is returned.
        """
        return self._group_limits.get(group)

    def get_task_count(self, group):
        """
        Return the number of tasks currently running in `group`.

        :param group: Group key of the group to query.
        :type group: hashable
        :return: Number of currently running tasks
        :rtype: :class:`int`
        """
        return 0

    def add(self, groups, coro):
        """
        Add a running coroutine in the given pool groups.

        :param groups: The groups the coroutine belongs to.
        :type groups: :class:`set` of group keys
        :param coro: Coroutine to add
        :raise RuntimeError: if the limit on any of the groups or the total
                             limit is exhausted
        :rtype: :class:`asyncio.Task`
        :return: The task in which the coroutine runs.

        Every group must have at least one free slot available for `coro` to be
        spawned; if any groups capacity (or the total limit) is exhausted, the
        coroutine is not accepted into the pool and :class:`RuntimeError` is
        raised.
        """

    def spawn(self, __groups, __coro_fun, *args, **kwargs):
        """
        Start a new coroutine and add it to the pool atomically.

        :param groups: The groups the coroutine belongs to.
        :type groups: :class:`set` of group keys
        :param coro_fun: Coroutine function to run
        :param args: Positional arguments to pass to `coro_fun`
        :param kwargs: Keyword arguments to pass to `coro_fun`
        :raise RuntimeError: if the limit on any of the groups or the total
                             limit is exhausted
        :rtype: :class:`asyncio.Task`
        :return: The task in which the coroutine runs.

        Every group must have at least one free slot available for `coro` to be
        spawned; if any groups capacity (or the total limit) is exhausted, the
        coroutine is not accepted into the pool and :class:`RuntimeError` is
        raised.

        If the coroutine cannot be added due to limiting, it is not started at
        all.

        The coroutine is started by calling `coro_fun` with `args` and
        `kwargs`.

        .. note::

           The first two arguments can only be passed positionally, not as
           keywords. This is to prevent conflicts with keyword arguments to
           `coro_fun`.

        """
        # ensure the implicit group is included
        __groups = set(__groups) | {()}

        return asyncio.ensure_future(__coro_fun(*args, **kwargs))
