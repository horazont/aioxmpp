import asyncio

import aioxmpp.service

import aioxmpp.disco

from aioxmpp.utils import namespaces


class Service(aioxmpp.service.Service):
    """
    This service implements :xep:`131` feature advertisment.

    It registers the ``http://jabber.org/protocol/shim`` node with the
    :class:`.disco.Service`. It publishes the supported headers on that node as
    specified in the XEP.

    To announce supported headers, use the :meth:`register_header` and
    :meth:`unregister_header` methods.

    .. automethod:: register_header

    .. automethod:: unregister_header
    """

    ORDER_AFTER = [aioxmpp.disco.Service]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._disco = client.summon(aioxmpp.disco.Service)
        self._disco.register_feature(namespaces.xep0131_shim)

        self._node = aioxmpp.disco.StaticNode()
        self._disco.mount_node(
            namespaces.xep0131_shim,
            self._node
        )

    @asyncio.coroutine
    def _shutdown(self):
        self._disco.unregister_feature(namespaces.xep0131_shim)
        self._disco.unmount_node(namespaces.xep0131_shim)
        yield from super()._shutdown()

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
