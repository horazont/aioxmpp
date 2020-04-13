########################################################################
# File name: __init__.py
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
:mod:`~aioxmpp.httpupload` --- HTTP Upload support (:xep:`363`)
###############################################################

The :xep:`363` HTTP Upload protocol allows an XMPP client to obtain a PUT and
GET URL for storage on the server. It can upload a file (once) using the PUT
URL and distribute access to the file via the GET url.

This module does *not* handle the HTTP part of the interaction. We recommend
to use :mod:`aiohttp` for this, but you can use any HTTP library which supports
GET, PUT and sending custom headers.

Example use::

    client = <your aioxmpp.Client>
    http_upload_service = <JID of the HTTP Upload service>
    slot = await client.send(aioxmpp.IQ(
        type_=aioxmpp.IQType.GET,
        to=http_upload_service,
        payload=aioxmpp.httpupload.Request(
            filename,
            size,
            content_type,
        )
    ))
    # http_put_file is provided by you via an HTTP library
    await http_put_file(
        slot.put.url,
        slot.put.headers,
        filename
    )

.. autofunction:: request_slot

.. autoclass:: Request

.. module:: aioxmpp.httpupload.xso

.. currentmodule:: aioxmpp.httpupload.xso

.. autoclass:: Slot()

.. autoclass:: Get()

.. autoclass:: Put()
"""
import asyncio

from ..structs import JID, IQType
from ..stanza import IQ
from .xso import Request


async def request_slot(client,
                       service: JID,
                       filename: str,
                       size: int,
                       content_type: str):
    """
    Request an HTTP upload slot.

    :param client: The client to request the slot with.
    :type client: :class:`aioxmpp.Client`
    :param service: Address of the HTTP upload service.
    :type service: :class:`~aioxmpp.JID`
    :param filename: Name of the file (without path), may be used by the server
        to generate the URL.
    :type filename: :class:`str`
    :param size: Size of the file in bytes
    :type size: :class:`int`
    :param content_type: The MIME type of the file
    :type content_type: :class:`str`
    :return: The assigned upload slot.
    :rtype: :class:`.xso.Slot`

    Sends a :xep:`363` slot request to the XMPP service to obtain HTTP
    PUT and GET URLs for a file upload.

    The upload slot is returned as a :class:`~.xso.Slot` object.
    """

    payload = Request(filename, size, content_type)
    return await client.send(IQ(
        type_=IQType.GET,
        to=service,
        payload=payload
    ))
