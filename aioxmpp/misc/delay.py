########################################################################
# File name: delay.py
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

from ..stanza import Message


namespaces.xep0203_delay = "urn:xmpp:delay"


class Delay(xso.XSO):
    """
    A marker indicating delayed delivery of a stanza.

    .. attribute:: from_

       The address as :class:`aioxmpp.JID` of the entity where the stanza was
       delayed. May be :data:`None`.

    .. attribute:: stamp

       The timestamp (as :class:`datetime.datetime`) at which the stanza was
       originally sent or intended to be sent.

    .. attribute:: reason

       The reason for which the stanza was delayed or :data:`None`.

    .. warning::

       Please take the security considerations of :xep:`203` into account.

    """

    TAG = namespaces.xep0203_delay, "delay"

    from_ = xso.Attr(
        "from",
        type_=xso.JID(),
        default=None,
    )

    stamp = xso.Attr(
        "stamp",
        type_=xso.DateTime(),
    )

    reason = xso.Text(
        default=None
    )


Message.xep0203_delay = xso.ChildList([Delay])
