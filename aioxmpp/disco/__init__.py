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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.disco` --- Service discovery support (:xep:`0030`)
#################################################################

This module provides support for :xep:`Service Discovery <30>`. For this, it
provides a :class:`~aioxmpp.service.Service` subclass which can be loaded into
a client using :meth:`.AbstractClient.summon`.

Service
=======

.. autoclass:: Service

Entity information
------------------

.. autoclass:: Node

.. autoclass:: StaticNode

.. module:: aioxmpp.disco.xso

.. currentmodule:: aioxmpp.disco.xso

:mod:`.disco.xso` --- IQ payloads
=================================

The submodule :mod:`aioxmpp.disco.xso` contains the :class:`~aioxmpp.xso.XSO`
classes which describe the IQ payloads used by this subpackage.

You will encounter some of these in return values, but there should never be a
need to construct them by yourself; the :class:`~aioxmpp.disco.Service` handles
it all.

Information queries
-------------------

.. autoclass:: InfoQuery(*[, identities][, features][, node])

.. autoclass:: Feature(*[, var])

.. autoclass:: Identity(*[, category][, type_][, name][, lang])

Item queries
------------

.. autoclass:: ItemsQuery(*[, node][, items])

.. autoclass:: Item(*[, jid][, name][, node])

.. currentmodule:: aioxmpp.disco

"""

from . import xso  # NOQA
from .service import Service, Node, StaticNode  # NOQA
