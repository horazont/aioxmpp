########################################################################
# File name: openpgp_legacy.py
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
import aioxmpp.stanza
import aioxmpp.xso

from aioxmpp.utils import namespaces

namespaces.xep0027_encrypted = "jabber:x:encrypted"
namespaces.xep0027_signed = "jabber:x:signed"


class OpenPGPEncrypted(aioxmpp.xso.XSO):
    """
    Wrapper around an ASCII-armored OpenPGP encrypted blob.

    .. warning::

        Please see the security considerations of :xep:`27` before making use
        of this protocol. Consider implementation of :xep:`373` instead.

    See :xep:`27` for details.

    .. attribute:: payload

        The character data of the wrapper element.

        .. note::

            While the wire format *is* base64, since the base64 output is
            intended to be passed verbatim to OpenPGP, the payload is declared
            as normal string and aioxmpp will *not* de-base64 it for you (and
            vice versa).
    """

    TAG = namespaces.xep0027_encrypted, "x"

    payload = aioxmpp.xso.Text()


class OpenPGPSigned(aioxmpp.xso.XSO):
    """
    Wrapper around an ASCII-armored OpenPGP signed blob.

    .. warning::

        Please see the security considerations of :xep:`27` before making use
        of this protocol. Consider implementation of :xep:`373` instead.

    See :xep:`27` for details.

    .. attribute:: payload

        The character data of the wrapper element.

        .. note::

            While the wire format *is* base64, since the base64 output is
            intended to be passed verbatim to OpenPGP, the payload is declared
            as normal string and aioxmpp will *not* de-base64 it for you (and
            vice versa).
    """
    TAG = namespaces.xep0027_signed, "x"

    payload = aioxmpp.xso.Text()


aioxmpp.stanza.Message.xep0027_encrypted = aioxmpp.xso.Child([OpenPGPEncrypted])
aioxmpp.stanza.Message.xep0027_signed = aioxmpp.xso.Child([OpenPGPSigned])
