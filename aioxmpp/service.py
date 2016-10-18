########################################################################
# File name: service.py
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
:mod:`~aioxmpp.service` --- Utilities for implementing :class:`~.Client` services
#################################################################################

Protocol extensions or in general support for parts of the XMPP protocol are
implemented using :class:`Service` classes, or rather, classes which use the
:class:`Meta` metaclass.

Both of these are provided in this module. To reduce the boilerplate required
to develop services, :ref:`decorators <api-aioxmpp.service-decorators>` are
provided which can be used to easily register coroutines and functions as
stanza handlers, filters and others.

.. autoclass:: Service

.. _api-aioxmpp.service-decorators:

Decorators
==========

These decorators provide special functionality when used on methods of
:class:`Service` subclasses.

.. note::

   Inheritance from classes which have any of these decorators on any of its
   methods is forbidden currently, because of the ambiguities which arise.

.. note::

   These decorators work only on methods declared on :class:`Service`
   subclasses, as their functionality are implemented in cooperation with the
   :class:`Meta` metaclass and :class:`Service` itself.

.. autodecorator:: iq_handler

.. autodecorator:: message_handler

.. autodecorator:: presence_handler

.. autodecorator:: inbound_message_filter()

.. autodecorator:: inbound_presence_filter()

.. autodecorator:: outbound_message_filter()

.. autodecorator:: outbound_presence_filter()

.. autodecorator:: depsignal

Test functions
--------------

.. autofunction:: is_iq_handler

.. autofunction:: is_message_handler

.. autofunction:: is_presence_handler

.. autofunction:: is_inbound_message_filter

.. autofunction:: is_inbound_presence_filter

.. autofunction:: is_outbound_message_filter

.. autofunction:: is_outbound_presence_filter

.. autofunction:: is_depsignal_handler

Metaclass
=========

.. autoclass:: Meta([inherit_dependencies=True])


