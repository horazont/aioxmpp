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
:mod:`~aioxmpp.disco` --- Service discovery support (:xep:`0030`)
#################################################################

This module provides support for :xep:`Service Discovery <30>`. For this, it
provides a :class:`~aioxmpp.service.Service` subclass which can be loaded into
a client using :meth:`.Client.summon`.

Services
========

The following services are provided by this subpackage and available directly
from :mod:`aioxmpp`:

.. currentmodule:: aioxmpp

.. autosummary::
   :nosignatures:

   DiscoServer
   DiscoClient

.. versionchanged:: 0.8

   Prior to version 0.8, both services were provided by a single class
   (:class:`aioxmpp.disco.Service`). This is not the case anymore, and there is
   no replacement.

   If you need to write backwards compatible code, you could be doing something
   like this::

     try:
         aioxmpp.DiscoServer
     except AttributeError:
         aioxmpp.DiscoServer = aioxmpp.disco.Service
         aioxmpp.DiscoClient = aioxmpp.disco.Service

   This should work, because the old :class:`Service` class provided the
   features of both of the individual classes.

The detailed documentation of the classes follows:

.. autoclass:: DiscoServer

.. autoclass:: DiscoClient

.. currentmodule:: aioxmpp.disco

Entity information
------------------

.. autoclass:: Node

.. autoclass:: StaticNode

.. autoclass:: mount_as_node

.. autoclass:: register_feature

.. autoclass:: RegisteredFeature

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

from . import xso  # NOQA: F401
from .service import (DiscoClient, DiscoServer, Node, StaticNode,  # NOQA: F401
                      mount_as_node, register_feature, RegisteredFeature)
