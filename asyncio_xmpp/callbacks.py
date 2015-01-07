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

    def emit(self, key, *args):
        for fn in self._callbacks[key].values():
            self._loop.call_soon(fn, *args)
