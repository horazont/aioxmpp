import asyncio

class DataEvent:
    def __init__(self, *, loop=None):
        super().__init__()
        self._event = asyncio.Event(loop=loop)
        self._event.clear()
        self._value = None
        self._exc = None

    @property
    def value(self):
        if not self.is_set():
            raise RuntimeError("DataEvent {!r} is not set".format(self))
        if self._exc:
            raise self._exc
        return self._value

    def set(self, value):
        if self.is_set():
            raise RuntimeError("DataEvent {!r} is set".format(self))
        self._value = value
        self._exc = None
        self._event.set()

    def set_exception(self, exc):
        if self.is_set():
            raise RuntimeError("DataEvent {!r} is set".format(self))
        self._value = None
        self._exc = exc
        self._event.set()

    def is_set(self):
        return self._event.is_set()

    def clear(self):
        self._event.clear()
        self._value = None
        self._exc = None

    @asyncio.coroutine
    def wait(self):
        yield from self._event.wait()
        return self.value

    def __repr__(self):
        if self._event.is_set():
            if self._exc is not None:
                data_or_exc_or_nothing = " exc={!r}".format(self._exc)
            else:
                data_or_exc_or_nothing = " value={!r}".format(self._value)
        else:
            data_or_exc_or_nothing = ""

        return "<DataEvent is_set={!r}{}>".format(
            self._event.is_set(),
            data_or_exc_or_nothing)
