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
:mod:`~aioxmpp.carbons` -- Message Carbons (:xep:`280`)
#######################################################

Message Carbons is an XMPP extension which allows an entity to receive copies
of inbound and outbound messages received and sent by other resources of the
same account. It is specified in :xep:`280`. The goal of this feature is to
allow users to have multiple devices which all have a consistent view on the
messages sent and received.

This subpackage provides basic support for Message Carbons. It allows enabling
and disabling the feature at the server side.

Service
=======

.. currentmodule:: aioxmpp

.. autoclass:: CarbonsClient

.. currentmodule:: aioxmpp.carbons


.. currentmodule:: aioxmpp.carbons.xso
.. module:: aioxmpp.carbons.xso

XSOs
====

.. attribute:: aioxmpp.Message.xep0280_sent

   On a Carbon message, this holds the :class:`~.carbons.xso.Sent` XSO which in
   turn holds the carbonated stanza.

.. attribute:: aioxmpp.Message.xep0280_received

   On a Carbon message, this holds the :class:`~.carbons.xso.Received` XSO
   which in turn holds the carbonated stanza.

.. autoclass:: Received

.. autoclass:: Sent

"""
from .service import CarbonsClient  # NOQA: F401
