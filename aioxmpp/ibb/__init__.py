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
:mod:`~aioxmpp.ibb` --- In-Band Bytestreams (:xep:`0047`)
#########################################################

This subpackage provides support for in-band bytestreams.  The
bytestreams are exposed as instances of :class:`asyncio.Transport`,
which allows to speak any protocol implemented as
:class:`asyncio.Protocol` over them.

.. autoclass:: IBBService

.. autoclass:: IBBStanzaType

.. currentmodule:: aioxmpp.ibb.service
.. autoclass:: IBBTransport()

For serializing and deserializing data payloads carried by
:class:`~aioxmpp.Message` stanzas, a descriptor is added to them:

.. attribute:: aioxmpp.Message.xep0047_data
"""
from .xso import IBBStanzaType # NOQA
from .service import IBBService # NOQA

# import aioxmpp.ibb.service
