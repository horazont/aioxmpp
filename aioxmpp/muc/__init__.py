"""
:mod:`~aioxmpp.muc` --- Multi-User-Chat support (XEP-0045)
##########################################################

This subpackage provides client-side support for `XEP-0045`_.

.. _xep-0045: https://xmpp.org/extensions/xep-0045.html

Using Multi-User-Chats
======================

To start using MUCs in your application, you have to load the :class:`Service`
into the client, using :meth:`~.node.AbstractClient.summon`.

.. autoclass:: Service

The service returns :class:`Room` objects which are used to track joined MUCs:

.. autoclass:: Room

Inside rooms, there are occupants:

.. autoclass:: Occupant

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
from .xso import (  # NOQA
    GenericExt,
    History,
    UserExt,
    Status,
    DestroyNotification,
    Decline,
    Invite,
    UserItem,
    UserActor,
    Continue,
    AdminQuery,
    AdminItem,
    AdminActor,
    OwnerQuery,
    DestroyRequest
)
