########################################################################
# File name: pars.py
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

from ..stanza import Presence


namespaces.xep0379_pars = "urn:xmpp:pars:0"


class Preauth(xso.XSO):
    """
    The preauth element for :xep:`Pre-Authenticated Roster Subcription <379>`.

    .. attribute:: token

       The pre-auth token associated with this subscription request.
    """
    TAG = namespaces.xep0379_pars, "preauth"

    token = xso.Attr(
        "token",
        type_=xso.String(),
    )


Presence.xep0379_preauth = xso.Child([Preauth])
