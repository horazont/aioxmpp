"""
:mod:`~aioxmpp.callbacks` -- Synchronous and asynchronous callbacks
###################################################################

This module provides facilities for objects to provide signals to which other
objects can connect.

Descriptor vs. ad-hoc
=====================

Descriptors can be used as class attributes and will create ad-hoc signals
dynamically for each instance. They are the most commonly used:

.. code-block:: python

   class Emitter:
       on_event = callbacks.Signal()

   def handler():
       pass

   emitter1 = Emitter()
   emitter2 = Emitter()
   emitter1.on_event.connect(handler)

   emitter1.on_event()  # calls `handler`
   emitter2.on_event()  # does not call `handler`

   # the actual signals are distinct
   assert emitter1.on_event is not emitter2.on_event

Ad-hoc signals are useful for testing and are the type of which the actual
fields are.

Class overview
==============

.. autosummary::

   Signal
   SyncSignal
   AdHocSignal
   SyncAdHocSignal

Signal implementations (ad-hoc signals)
---------------------------------------

Whenever accessing an attribute using the :class:`Signal` or
:class:`SyncSignal` descriptors, an object of one of the following classes is
returned. This is where the behaviour of the signals is specified.

.. autoclass:: AdHocSignal

.. autoclass:: SyncAdHocSignal

Signal descriptors
------------------

These descriptors can be used on classes to have attributes which are signals:

.. autoclass:: Signal

.. autoclass:: SyncSignal

"""

import abc
import asyncio
import collections
import functools
import logging
import weakref


logger = logging.getLogger(__name__)


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

    def unicast_error(self, tag, exc):
        cb = self._listeners[tag]
        if not cb.is_valid():
            del self._listeners[tag]
            self._listeners[tag]
        if cb.error(exc):
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


class AbstractAdHocSignal:
    def __init__(self):
        super().__init__()
        self._connections = collections.OrderedDict()
        self.logger = logger

    def _connect(self, wrapper):
        token = object()
        self._connections[token] = wrapper
        return token

    def disconnect(self, token):
        """
        Disconnect the connection identified by `token`. This never raises,
        even if an invalid `token` is passed.
        """
        try:
            del self._connections[token]
        except KeyError:
            pass


class AdHocSignal(AbstractAdHocSignal):
    """
    An ad-hoc signal is a single emitter. This is where callables are connected
    to, using the :meth:`connect` method of the :class:`AdHocSignal`.

    .. automethod:: fire

    .. automethod:: connect

    .. attribute:: logger

       This may be a :class:`logging.Logger` instance to allow the signal to
       log errors and debug events to a specific logger instead of the default
       logger (``aioxmpp.callbacks``).

       This attribute must not be :data:`None`, and it is initialised to the
       default logger on creation of the :class:`AdHocSignal`.

    The different ways callables can be connected to an ad-hoc signal are shown
    below:

    .. attribute:: STRONG

       Connections using this mode keep a strong reference to the callable. The
       callable is called directly, thus blocking the emission of the signal.

    .. attribute:: WEAK

       Connections using this mode keep a weak reference to the callable. The
       callable is executed directly, thus blocking the emission of the signal.

       If the weak reference is dead, it is automatically removed from the
       signals connection list.

    For both :attr:`STRONG` and :attr:`WEAK` holds: if the callable returns a
    true value, it is disconnected from the signal.

    .. classmethod:: ASYNC_WITH_LOOP(loop)

       This mode requires an :mod:`asyncio` event loop as argument. When the
       signal is emitted, the callable is not called directly. Instead, it is
       enqueued for calling with the event loop using
       :meth:`asyncio.BaseEventLoop.call_soon`.

       A strong reference is held to the callable.

       Connections using this mode are never removed automatically from the
       signals connection list. You have to use :meth:`disconnect` explicitly.

    .. attribute:: AUTO_FUTURE

       Instead of a callable, a :class:`asyncio.Future` must be passed when
       using this mode.

       This mode can only be used for signals which send at most one
       argument. If no argument is sent, the :meth:`~asyncio.Future.set_result`
       method is called with :data:`None`.

       If one argument is sent and it is an instance of :class:`Exception`, it
       is passed to :meth:`~asyncio.Future.set_exception`. Otherwise, if one
       argument is sent, it is passed to
       :meth:`~asyncio.Future.set_exception`.

       In any case, the future is removed after the next emission of the
       signal.

    .. automethod:: disconnect

    """

    @classmethod
    def STRONG(cls, f):
        if not hasattr(f, "__call__"):
            raise TypeError("must be callable, got {!r}".format(f))
        return functools.partial(cls._strong_wrapper, f)

    @classmethod
    def ASYNC_WITH_LOOP(cls, loop):
        if loop is None:
            loop = asyncio.get_event_loop()

        def create_wrapper(f):
            if not hasattr(f, "__call__"):
                raise TypeError("must be callable, got {!r}".format(f))
            return functools.partial(cls._async_wrapper,
                                     f,
                                     loop)

        return create_wrapper

    @classmethod
    def WEAK(cls, f):
        if not hasattr(f, "__call__"):
            raise TypeError("must be callable, got {!r}".format(f))
        return functools.partial(cls._weakref_wrapper, weakref.ref(f))

    @classmethod
    def AUTO_FUTURE(cls, f):
        def future_wrapper(args, kwargs):
            if kwargs:
                raise TypeError("keyword arguments not supported")
            if len(args) > 0:
                try:
                    arg, = args
                except ValueError:
                    raise TypeError("too many arguments") from None
            else:
                arg = None
            if f.done():
                return
            if isinstance(arg, Exception):
                f.set_exception(arg)
            else:
                f.set_result(arg)
        return future_wrapper

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

    def connect(self, f, mode=None):
        """
        Connect an object `f` to the signal. The type the object needs to have
        depends on `mode`, but usually it needs to be a callable.

        :meth:`connect` returns an opaque token which can be used with
        :meth:`disconnect` to disconnect the object from the signal.

        The default value for `mode` is :attr:`STRONG`. Any decorator can be
        used as argument for `mode` and it is applied to `f`. The result is
        stored internally and is what will be called when the signal is being
        emitted.

        If the result of `mode` returns a false value during emission, the
        connection is removed.

        .. note::

           The return values required by the callable returned by `mode` and
           the one required by a callable passed to `f` using the predefined
           modes are complementary!

           A callable `f` needs to return true to be removed from the
           connections, while a callable returned by the `mode` decorator needs
           to return false.

        Existing modes are listed below.
        """

        mode = mode or self.STRONG
        self.logger.debug("connecting %r with mode %r", f, mode)
        return self._connect(mode(f))

    def context_connect(self, f, mode=None):
        """
        This returns a *context manager*. When entering the context, `f` is
        connected to the :class:`AdHocSignal` using `mode`. When leaving the
        context (no matter whether with or without exception), the connection
        is disconnected.

        .. seealso::

           The returned object is an instance of
           :class:`SignalConnectionContext`.

        """
        return SignalConnectionContext(self, f, mode=mode)

    def fire(self, *args, **kwargs):
        """
        Emit the signal, calling all connected objects in-line with the given
        arguments and in the order they were registered.

        :class:`AdHocSignal` provides full isolation with respect to
        exceptions. If a connected listener raises an exception, the other
        listeners are executed as normal, but the raising listener is removed
        from the signal. The exception is logged to :attr:`logger` and *not*
        re-raised, so that the caller of the signal is also not affected.

        Instead of calling :meth:`fire` explicitly, the ad-hoc signal object
        itself can be called, too.
        """
        for token, wrapper in list(self._connections.items()):
            try:
                keep = wrapper(args, kwargs)
            except Exception:
                self.logger.exception("listener attached to signal raised")
                keep = False
            if not keep:
                del self._connections[token]

    __call__ = fire

