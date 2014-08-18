import asyncio
import collections

class AsyncDeque:
    def __init__(self, initial_data=[], *, loop=None):
        super().__init__()
        self._data = collections.deque(initial_data)
        self._loop = loop
        self._non_empty = asyncio.Event()
        self._non_empty.clear()

    def append(self, value):
        self._data.append(value)
        self._non_empty.set()

    def appendleft(self, value):
        self._data.appendleft(value)
        self._non_empty.set()

    @asyncio.coroutine
    def pop(self):
        while not self._data:
            yield from self._non_empty.wait()
        result = self._data.pop()
        if not self._data:
            self._non_empty.clear()
        return result

    @asyncio.coroutine
    def popleft(self):
        while not self._data:
            yield from self._non_empty.wait()
        result = self._data.popleft()
        if not self._data:
            self._non_empty.clear()
        return result

    def extend(self, value):
        self._data.extend(value)
        self._non_empty.set()

    def extendleft(self, value):
        self._data.extend(value)
        self._non_empty.set()

    def empty(self):
        return bool(self._data)

    def clear(self):
        self._data.clear()
        self._non_empty.clear()
