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
:mod:`~aioxmpp.ping` --- XMPP Ping (:xep:`199`)
###############################################

XMPP Ping is a ping on the XMPP protocol level. It can be used to detect
connection liveness (although :class:`aioxmpp.stream.StanzaStream` and thus
:class:`aioxmpp.Client` does that for you) and connectivity/availablility of
remote domains.

Service
=======

.. currentmodule:: aioxmpp

.. autoclass:: PingService()

.. currentmodule:: aioxmpp.ping

.. autofunction:: ping

XSOs
====

Sometimes it is useful to send a ping manually instead of relying on the
:class:`Service`. For this, the :class:`Ping` IQ payload can be used.

.. autoclass:: Ping()

"""

from .service import PingService, ping  # NOQA: F401
from .xso import Ping  # NOQA: F401
