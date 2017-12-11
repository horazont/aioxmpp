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
import aioxmpp
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0054 = "vcard-temp"

@aioxmpp.IQ.as_payload_class
class VCard(xso.XSO):
    """
    The container for vCard data as per :xep:`vcard-temp <54>`.

    .. attribute:: elements

       The raw elements of the vCard (as etree).
    """

    TAG = (namespaces.xep0054, "vCard")

    elements = xso.Collector()