AdHocSignal.ASYNC = AdHocSignal.ASYNC_WITH_LOOP(None)


class SyncAdHocSignal(AbstractAdHocSignal):
    """
    A synchronous ad-hoc signal is like :class:`AdHocSignal`, but for
    coroutines instead of ordinary callables.

    .. automethod:: connect

    .. automethod:: context_connect

    .. automethod:: fire

    .. automethod:: disconnect
    """

    def connect(self, coro):
        """
        The coroutine `coro` is connected to the signal. The coroutine must
        return a true value, unless it wants to be disconnected from the
        signal.

        .. note::

           This is different from the return value convention with
           :attr:`AdHocSignal.STRONG` and :attr:`AdHocSignal.WEAK`.

        :meth:`connect` returns a token which can be used with
        :meth:`disconnect` to disconnect the coroutine.
        """
        return self._connect(coro)

    def context_connect(self, coro):
        """
        This returns a *context manager*. When entering the context, `coro` is
        connected to the :class:`SyncAdHocSignal`. When leaving the context (no
        matter whether with or without exception), the connection is
        disconnected.

        .. seealso::

           The returned object is an instance of
           :class:`SignalConnectionContext`.

        """
        return SignalConnectionContext(self, coro)

    @asyncio.coroutine
    def fire(self, *args, **kwargs):
        """
        Emit the signal, calling all coroutines in-line with the given
        arguments and in the order they were registered.

        This is obviously a coroutine.

        Instead of calling :meth:`fire` explicitly, the ad-hoc signal object
        itself can be called, too.
        """
        for token, coro in list(self._connections.items()):
            keep = yield from coro(*args, **kwargs)
            if not keep:
                del self._connections[token]

    __call__ = fire


class SignalConnectionContext:
    def __init__(self, signal, *args, **kwargs):
        self._signal = signal
        self._args = args
        self._kwargs = kwargs

    def __enter__(self):
        try:
            token = self._signal.connect(*self._args, **self._kwargs)
        finally:
            del self._args
            del self._kwargs
        self._token = token
        return token

    def __exit__(self, exc_type, exc_value, traceback):
        self._signal.disconnect(self._token)
        return False


class AbstractSignal(metaclass=abc.ABCMeta):
    def __init__(self):
        super().__init__()
        self._instances = weakref.WeakKeyDictionary()

    @abc.abstractclassmethod
    def make_adhoc_signal(cls):
        pass

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return self._instances[instance]
        except KeyError:
            new = self.make_adhoc_signal()
            self._instances[instance] = new
            return new

    def __set__(self, instance, value):
        raise AttributeError("cannot override Signal attribute")

    def __delete__(self, instance):
        raise AttributeError("cannot override Signal attribute")


class Signal(AbstractSignal):
    """
    A descriptor which returns per-instance :class:`AdHocSignal` objects on
    attribute access.

    Example use:

    .. code-block:: python

       class Foo:
           on_event = Signal()

       f = Foo()
       assert isinstance(f.on_event, AdHocSignal)
       assert f.on_event is f.on_event
       assert Foo().on_event is not f.on_event

    """

    @classmethod
    def make_adhoc_signal(cls):
        return AdHocSignal()


class SyncSignal(AbstractSignal):
    """
    A descriptor which returns per-instance :class:`SyncAdHocSignal` objects on
    attribute access.

    Example use:

    .. code-block:: python

       class Foo:
           on_event = SyncSignal()

       f = Foo()
       assert isinstance(f.on_event, SyncAdHocSignal)
       assert f.on_event is f.on_event
       assert Foo().on_event is not f.on_event
    """

    @classmethod
    def make_adhoc_signal(cls):
        return SyncAdHocSignal()
