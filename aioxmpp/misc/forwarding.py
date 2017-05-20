########################################################################
# File name: forwarding.py
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
import aioxmpp.xso as xso

from ..stanza import IQ, Message, Presence
from .delay import Delay

from aioxmpp.utils import namespaces

namespaces.xep0297_forward = "urn:xmpp:forward:0"


class Forwarded(xso.XSO):
    """
    Wrap a stanza for forwarding.

    .. attribute:: delay

       If not :data:`None`, this is a :class:`aioxmpp.misc.Delay` XSO which
       indicates the timestamp at which the wrapped stanza was originally sent.

    .. attribute:: stanza

       The forwarded stanza.

    .. warning::

       Please take the security considerations of :xep:`297` and the protocol
       using this XSO into account.

    """
    TAG = namespaces.xep0297_forward, "forwarded"

    delay = xso.Child([Delay])

    stanza = xso.Child(
        [
            Message,
            IQ,
            Presence,
        ]
    )