"""

import abc
import asyncio
import collections
import contextlib
import logging
import warnings

import aioxmpp.callbacks
import aioxmpp.stream


def _automake_magic_attr(obj):
    obj._aioxmpp_service_handlers = getattr(
        obj, "_aioxmpp_service_handlers", set()
    )
    return obj._aioxmpp_service_handlers


def _get_magic_attr(obj):
    return obj._aioxmpp_service_handlers


def _has_magic_attr(obj):
    return hasattr(
        obj, "_aioxmpp_service_handlers"
    )


class Meta(abc.ABCMeta):
    """
    The metaclass for services. The :class:`Service` class uses it and in
    general you should just inherit from :class:`Service` and define the
    dependency attributes as needed.

    Services have dependencies. A :class:`Meta` instance (i.e. a service class)
    can declare dependencies using the following two attributes.

    .. attribute:: ORDER_BEFORE

       An iterable of :class:`Service` classes before which the class which is
       currently being declared needs to be instanciated.

       Thus, any service which occurs in :attr:`ORDER_BEFORE` will be
       instanciated *after* this class (if at all). Think of it as "*this*
       class is ordered *before* the classes in this attribute".

       .. versionadded:: 0.3

    .. attribute:: SERVICE_BEFORE

       Before 0.3, this was the name of the :attr:`ORDER_BEFORE` attribute. It
       is still supported, but use emits a :data:`DeprecationWarning`. It must
       not be mixed with :attr:`ORDER_BEFORE` or :attr:`ORDER_AFTER` on a class
       declaration, or the declaration will raise :class:`ValueError`.

       .. deprecated:: 0.3

          Support for this attribute will be removed in 1.0; starting with 1.0,
          using this attribute will raise a :class:`TypeError` on class
          declaration and a :class:`AttributeError` when accessing it on a
          class or instance.

    .. attribute:: ORDER_AFTER

       An iterable of :class:`Service` classes which will be instanciated
       *before* the class which is being declraed.

       Classes which are declared in this attribute are always instanciated
       before this class is instantiated. Think of it as "*this* class is
       ordered *after* the classes in this attribute".

       .. versionadded:: 0.3

    .. attribute:: SERVICE_AFTER

       Before 0.3, this was the name of the :attr:`ORDER_AFTER` attribute. It
       is still supported, but use emits a :data:`DeprecationWarning`. It must
       not be mixed with :attr:`ORDER_BEFORE` or :attr:`ORDER_AFTER` on a class
       declaration, or the declaration will raise :class:`ValueError`.

       .. deprecated:: 0.3

          See :attr:`SERVICE_BEFORE` for details on the deprecation cycle.

    The dependencies are inherited from bases unless the `inherit_dependencies`
    keyword argument is set to false.

    After a class has been instanciated, the full set of dependencies is
    provided in the attributes, including all transitive relationships. These
    attributes are updated when new classes are declared.

    Dependency relationships must not have cycles; a cycle results in a
    :class:`ValueError` when the class causing the cycle is declared.

    Example::

        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            ORDER_BEFORE = [Bar]

        class Fourth(metaclass=service.Meta):
            ORDER_BEFORE = [Bar]

    ``Baz`` and ``Fourth`` will be instanciated before ``Bar`` and ``Bar`` will
    be instanciated before ``Foo``. There is no dependency relationship between
    ``Baz`` and ``Fourth``.

    Inheritance works too::

        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        class Baz(Bar):
            # has ORDER_BEFORE == {Foo}
            pass

        class Fourth(Bar, inherit_dependencies=False):
            # has empty ORDER_BEFORE
            pass

    """

    @classmethod
    def transitive_collect(mcls, classes, attr, seen):
        for cls in classes:
            yield cls
            yield from mcls.transitive_collect(getattr(cls, attr), attr, seen)

    @classmethod
    def collect_and_inherit(mcls, bases, namespace, attr,
                            inherit_dependencies):
        classes = set(namespace.get(attr, []))
        if inherit_dependencies:
            for base in bases:
                if isinstance(base, mcls):
                    classes.update(getattr(base, attr))
        classes.update(
            mcls.transitive_collect(
                list(classes),
                attr,
                set())
        )
        return classes

    def __new__(mcls, name, bases, namespace, inherit_dependencies=True):
        if "SERVICE_BEFORE" in namespace or "SERVICE_AFTER" in namespace:
            if "ORDER_BEFORE" in namespace or "ORDER_AFTER" in namespace:
                raise ValueError("declaration mixes old and new ordering "
                                 "attribute names (SERVICE_* vs. ORDER_*)")
            warnings.warn(
                "SERVICE_BEFORE/AFTER used on class; use ORDER_BEFORE/AFTER",
                DeprecationWarning)
            try:
                namespace["ORDER_BEFORE"] = namespace.pop("SERVICE_BEFORE")
            except KeyError:
                pass
            try:
                namespace["ORDER_AFTER"] = namespace.pop("SERVICE_AFTER")
            except KeyError:
                pass

        orig_after = set(namespace.get("ORDER_AFTER", set()))

        before_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "ORDER_BEFORE",
            inherit_dependencies)

        after_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "ORDER_AFTER",
            inherit_dependencies)

        if before_classes & after_classes:
            raise ValueError("dependency loop: {} loops through {}".format(
                name,
                next(iter(before_classes & after_classes)).__qualname__
            ))

        for base in bases:
            if hasattr(base, "SERVICE_HANDLERS") and base.SERVICE_HANDLERS:
                raise TypeError(
                    "inheritance from service class with handlers is forbidden"
                )

        namespace["ORDER_BEFORE"] = set(before_classes)
        namespace["ORDER_AFTER"] = set(after_classes)

        SERVICE_HANDLERS = []
        existing_handlers = set()

        for attr_name, attr_value in namespace.items():
            if not _has_magic_attr(attr_value):
                continue

            new_handlers = _get_magic_attr(attr_value)

            unique_handlers = {
                spec.key
                for spec in new_handlers
                if spec.is_unique
            }

            conflicting = unique_handlers & existing_handlers
            if conflicting:
                key = next(iter(conflicting))
                obj = next(iter(
                    obj
                    for obj_key, obj in SERVICE_HANDLERS
                    if obj_key == key
                ))

                raise TypeError(
                    "handler conflict between {!r} and {!r}: "
                    "both want to use {!r}".format(
                        obj,
                        attr_value,
                        key,
                    )
                )

            existing_handlers |= unique_handlers

            for spec in new_handlers:
                missing = spec.require_deps - orig_after
                if missing:
                    raise TypeError(
                        "decorator requires dependency {!r} "
                        "but it is not declared".format(
                            next(iter(missing))
                        )
                    )

                SERVICE_HANDLERS.append(
                    (spec.key, attr_value)
                )

        namespace["SERVICE_HANDLERS"] = tuple(SERVICE_HANDLERS)

        return super().__new__(mcls, name, bases, namespace)

    def __init__(self, name, bases, namespace, inherit_dependencies=True):
        super().__init__(name, bases, namespace)
        for cls in self.ORDER_BEFORE:
            cls.ORDER_AFTER.add(self)
        for cls in self.ORDER_AFTER:
            cls.ORDER_BEFORE.add(self)
        self.SERVICE_BEFORE = self.ORDER_BEFORE
        self.SERVICE_AFTER = self.ORDER_AFTER

    def __lt__(self, other):
        return other in self.ORDER_BEFORE

    def __le__(self, other):
        return self < other


class Service(metaclass=Meta):
    """
    A :class:`Service` is used to implement XMPP or XEP protocol parts, on top
    of the more or less fixed stanza handling implemented in
    :mod:`aioxmpp.node` and :mod:`aioxmpp.stream`.

    :class:`Service` is a base class which can be used by extension developers
    to implement support for custom or standardized protocol extensions. Some
    of the features for which :mod:`aioxmpp` has support are also implemented
    using :class:`Service` subclasses.

    `client` must be a :class:`~.Client` to which the service will be attached.
    The `client` cannot be changed later, for the sake of simplicity.

    `logger_base` may be a :class:`logging.Logger` instance or :data:`None`. If
    it is :data:`None`, a logger is automatically created, by taking the fully
    qualified name of the :class:`Service` subclass which is being
    instanciated. Otherwise, the logger is passed to :meth:`derive_logger` and
    the result is used as value for the :attr:`logger` attribute.

    To implement your own service, derive from :class:`Service`. If your
    service depends on other services (such as :mod:`aioxmpp.pubsub` or
    :mod:`aioxmpp.disco`), these dependencies *must* be declared as documented
    in the service meta class :class:`Meta`.

    To stay forward compatible, accept arbitrary keyword arguments and pass
    them down to :class:`Service`. As it is not possible to directly pass
    arguments to :class:`Service`\ s on construction (due to the way
    :meth:`aioxmpp.Client.summon` works), there is no need for you
    to introduce custom arguments, and thus there should be no conflicts.

    .. autoattribute:: client

    .. autoattribute:: dependencies

    .. automethod:: derive_logger

    .. automethod:: shutdown
    """

    def __init__(self, client, *, logger_base=None, dependencies={}):
        super().__init__()
        self.__context = contextlib.ExitStack()
        self.__client = client
        self.__dependencies = dependencies

        if logger_base is None:
            self.logger = logging.getLogger(".".join([
                type(self).__module__, type(self).__qualname__
            ]))
        else:
            self.logger = self.derive_logger(logger_base)

        for (handler_cm, additional_args), obj in self.SERVICE_HANDLERS:
            self.__context.enter_context(
                handler_cm(self,
                           self.__client.stream,
                           obj.__get__(self, type(self)),
                           *additional_args)
            )

    def derive_logger(self, logger):
        """
        Return a child of `logger` specific for this instance. This is called
        after :attr:`client` has been set, from the constructor.

        The child name is calculated by the default implementation in a way
        specific for aioxmpp services; it is not meant to be used by
        non-:mod:`aioxmpp` classes; do not rely on the way how the child name
        is calculated.
        """
        parts = type(self).__module__.split(".")[1:]
        if parts[-1] == "service" and len(parts) > 1:
            del parts[-1]

        return logger.getChild(".".join(
            parts+[type(self).__qualname__]
        ))

    @property
    def client(self):
        """
        The client to which the :class:`Service` is bound. This attribute is
        read-only.

        If the service has been shut down using :meth:`shutdown`, this reads as
        :data:`None`.
        """
        return self.__client

    @property
    def dependencies(self):
        """
        When the service is instantiated through
        :meth:`~.Client.summon`, this attribute holds a mapping which maps the
        service classes contained in the :attr:`~.Meta.ORDER_BEFORE` attribute
        to the respective instances related to the :attr:`client`.

        This is the preferred way to obtain dependencies specified via
        :attr:`~.Meta.ORDER_BEFORE`.
        """
        return self.__dependencies

    @asyncio.coroutine
    def _shutdown(self):
        """
        Actual implementation of the shut down process.

        This *must* be called using super from inheriting classes after their
        own shutdown procedure. Inheriting classes *must* override this method
        instead of :meth:`shutdown`.
        """

    @asyncio.coroutine
    def shutdown(self):
        """
        Close the service and wait for it to completely shut down.

        Some services which are still running may depend on this service. In
        that case, the service may refuse to shut down instead of shutting
        down, by raising a :class:`RuntimeError` exception.

        .. note::

           Developers creating subclasses of :class:`Service` to implement
           services should not override this method. Instead, they should
           override the :meth:`_shutdown` method.

        """
        yield from self._shutdown()
        self.__context.close()
        self.__client = None


class HandlerSpec(collections.namedtuple(
        "HandlerSpec",
        [
            "is_unique",
            "key",
            "require_deps",
        ])):
    def __new__(cls, key, is_unique=True, require_deps=()):
        return super().__new__(cls, is_unique, key, frozenset(require_deps))


def _apply_iq_handler(instance, stream, func, type_, payload_cls):
    return aioxmpp.stream.iq_handler(stream, type_, payload_cls, func)


def _apply_message_handler(instance, stream, func, type_, from_):
    return aioxmpp.stream.message_handler(stream, type_, from_, func)


def _apply_presence_handler(instance, stream, func, type_, from_):
    return aioxmpp.stream.presence_handler(stream, type_, from_, func)


def _apply_inbound_message_filter(instance, stream, func):
    return aioxmpp.stream.stanza_filter(
        stream.service_inbound_message_filter,
        func,
        type(instance),
    )


def _apply_inbound_presence_filter(instance, stream, func):
    return aioxmpp.stream.stanza_filter(
        stream.service_inbound_presence_filter,
        func,
        type(instance),
    )


def _apply_outbound_message_filter(instance, stream, func):
    return aioxmpp.stream.stanza_filter(
        stream.service_outbound_message_filter,
        func,
        type(instance),
    )


def _apply_outbound_presence_filter(instance, stream, func):
    return aioxmpp.stream.stanza_filter(
        stream.service_outbound_presence_filter,
        func,
        type(instance),
    )


def _apply_connect_depsignal(instance, stream, func, dependency, signal_name,
                             mode):
    signal = getattr(instance.dependencies[dependency], signal_name)
    if mode is None:
        return signal.context_connect(func)
    else:
        return signal.context_connect(func, mode)


def iq_handler(type_, payload_cls):
    """
    Register the decorated coroutine function as IQ request handler.

    :param type_: IQ type to listen for
    :type type_: :class:`~.IQType`
    :param payload_cls: Payload XSO class to listen for
    :type payload_cls: :class:`~.XSO` subclass
    :raise TypeError: if the decorated object is not a coroutine function

    .. seealso::

       :meth:`~.StanzaStream.register_iq_request_coro`
          for more details on the `type_` and `payload_cls` arguments

    """

    def decorator(f):
        if not asyncio.iscoroutinefunction(f):
            raise TypeError("a coroutine function is required")

        _automake_magic_attr(f).add(
            HandlerSpec(
                (_apply_iq_handler, (type_, payload_cls)),
            )
        )
        return f
    return decorator


def message_handler(type_, from_):
    """
    Register the decorated function as message handler.

    :param type_: Message type to listen for
    :type type_: :class:`~.MessageType`
    :param from_: Sender JIDs to listen for
    :type from_: :class:`aioxmpp.JID` or :data:`None`
    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :meth:`~.StanzaStream.register_message_callback`
          for more details on the `type_` and `from_` arguments
    """

    def decorator(f):
        if asyncio.iscoroutinefunction(f):
            raise TypeError("message_handler must not be a coroutine function")

        _automake_magic_attr(f).add(
            HandlerSpec(
                (_apply_message_handler, (type_, from_))
            )
        )
        return f
    return decorator


def presence_handler(type_, from_):
    """
    Register the decorated function as presence stanza handler.

    :param type_: Presence type to listen for
    :type type_: :class:`~.PresenceType`
    :param from_: Sender JIDs to listen for
    :type from_: :class:`aioxmpp.JID` or :data:`None`
    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :meth:`~.StanzaStream.register_presence_callback`
          for more details on the `type_` and `from_` arguments
    """

    def decorator(f):
        if asyncio.iscoroutinefunction(f):
            raise TypeError(
                "presence_handler must not be a coroutine function"
            )

        _automake_magic_attr(f).add(
            HandlerSpec(
                (_apply_presence_handler, (type_, from_)),
            )
        )
        return f
    return decorator


def inbound_message_filter(f):
    """
    Register the decorated function as a service-level inbound message filter.

    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :class:`StanzaStream`
          for important remarks regarding the use of stanza filters.

    """

    if asyncio.iscoroutinefunction(f):
        raise TypeError(
            "inbound_message_filter must not be a coroutine function"
        )

    _automake_magic_attr(f).add(
        HandlerSpec(
            (_apply_inbound_message_filter, ())
        ),
    )
    return f


def inbound_presence_filter(f):
    """
    Register the decorated function as a service-level inbound presence filter.

    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :class:`StanzaStream`
          for important remarks regarding the use of stanza filters.

    """

    if asyncio.iscoroutinefunction(f):
        raise TypeError(
            "inbound_presence_filter must not be a coroutine function"
        )

    _automake_magic_attr(f).add(
        HandlerSpec(
            (_apply_inbound_presence_filter, ())
        ),
    )
    return f


def outbound_message_filter(f):
    """
    Register the decorated function as a service-level outbound message filter.

    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :class:`StanzaStream`
          for important remarks regarding the use of stanza filters.

    """

    if asyncio.iscoroutinefunction(f):
        raise TypeError(
            "outbound_message_filter must not be a coroutine function"
        )

    _automake_magic_attr(f).add(
        HandlerSpec(
            (_apply_outbound_message_filter, ())
        ),
    )
    return f


def outbound_presence_filter(f):
    """
    Register the decorated function as a service-level outbound presence
    filter.

    :raise TypeError: if the decorated object is a coroutine function

    .. seealso::

       :class:`StanzaStream`
          for important remarks regarding the use of stanza filters.

    """

    if asyncio.iscoroutinefunction(f):
        raise TypeError(
            "outbound_presence_filter must not be a coroutine function"
        )

    _automake_magic_attr(f).add(
        HandlerSpec(
            (_apply_outbound_presence_filter, ())
        ),
    )
    return f


def _depsignal_spec(class_, signal_name, f, defer):
    signal = getattr(class_, signal_name)

    if isinstance(signal, aioxmpp.callbacks.SyncSignal):
        if not asyncio.iscoroutinefunction(f):
            raise TypeError(
                "a coroutine function is required for this signal"
            )
        if defer:
            raise ValueError(
                "cannot use defer with this signal"
            )
        mode = None
    else:
        if asyncio.iscoroutinefunction(f):
            if defer:
                mode = aioxmpp.callbacks.AdHocSignal.SPAWN_WITH_LOOP(None)
            else:
                raise TypeError(
                    "cannot use coroutine function with this signal"
                    " without defer"
                )
        elif defer:
            mode = aioxmpp.callbacks.AdHocSignal.ASYNC_WITH_LOOP(None)
        else:
            mode = aioxmpp.callbacks.AdHocSignal.STRONG

    return HandlerSpec(
        (
            _apply_connect_depsignal,
            (
                class_,
                signal_name,
                mode,
            )
        ),
        require_deps=(class_,)
    )


def depsignal(class_, signal_name, *, defer=False):
    """
    Connect the decorated method or coroutine method to the addressed signal on
    a class on which the service depends.

    :param class_: A service class which is listed in the
                   :attr:`~.Meta.ORDERED_AFTER` relationship.
    :type class_: :class:`Service` class
    :param signal_name: Attribute name of the signal to connect to
    :type signal_name: :class:`str`
    :param defer: Flag indicating whether deferred execution of the decorated
                  method is desired; see below for details.
    :type defer: :class:`bool`

    The signal is discovered by accessing the attribute with the name
    `signal_name` on the given `class_`.

    If the signal is a :class:`.callbacks.Signal` and `defer` is false, the
    decorated object is connected using the default
    :attr:`~.callbacks.AdHocSignal.STRONG` mode.

    If the signal is a :class:`.callbacks.Signal` and `defer` is true and the
    decorated object is a coroutine function, the
    :attr:`~.callbacks.AdHocSignal.SPAWN_WITH_LOOP` mode with the default
    asyncio event loop is used. If the decorated object is not a coroutine
    function, :attr:`~.callbacks.AdHocSignal.ASYNC_WITH_LOOP` is used instead.

    If the signal is a :class:`.callbacks.SyncSignal`, `defer` must be false
    and the decorated object must be a coroutine function.
    """

    def decorator(f):
        _automake_magic_attr(f).add(
            _depsignal_spec(class_, signal_name, f, defer)
        )
        return f
    return decorator


def is_iq_handler(type_, payload_cls, coro):
    """
    Return true if `coro` has been decorated with :func:`iq_handler` for the
    given `type_` and `payload_cls`.
    """

    try:
        handlers = _get_magic_attr(coro)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_iq_handler, (type_, payload_cls)),
    ) in handlers


def is_message_handler(type_, from_, cb):
    """
    Return true if `cb` has been decorated with :func:`message_handler` for the
    given `type_` and `from_`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_message_handler, (type_, from_))
    ) in handlers


