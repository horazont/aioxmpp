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
""":mod:`~aioxmpp.bookmarks` – Bookmark support (:xep:`0048`)
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

The following XSOs are used to represent an manipulate bookmark lists.

.. autoclass:: Storage

.. autoclass:: Conference

.. autoclass:: URL

Notes on usage
==============

It is important to use this class carefully to prevent race conditions
with other clients modifying the bookmark data (unfortunately, this is
not entirely preventable due to the design of the bookmark protocol).

The recommended practice is to modify the bookmarks in a get, modify,
set fashion, where the modify step should be as short as possible
(that is, should not depend on user input).

The individual bookmark classes support comparison by value. This
allows useful manipulation of the bookmark list in agreement with
the get-modify-set pattern. Where we reference the objects to operate
on by with the value retrieved in an earlier get.

Removal::

  storage = bookmark_client.get_bookmarks()
  storage.bookmarks.remove(old_bookmark)
  bookmark_client.set_bookmarks(storage)

Modifying::

  storage = bookmark_client.get_bookmarks()
  i = storage.bookmarks.index(old_bookmark)
  storage.bookmarks[i].name = "New Shiny Name"
  storage.bookmarks[i].nick = "new_nick"
  bookmark_client.set_bookmarks(storage)

Adding::

  storage = bookmark_client.get_bookmarks()
  storage.bookmarks.append(new_bookmark)
  bookmark_client.set_bookmarks(storage)
"""

from .xso import (Storage, Conference, URL)  # NOQA
from .service import BookmarkClient  # NOQA
