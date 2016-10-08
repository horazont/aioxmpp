########################################################################
# File name: __init__.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
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

Forms
=====

.. autoclass:: ConfigurationForm
   :members:

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
from .xso import (  # NOQA
    ConfigurationForm
)
