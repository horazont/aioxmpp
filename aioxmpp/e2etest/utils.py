########################################################################
# File name: utils.py
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


def blocking(f):
    """
    The decorated coroutine function is run using the
    :meth:`~asyncio.AbstractEventLoop.run_until_complete` method of the current
    (at the time of call) event loop.

    The decorated function behaves like a normal function and is not a
    coroutine function.

    This decorator must be applied to a coroutine function (or method).
    """

    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(f(*args, **kwargs))
    return wrapped
