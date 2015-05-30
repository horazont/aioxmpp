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
            OneshotTagListener(fut.set_result,
                               fut.set_exception)
        )

    def add_future_async(self, tag, fut, *, loop=None):
        return self.add_listener(
            tag,
            OneshotAsyncTagListener(fut.set_result,
                                    fut.set_exception,
                                    loop=loop)
        )

    def add_listener(self, tag, listener):
        try:
            self._listeners[tag]
        except KeyError:
            self._listeners[tag] = listener
        else:
            raise ValueError("only one listener is allowed per tag")

    def unicast(self, tag, data):
        cb = self._listeners[tag]
        if cb.data(data):
            del self._listeners[tag]

    def remove_listener(self, tag):
        del self._listeners[tag]

    def broadcast_error(self, exc):
        for tag, listener in list(self._listeners.items()):
            if listener.error(exc):
                del self._listeners[tag]

    def close_all(self, exc):
        self.broadcast_error(exc)
        self._listeners.clear()


class AdHocSignal:
    def __init__(self):
        super().__init__()
        self._connections = {}
        self._token_ctr = 0

    @staticmethod
    def _async_wrapper(fref, loop, args, kwargs):
        f = fref()
        if f is None:
            return False
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

    def _connect(self, wrapper):
        token = self._token_ctr + 1
        self._token_ctr = token
        self._connections[token] = wrapper
        return token

    def connect(self, f):
        return self._connect(
            functools.partial(self._weakref_wrapper, weakref.ref(f))
        )

    def connect_async(self, f, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()

        return self._connect(
            functools.partial(self._async_wrapper,
                              weakref.ref(f),
                              loop)
        )

    def fire(self, *args, **kwargs):
        for token, wrapper in list(self._connections.items()):
            if not wrapper(args, kwargs):
                del self._connections[token]

    def remove(self, token):
        try:
            del self._connections[token]
        except KeyError:
            pass

    __call__ = fire


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
