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
:mod:`~aioxmpp.adhoc` --- Ad-Hoc Commands support (:xep:`50`)
#############################################################

This subpackage implements support for Ad-Hoc Commands as specified in
:xep:`50`. Both the client and the server side of Ad-Hoc Commands are
supported.

.. versionadded:: 0.8

Client-side
===========

.. currentmodule:: aioxmpp

.. autoclass:: AdHocClient

.. currentmodule:: aioxmpp.adhoc.service

.. autoclass:: ClientSession

Server-side
===========

.. currentmodule:: aioxmpp.adhoc

.. autoclass:: AdHocServer

.. currentmodule:: aioxmpp.adhoc.service

..
    .. autoclass:: ServerSession

XSOs
====

.. currentmodule:: aioxmpp.adhoc.xso

.. autoclass:: Command

.. autoclass:: Actions

.. autoclass:: Note

.. currentmodule:: aioxmpp.adhoc

Enumerations
------------

.. autoclass:: CommandStatus

.. autoclass:: ActionType
"""

from .service import (  # NOQA: F401
    AdHocClient,
    ClientSession,
    AdHocServer,
)

from .xso import (  # NOQA: F401
    CommandStatus,
    ActionType,
)

from . import xso  # NOQA: F401
