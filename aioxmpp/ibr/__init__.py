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
:mod:`~aioxmpp.ibr` --- In-Band Registration (:xep:`0077`)
##########################################################

This module implements in-band registration.

Registration Functions
======================

The module level registration functions work on an
:class:`aioxmpp.protocol.XMLStream` and before authentication. They
allow to register a new account with a server.

.. autofunction:: get_registration_fields

.. autofunction:: register

Helper Function
===============

.. autofunction:: get_used_fields

Service
=======

.. autoclass:: RegistrationService

XSO Definitions
===============

.. autoclass:: Query
"""

from .service import (  # NOQA: F401
    RegistrationService,
    get_registration_fields,
    register,
)
from .service import get_used_fields  # NOQA: F401
from .xso import Query  # NOQA: F401
