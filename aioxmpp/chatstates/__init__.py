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
:mod:`~aioxmpp.chatstates` – Chat State Notification support (:xep:`0085`)
##########################################################################

This module provides support to implement :xep:`Chat State
Notifications <85>`.

XSOs
====

The module registers an attribute ``xep0085_chatstate`` with
:class:`aioxmpp.Message` to represent the chat state
notification tags, it takes values from the following enumeration (or
:data:`None` if no tag is present):

.. autoclass:: ChatState

Helpers
=======

The module provides the following helper class, that handles the state
management for chat state notifications:

.. autoclass:: ChatStateManager

Its operation is controlled by one of the chat state strategies:

.. autoclass:: DoNotEmit

.. autoclass:: DiscoverSupport

.. autoclass:: AlwaysEmit

"""
from .xso import ChatState  # NOQA: F401
from .utils import (ChatStateManager, DoNotEmit, AlwaysEmit,  # NOQA: F401
                    DiscoverSupport)
