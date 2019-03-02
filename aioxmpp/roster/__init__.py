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
:mod:`~aioxmpp.roster` --- :rfc:`6121` roster implementation
############################################################

This subpackage provides :class:`.RosterClient`, a service to interact with
:rfc:`6121` rosters.

.. currentmodule:: aioxmpp

.. autoclass:: RosterClient

.. currentmodule:: aioxmpp.roster

.. class:: Service

   Alias of :class:`.RosterClient`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

.. autoclass:: Item

.. module:: aioxmpp.roster.xso

.. currentmodule:: aioxmpp.roster.xso

:mod:`.roster.xso` --- IQ payloads and stream feature
=====================================================

The submodule :mod:`aioxmpp.roster.xso` contains the :class:`~aioxmpp.xso.XSO`
classes which describe the IQ payloads used by this subpackage.

.. autoclass:: Query

.. autoclass:: Item

.. autoclass:: Group

The stream feature which is used by servers to announce support for roster
versioning:

.. autoclass:: RosterVersioningFeature()
"""

from .service import RosterClient, Item  # NOQA: F401
Service = RosterClient  # NOQA
