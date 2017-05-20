########################################################################
# File name: xso.py
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

from aioxmpp.utils import namespaces

from ..misc import Forwarded
from ..stanza import Message, IQ


namespaces.xep0280_carbons_2 = "urn:xmpp:carbons:2"


@IQ.as_payload_class
class Enable(xso.XSO):
    TAG = (namespaces.xep0280_carbons_2, "enable")


@IQ.as_payload_class
class Disable(xso.XSO):
    TAG = (namespaces.xep0280_carbons_2, "disable")


class _CarbonsWrapper(xso.XSO):
    forwarded = xso.Child([Forwarded])

    @property
    def stanza(self):
        """
        The wrapped stanza, usually a :class:`aioxmpp.Message`.

        Internally, this accesses the :attr:`~.misc.Forwarded.stanza` attribute
        of :attr:`forwarded`. If :attr:`forwarded` is :data:`None`, reading
        this attribute returns :data:`None`. Writing to this attribute creates
        a new :class:`~.misc.Forwarded` object if necessary, but re-uses an
        existing object if available.
        """
        if self.forwarded is None:
            return None
        return self.forwarded.stanza

    @stanza.setter
    def stanza(self, value):
        if self.forwarded is None:
            self.forwarded = Forwarded()
        self.forwarded.stanza = value


class Sent(_CarbonsWrapper):
    """
    Wrap a stanza which was sent by another entity of the same account.

    :class:`Sent` XSOs are available in Carbon messages at
    :attr:`aioxmpp.Message.xep0280_sent`.

    .. autoattribute:: stanza

    .. attribute:: forwarded

       The full :class:`~.misc.Forwarded` object which holds the sent stanza.

    """

    TAG = (namespaces.xep0280_carbons_2, "sent")


class Received(_CarbonsWrapper):
    """
    Wrap a stanza which was received by another entity of the same account.

    :class:`Received` XSOs are available in Carbon messages at
    :attr:`aioxmpp.Message.xep0280_received`.

    .. autoattribute:: stanza

    .. attribute:: forwarded

       The full :class:`~.misc.Forwarded` object which holds the received
       stanza.

    """
    TAG = (namespaces.xep0280_carbons_2, "received")


Message.xep0280_sent = xso.Child([Sent])
Message.xep0280_received = xso.Child([Received])
