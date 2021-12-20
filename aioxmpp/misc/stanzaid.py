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

namespaces.xep0359_stanza_ids = "urn:xmpp:sid:0"


class StanzaID(xso.XSO):
    """
    Represent a :xep:`359` Stanza ID.

    :param id_: The stanza ID to set
    :param by: The entity which has set the stanza ID
    :type by: :class:`aioxmpp.JID`

    .. attribute:: id_

        The assigned stanza ID.

    .. attribute:: by

        The entity who has assigned the stanza ID.

    .. warning::

        Stanza IDs may be spoofed. Please take the security considerations of
        :xep:`359` and the protocols using it into account.
    """
    TAG = (namespaces.xep0359_stanza_ids, "stanza-id")

    id_ = xso.Attr("id", default=None)
    by = xso.Attr("by", type_=xso.JID(), default=None)

    def __init__(self, *, id_=None, by=None, **kwargs):
        super().__init__(**kwargs)
        self.id_ = id_
        self.by = by


class OriginID(xso.XSO):
    """
    Represent a :xep:`359` Origin ID.

    :param id_: The origin ID to set

    .. attribute:: id_

        The assigned origin ID.

    .. warning::

        Origin IDs may be spoofed. Please take the security considerations of
        :xep:`359` and the protocols using it into account.
    """

    TAG = (namespaces.xep0359_stanza_ids, "origin-id")

    id_ = xso.Attr("id", default=None)

    def __init__(self, id_=None):
        super().__init__()
        self.id_ = id_


Message.xep0359_stanza_ids = xso.ChildList([StanzaID])
Message.xep0359_origin_id = xso.Child([OriginID])
