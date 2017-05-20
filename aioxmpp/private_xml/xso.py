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


namespaces.xep0049 = "jabber:iq:private"


@aioxmpp.IQ.as_payload_class
class Query(xso.XSO):
    """
    The XSO for queries to private XML storage.

    .. automethod:: as_payload_class
    """
    TAG = (namespaces.xep0049, "query")

    registered_payload = xso.Child([], strict=True)
    unregistered_payload = xso.Collector()

    def __init__(self, payload):
        self.registered_payload = payload

    @classmethod
    def as_payload_class(mycls, xso_class):
        """
        Register the given class `xso_class` as possible payload
        for private XML storage.

        Return `xso_class`, to allow this to be used as a decorator.
        """
        mycls.register_child(
            Query.registered_payload,
            xso_class
        )

        return xso_class
