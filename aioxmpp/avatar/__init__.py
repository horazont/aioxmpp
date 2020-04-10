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

The following service is provided by this subpackage:

.. currentmodule:: aioxmpp

.. autosummary::

   AvatarService

The detailed documentation of the classes follows:

.. autoclass:: AvatarService()

.. currentmodule:: aioxmpp.avatar

Data Representation
===================

The following class is used to describe the possible locations of an
avatar image:

.. autoclass:: AvatarSet

.. module:: aioxmpp.avatar.service
.. currentmodule:: aioxmpp.avatar.service
.. autoclass:: AbstractAvatarDescriptor()

.. currentmodule:: aioxmpp.avatar

Helpers
=======

.. autofunction:: normalize_id

How to work with avatar descriptors
===================================

.. currentmodule:: aioxmpp.avatar.service

One you have retrieved the avatar descriptor list, the correct way to
handle it in the application:

1. Select the avatar you prefer based on the
   :attr:`~AbstractAvatarDescriptor.can_get_image_bytes_via_xmpp`, and
   metadata information (:attr:`~AbstractAvatarDescriptor.mime_type`,
   :attr:`~AbstractAvatarDescriptor.width`,
   :attr:`~AbstractAvatarDescriptor.height`,
   :attr:`~AbstractAvatarDescriptor.nbytes`). If you cache avatar
   images it might be a good choice to choose an avatar image you
   already have cached based on
   :attr:`~AbstractAvatarDescriptor.normalized_id`.

2. If :attr:`~AbstractAvatarDescriptor.can_get_image_bytes_via_xmpp`
   is true, try to retrieve the image by
   :attr:`~AbstractAvatarDescriptor.get_image_bytes()`; if it is false
   try to retrieve the object at the URL
   :attr:`~AbstractAvatarDescriptor.url`.
"""

from .service import (AvatarSet, AvatarService,  # NOQA: F401
                      normalize_id)
