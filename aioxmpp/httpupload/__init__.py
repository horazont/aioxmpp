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
    slot = await client.send(aioxmpp.httpupload.Request(
        filename,
        size,
        content_type,
    ))
    # http_put_file is provided by you via an HTTP library
    await http_put_file(
        slot.put.url,
        slot.put.headers,
        filename
    )

.. autoclass:: Request

.. module:: aioxmpp.httpupload.xso

.. currentmodule:: aioxmpp.httpupload.xso

.. autoclass:: Slot()

.. autoclass:: Get()

.. autoclass:: Put()
"""
from .xso import Request
