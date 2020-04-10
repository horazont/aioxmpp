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
:mod:`~aioxmpp.pep` --- PEP support (:xep:`0163`)
#################################################

This module provides support for using the :xep:`Personal Eventing
Protocol <163>` subset of :xep:`Publish-Subscribe <60>` comfortably.

This protocol does not define any XSOs since PEP reuses the protocol
defined by PubSub.

.. note:: Splitting PEP services into client and server parts is not
          well supported, since only one claim per PEP node can be made.

.. note:: Payload classes which are to be used with PEP *must* be
          registered with :func:`aioxmpp.pubsub.xso.as_payload_class`.

.. currentmodule:: aioxmpp

.. autoclass:: PEPClient

.. currentmodule:: aioxmpp.pep

.. autoclass:: register_pep_node

.. module:: aioxmpp.pep.service
.. autoclass:: RegisteredPEPNode()
.. currentmodule:: aioxmpp.pep

"""
from .service import (PEPClient, register_pep_node)  # NOQA: F401
