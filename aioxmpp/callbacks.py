import asyncio
import collections

class Token(collections.namedtuple("Token", ["key"])):
    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __repr__(self):
        return "<Token key={!r} id={!r}>".format(
            self.key,
            id(self))


class CallbacksWithToken:
    def __init__(self, *keys, loop=None):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._callbacks = {
            key: {}
            for key in keys
        }

    def add_callback(self, key, fn):
        token = Token(key)
        self._callbacks[key][token] = fn
        return token

    def remove_callback(self, token):
        self._callbacks[token.key].pop(token)

    def remove_callback_fn(self, key, fn):
        self._callbacks[key].remove(fn)

    def emit(self, key, *args, **kwargs):
        for fn in self._callbacks[key].values():
            self._loop.call_soon(fn, *args, **kwargs)


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
            existing = self._listeners[tag]
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
