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

import aioxmpp.service

from aioxmpp.utils import namespaces


class SHIMService(aioxmpp.service.Service):
    """
    This service implements :xep:`131` feature advertisement.

    It registers the ``http://jabber.org/protocol/shim`` node with the
    :class:`.DiscoServer`. It publishes the supported headers on that node as
    specified in the XEP.

    To announce supported headers, use the :meth:`register_header` and
    :meth:`unregister_header` methods.

    .. automethod:: register_header

    .. automethod:: unregister_header

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.shim.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.
    """

    ORDER_AFTER = [aioxmpp.DiscoServer]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._disco = self.dependencies[aioxmpp.DiscoServer]
        self._disco.register_feature(namespaces.xep0131_shim)

        self._node = aioxmpp.disco.StaticNode()
        self._disco.mount_node(
            namespaces.xep0131_shim,
            self._node
        )

    async def _shutdown(self):
        self._disco.unregister_feature(namespaces.xep0131_shim)
        self._disco.unmount_node(namespaces.xep0131_shim)
        await super()._shutdown()

    def register_header(self, name):
        """
        Register support for the SHIM header with the given `name`.

        If the header has already been registered as supported,
        :class:`ValueError` is raised.
        """

        self._node.register_feature(
            "#".join([namespaces.xep0131_shim, name])
        )

    def unregister_header(self, name):
        """
        Unregister support for the SHIM header with the given `name`.

        If the header is currently not registered as supported,
        :class:`KeyError` is raised.
        """

        self._node.unregister_feature(
            "#".join([namespaces.xep0131_shim, name])
        )
