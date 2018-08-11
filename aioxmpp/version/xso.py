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
"""
XSO Definitions
===============

.. autoclass:: Query
"""
import aioxmpp
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


namespaces.xep0092_version = "jabber:iq:version"


@aioxmpp.IQ.as_payload_class
class Query(xso.XSO):
    """
    :xep:`92` Software Version query :class:`~aioxmpp.xso.XSO`.

    .. attribute:: name

        Software name as string. May be :data:`None`.

    .. attribute:: version

        Software version as string. May be :data:`None`.

    .. attribute:: os

        Operating system as string. May be :data:`None`.
    """

    TAG = namespaces.xep0092_version, "query"

    version = xso.ChildText(
        (namespaces.xep0092_version, "version"),
        default=None,
    )

    name = xso.ChildText(
        (namespaces.xep0092_version, "name"),
        default=None,
    )

    os = xso.ChildText(
        (namespaces.xep0092_version, "os"),
        default=None,
    )
