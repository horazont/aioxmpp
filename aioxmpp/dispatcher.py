########################################################################
# File name: dispatcher.py
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
:mod:`~aioxmpp.dispatcher` --- Dispatch stanzas to callbacks
############################################################

.. versionadded:: 0.9

   The whole module was added in 0.9.

Stanza Dispatchers for Messages and Presences
=============================================

.. autoclass:: SimpleMessageDispatcher

.. autoclass:: SimplePresenceDispatcher


Decorators for :class:`aioxmpp.service.Service` Methods
=======================================================

.. autodecorator:: message_handler

.. autodecorator:: presence_handler

Test Functions
--------------

.. autofunction:: is_message_handler

.. autofunction:: is_presence_handler

Base Class for Stanza Dispatchers
=================================

.. autoclass:: SimpleStanzaDispatcher
"""
import abc
import asyncio
import contextlib

import aioxmpp.service
import aioxmpp.stream


class SimpleStanzaDispatcher(metaclass=abc.ABCMeta):
    """
    Dispatch stanzas based on their sender and type.

    This is a service base class (not a service you should summon) which can be
    used to implement simple, pre-0.9 presence and message dispatching.

    For users, the following methods are relevant:

    .. automethod:: register_callback

    .. automethod:: unregister_callback

    .. automethod:: handler_context

    For deriving classes, the following methods are relevant:

    .. automethod:: _feed

    Subclasses must also provide the following property:

    .. autoattribute:: local_jid

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._map = {}

    @abc.abstractproperty
    def local_jid(self):
        """
        The bare JID of the client for which this dispatcher is used.

        This is required to map missing ``@from`` attributes to this JID. The
        attribute must be provided by implementing subclasses.
        """

    def _feed(self, stanza):
        """
        Dispatch the given `stanza`.

        :param stanza: Stanza to dispatch
        :type stanza: :class:`~.StanzaBase`
        :rtype: :class:`bool`
        :return: true if the stanza was dispatched, false otherwise.

        Dispatch the stanza to up to one handler registered on the dispatcher.
        If no handler is found for the stanza, :data:`False` is returned.
        Otherwise, :data:`True` is returned.
        """
        from_ = stanza.from_
        if from_ is None:
            from_ = self.local_jid

        keys = [
            (stanza.type_, from_, False),
            (stanza.type_, from_.bare(), True),
            (None, from_, False),
            (None, from_.bare(), True),
            (stanza.type_, None, False),
            (None, from_, False),
            (None, None, False),
        ]

        for key in keys:
            try:
                cb = self._map[key]
            except KeyError:
                continue
            cb(stanza)
            return

    def register_callback(self, type_, from_, cb, *,
                          wildcard_resource=True):
        """
        Register a callback function.

        :param type_: Stanza type to listen for, or :data:`None` for a
                      wildcard match.
        :param from_: Sender to listen for, or :data:`None` for a full wildcard
                      match.
        :type from_: :class:`aioxmpp.JID` or :data:`None`
        :param cb: Callback function to register
        :param wildcard_resource: Whether to wildcard the resourcepart of the
                                  JID.
        :type wildcard_resource: :class:`bool`
        :raises ValueError: if another function is already registered for the
                            callback slot.

        `cb` will be called whenever a stanza with the matching `type_` and
        `from_` is processed. The following wildcarding rules apply:

        1. If the :attr:`~aioxmpp.stanza.StanzaBase.from_` attribute of the
           stanza has a resourcepart, the following lookup order for callbacks is used:

           +---------------------------+----------------------------------+----------------------+
           |``type_``                  |``from_``                         |``wildcard_resource`` |
           +===========================+==================================+======================+
           |:attr:`~.StanzaBase.type_` |:attr:`~.StanzaBase.from_`        |*any*                 |
           +---------------------------+----------------------------------+----------------------+
           |:attr:`~.StanzaBase.type_` |*bare* :attr:`~.StanzaBase.from_` |:data:`True`          |
           +---------------------------+----------------------------------+----------------------+
           |:data:`None`               |:attr:`~.StanzaBase.from_`        |*any*                 |
           +---------------------------+----------------------------------+----------------------+
           |:data:`None`               |*bare* :attr:`~.StanzaBase.from_` |:data:`True`          |
           +---------------------------+----------------------------------+----------------------+
           |:attr:`~.StanzaBase.type_` |:data:`None`                      |*any*                 |
           +---------------------------+----------------------------------+----------------------+
           |:data:`None`               |:data:`None`                      |*any*                 |
           +---------------------------+----------------------------------+----------------------+

        2. If the :attr:`~aioxmpp.stanza.StanzaBase.from_` attribute of the
           stanza does *not* have a resourcepart, the following lookup order
           for callbacks is used:

           +---------------------------+---------------------------+----------------------+
           |``type_``                  |``from_``                  |``wildcard_resource`` |
           +===========================+===========================+======================+
           |:attr:`~.StanzaBase.type_` |:attr:`~.StanzaBase.from_` |:data:`False`         |
           +---------------------------+---------------------------+----------------------+
           |:data:`None`               |:attr:`~.StanzaBase.from_` |:data:`False`         |
           +---------------------------+---------------------------+----------------------+
           |:attr:`~.StanzaBase.type_` |:data:`None`               |*any*                 |
           +---------------------------+---------------------------+----------------------+
           |:data:`None`               |:data:`None`               |*any*                 |
           +---------------------------+---------------------------+----------------------+

        Only the first callback which matches is called. `wildcard_resource` is
        ignored if `from_` is a full JID or :data:`None`.

        .. note::

           When the server sends a stanza without from attribute, it is
           replaced with the bare :attr:`local_jid`, as per :rfc:`6120`.

        """  # NOQA: E501
        if from_ is None or not from_.is_bare:
            wildcard_resource = False

        key = (type_, from_, wildcard_resource)
        if key in self._map:
            raise ValueError(
                "only one listener allowed per matcher"
            )

        self._map[type_, from_, wildcard_resource] = cb

    def unregister_callback(self, type_, from_, *,
                            wildcard_resource=True):
        """
        Unregister a callback function.

        :param type_: Stanza type to listen for, or :data:`None` for a
                      wildcard match.
        :param from_: Sender to listen for, or :data:`None` for a full wildcard
                      match.
        :type from_: :class:`aioxmpp.JID` or :data:`None`
        :param wildcard_resource: Whether to wildcard the resourcepart of the
                                  JID.
        :type wildcard_resource: :class:`bool`

        The callback must be disconnected with the same arguments as were used
        to connect it.
        """
        if from_ is None or not from_.is_bare:
            wildcard_resource = False

        self._map.pop((type_, from_, wildcard_resource))

    @contextlib.contextmanager
    def handler_context(self, type_, from_, cb, *, wildcard_resource=True):
        """
        Context manager which temporarily registers a callback.

        The arguments are the same as for :meth:`register_callback`.

        When the context is entered, the callback `cb` is registered. When the
        context is exited, no matter if an exception is raised or not, the
        callback is unregistered.
        """
        self.register_callback(
            type_, from_, cb,
            wildcard_resource=wildcard_resource
        )
        try:
            yield
        finally:
            self.unregister_callback(
                type_, from_,
                wildcard_resource=wildcard_resource
            )


