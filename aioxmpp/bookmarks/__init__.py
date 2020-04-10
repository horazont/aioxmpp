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
:mod:`~aioxmpp.bookmarks` – Bookmark support (:xep:`0048`)
##########################################################

This module provides support for storing and retrieving bookmarks on
the server as per :xep:`Bookmarks <48>`.

Service
=======

.. currentmodule:: aioxmpp

.. autoclass:: BookmarkClient

.. currentmodule:: aioxmpp.bookmarks

XSOs
====

All bookmark types must adhere to the following ABC:

.. autoclass:: Bookmark

The following XSOs are used to represent an manipulate bookmark lists.

.. autoclass:: Conference

.. autoclass:: URL

To register custom bookmark classes use:

.. autofunction:: as_bookmark_class

The following is used internally as the XSO container for bookmarks.

.. autoclass:: Storage

Notes on usage
==============

.. currentmodule:: aioxmpp

It is highly recommended to interact with the bookmark client via the
provided signals and the get-modify-set methods
:meth:`~BookmarkClient.add_bookmark`,
:meth:`~BookmarkClient.discard_bookmark` and
:meth:`~BookmarkClient.update_bookmark`.  Using
:meth:`~BookmarkClient.set_bookmarks` directly is error prone and
might cause data loss due to race conditions.

"""

from .xso import (Storage, Bookmark, Conference, URL,  # NOQA: F401
                  as_bookmark_class)
from .service import BookmarkClient  # NOQA: F401
