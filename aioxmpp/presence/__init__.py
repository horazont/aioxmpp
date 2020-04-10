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
:mod:`~aioxmpp.presence` --- Peer presence bookkeeping
######################################################

This module provides a :class:`.PresenceClient` service to track the presence
of peers, no matter whether they are in the roster or not.

.. versionadded:: 0.4

.. currentmodule:: aioxmpp

.. autoclass:: PresenceClient

.. autoclass:: PresenceServer

.. currentmodule:: aioxmpp.presence

.. class:: Service

   Alias of :class:`.PresenceClient`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

"""

from .service import PresenceClient, PresenceServer  # NOQA: F401
Service = PresenceClient  # NOQA
