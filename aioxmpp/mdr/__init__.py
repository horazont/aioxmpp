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
:mod:`~aioxmpp.mdr` --- Message Delivery Reciepts (:xep:`184`)
##############################################################

This module provides a :mod:`aioxmpp.tracking` service which tracks :xep:`184`
replies to messages and accordingly updates attached
:class:`~aioxmpp.tracking.MessageTracker` objects.

.. versionadded:: 0.10

To make use of receipt tracking, :meth:`~aioxmpp.Client.summon` the
:class:`~aioxmpp.DeliveryReceiptsService` on your :class:`aioxmpp.Client` and
use the :meth:`~.DeliveryReceiptsService.attach_tracker` method.

To send delivery receipts, the :func:`aioxmpp.mdr.compose_receipt` helper
function is provided.

.. currentmodule:: aioxmpp

.. autoclass:: DeliveryReceiptsService

.. currentmodule:: aioxmpp.mdr

.. autofunction:: compose_receipt
"""
from .service import (  # NOQA: F401
    DeliveryReceiptsService,
    compose_receipt,
)
