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
:mod:`~aioxmpp.version` --- Software Version (XEP-0092) support
###############################################################

This subpackage provides support for querying and answering queries adhering to
the :xep:`92` (Software Support) protocol.

.. versionadded:: 0.10

The protocol allows entities to find out the software version and operating
system of other entities in the XMPP network.

.. currentmodule:: aioxmpp

.. autoclass:: aioxmpp.VersionServer()

.. currentmodule:: aioxmpp.version

.. autofunction:: query_version

.. automodule:: aioxmpp.version.xso
"""
from .service import (  # NOQA: F401
    VersionServer,
    query_version,
)
