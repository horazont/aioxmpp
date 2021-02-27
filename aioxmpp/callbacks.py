########################################################################
# File name: callbacks.py
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

Signal overview
===============

.. autosummary::

   Signal
   SyncSignal
   AdHocSignal
   SyncAdHocSignal

Utilities
---------

.. autofunction:: first_signal

Signal descriptors
------------------

These descriptors can be used on classes to have attributes which are signals:

.. autoclass:: Signal

.. autoclass:: SyncSignal

Signal implementations (ad-hoc signals)
---------------------------------------

Whenever accessing an attribute using the :class:`Signal` or
:class:`SyncSignal` descriptors, an object of one of the following classes is
returned. This is where the behaviour of the signals is specified.

.. autoclass:: AdHocSignal

.. autoclass:: SyncAdHocSignal


Filters
=======

.. autoclass:: Filter

"""

import abc
import asyncio
import collections
import contextlib
import functools
import logging
import types
import weakref


logger = logging.getLogger(__name__)


def log_spawned(logger, fut):
    try:
        result = fut.result()
    except asyncio.CancelledError:
        logger.debug("spawned task was cancelled")
    except:  # NOQA
        logger.warning("spawned task raised exception", exc_info=True)
    else:
        if result is not None:
            logger.info("value returned by spawned task was ignored: %r",
                        result)


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
    def __init__(self, ondata, onerror=None, **kwargs):
        super().__init__(ondata, onerror=onerror, **kwargs)
        self._cancelled = False

    def data(self, data):
        super().data(data)
        return True

    def error(self, exc):
        super().error(exc)
        return True

    def cancel(self):
        self._cancelled = True

    def is_valid(self):
        return not self._cancelled and super().is_valid()


class OneshotAsyncTagListener(OneshotTagListener, AsyncTagListener):
    pass


class FutureListener:
    def __init__(self, fut):
        self.fut = fut

    def data(self, data):
        try:
            self.fut.set_result(data)
        except asyncio.InvalidStateError:
            pass
        return True

    def error(self, exc):
        try:
            self.fut.set_exception(exc)
        except asyncio.InvalidStateError:
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

    .. automethod:: context_connect

    .. automethod:: future

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
       signals connection list. If the callable is a bound method,
       :class:`weakref.WeakMethod` is used automatically.

    For both :attr:`STRONG` and :attr:`WEAK` holds: if the callable returns a
    true value, it is disconnected from the signal.

    .. classmethod:: ASYNC_WITH_LOOP(loop)

       This mode requires an :mod:`asyncio` event loop as argument. When the
       signal is emitted, the callable is not called directly. Instead, it is
       enqueued for calling with the event loop using
       :meth:`asyncio.BaseEventLoop.call_soon`. If :data:`None` is passed as
       `loop`, the loop is obtained from :func:`asyncio.get_event_loop` at
       connect time.

       A strong reference is held to the callable.

       Connections using this mode are never removed automatically from the
       signals connection list. You have to use :meth:`disconnect` explicitly.

    .. attribute:: AUTO_FUTURE

       Instead of a callable, a :class:`asyncio.Future` must be passed when
       using this mode.

       This mode can only be used for signals which send at most one
       positional argument. If no argument is sent, the
       :meth:`~asyncio.Future.set_result` method is called with :data:`None`.

       If one argument is sent and it is an instance of :class:`Exception`, it
       is passed to :meth:`~asyncio.Future.set_exception`. Otherwise, if one
       argument is sent, it is passed to
       :meth:`~asyncio.Future.set_exception`.

       In any case, the future is removed after the next emission of the
       signal.

    .. classmethod:: SPAWN_WITH_LOOP(loop)

       This mode requires an :mod:`asyncio` event loop as argument and a
       coroutine to be passed to :meth:`connect`. If :data:`None` is passed as
       `loop`, the loop is obtained from :func:`asyncio.get_event_loop` at
       connect time.

       When the signal is emitted, the coroutine is spawned using
       :func:`asyncio.ensure_future` in the given `loop`, with the arguments
       passed to the signal.

       A strong reference is held to the coroutine.

       Connections using this mode are never removed automatically from the
       signals connection list. You have to use :meth:`disconnect` explicitly.

       If the spawned coroutine returns with an exception or a non-:data:`None`
       return value, a message is logged, with the following log levels:

       * Return with non-:data:`None` value: :data:`logging.INFO`
       * Raises :class:`asyncio.CancelledError`: :data:`logging.DEBUG`
       * Raises any other exception: :data:`logging.WARNING`

       .. versionadded:: 0.6

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
        if isinstance(f, types.MethodType):
            ref = weakref.WeakMethod(f)
        else:
            ref = weakref.ref(f)
        return functools.partial(cls._weakref_wrapper, ref)

    @classmethod
    def AUTO_FUTURE(cls, f):
        def future_wrapper(args, kwargs):
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

    @classmethod
    def SPAWN_WITH_LOOP(cls, loop):
        loop = asyncio.get_event_loop() if loop is None else loop

        def spawn(f):
            if not asyncio.iscoroutinefunction(f):
                raise TypeError("must be coroutine, got {!r}".format(f))

            def wrapper(args, kwargs):
                task = asyncio.ensure_future(f(*args, **kwargs), loop=loop)
                task.add_done_callback(
                    functools.partial(
                        log_spawned,
                        logger,
                    )
                )
                return True

            return wrapper

        return spawn

    @staticmethod
    def _async_wrapper(f, loop, args, kwargs):
        if kwargs:
            functools.partial(f, *args, **kwargs)
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

    def future(self):
        """
        Return a :class:`asyncio.Future` which has been :meth:`connect`\\ -ed
        using :attr:`AUTO_FUTURE`.

        The token returned by :meth:`connect` is not returned; to remove the
        future from the signal, just cancel it.
        """
        fut = asyncio.Future()
        self.connect(fut, self.AUTO_FUTURE)
        return fut

    __call__ = fire


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
        self.logger.debug("connecting %r", coro)
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

    async def fire(self, *args, **kwargs):
        """
        Emit the signal, calling all coroutines in-line with the given
        arguments and in the order they were registered.

        This is obviously a coroutine.

        Instead of calling :meth:`fire` explicitly, the ad-hoc signal object
        itself can be called, too.
        """
        for token, coro in list(self._connections.items()):
            keep = await coro(*args, **kwargs)
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
    def __init__(self, *, doc=None):
        super().__init__()
        self.__doc__ = doc
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


class Filter:
    """
    A filter chain for arbitrary data.

    This is used for example in :class:`~.stream.StanzaStream` to allow
    services and applications to filter inbound and outbound stanzas.

    Each function registered with the filter receives at least one argument.
    This argument is the object which is to be filtered. The function must
    return the object, a replacement or :data:`None`. If :data:`None` is
    returned, the filter chain aborts and further functions are not called.
    Otherwise, the next function is called with the result of the previous
    function until the filter chain is complete.

    Other arguments passed to :meth:`filter` are passed unmodified to each
    function called; only the first argument is subject to filtering.

    .. versionchanged:: 0.9

       This class was formerly available at :class:`aioxmpp.stream.Filter`.

    .. automethod:: register

    .. automethod:: filter

    .. automethod:: unregister

    .. automethod:: context_register(func[, order])
    """

    class Token:
        def __str__(self):
            return "<{}.{} 0x{:x}>".format(
                type(self).__module__,
                type(self).__qualname__,
                id(self))

    def __init__(self):
        super().__init__()
        self._filter_order = []

    def register(self, func, order):
        """
        Add a function to the filter chain.

        :param func: A callable which is to be added to the filter chain.
        :param order: An object indicating the ordering of the function
                      relative to the others.
        :return: Token representing the registration.

        Register the function `func` as a filter into the chain. `order` must
        be a value which is used as a sorting key to order the functions
        registered in the chain.

        The type of `order` depends on the use of the filter, as does the
        number of arguments and keyword arguments which `func` must accept.
        This will generally be documented at the place where the
        :class:`Filter` is used.

        Functions with the same order are sorted in the order of their
        addition, with the function which was added earliest first.

        Remember that all values passed to `order` which are registered at the
        same time in the same :class:`Filter` need to be totally orderable with
        respect to each other.

        The returned token can be used to :meth:`unregister` a filter.
        """
        token = self.Token()
        self._filter_order.append((order, token, func))
        self._filter_order.sort(key=lambda x: x[0])
        return token

    def filter(self, obj, *args, **kwargs):
        """
        Filter the given object through the filter chain.

        :param obj: The object to filter
        :param args: Additional arguments to pass to each filter function.
        :param kwargs: Additional keyword arguments to pass to each filter
                       function.
        :return: The filtered object or :data:`None`

        See the documentation of :class:`Filter` on how filtering operates.

        Returns the object returned by the last function in the filter chain or
        :data:`None` if any function returned :data:`None`.
        """
        for _, _, func in self._filter_order:
            obj = func(obj, *args, **kwargs)
            if obj is None:
                return None
        return obj

    def unregister(self, token_to_remove):
        """
        Unregister a filter function.

        :param token_to_remove: The token as returned by :meth:`register`.

        Unregister a function from the filter chain using the token returned by
        :meth:`register`.
        """
        for i, (_, token, _) in enumerate(self._filter_order):
            if token == token_to_remove:
                break
        else:
            raise ValueError("unregistered token: {!r}".format(
                token_to_remove))
        del self._filter_order[i]

    @contextlib.contextmanager
    def context_register(self, func, *args):
        """
        :term:`Context manager <context manager>` which temporarily registers a
        filter function.

        :param func: The filter function to register.
        :param order: The sorting key for the filter function.
        :rtype: :term:`context manager`
        :return: Context manager which temporarily registers the filter
                 function.

        If :meth:`register` does not require `order` because it has been
        overridden in a subclass, the `order` argument can be omitted here,
        too.

        .. versionadded:: 0.9
        """
        token = self.register(func, *args)
        try:
            yield
        finally:
            self.unregister(token)


def first_signal(*signals):
    """
    Connect to multiple signals and wait for the first to emit.

    :param signals: Signals to connect to.
    :type signals: :class:`AdHocSignal`
    :return: An awaitable for the first signal to emit.

    The awaitable returns the first argument passed to the signal. If the first
    argument is an exception, the exception is re-raised from the awaitable.

    A common use-case is a situation where a class exposes a "on_finished" type
    signal and an "on_failure" type signal. :func:`first_signal` can be used
    to combine those nicely::

        # e.g. a aioxmpp.im.conversation.AbstractConversation
        conversation = ...
        await first_signal(
            # emits without arguments when the conversation is successfully
            # entered
            conversation.on_enter,
            # emits with an exception when entering the conversation fails
            conversation.on_failure,
        )
        # await first_signal(...) will either raise an exception (failed) or
        # return None (success)

    .. warning::

        Only works with signals which emit with zero or one argument. Signals
        which emit with more than one argument or with keyword arguments are
        silently ignored! (Thus, if only such signals are connected, the
        future will never complete.)

        (This is a side-effect of the implementation of
        :meth:`AdHocSignal.AUTO_FUTURE`).

    .. note::

        Does not work with coroutine signals (:class:`SyncAdHocSignal`).
    """

    fut = asyncio.Future()
    for signal in signals:
        signal.connect(fut, signal.AUTO_FUTURE)
    return fut
