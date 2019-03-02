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
import aioxmpp.stanza
import aioxmpp.xso

from aioxmpp.utils import namespaces

namespaces.xep0363_http_upload = "urn:xmpp:http:upload:0"


@aioxmpp.IQ.as_payload_class
class Request(aioxmpp.xso.XSO):
    """
    XSO to request an upload slot from the server.

    The parameters initialise the attributes below.

    .. attribute:: filename
        :annotation: : str

        The file name (without path, but possibly with "extension") of the
        file to upload. The server MAY use this in the URL.


    .. attribute:: size
        :annotation: : int

        The size of the file in bytes. This must be accurate and MUST also
        be used as ``Content-Length`` header in the PUT request.

    .. attribute:: content_type
        :annotation: : str

        The MIME type of the file. This MUST be set in the PUT request as
        ``Content-Type`` header.
    """

    TAG = namespaces.xep0363_http_upload, "request"

    filename = aioxmpp.xso.Attr("filename")

    size = aioxmpp.xso.Attr(
        "size",
        type_=aioxmpp.xso.Integer(),
    )

    content_type = aioxmpp.xso.Attr("content-type")

    def __init__(self, filename, size, content_type):
        super().__init__()
        self.filename = filename
        self.size = size
        self.content_type = content_type


class Header(aioxmpp.xso.XSO):
    TAG = namespaces.xep0363_http_upload, "header"

    name = aioxmpp.xso.Attr("name")

    value = aioxmpp.xso.Text()


class HeaderType(aioxmpp.xso.AbstractElementType):
    @staticmethod
    def get_xso_types():
        return (Header,)

    @classmethod
    def unpack(self, header_xso):
        return header_xso.name, header_xso.value

    @classmethod
    def pack(self, t):
        header_xso = Header()
        header_xso.name, header_xso.value = t
        return header_xso


class Put(aioxmpp.xso.XSO):
    """
    .. attribute:: url
        :annotation: : str

        The URL against which the PUT request must be made.

    .. attribute:: headers
        :annotation: : multidict.MultiDict

        The headers which MUST be used in the PUT request as
        :class:`multidict.MultiDict`, in addition to the ``Content-Type``
        and ``Content-Length`` headers.

        The headers are already sanitised according to :xep:`363` (see also
        :attr:`HEADER_WHITELIST`).

    .. attribute:: HEADER_WHITELIST

        This *class attribute* holds the list of headers which are allowed to
        be used by the server. This defaults to the list specified in
        :xep:`363`.

        .. warning::

            Changing the list of allowed headers may have unintended security
            implications.
    """

    HEADER_WHITELIST = (
        "Authorization",
        "Expires",
        "Cookie",
    )

    TAG = namespaces.xep0363_http_upload, "put"

    url = aioxmpp.xso.Attr("url")

    headers = aioxmpp.xso.ChildValueMultiMap(
        HeaderType
    )

    def xso_after_load(self):
        whitelist = self.HEADER_WHITELIST
        headers = list(self.headers.items())
        self.headers.clear()

        for key, value in headers:
            if key not in whitelist:
                continue
            value = value.replace("\n", "")
            self.headers.add(key, value)


class Get(aioxmpp.xso.XSO):
    """
    .. attribute:: url
        :annotation: : str

        The URL at which the file can be retrieved after uploading.
    """

    TAG = namespaces.xep0363_http_upload, "get"

    url = aioxmpp.xso.Attr("url")


@aioxmpp.IQ.as_payload_class
class Slot(aioxmpp.xso.XSO):
    """
    XSO representing the an upload slot provided by the server.

    .. attribute:: get

        Information about the GET request for the slot as :class:`.Get` XSO.

    .. attribute:: put

        Information about the PUT request for the slot as :class:`.Put` XSO.
    """

    TAG = namespaces.xep0363_http_upload, "slot"

    put = aioxmpp.xso.Child([Put])

    get = aioxmpp.xso.Child([Get])

    def validate(self):
        super().validate()

        if self.put is None:
            raise ValueError("missing PUT information")

        if self.get is None:
            raise ValueError("missing GET information")
