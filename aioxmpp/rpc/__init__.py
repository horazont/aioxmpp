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
:mod:`~aioxmpp.rpc` --- Jabber-RPC support (:xep:`0009`)
#############################################################

This subpackage implements support for Jabber-RPC as specified in
:xep:`0009`. Both the client and the server side of RPC protocol are
supported.

Client-side
===========

.. currentmodule:: aioxmpp.rpc

.. autoclass:: RPCClient

.. currentmodule:: aioxmpp.rpc.service

Server-side
===========

.. currentmodule:: aioxmpp.rpc

.. autoclass:: RPCServer

.. currentmodule:: aioxmpp.rpc.service

XSOs
====

.. currentmodule:: aioxmpp.rpc.xso

.. autoclass:: Query

.. autoclass:: MethodCall

.. autoclass:: MethodResponse

.. autoclass:: MethodName

.. autoclass:: Params

.. autoclass:: Param

.. currentmodule:: aioxmpp.rpc

"""

from .service import RPCServer, RPCClient
from . import xso