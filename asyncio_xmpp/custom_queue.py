import asyncio
import collections


class AsyncDeque:
    def __init__(self, *, loop=None):
        super().__init__()
        self._loop = loop
        self._data = collections.deque()
        self._non_empty = asyncio.Event(loop=self._loop)
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

    @asyncio.coroutine
    def get(self):
        while not self._data:
            yield from self._non_empty.wait()
        return self.get_nowait()

    def clear(self):
        self._data.clear()
        self._non_empty.clear()
