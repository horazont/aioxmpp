import asyncio
import collections
import functools
import weakref


class TagListener:
    def __init__(self, ondata, onerror=None):
        self._ondata = ondata
        self._onerror = onerror

    def data(self, data):
        return self._ondata(data)

    def error(self, exc):
        if self._onerror is not None:
            return self._onerror(exc)

    def is_valid(self):
        return True


class AsyncTagListener(TagListener):
    def __init__(self, ondata, onerror=None, *, loop=None):
        super().__init__(ondata, onerror)
        self._loop = loop or asyncio.get_event_loop()

    def data(self, data):
        self._loop.call_soon(self._ondata, data)

    def error(self, exc):
        if self._onerror is not None:
            self._loop.call_soon(self._onerror, exc)


class OneshotTagListener(TagListener):
    def data(self, data):
        super().data(data)
        return True

    def error(self, exc):
        super().error(exc)
        return True


class OneshotAsyncTagListener(OneshotTagListener, AsyncTagListener):
    pass


class FutureListener:
    def __init__(self, fut):
        self.fut = fut

    def data(self, data):
        try:
            self.fut.set_result(data)
        except asyncio.futures.InvalidStateError:
            pass
        return True

    def error(self, exc):
        try:
            self.fut.set_exception(exc)
        except asyncio.futures.InvalidStateError:
            pass
        return True

    def is_valid(self):
        return not self.fut.done()


class TagDispatcher:
    def __init__(self):
        self._listeners = {}

    def add_callback(self, tag, fn):
        return self.add_listener(tag, TagListener(fn))

    def add_callback_async(self, tag, fn, *, loop=None):
        return self.add_listener(
            tag,
            AsyncTagListener(fn, loop=loop)
        )

    def add_future(self, tag, fut):
        return self.add_listener(
            tag,
            FutureListener(fut)
        )

    def add_listener(self, tag, listener):
        try:
            existing = self._listeners[tag]
            if not existing.is_valid():
                raise KeyError()
        except KeyError:
            self._listeners[tag] = listener
        else:
            raise ValueError("only one listener is allowed per tag")

    def unicast(self, tag, data):
        cb = self._listeners[tag]
        if not cb.is_valid():
            del self._listeners[tag]
            self._listeners[tag]
        if cb.data(data):
            del self._listeners[tag]

    def remove_listener(self, tag):
        del self._listeners[tag]

    def broadcast_error(self, exc):
        for tag, listener in list(self._listeners.items()):
            if listener.is_valid() and listener.error(exc):
                del self._listeners[tag]

    def close_all(self, exc):
        self.broadcast_error(exc)
        self._listeners.clear()


class AdHocSignal:
    @classmethod
    def STRONG(cls, f):
        return functools.partial(cls._strong_wrapper, f)

    @classmethod
    def ASYNC_WITH_LOOP(cls, loop):
        if loop is None:
            loop = asyncio.get_event_loop()

        def create_wrapper(f):
            return functools.partial(cls._async_wrapper,
                                     f,
                                     loop)

        return create_wrapper

    @classmethod
    def WEAK(cls, f):
        return functools.partial(cls._weakref_wrapper, weakref.ref(f))

    def __init__(self):
        super().__init__()
        self._connections = {}

    @staticmethod
    def _async_wrapper(f, loop, args, kwargs):
        if kwargs:
            loop.call_soon(functools.partial(*args, **kwargs))
        loop.call_soon(f, *args)
        return True

    @staticmethod
    def _weakref_wrapper(fref, args, kwargs):
        f = fref()
        if f is None:
            return False
        return not f(*args, **kwargs)

    @staticmethod
    def _strong_wrapper(f, args, kwargs):
        return not f(*args, **kwargs)

    def _connect(self, wrapper):
        token = object()
        self._connections[token] = wrapper
        return token

    def connect(self, f, mode=None):
        mode = mode or self.STRONG
        return self._connect(mode(f))

    def context_connect(self, f, mode=None):
        return SignalConnectionContext(self, f, mode=mode)

    def fire(self, *args, **kwargs):
        for token, wrapper in list(self._connections.items()):
            if not wrapper(args, kwargs):
                del self._connections[token]

    def disconnect(self, token):
        try:
            del self._connections[token]
        except KeyError:
            pass

    __call__ = fire

AdHocSignal.ASYNC = AdHocSignal.ASYNC_WITH_LOOP(None)


class SignalConnectionContext:
    def __init__(self, signal, f, mode=None):
        self._signal = signal
        self._f = f
        self._mode = mode

    def __enter__(self):
        try:
            token = self._signal.connect(self._f, mode=self._mode)
        finally:
            del self._f
            del self._mode
        self._token = token
        return token

    def __exit__(self, exc_type, exc_value, traceback):
        self._signal.disconnect(self._token)
        return False


class Signal:
    def __init__(self):
        super().__init__()
        self._instances = weakref.WeakKeyDictionary()

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return self._instances[instance]
        except KeyError:
            new = AdHocSignal()
            self._instances[instance] = new
            return new

    def __set__(self, instance, value):
        raise AttributeError("cannot override Signal attribute")

    def __delete__(self, instance):
        raise AttributeError("cannot override Signal attribute")
