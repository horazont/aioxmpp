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

namespaces.xep0077_in_band = "jabber:iq:register"


@aioxmpp.IQ.as_payload_class
class Query(xso.XSO):
    """
    :xep:`077` In-Band Registraion query :class:`~aioxmpp.xso.XSO`.

    It has the following fields described in the XEP document:

    .. attribute:: username

    .. attribute:: nick

    .. attribute:: password

    .. attribute:: name

    .. attribute:: first

    .. attribute:: last

    .. attribute:: email

    .. attribute:: address

    .. attribute:: city

    .. attribute:: state

    .. attribute:: zip

    .. attribute:: phone

    .. attribute:: url

    .. attribute:: date

    .. attribute:: misc

    .. attribute:: text

    .. attribute:: key

    .. attribute:: registered

    .. attribute:: remove
    """

    TAG = (namespaces.xep0077_in_band, "query")
    username = xso.ChildText(
        (namespaces.xep0077_in_band, "username"),
        default=None,
    )

    instructions = xso.ChildText(
        (namespaces.xep0077_in_band, "instructions"),
        default=None,
    )

    nick = xso.ChildText(
        (namespaces.xep0077_in_band, "nick"),
        default=None,
    )

    password = xso.ChildText(
        (namespaces.xep0077_in_band, "password"),
        default=None,
    )

    name = xso.ChildText(
        (namespaces.xep0077_in_band, "name"),
        default=None,
    )

    first = xso.ChildText(
        (namespaces.xep0077_in_band, "first"),
        default=None,
    )

    last = xso.ChildText(
        (namespaces.xep0077_in_band, "last"),
        default=None,
    )

    email = xso.ChildText(
        (namespaces.xep0077_in_band, "email"),
        default=None,
    )

    address = xso.ChildText(
        (namespaces.xep0077_in_band, "address"),
        default=None,
    )

    city = xso.ChildText(
        (namespaces.xep0077_in_band, "city"),
        default=None,
    )

    state = xso.ChildText(
        (namespaces.xep0077_in_band, "state"),
        default=None,
    )

    zip = xso.ChildText(
        (namespaces.xep0077_in_band, "zip"),
        default=None,
    )

    phone = xso.ChildText(
        (namespaces.xep0077_in_band, "phone"),
        default=None,
    )

    url = xso.ChildText(
        (namespaces.xep0077_in_band, "url"),
        default=None,
    )

    date = xso.ChildText(
        (namespaces.xep0077_in_band, "date"),
        default=None,
    )

    misc = xso.ChildText(
        (namespaces.xep0077_in_band, "misc"),
        default=None,
    )

    text = xso.ChildText(
        (namespaces.xep0077_in_band, "text"),
        default=None,
    )

    key = xso.ChildText(
        (namespaces.xep0077_in_band, "key"),
        default=None,
    )

    registered = xso.ChildFlag(
        (namespaces.xep0077_in_band, "registered")
    )

    remove = xso.ChildFlag(
        (namespaces.xep0077_in_band, "remove")
    )

    def __init__(self, username=None, password=None, aux_fields=None):
        """
        Get an xso.Query object with the info provided in he parameters.

        :param username: Username of the query
        :type username: :class:`str`
        :param password: Password of the query.
        :type password: :class:`str`
        :param aux_fields: Auxiliary fields in case additional info is needed.
        :type aux_fields: :class:`dict`
        :return: :class:`xso.Query`
        """
        self.username = username
        self.password = password

        if aux_fields is not None:
            for key, value in aux_fields.items():
                setattr(self, key, value)
