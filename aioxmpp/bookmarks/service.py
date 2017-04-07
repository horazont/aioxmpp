########################################################################
# File name: service.py
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
import asyncio

import aioxmpp
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.disco as disco
import aioxmpp.pubsub as pubsub
import aioxmpp.private_xml as private_xml

from . import xso as bookmark_xso


# TODO: use private storage in pubsub where available.
# TODO: sync bookmarks between pubsub and private xml storage
class BookmarkClient(service.Service):
    """
    Supports retrieval and storage of bookmarks on the server.
    It currently only supports :xep:`Private XML Storage <49>` as
    backend.

    .. automethod:: get_bookmarks

    .. automethod:: set_bookmarks

    .. note:: The bookmark protocol is prone to race conditions if
              several clients access it concurrently. Be careful to
              use a get-modify-set pattern.

    .. note:: Some other clients extend the bookmark format. For now
              those extensions are silently dropped by our XSOs, and
              therefore are lost, when changing the bookmarks with
              aioxmpp. This is considered a bug to be fixed in the future.
    """

    ORDER_AFTER = [
        private_xml.PrivateXMLService,
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._private_xml = self.dependencies[private_xml.PrivateXMLService]

    @asyncio.coroutine
    def get_bookmarks(self):
        """
        Get the stored bookmarks from the server.

        :returns: the bookmarks as a :class:`~bookmark_xso.Storage` object
        """
        res = yield from self._private_xml.get_private_xml(
            bookmark_xso.Storage()
        )
        return res

    @asyncio.coroutine
    def set_bookmarks(self, bookmarks):
        """
        Set the bookmarks stored on the server.
        """
        if not isinstance(bookmarks, bookmark_xso.Storage):
            raise TypeError(
                "set_bookmarks only accepts bookmark.Storage objects"
            )
        yield from self._private_xml.set_private_xml(bookmarks)