class SimpleMessageDispatcher(aioxmpp.service.Service,
                              SimpleStanzaDispatcher):
    """
    Dispatch messages to callbacks.

    This :class:`~aioxmpp.service.Service` dispatches :class:`~aioxmpp.Message`
    stanzas to callbacks. Callbacks registrations are managed with the
    :meth:`.SimpleStanzaDispatcher.register_callback` and
    :meth:`.SimpleStanzaDispatcher.unregister_callback` methods of the base
    class. The `type_` argument to these methods must be a
    :class:`aioxmpp.MessageType` or :data:`None` to make any sense.

    .. note::

       It is not recommended to mix the use of a
       :class:`SimpleMessageDispatcher` with the modern Instant Messaging
       features provided by the :mod:`aioxmpp.im` module. Both will receive the
       messages and this may thus lead to duplicate messages.

    """

    @property
    def local_jid(self):
        return self.client.local_jid

    @aioxmpp.service.depsignal(aioxmpp.stream.StanzaStream,
                               "on_message_received")
    def _feed(self, stanza):
        super()._feed(stanza)


class SimplePresenceDispatcher(aioxmpp.service.Service,
                               SimpleStanzaDispatcher):
    """
    Dispatch presences to callbacks.

    This :class:`~aioxmpp.service.Service` dispatches
    :class:`~aioxmpp.Presence` stanzas to callbacks. Callbacks registrations
    are managed with the :meth:`.SimpleStanzaDispatcher.register_callback` and
    :meth:`.SimpleStanzaDispatcher.unregister_callback` methods of the base
    class. The `type_` argument to these methods must be a
    :class:`aioxmpp.MessageType` or :data:`None` to make any sense.

    .. warning::

       It is not recommended to mix the use of a
       :class:`SimplePresenceDispatcher` with :class:`aioxmpp.RosterClient` and
       :class:`aioxmpp.PresenceClient`. Both of these register callbacks at the
       :class:`SimplePresenceDispatcher`. Registering callbacks for different
       slots will either make those callbacks not be called at all or will
       make the services miss stanzas.
    """

    @property
    def local_jid(self):
        return self.client.local_jid

    @aioxmpp.service.depsignal(aioxmpp.stream.StanzaStream,
                               "on_presence_received")
    def _feed(self, stanza):
        super()._feed(stanza)


