########################################################################
# File name: utils.py
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
:mod:`~aioxmpp.utils` --- Internal utils
========================================

Miscellaneous utilities used throughout the aioxmpp codebase.

.. data:: namespaces

   Collects all the namespaces from the various standards. Each namespace
   is given a shortname and its value is the namespace string.

   .. note:: This is intended to be promoted to the public API in a
             future release. Third-party users should not assign
             short-names for their own namespaces here, but instead
             use a separate instance of :class:`Namespaces`.

.. autoclass:: Namespaces

.. autofunction:: gather_reraise_multi

.. autofunction:: mkdir_exist_ok

.. autofunction:: to_nmtoken

.. autoclass:: LazyTask

.. autoclass:: AlivenessMonitor

.. autodecorator:: magicmethod

.. autofunction:: proxy_property

"""

import asyncio
import base64
import contextlib
import time
import types

import aioxmpp.callbacks
import aioxmpp.errors

import lxml.etree as etree

__all__ = [
    "etree",
    "namespaces",
]


class Namespaces:
    """
    Manage short-hands for XML namespaces.

    Instances of this class may be used to assign mnemonic short-hands
    to XML namespaces, for example:

    .. code-block:: python

        namespaces = Namespaces()
        namespaces.foo = "urn:example:foo"
        namespaces.bar = "urn:example:bar"

    The class ensures that

    1. only one short-hand is bound to each namespace, so continuing the
       example, the following raises :class:`ValueError`:

       .. code-block:: python

           namespace.example_foo = "urn:example:foo"

    2. no short-hand is redefined to point to a different namespace,
       continuing the example, the following raises
       :class:`ValueError`:

       .. code-block:: python

           namespaces.foo = "urn:example:foo:2"

    3. deleting a short-hand is prohibited, the following raises
       :class:`AttributeError`:

       .. code-block:: python

           del namespaces.foo

    The defined short-hands MUST NOT start with an underscore.

    .. note:: This is intended to be promoted to the public API in a
              future release.
    """

    def __init__(self):
        self._all_namespaces = {}

    def __setattr__(self, attr, value):
        if not attr.startswith("_"):
            try:
                existing_attr = self._all_namespaces[value]
                if attr != existing_attr:
                    raise ValueError(
                        "namespace {} already defined as {}".format(
                            value,
                            existing_attr,
                        )
                    )
            except KeyError:
                try:
                    if getattr(self, attr) != value:
                        raise ValueError("inconsistent namespace redefinition")
                except AttributeError:
                    pass
            self._all_namespaces[value] = attr
        super().__setattr__(attr, value)

    def __delattr__(self, attr):
        if not attr.startswith("_"):
            raise AttributeError("deleting short-hands is prohibited")
        super().__delattr__(attr)


namespaces = Namespaces()
namespaces.xmlstream = "http://etherx.jabber.org/streams"
namespaces.client = "jabber:client"
namespaces.starttls = "urn:ietf:params:xml:ns:xmpp-tls"
namespaces.sasl = "urn:ietf:params:xml:ns:xmpp-sasl"
namespaces.stanzas = "urn:ietf:params:xml:ns:xmpp-stanzas"
namespaces.streams = "urn:ietf:params:xml:ns:xmpp-streams"
namespaces.stream_management = "urn:xmpp:sm:3"
namespaces.aioxmpp = "https://zombofant.net/xmlns/aioxmpp"
namespaces.aioxmpp_test = "https://zombofant.net/xmlns/aioxmpp#test"
namespaces.aioxmpp_internal = "https://zombofant.net/xmlns/aioxmpp#internal"
namespaces.xml = "http://www.w3.org/XML/1998/namespace"


@contextlib.contextmanager
def background_task(coro, logger):
    def log_result(task):
        try:
            result = task.result()
        except asyncio.CancelledError:
            logger.debug("background task terminated by CM exit: %r",
                         task)
        except:  # NOQA
            logger.error("background task failed: %r",
                         task,
                         exc_info=True)
        else:
            if result is not None:
                logger.info("background task (%r) returned a value: %r",
                            task,
                            result)

    task = asyncio.ensure_future(coro)
    task.add_done_callback(log_result)
    try:
        yield
    finally:
        task.cancel()


class magicmethod:
    """
    Decorator for methods that makes them work as instance *and* class
    method.  The first argument will be the class if called on the
    class and the instance when called on the instance.
    """

    __slots__ = ("_f",)

    def __init__(self, f):
        super().__init__()
        self._f = f

    def __get__(self, instance, class_):
        if instance is None:
            return types.MethodType(self._f, class_)
        return types.MethodType(self._f, instance)


def mkdir_exist_ok(path):
    """
    Create a directory (including parents) if it does not exist yet.

    :param path: Path to the directory to create.
    :type path: :class:`pathlib.Path`

    Uses :meth:`pathlib.Path.mkdir`; if the call fails with
    :class:`FileNotFoundError` and `path` refers to a directory, it is treated
    as success.
    """

    try:
        path.mkdir(parents=True)
    except FileExistsError:
        if not path.is_dir():
            raise


class LazyTask(asyncio.Future):
    """
    :class:`asyncio.Future` subclass which spawns a coroutine when it is first
    awaited.

    :param coroutine_function: The coroutine function to invoke.
    :param args: Arguments to pass to `coroutine_function`.

    :class:`LazyTask` objects are awaitable. When the first attempt to await
    them is made, the `coroutine_function` is started with the given `args` and
    the result is awaited. Any further awaits on the :class:`LazyTask` will
    await the same coroutine.
    """

    def __init__(self, coroutine_function, *args):
        super().__init__()
        self.__coroutine_function = coroutine_function
        self.__args = args
        self.__task = None

    def add_done_callback(self, cb, *args):
        self.__start_task()
        return super().add_done_callback(cb, *args)

    def __start_task(self):
        if self.__task is None:
            self.__task = asyncio.ensure_future(
                self.__coroutine_function(*self.__args)
            )
            self.__task.add_done_callback(self.__task_done)

    def __task_done(self, task):
        if task.exception():
            self.set_exception(task.exception())
        else:
            self.set_result(task.result())

    def __iter__(self):
        self.__start_task()
        return iter(self.__task)

    if hasattr(asyncio.Future, "__await__"):
        def __await__(self):
            self.__start_task()
            if hasattr(self.__task, "__await__"):
                return self.__task.__await__()
            else:
                return super().__await__()


async def gather_reraise_multi(*fut_or_coros, message="gather_reraise_multi"):
    """
    Wrap all the arguments `fut_or_coros` in futures with
    :func:`asyncio.ensure_future` and wait until all of them are finish or
    fail.

    :param fut_or_coros: the futures or coroutines to wait for
    :type fut_or_coros: future or coroutine
    :param message: the message included with the raised
        :class:`aioxmpp.errors.GatherError` in the case of failure.
    :type message: :class:`str`
    :returns: the list of the results of the arguments.
    :raises aioxmpp.errors.GatherError: if any of the futures or
        coroutines fail.

    If an exception was raised, reraise all exceptions wrapped in a
    :class:`aioxmpp.errors.GatherError` with the message set to
    `message`.

    .. note::

       This is similar to the standard function
       :func:`asyncio.gather`, but avoids the in-band signalling of
       raised exceptions as return values, by raising exceptions bundled
       as a :class:`aioxmpp.errors.GatherError`.

    .. note::

       Use this function only if you are either

       a) not interested in the return values, or

       b) only interested in the return values if all futures are
          successful.
    """
    todo = [asyncio.ensure_future(fut_or_coro) for fut_or_coro in fut_or_coros]
    if not todo:
        return []

    await asyncio.wait(todo)
    results = []
    exceptions = []
    for fut in todo:
        if fut.exception() is not None:
            exceptions.append(fut.exception())
        else:
            results.append(fut.result())
    if exceptions:
        raise aioxmpp.errors.GatherError(message, exceptions)
    return results


def to_nmtoken(rand_token):
    """
    Convert a (random) token given as raw :class:`bytes` or
    :class:`int` to a valid NMTOKEN
    <https://www.w3.org/TR/xml/#NT-Nmtoken>.

    The encoding as a valid nmtoken is injective, ensuring that two
    different inputs cannot yield the same token. Nevertheless, it is
    recommended to only use one kind of inputs (integers or bytes of a
    consistent length) in one context.
    """

    if isinstance(rand_token, int):
        rand_token = rand_token.to_bytes(
            (rand_token.bit_length() + 7) // 8,
            "little"
        )
        e = base64.urlsafe_b64encode(rand_token).rstrip(b"=").decode("ascii")
        return ":" + e

    if isinstance(rand_token, bytes):
        e = base64.urlsafe_b64encode(rand_token).rstrip(b"=").decode("ascii")
        if not e:
            e = "."
        return  e

    raise TypeError("rand_token musst be a bytes or int instance")


class AlivenessMonitor:
    """
    Monitors aliveness of a data stream.

    .. versionadded:: 0.10

    :param loop: The event loop to operate the checks in.
    :type loop: :class:`asyncio.BaseEventLoop`

    This class is a utility class to implement a traffic-efficient timeout
    mechanism.

    This class can be used to monitor a stream if it is possible to ask the
    remote party send some data (classic ping mechanism). It works particularly
    well if the remote party will send data even without being specifically
    asked for it (saves traffic).

    It is notabily not a mean to enforce a maximum acceptable round-trip time.
    Quite on the contrary, this class was designed specifically to provide a
    reliable experience even *without* an upper bound on the round-trip time.

    To use this class, the using code has to configure the
    :attr:`deadtime_soft_limit`, :attr:`deadtime_hard_limit`, subscribe to the
    signals below and call :meth:`notify_received` whenever *any* data is
    received from the peer.

    There exist two timers, the *soft limit timer* and the *hard limit timer*
    (configured by the respective limit attributes). When the class is
    instantiated, the timers are reset to zero (*but* they start running
    immediately!).

    When a timer exceeds its respective limit, its corresponding signal is
    emitted. The signal is not re-emitted until the next call of
    :meth:`notfiy_received`.

    When :meth:`notify_received` is called, the timers are reset to zero.

    This allows for the following features:

    - Keep a stream alive on a high-latency link as long as data is pouring in.

      This is very useful on saturated (mobile) links. Imagine firing a MAM
      query and a bunch of avatar requests after connecting. With naive ping
      logic, this would easily cause the stream to be considered dead because
      the round-trip time is extremely high.

      However, with this logic, as long as data is pouring in, the stream is
      considered alive.

    - When using the soft limit to trigger a ping and a reasonable difference
      between the soft and the hard limit timeout, this logic gracefully
      reverts to classic pinging when no traffic is seen on the stream.

    - If the peer is pinging us in an interval which works for us (i.e. is less
      than the soft limit), we don’t need to ping the peer; no extra logic
      required.

    This mechanism is used by :class:`aioxmpp.protocol.XMLStream`.

    .. signal:: on_deadtime_soft_limit_tripped()

        Emits when the :attr:`deadtime_soft_limit` expires.

    .. signal:: on_deadtime_hard_limit_tripped()

        Emits when the :attr:`deadtime_hard_limit` expires.

    .. automethod:: notify_received

    .. autoattribute:: deadtime_soft_limit
        :annotation: = None

    .. autoattribute:: deadtime_hard_limit
        :annotation: = None

    """

    on_deadtime_soft_limit_tripped = aioxmpp.callbacks.Signal()
    on_deadtime_hard_limit_tripped = aioxmpp.callbacks.Signal()

    def __init__(self, loop):
        super().__init__()
        self._loop = loop
        self._soft_limit = None
        self._soft_limit_timer = None
        self._soft_limit_tripped = False
        self._hard_limit = None
        self._hard_limit_timer = None
        self._hard_limit_tripped = False
        self._reset_trips()

    def _trip_soft_limit(self):
        if self._soft_limit_tripped:
            return
        self._soft_limit_tripped = True
        self.on_deadtime_soft_limit_tripped()

    def _trip_hard_limit(self):
        if self._hard_limit_tripped:
            return
        self._hard_limit_tripped = True
        self.on_deadtime_hard_limit_tripped()

    def _retrigger_timers(self):
        now = time.monotonic()

        if self._soft_limit_timer is not None:
            self._soft_limit_timer.cancel()
            self._soft_limit_timer = None

        if self._soft_limit is not None:
            self._soft_limit_timer = self._loop.call_later(
                self._soft_limit.total_seconds() - (now - self._last_rx),
                self._trip_soft_limit
            )

        if self._hard_limit_timer is not None:
            self._hard_limit_timer.cancel()
            self._hard_limit_timer = None

        if self._hard_limit is not None:
            self._hard_limit_timer = self._loop.call_later(
                self._hard_limit.total_seconds() - (now - self._last_rx),
                self._trip_hard_limit
            )

    def _reset_trips(self):
        self._soft_limit_tripped = False
        self._hard_limit_tripped = False
        self._last_rx = time.monotonic()

    def notify_received(self):
        """
        Inform the aliveness check that something was received.

        Resets the internal soft/hard limit timers.
        """
        self._reset_trips()
        self._retrigger_timers()

    @property
    def deadtime_soft_limit(self):
        """
        Soft limit for the timespan in which no data is received in the stream.

        When the last data reception was longer than this limit ago,
        :meth:`on_deadtime_soft_limit_tripped` emits once.

        Changing this makes the monitor re-check its limits immediately. Setting
        this to :data:`None` disables the soft limit check.

        Note that setting this to a value greater than
        :attr:`deadtime_hard_limit` means that the hard limit will fire first.
        """
        return self._soft_limit

    @deadtime_soft_limit.setter
    def deadtime_soft_limit(self, value):
        if self._soft_limit_timer is not None:
            self._soft_limit_timer.cancel()
        self._soft_limit = value
        self._retrigger_timers()

    @property
    def deadtime_hard_limit(self):
        """
        Hard limit for the timespan in which no data is received in the stream.

        When the last data reception was longer than this limit ago,
        :meth:`on_deadtime_hard_limit_tripped` emits once.

        Changing this makes the monitor re-check its limits immediately. Setting
        this to :data:`None` disables the hard limit check.

        Note that setting this to a value less than
        :attr:`deadtime_soft_limit` means that the hard limit will fire first.
        """
        return self._hard_limit

    @deadtime_hard_limit.setter
    def deadtime_hard_limit(self, value):
        if self._hard_limit_timer is not None:
            self._hard_limit_timer.cancel()
        self._hard_limit = value
        self._retrigger_timers()


def proxy_property(owner_attr, member_attr, *,
                   readonly=False,
                   allow_delete=False):
    """
    Proxy a property of a member.

    :param owner_attr: The name of the attribute at which the member can
        be found.
    :type owner_attr: :class:`str`
    :param member_attr: The name of the member property to proxy.
    :type member_attr: :class:`str`
    :param readonly: If true, the proxied property will not be writable, even
        if the original property is writable.
    :type readonly: :class:`bool`
    :param allow_delete: If true, the ``del`` operator is allowed on the
        proxy property and will be forwarded to the target property.
    :type allow_delete: :class:`bool`

    .. versionadded:: 0.11.0

    This can be useful when combining classes via composition instead of
    inheritance.

    It is not necessary to set `readonly` to true if the target property is
    already readonly.
    """
    ga = getattr
    sa = setattr
    da = delattr

    def getter(instance):
        return ga(ga(instance, owner_attr), member_attr)

    if readonly:
        setter = None
    else:
        def setter(instance, value):
            return sa(ga(instance, owner_attr), member_attr, value)

    if allow_delete:
        def deleter(instance):
            da(ga(instance, owner_attr), member_attr)
    else:
        deleter = None

    return property(
        getter,
        setter,
        deleter,
    )
