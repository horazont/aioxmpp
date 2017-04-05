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
import contextlib

import aioxmpp
import aioxmpp.service as service
import aioxmpp.callbacks as callbacks


class PEPClient(service.Service):
    """
    :class:`PEPClient` simplifies working with PEP services.

    Compared to :class:`~aioxmpp.PubSubClient` it supports automatic
    checking for server support, a stream-lined API. It is intended to
    make PEP things easy. If you need more fine-grained control or do
    things which are not usually handled by the defaults when using PEP, use
    :class:`~aioxmpp.PubSubClient` directly.

    See :class:`register_pep_node` for the high-level interface for
    claiming a PEP node and receiving event notifications.

    There also is a low-level interface:

    .. automethod:: claim_pep_node

    .. automethod:: unclaim_pep_node

    """
    ORDER_AFTER = [
        aioxmpp.DiscoClient,
        aioxmpp.DiscoServer,
        aioxmpp.PubSubClient
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._pubsub = self.dependencies[aioxmpp.PubSubClient]
        self._disco_client = self.dependencies[aioxmpp.DiscoClient]
        self._disco_server = self.dependencies[aioxmpp.DiscoServer]

        self._pep_node_claims = {}

    def claim_pep_node(self, node_namespace, handler, *,
                       register_feature=True, notify=False):
        """
        Claim node `node_namespace`.

        Dispatch event notifications for `node_namespace` to `handler`.

        This registers `node_namespace` as feature for service discovery
        unless ``register_feature=False`` is passed.

        :param node_namespace: the pubsub node whose events shall be
            handled.
        :param handler: the handler to install.
        :type handler: callable, see
            :attr:`aioxmpp.PubSubClient.on_item_publish`
            for the arguments.
        :param register_feature: Whether to publish the `node_namespace`
            as feature.
        :param notify: Whether to register the ``+notify`` feature to
            receive notification without explicit subscription.

        :raises RuntimeError: if a handler for `node_namespace` is already
            set.
        """
        if node_namespace in self._pep_node_claims:
            raise RuntimeError(
                "setting handler for already handled namespace"
            )
        if register_feature:
            self._disco_server.register_feature(node_namespace)
        if notify:
            self._disco_server.register_feature(node_namespace + "+notify")
        self._pep_node_claims[node_namespace] = handler, register_feature, notify

    def unclaim_pep_node(self, node_namespace):
        """
        Unclaim `node_namespace`.

        The feature for `node_namespace` and the ``+notify`` feature
        are automatically retracted if they were set by
        :method:`claim_pep_node`.

        :param node_namespace: The PubSub node whose handler shall be unset.

        :raises KeyError: If the no handler is registered for
            `node_namespace`.
        """
        _, feature, notify = self._pep_node_claims.pop(node_namespace)
        if notify:
            self._disco_server.unregister_feature(node_namespace + "+notify")
        if feature:
            self._disco_server.unregister_feature(node_namespace)

    @asyncio.coroutine
    def _check_for_pep(self):
        # XXX: should this be done when the stream connects
        # and we use the cached result later on (i.e. disable
        # the PEP service if the server does not support PEP)
        disco_info = yield from self._disco_client.query_info(
            self.client.local_jid.bare()
        )

        for item in disco_info.identities.filter(attrs={"category": "pubsub"}):
            if item.type_ == "pep":
                break
        else:
            raise RuntimeError("server does not support PEP")

    @service.depsignal(aioxmpp.PubSubClient, "on_item_published")
    def _handle_pubsub_publish(self, jid, node, item, *, message=None):
        try:
            handler, _, _ = self._pep_node_claims[node]
        except KeyError:
            return

        # TODO: handle empty payloads due to (mis-)configuration of
        # the node specially.
        handler(jid, node, item, message=message)

    def publish(self, node, data, *, id_=None):
        """
        Publish an item `data` in the PubSub node `node` on the
        PEP service associated with the user's JID.

        If no `id_` is given it is generated by the server (and may be
        returned).

        :param node: The PubSub node to publish to.
        :param data: The item to publish.
        :type data: An XSO representing the paylaod.
        :param id_: The id the published item shall have.

        :returns: The PubSub id of the published item or
            :data:`None` if it is unknown.

        """
        yield from self._check_for_pep()
        return (yield from self._pubsub.publish(None, node, data, id_=id_))

    def subscribe(self, jid, node):
        yield from self._pubsub.subscribe(jid, node)

class RegisteredPEPNode:
    # XXX: do we want to provide metadata in this class?
    on_event_received = callbacks.Signal()

class register_pep_node(service.Descriptor):
    """
    Service descriptor claiming a PEP node.

    If `notify` is :data:`True` it registers a ``+notify`` feature,
    for automatic pubsub subscription. All notifications sent to this
    PEP node are broadcast by the :attr:`on_event_received` signal.

    :param node_namespace: The PubSub payload namespace to handle.
    :param register_feature: Whether to register the node namespace as feature.
    :param notify: Whether to register for notifications.
    :param max_items: Transparently handle the `max_items` configuration
        option of the PubSub node.

    .. signal:: on_event_received(jid, node, item, *, message=None)

        Fires when a PubSub publish event is received for
        :attr:`node_namespace`.

    .. autoattribute:: node_namespace

    .. autoattribute:: notify

    """
    def __init__(self, node_namespace, *, register_feature=True,
                 notify=False, max_items=None):
        super().__init__()
        self._node_namespace = node_namespace
        self._notify = notify
        self._register_feature = register_feature
        self._max_items = max_items

    @property
    def node_namespace(self):
        """
        The node namespace to request notifications for.
        """
        return self._node_namespace

    @property
    def register_feature(self):
        """
        Whether we register the node namespace as feature.
        """
        return self._register_feature

    @property
    def notify(self):
        """
        Wether we register the ``+nofity`` feature.
        """
        return self._notify

    @property
    def required_dependencies(self):
        return [PEPClient]

    @contextlib.contextmanager
    def init_cm(self, instance):
        value = RegisteredPEPNode()
        pep_client = instance.dependencies[PEPClient]
        pep_client.claim_pep_node(
            self._node_namespace,
            value.on_event_received,
            register_feature=self._register_feature,
            notify=self._notify,
        )
        yield value
        pep_client.unclaim_pep_node(self._node_namespace)
