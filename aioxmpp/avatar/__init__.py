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
:mod:`~aioxmpp.avatar` --- User avatar support (:xep:`0084`)
############################################################

This module provides support for publishing and retrieving user
avatars as per :xep:`User Avatar <84>`.

Services
========

The following services are provided by this subpackage:

.. currentmodule:: aioxmpp

.. autosummary::

   AvatarServer
   AvatarClient

The detailed documentation of the classes follows:

.. autoclass:: AvatarServer

.. autoclass:: AvatarClient

.. currentmodule:: aioxmpp.avatar

Data Representation
===================

The following class is used to describe the possible locations of an
avatar image:

.. autoclass:: AvatarSet

.. module:: aioxmpp.avatar.service
.. currentmodule:: aioxmpp.avatar.service
.. autoclass:: AbstractAvatarDescriptor()

"""

from .service import (AvatarSet, AvatarServer, AvatarClient)  # NOQA
