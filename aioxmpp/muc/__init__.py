"""
:mod:`~aioxmpp.muc` --- Multi-User-Chat support (:xep:`45`)
###########################################################

This subpackage provides client-side support for :xep:`0045`.

.. versionadded:: 0.5

Using Multi-User-Chats
======================

To start using MUCs in your application, you have to load the :class:`Service`
into the client, using :meth:`~.node.AbstractClient.summon`.

.. autoclass:: Service

The service returns :class:`Room` objects which are used to track joined MUCs:

.. autoclass:: Room

Inside rooms, there are occupants:

.. autoclass:: Occupant

.. currentmodule:: aioxmpp.muc.xso

XSOs
====

Generic namespace
-----------------

.. autoclass:: GenericExt

.. autoclass:: History

User namespace
--------------

.. autoclass:: UserExt

.. autoclass:: Status

.. autoclass:: DestroyNotification

.. autoclass:: Decline

.. autoclass:: Invite

.. autoclass:: UserItem

.. autoclass:: UserActor

.. autoclass:: Continue

Admin namespace
---------------

.. autoclass:: AdminQuery

.. autoclass:: AdminItem

.. autoclass:: AdminActor

Owner namespace
---------------

.. autoclass:: OwnerQuery

.. autoclass:: DestroyRequest

"""
from .service import Service, Occupant, Room  # NOQA
from . import xso  # NOQA
