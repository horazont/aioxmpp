########################################################################
# File name: pam0.py
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
import aioxmpp.xso

from aioxmpp.utils import namespaces

from . import core0

namespaces.xep0405_mix_pam_0 = "urn:xmpp:mix:pam:0"


class ClientJoin0(aioxmpp.xso.XSO):
    TAG = namespaces.xep0405_mix_pam_0, "client-join"

    join = aioxmpp.xso.Child([core0.Join0])

    channel = aioxmpp.xso.Attr("channel", type_=aioxmpp.xso.JID())

    def __init__(self, channel, subscribe_to_nodes):
        super().__init__()
        self.channel = channel
        self.join = core0.Join0(subscribe_to_nodes)
