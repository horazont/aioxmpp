########################################################################
# File name: custom_queue.py
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
import collections


class AsyncDeque:
    def __init__(self, *, loop=None):
        super().__init__()
        self._loop = loop
        self._data = collections.deque()
        self._non_empty = asyncio.Event()
        self._non_empty.clear()

    def __len__(self):
        return len(self._data)

    def __contains__(self, obj):
        return obj in self._data

    def empty(self):
        return not self._non_empty.is_set()

    def put_nowait(self, obj):
        self._data.append(obj)
        self._non_empty.set()

    def putleft_nowait(self, obj):
        self._data.appendleft(obj)
        self._non_empty.set()

    def get_nowait(self):
        try:
            item = self._data.popleft()
        except IndexError:
            raise asyncio.QueueEmpty() from None
        if not self._data:
            self._non_empty.clear()
        return item

    def getright_nowait(self):
        try:
            item = self._data.pop()
        except IndexError:
            raise asyncio.QueueEmpty() from None
        if not self._data:
            self._non_empty.clear()
        return item

    async def get(self):
        while not self._data:
            await self._non_empty.wait()
        return self.get_nowait()

    def clear(self):
        self._data.clear()
        self._non_empty.clear()
