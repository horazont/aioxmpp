"""
:mod:`~aioxmpp.service` --- Utilities for implementing :class:`~aioxmpp.node.AbstractClient` services
#####################################################################################################

Protocol extensions or in general support for parts of the XMPP protocol are
implemented using :class:`Service` classes, or rather, classes which use the
:class:`Meta` metaclass.

Both of these are provided in this module.

.. autoclass:: Service

.. autoclass:: Meta([inherit_dependencies=True])


"""

import abc
import asyncio
import logging


class Meta(abc.ABCMeta):
    """
    The metaclass for services. The :class:`Service` class uses it and in
    general you should just inherit from :class:`Service` and define the
    dependency attributes as needed.

    Services have dependencies. A :class:`Meta` instance (i.e. a service class)
    can declare dependencies using the following two attributes.

    .. attribute:: SERVICE_BEFORE

       An iterable of :class:`Service` classes before which the class which is
       currently being declared needs to be instanciated.

       Thus, any service which occurs in :attr:`SERVICE_BEFORE` will be
       instanciated *after* this class (if at all).

    .. attribute:: SERVICE_AFTER

       An iterable of :class:`Service` classes which would be instanciated
       after the class which is currently being declared, it at all.

       Classes which are declared in this attribute are not forced to be
       instanciated (unlike with :attr:`SERVICE_BEFORE`). However, if any of
       these classes is requested, it is made sure that *this* class is
       instanciated before.

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
            SERVICE_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            SERVICE_BEFORE = [Bar]

        class Fourth(metaclass=service.Meta):
            SERVICE_BEFORE = [Bar]

    ``Baz`` and ``Fourth`` will be instanciated before ``Bar`` and ``Bar`` will
    be instanciated before ``Foo``. There is no dependency relationship between
    ``Baz`` and ``Fourth``.



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
        before_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_BEFORE",
            inherit_dependencies)

        after_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_AFTER",
            inherit_dependencies)

        if before_classes & after_classes:
            raise ValueError("dependency loop: {} loops through {}".format(
                name,
                next(iter(before_classes & after_classes)).__qualname__
            ))

        namespace["SERVICE_BEFORE"] = set(before_classes)
        namespace["SERVICE_AFTER"] = set(after_classes)

        return super().__new__(mcls, name, bases, namespace)

    def __init__(self, name, bases, namespace, inherit_dependencies=True):
        super().__init__(name, bases, namespace)
        for cls in self.SERVICE_BEFORE:
            cls.SERVICE_AFTER.add(self)
        for cls in self.SERVICE_AFTER:
            cls.SERVICE_BEFORE.add(self)

    def __lt__(self, other):
        return other in self.SERVICE_BEFORE

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

    `client` must be a :class:`~aioxmpp.node.AbstractClient` to which the
    service will be attached. The `client` cannot be changed later, for the
    sake of simplicity.

    `logger` may be a :class:`logging.Logger` instance or :data:`None`. If it
    is :data:`None`, a logger is automatically created, by taking the fully
    qualified name of the :class:`Service` subclass which is being
    instanciated.

    .. autoattribute:: client

    .. automethod:: shutdown

    For rules with respect to inheriting from :class:`Service` see the
    documentation of the used metaclass, :class:`Meta`.
    """

    def __init__(self, client, *, logger=None):
        super().__init__()
        if logger is None:
            self.logger = logging.getLogger(".".join([
                type(self).__module__, type(self).__qualname__
            ]))
        else:
            self.logger = logger

        self._client = client

    @property
    def client(self):
        """
        The client to which the :class:`Service` is bound. This attribute is
        read-only.

        If the service has been shut down using :meth:`shutdown`, this reads as
        :data:`None`.
        """
        return self._client

    @asyncio.coroutine
    def _shutdown(self):
        """
        Actual implementation of the shut down process.

        This *must* be called using super from inheriting classes after their
        own shutdown procedure.
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
           override the (intentionally undocumented) :meth:`_shutdown` method,
           which is also a coroutine and has the same signature as
           :meth:`shutdown`.

        """
        yield from self._shutdown()
        self._client = None
