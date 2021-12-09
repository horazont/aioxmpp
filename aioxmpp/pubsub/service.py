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

import aioxmpp.callbacks
import aioxmpp.disco
import aioxmpp.service
import aioxmpp.stanza
import aioxmpp.structs

from . import xso as pubsub_xso


class PubSubClient(aioxmpp.service.Service):
    """
    Client service implementing a Publish-Subscribe client. By loading it into
    a client, it is possible to subscribe to, publish to and otherwise interact
    with Publish-Subscribe nodes.

    .. note::

       Signal handlers attached to any of the signals below **must** accept
       arbitrary keyword arguments for forward compatibility. If any of the
       arguments is listed as positional in the signal signature, it is always
       present and handed as positional argument.

    Subscriber use cases:
       .. autosummary::

          get_default_config
          get_items
          get_items_by_id
          get_subscription_config
          get_subscriptions
          set_subscription_config
          subscribe
          unsubscribe
          on_affiliation_update
          on_item_published
          on_item_retracted
          on_node_deleted
          on_subscription_update

    Publisher use cases:
       .. autosummary::

          notify
          publish
          retract

    Owner use cases:
       .. autosummary::

          change_node_affiliations
          change_node_subscriptions
          create
          delete
          get_nodes
          get_node_affiliations
          get_node_config
          get_node_subscriptions
          purge
          set_node_config

    Meta-information about the service:

    .. automethod:: get_features

    Subscribing, unsubscribing and listing subscriptions:

    .. automethod:: get_subscriptions

    .. automethod:: subscribe

    .. automethod:: unsubscribe

    Configuring subscriptions:

    .. automethod:: get_default_config

    .. automethod:: get_subscription_config

    .. automethod:: set_subscription_config

    Retrieving items:

    .. automethod:: get_items

    .. automethod:: get_items_by_id

    Publishing and retracting items:

    .. automethod:: notify

    .. automethod:: publish

    .. automethod:: retract

    Manage nodes:

    .. automethod:: change_node_affiliations

    .. automethod:: change_node_subscriptions

    .. automethod:: create

    .. automethod:: delete

    .. automethod:: get_nodes

    .. automethod:: get_node_affiliations

    .. automethod:: get_node_config

    .. automethod:: get_node_subscriptions

    .. automethod:: purge

    .. automethod:: set_node_config

    Receiving notifications:

    .. signal:: on_item_published(jid, node, item, *, message=None)

        Fires when a new item is published to a node to which we have a
        subscription.

        The node at which the item has been published is identified by `jid`
        and `node`. `item` is the :class:`xso.EventItem` payload.

        `message` is the :class:`.Message` which carried the notification.
        If a notification message contains more than one published item, the
        event is fired for each of the items, and `message` is passed to all
        of them.

    .. signal:: on_item_retracted(jid, node, id_, *, message=None)

        Fires when an item is retracted from a node to which we have a
        subscription.

        The node at which the item has been retracted is identified by `jid`
        and `node`. `id_` is the ID of the item which has been retract.

        `message` is the :class:`.Message` which carried the notification.
        If a notification message contains more than one retracted item, the
        event is fired for each of the items, and `message` is passed to all
        of them.

    .. signal:: on_node_deleted(jid, node, *, redirect_uri=None, message=None)

        Fires when a node is deleted. `jid` and `node` identify the node.

        If the notification included a redirection URI, it is passed as
        `redirect_uri`. Otherwise, :data:`None` is passed for `redirect_uri`.

        `message` is the :class:`.Message` which carried the notification.

    .. signal:: on_affiliation_update(jid, node, affiliation, *, message=None)

        Fires when the affiliation with a node is updated.

        `jid` and `node` identify the node for which the affiliation was updated.
        `affiliation` is the new affiliaton.

        `message` is the :class:`.Message` which carried the notification.

    .. signal:: on_subscription_update(jid, node, state, *, subid=None, message=None)

        Fires when the subscription state is updated.

        `jid` and `node` identify the node for which the subscription was updated.
        `subid` is optional and if it is not :data:`None` it is the affected
        subscription id. `state` is the new subscription state.

        This event can happen in several cases, for example when a subscription
        request is approved by the node owner or when a subscription is cancelled.

        `message` is the :class:`.Message` which carried the notification.

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.pubsub.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.
    """  # NOQA: E501

    ORDER_AFTER = [
        aioxmpp.DiscoClient,
    ]

    on_item_published = aioxmpp.callbacks.Signal()
    on_item_retracted = aioxmpp.callbacks.Signal()
    on_node_deleted = aioxmpp.callbacks.Signal()
    on_affiliation_update = aioxmpp.callbacks.Signal()
    on_subscription_update = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._disco = self.dependencies[aioxmpp.DiscoClient]

    @aioxmpp.service.inbound_message_filter
    def filter_inbound_message(self, msg):
        if (msg.xep0060_event is not None and
                msg.xep0060_event.payload is not None):
            payload = msg.xep0060_event.payload
            if isinstance(payload, pubsub_xso.EventItems):
                for item in payload.items:
                    node = item.node or payload.node
                    self.on_item_published(
                        msg.from_,
                        node,
                        item,
                        message=msg,
                    )
                for retract in payload.retracts:
                    node = payload.node
                    self.on_item_retracted(
                        msg.from_,
                        node,
                        retract.id_,
                        message=msg,
                    )
            elif isinstance(payload, pubsub_xso.EventDelete):
                self.on_node_deleted(
                    msg.from_,
                    payload.node,
                    redirect_uri=payload.redirect_uri,
                    message=msg,
                )

        elif (msg.xep0060_request is not None and
              msg.xep0060_request.payload is not None):
            payload = msg.xep0060_request.payload
            if isinstance(payload, pubsub_xso.Affiliations):
                for item in payload.affiliations:
                    self.on_affiliation_update(
                        msg.from_,
                        item.node,
                        item.affiliation,
                        message=msg,
                    )
            elif isinstance(payload, pubsub_xso.Subscriptions):
                for item in payload.subscriptions:
                    self.on_subscription_update(
                        msg.from_,
                        item.node,
                        item.subscription,
                        subid=item.subid,
                        message=msg,
                    )
        else:
            return msg

    async def get_features(self, jid):
        """
        Return the features supported by a service.

        :param jid: Address of the PubSub service to query.
        :type jid: :class:`aioxmpp.JID`
        :return: Set of supported features
        :rtype: set containing :class:`~.pubsub.xso.Feature` enumeration
                members.

        This simply uses service discovery to obtain the set of features and
        converts the features to :class:`~.pubsub.xso.Feature` enumeration
        members. To get the full feature information, resort to using
        :meth:`.DiscoClient.query_info` directly on `jid`.

        Features returned by the peer which are not valid pubsub features are
        not returned.
        """

        response = await self._disco.query_info(jid)
        result = set()
        for feature in response.features:
            try:
                result.add(pubsub_xso.Feature(feature))
            except ValueError:
                continue
        return result

    async def subscribe(self, jid, node=None, *,
                        subscription_jid=None,
                        config=None):
        """
        Subscribe to a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to subscribe to.
        :type node: :class:`str`
        :param subscription_jid: The address to subscribe to the service.
        :type subscription_jid: :class:`aioxmpp.JID`
        :param config: Optional configuration of the subscription
        :type config: :class:`~.forms.Data`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The response from the server.
        :rtype: :class:`.xso.Request`

        By default, the subscription request will be for the bare JID of the
        client. It can be specified explicitly using the `subscription_jid`
        argument.

        If the service requires it or if it makes sense for other reasons, the
        subscription configuration :class:`~.forms.Data` form can be passed
        using the `config` argument.

        On success, the whole :class:`.xso.Request` object returned by the
        server is returned. It contains a :class:`.xso.Subscription`
        :attr:`~.xso.Request.payload` which has information on the nature of
        the subscription (it may be ``"pending"`` or ``"unconfigured"``) and
        the :attr:`~.xso.Subscription.subid` which may be required for other
        operations.

        On failure, the corresponding :class:`~.errors.XMPPError` is raised.
        """

        subscription_jid = subscription_jid or self.client.local_jid.bare()

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Subscribe(subscription_jid, node=node)
        )

        if config is not None:
            iq.payload.options = pubsub_xso.Options(
                subscription_jid,
                node=node
            )
            iq.payload.options.data = config

        response = await self.client.send(iq)
        return response

    async def unsubscribe(self, jid, node=None, *,
                          subscription_jid=None,
                          subid=None):
        """
        Unsubscribe from a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to unsubscribe from.
        :type node: :class:`str`
        :param subscription_jid: The address to subscribe from the service.
        :type subscription_jid: :class:`aioxmpp.JID`
        :param subid: Unique ID of the subscription to remove.
        :type subid: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service

        By default, the unsubscribe request will be for the bare JID of the
        client. It can be specified explicitly using the `subscription_jid`
        argument.

        If available, the `subid` should also be specified.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        subscription_jid = subscription_jid or self.client.local_jid.bare()

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Unsubscribe(subscription_jid, node=node, subid=subid)
        )

        await self.client.send(iq)

    async def get_subscription_config(self, jid, node=None, *,
                                      subscription_jid=None,
                                      subid=None):
        """
        Request the current configuration of a subscription.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :param subscription_jid: The address to query the configuration for.
        :type subscription_jid: :class:`aioxmpp.JID`
        :param subid: Unique ID of the subscription to query.
        :type subid: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The current configuration of the subscription.
        :rtype: :class:`~.forms.Data`

        By default, the request will be on behalf of the bare JID of the
        client. It can be overridden using the `subscription_jid` argument.

        If available, the `subid` should also be specified.

        On success, the :class:`~.forms.Data` form is returned.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        subscription_jid = subscription_jid or self.client.local_jid.bare()

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request()
        iq.payload.options = pubsub_xso.Options(
            subscription_jid,
            node=node,
            subid=subid,
        )

        response = await self.client.send(iq)
        return response.options.data

    async def set_subscription_config(self, jid, data, node=None, *,
                                      subscription_jid=None,
                                      subid=None):
        """
        Update the configuration of a subscription.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param data: The new configuration of the subscription.
        :type data: :class:`~.forms.Data`
        :param node: Name of the PubSub node to modify.
        :type node: :class:`str`
        :param subscription_jid: The address to modify the configuration for.
        :type subscription_jid: :class:`aioxmpp.JID`
        :param subid: Unique ID of the subscription to modify.
        :type subid: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service

        By default, the request will be on behalf of the bare JID of the
        client. It can be overridden using the `subscription_jid` argument.

        If available, the `subid` should also be specified.

        The configuration must be given as `data` as a
        :class:`~.forms.Data` instance.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        subscription_jid = subscription_jid or self.client.local_jid.bare()

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.Request()
        iq.payload.options = pubsub_xso.Options(
            subscription_jid,
            node=node,
            subid=subid,
        )
        iq.payload.options.data = data

        await self.client.send(iq)

    async def get_default_config(self, jid, node=None):
        """
        Request the default configuration of a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The default configuration of subscriptions at the node.
        :rtype: :class:`~.forms.Data`

        On success, the :class:`~.forms.Data` form is returned.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Default(node=node)
        )

        response = await self.client.send(iq)
        return response.payload.data

    async def get_node_config(self, jid, node=None):
        """
        Request the configuration of a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The configuration of the node.
        :rtype: :class:`~.forms.Data`

        On success, the :class:`~.forms.Data` form is returned.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.OwnerRequest(
            pubsub_xso.OwnerConfigure(node=node)
        )

        response = await self.client.send(iq)
        return response.payload.data

    async def set_node_config(self, jid, config, node=None):
        """
        Update the configuration of a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param config: Configuration form
        :type config: :class:`aioxmpp.forms.Data`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The configuration of the node.
        :rtype: :class:`~.forms.Data`

        .. seealso::

            :class:`aioxmpp.pubsub.NodeConfigForm`
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.OwnerRequest(
            pubsub_xso.OwnerConfigure(node=node)
        )
        iq.payload.payload.data = config

        await self.client.send(iq)

    async def get_items(self, jid, node, *, max_items=None):
        """
        Request the most recent items from a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :param max_items: Number of items to return at most.
        :type max_items: :class:`int` or :data:`None`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The response from the server.
        :rtype: :class:`.xso.Request`.

        By default, as many as possible items are requested. If `max_items` is
        given, it must be a positive integer specifying the maximum number of
        items which is to be returned by the server.

        Return the :class:`.xso.Request` object, which has a
        :class:`~.xso.Items` :attr:`~.xso.Request.payload`.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Items(node, max_items=max_items)
        )

        return await self.client.send(iq)

    async def get_items_by_id(self, jid, node, ids):
        """
        Request specific items by their IDs from a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :param ids: The item IDs to return.
        :type ids: :class:`~collections.abc.Iterable` of :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The response from the service
        :rtype: :class:`.xso.Request`

        `ids` must be an iterable of :class:`str` of the IDs of the items to
        request from the pubsub node. If the iterable is empty,
        :class:`ValueError` is raised (as otherwise, the request would be
        identical to calling :meth:`get_items` without `max_items`).

        Return the :class:`.xso.Request` object, which has a
        :class:`~.xso.Items` :attr:`~.xso.Request.payload`.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Items(node)
        )

        iq.payload.payload.items = [
            pubsub_xso.Item(id_)
            for id_ in ids
        ]

        if not iq.payload.payload.items:
            raise ValueError("ids must not be empty")

        return await self.client.send(iq)

    async def get_subscriptions(self, jid, node=None):
        """
        Return all subscriptions of the local entity to a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to query.
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The subscriptions response from the service.
        :rtype: :class:`.xso.Subscriptions`

        If `node` is :data:`None`, subscriptions on all nodes of the entity
        `jid` are listed.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Subscriptions(node=node)
        )

        response = await self.client.send(iq)
        return response.payload

    async def publish(self, jid, node, payload, *,
                      id_=None,
                      publish_options=None):
        """
        Publish an item to a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to publish to.
        :type node: :class:`str`
        :param payload: Registered payload to publish.
        :type payload: :class:`aioxmpp.xso.XSO`
        :param id_: Item ID to use for the item.
        :type id_: :class:`str` or :data:`None`.
        :param publish_options: A data form with the options for the publish
            request
        :type publish_options: :class:`aioxmpp.forms.Data`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :raises RuntimeError: if `publish_options` is not :data:`None` but
            the service does not support `publish_options`
        :return: The Item ID which was used to publish the item.
        :rtype: :class:`str` or :data:`None`

        Publish the given `payload` (which must be a :class:`aioxmpp.xso.XSO`
        registered with :attr:`.xso.Item.registered_payload`).

        The item is published to `node` at `jid`. If `id_` is given, it is used
        as the ID for the item. If an item with the same ID already exists at
        the node, it is replaced. If no ID is given, a ID is generated by the
        server.

        If `publish_options` is given, it is passed as ``<publish-options/>``
        element to the server. This needs to be a data form which allows to
        define e.g. node configuration as a pre-condition to publishing. If
        the publish-options cannot be satisfied, the server will raise a
        :attr:`aioxmpp.ErrorCondition.CONFLICT` error.

        If `publish_options` is given and the server does not announce the
        :attr:`aioxmpp.pubsub.xso.Feature.PUBLISH_OPTIONS` feature,
        :class:`RuntimeError` is raised to prevent security issues (e.g. if
        the publish options attempt to assert a restrictive access model).

        Return the ID of the item as published (or :data:`None` if the server
        does not inform us; this is unfortunately common).
        """

        publish = pubsub_xso.Publish()
        publish.node = node

        if payload is not None:
            item = pubsub_xso.Item()
            item.id_ = id_
            item.registered_payload = payload
            publish.item = item

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.Request(
            publish
        )

        if publish_options is not None:
            features = await self.get_features(jid)
            if pubsub_xso.Feature.PUBLISH_OPTIONS not in features:
                raise RuntimeError(
                    "publish-options given, but not supported by server"
                )

            iq.payload.publish_options = pubsub_xso.PublishOptions()
            iq.payload.publish_options.data = publish_options

        response = await self.client.send(iq)

        if response is not None and response.payload.item is not None:
            return response.payload.item.id_ or id_
        return id_

    async def notify(self, jid, node):
        """
        Notify all subscribers of a node without publishing an item.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to send a notify from.
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service

        "Publish" to the `node` at `jid` without any item. This merely fans out
        a notification. The exact semantics can be checked in :xep:`60`.
        """
        await self.publish(jid, node, None)

    async def retract(self, jid, node, id_, *, notify=False):
        """
        Retract a previously published item from a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to send a notify from.
        :type node: :class:`str`
        :param id_: The ID of the item to retract.
        :type id_: :class:`str`
        :param notify: Flag indicating whether subscribers shall be notified
            about the retraction.
        :type notify: :class:`bool`
        :raises aioxmpp.errors.XMPPError: as returned by the service

        Retract an item previously published to `node` at `jid`. `id_` must be
        the ItemID of the item to retract.

        If `notify` is set to true, notifications will be generated (by setting
        the `notify` attribute on the retraction request).
        """
        retract = pubsub_xso.Retract()
        retract.node = node
        item = pubsub_xso.Item()
        item.id_ = id_
        retract.item = item
        retract.notify = notify

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.SET)
        iq.payload = pubsub_xso.Request(
            retract
        )

        await self.client.send(iq)

    async def create(self, jid, node=None):
        """
        Create a new node at a service.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to create.
        :type node: :class:`str` or :data:`None`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The name of the created node.
        :rtype: :class:`str`

        If `node` is :data:`None`, an instant node is created (see :xep:`60`).
        The server may not support or allow the creation of instant nodes.

        Return the actual `node` identifier.
        """

        create = pubsub_xso.Create()
        create.node = node

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=jid,
            payload=pubsub_xso.Request(create)
        )

        response = await self.client.send(iq)

        if response is not None and response.payload.node is not None:
            return response.payload.node

        return node

    async def delete(self, jid, node, *, redirect_uri=None):
        """
        Delete an existing node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the PubSub node to delete.
        :type node: :class:`str` or :data:`None`
        :param redirect_uri: A URI to send to subscribers to indicate a
            replacement for the deleted node.
        :type redirect_uri: :class:`str` or :data:`None`
        :raises aioxmpp.errors.XMPPError: as returned by the service

        Optionally, a `redirect_uri` can be given. The `redirect_uri` will be
        sent to subscribers in the message notifying them about the node
        deletion.
        """

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerDelete(
                    node,
                    redirect_uri=redirect_uri
                )
            )
        )

        await self.client.send(iq)

    async def get_nodes(self, jid, node=None):
        """
        Request all nodes at a service or collection node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the collection node to query
        :type node: :class:`str` or :data:`None`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The list of nodes at the service or collection node.
        :rtype: :class:`~collections.abc.Sequence` of tuples consisting of the
            node name and its description.

        Request the nodes available at `jid`. If `node` is not :data:`None`,
        the request returns the children of the :xep:`248` collection node
        `node`. Make sure to check for the appropriate server feature first.

        Return a list of tuples consisting of the node names and their
        description (if available, otherwise :data:`None`). If more information
        is needed, use :meth:`.DiscoClient.get_items` directly.

        Only nodes whose :attr:`~.disco.xso.Item.jid` match the `jid` are
        returned.
        """

        response = await self._disco.query_items(
            jid,
            node=node,
        )

        result = []
        for item in response.items:
            if item.jid != jid:
                continue
            result.append((
                item.node,
                item.name,
            ))

        return result

    async def get_node_affiliations(self, jid, node):
        """
        Return the affiliations of other jids at a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the node to query
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The response from the service.
        :rtype: :class:`.xso.OwnerRequest`

        The affiliations are returned as :class:`.xso.OwnerRequest` instance
        whose :attr:`~.xso.OwnerRequest.payload` is a
        :class:`.xso.OwnerAffiliations` instance.
        """
        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.GET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerAffiliations(node),
            )
        )

        return await self.client.send(iq)

    async def get_node_subscriptions(self, jid, node):
        """
        Return the subscriptions of other jids with a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the node to query
        :type node: :class:`str`
        :raises aioxmpp.errors.XMPPError: as returned by the service
        :return: The response from the service.
        :rtype: :class:`.xso.OwnerRequest`

        The subscriptions are returned as :class:`.xso.OwnerRequest` instance
        whose :attr:`~.xso.OwnerRequest.payload` is a
        :class:`.xso.OwnerSubscriptions` instance.
        """
        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.GET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerSubscriptions(node),
            )
        )

        return await self.client.send(iq)

    async def change_node_affiliations(self, jid, node, affiliations_to_set):
        """
        Update the affiliations at a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the node to modify
        :type node: :class:`str`
        :param affiliations_to_set: The affiliations to set at the node.
        :type affiliations_to_set: :class:`~collections.abc.Iterable` of tuples
            consisting of the JID to affiliate and the affiliation to use.
        :raises aioxmpp.errors.XMPPError: as returned by the service

        `affiliations_to_set` must be an iterable of pairs (`jid`,
        `affiliation`), where the `jid` indicates the JID for which the
        `affiliation` is to be set.
        """
        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerAffiliations(
                    node,
                    affiliations=[
                        pubsub_xso.OwnerAffiliation(
                            jid,
                            affiliation
                        )
                        for jid, affiliation in affiliations_to_set
                    ]
                )
            )
        )

        await self.client.send(iq)

    async def change_node_subscriptions(self, jid, node, subscriptions_to_set):
        """
        Update the subscriptions at a node.

        :param jid: Address of the PubSub service.
        :type jid: :class:`aioxmpp.JID`
        :param node: Name of the node to modify
        :type node: :class:`str`
        :param subscriptions_to_set: The subscriptions to set at the node.
        :type subscriptions_to_set: :class:`~collections.abc.Iterable` of
            tuples consisting of the JID to (un)subscribe and the subscription
            level to use.
        :raises aioxmpp.errors.XMPPError: as returned by the service

        `subscriptions_to_set` must be an iterable of pairs (`jid`,
        `subscription`), where the `jid` indicates the JID for which the
        `subscription` is to be set.
        """
        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerSubscriptions(
                    node,
                    subscriptions=[
                        pubsub_xso.OwnerSubscription(
                            jid,
                            subscription
                        )
                        for jid, subscription in subscriptions_to_set
                    ]
                )
            )
        )

        await self.client.send(iq)

    async def purge(self, jid, node):
        """
        Delete all items from a node.

        :param jid: JID of the PubSub service
        :param node: Name of the PubSub node
        :type node: :class:`str`

        Requires :attr:`.xso.Feature.PURGE`.
        """

        iq = aioxmpp.stanza.IQ(
            type_=aioxmpp.structs.IQType.SET,
            to=jid,
            payload=pubsub_xso.OwnerRequest(
                pubsub_xso.OwnerPurge(
                    node
                )
            )
        )

        await self.client.send(iq)
