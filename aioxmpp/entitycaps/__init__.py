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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.entitycaps` --- Entity Capabilities support (:xep:`390`, :xep:`0115`)
####################################################################################

This module provides support for :xep:`XEP-0115 (Entity Capabilities) <0115>`
and :xep:`XEP-0390 (Entity Capabilities 2.0) <0390>`. To use it,
:meth:`.Client.summon` the :class:`aioxmpp.EntityCapsService` on a
:class:`~.Client`. See the service documentation for more information.

.. versionadded:: 0.5

.. versionchanged:: 0.9

    Support for :xep:`390` was added.

Service
=======

.. currentmodule:: aioxmpp

.. autoclass:: EntityCapsService

.. currentmodule:: aioxmpp.entitycaps

.. class:: Service

   Alias of :class:`.EntityCapsService`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

.. autoclass:: Cache

.. currentmodule:: aioxmpp.entitycaps.xso


"""  # NOQA: E501

from .service import EntityCapsService, Cache  # NOQA: F401
from . import xso  # NOQA: F401
Service = EntityCapsService