def is_presence_handler(type_, from_, cb):
    """
    Return true if `cb` has been decorated with :func:`presence_handler` for
    the given `type_` and `from_`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_presence_handler, (type_, from_))
    ) in handlers


def is_inbound_message_filter(cb):
    """
    Return true if `cb` has been decorated with :func:`inbound_message_filter`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_inbound_message_filter, ())
    ) in handlers


def is_inbound_presence_filter(cb):
    """
    Return true if `cb` has been decorated with
    :func:`inbound_presence_filter`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_inbound_presence_filter, ())
    ) in handlers


def is_outbound_message_filter(cb):
    """
    Return true if `cb` has been decorated with
    :func:`outbound_message_filter`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_outbound_message_filter, ())
    ) in handlers


def is_outbound_presence_filter(cb):
    """
    Return true if `cb` has been decorated with
    :func:`outbound_presence_filter`.
    """

    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return HandlerSpec(
        (_apply_outbound_presence_filter, ())
    ) in handlers


def is_depsignal_handler(class_, signal_name, cb, *, defer=False):
    """
    Return true if `cb` has been decorated with :func:`depsignal` for the given
    signal, class and connection mode.
    """
    try:
        handlers = _get_magic_attr(cb)
    except AttributeError:
        return False

    return _depsignal_spec(class_, signal_name, cb, defer) in handlers