def _apply_message_handler(instance, stream, func, type_, from_):
    return instance.dependencies[SimpleMessageDispatcher].handler_context(
        type_,
        from_,
        func,
    )


def _apply_presence_handler(instance, stream, func, type_, from_):
    return instance.dependencies[SimplePresenceDispatcher].handler_context(
        type_,
        from_,
        func,
    )


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

    .. versionchanged:: 0.9

       This is now based on
       :class:`aioxmpp.dispatcher.SimpleMessageDispatcher`.
    """

    def decorator(f):
        if asyncio.iscoroutinefunction(f):
            raise TypeError("message_handler must not be a coroutine function")

        aioxmpp.service.add_handler_spec(
            f,
            aioxmpp.service.HandlerSpec(
                (_apply_message_handler, (type_, from_)),
                require_deps=(
                    SimpleMessageDispatcher,
                )
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

    .. versionchanged:: 0.9

       This is now based on
       :class:`aioxmpp.dispatcher.SimplePresenceDispatcher`.
    """

    def decorator(f):
        if asyncio.iscoroutinefunction(f):
            raise TypeError(
                "presence_handler must not be a coroutine function"
            )

        aioxmpp.service.add_handler_spec(
            f,
            aioxmpp.service.HandlerSpec(
                (_apply_presence_handler, (type_, from_)),
                require_deps=(
                    SimplePresenceDispatcher,
                )
            )
        )
        return f
    return decorator


def is_message_handler(type_, from_, cb):
    """
    Return true if `cb` has been decorated with :func:`message_handler` for the
    given `type_` and `from_`.
    """

    try:
        handlers = aioxmpp.service.get_magic_attr(cb)
    except AttributeError:
        return False

    return aioxmpp.service.HandlerSpec(
        (_apply_message_handler, (type_, from_)),
        require_deps=(
            SimpleMessageDispatcher,
        )
    ) in handlers


def is_presence_handler(type_, from_, cb):
    """
    Return true if `cb` has been decorated with :func:`presence_handler` for
    the given `type_` and `from_`.
    """

    try:
        handlers = aioxmpp.service.get_magic_attr(cb)
    except AttributeError:
        return False

    return aioxmpp.service.HandlerSpec(
        (_apply_presence_handler, (type_, from_)),
        require_deps=(
            SimplePresenceDispatcher,
        )
    ) in handlers
