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
:mod:`~aioxmpp.misc` -- Miscellaneous XSOs
##########################################

This subpackage bundles XSO definitions for several XEPs. They do not get their
own subpackage because they often only define one or two XSOs without any logic
involved. The XSOs are often intended for re-use by other protocols.


Delayed Delivery (:xep:`203`)
=============================

.. autoclass:: Delay()

.. attribute:: aioxmpp.Message.xep0203_delay

   A :class:`Delay` instance which indicates that the message has been
   delivered with delay.


Stanza Forwarding (:xep:`297`)
==============================

.. autoclass:: Forwarded()


"""

from .delay import Delay  # NOQA
from .forwarding import Forwarded  # NOQA
