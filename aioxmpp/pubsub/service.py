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
# General Public License for more details.
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


class Service(aioxmpp.service.Service):
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
          get_node_subscriptions

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

    .. automethod:: get_node_subscriptions

    Receiving notifications:

    .. autosignal:: on_item_published(jid, node, item, *, message=None)

    .. autosignal:: on_item_retracted(jid, node, id_, *, message=None)

    .. autosignal:: on_node_deleted(jid, node, *, redirect_uri=None, message=None)

    .. autosignal:: on_affiliation_update(jid, node, affiliation, *, message=None)

    .. autosignal:: on_subscription_update(jid, node, state, *, subid=None, message=None)

    """

    ORDER_AFTER = [
        aioxmpp.disco.Service
    ]

    on_item_published = aioxmpp.callbacks.Signal(doc=
    """
    Fires when a new item is published to a node to which we have a
    subscription.

    The node at which the item has been published is identified by `jid` and
    `node`. `item` is the :class:`xso.EventItem` payload.

    `message` is the :class:`.Message` which carried the notification.
    If a notification message contains more than one published item, the event
    is fired for each of the items, and `message` is passed to all of them.
    """)  # NOQA

    on_item_retracted = aioxmpp.callbacks.Signal(doc=
    """
    Fires when an item is retracted from a node to which we have a subscription.

    The node at which the item has been retracted is identified by `jid` and
    `node`. `id_` is the ID of the item which has been retract.

    `message` is the :class:`.Message` which carried the notification.
    If a notification message contains more than one retracted item, the event
    is fired for each of the items, and `message` is passed to all of them.
    """)  # NOQA

    on_node_deleted = aioxmpp.callbacks.Signal(doc=
    """
    Fires when a node is deleted. `jid` and `node` identify the node.

    If the notification included a redirection URI, it is passed as
    `redirect_uri`. Otherwise, :data:`None` is passed for `redirect_uri`.

    `message` is the :class:`.Message` which carried the notification.
    """)  # NOQA

    on_affiliation_update = aioxmpp.callbacks.Signal(doc=
    """
    Fires when the affiliation with a node is updated.

    `jid` and `node` identify the node for which the affiliation was updated.
    `affiliation` is the new affiliaton.

    `message` is the :class:`.Message` which carried the notification.
    """)  # NOQA

    on_subscription_update = aioxmpp.callbacks.Signal(doc=
    """
    Fires when the subscription state is updated.

    `jid` and `node` identify the node for which the subscription was updated.
    `subid` is optional and if it is not :data:`None` it is the affected
    subscription id. `state` is the new subscription state.

    This event can happen in several cases, for example when a subscription
    request is approved by the node owner or when a subscription is cancelled.

    `message` is the :class:`.Message` which carried the notification.s
    """)  # NOQA

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._disco = self._client.summon(aioxmpp.disco.Service)

        client.stream.service_inbound_message_filter.register(
            self.filter_inbound_message,
            type(self)
        )

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

    @asyncio.coroutine
    def get_features(self, jid):
        """
        Return the features as set of values from :class:`.xso.Feature`. To
        get the full feature information, resort to using
        :meth:`.disco.Service.query_info` directly on `jid`.

        Features returned by the peer which are not valid pubsub features are
        not returned.
        """
        response = yield from self._disco.query_info(jid)
        result = set()
        for feature in response.features:
            try:
                result.add(pubsub_xso.Feature(feature))
            except ValueError:
                continue
        return result

    @asyncio.coroutine
    def subscribe(self, jid, node=None, *,
                  subscription_jid=None,
                  config=None):
        """
        Subscribe to the pubsub `node` hosted at `jid`.

        By default, the subscription request will be for the bare JID of the
        client. It can be specified explicitly using the `subscription_jid`
        argument.

        If the service requires it or if it makes sense for other reasons, the
        subscription configuration :class:`~.forms.xso.Data` form can be passed
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

        response = yield from self.client.stream.send_iq_and_wait_for_reply(
            iq
        )
        return response

    @asyncio.coroutine
    def unsubscribe(self, jid, node=None, *,
                    subscription_jid=None,
                    subid=None):
        """
        Unsubscribe from the pubsub `node` hosted at `jid`.

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

        yield from self.client.stream.send_iq_and_wait_for_reply(
            iq
        )

    @asyncio.coroutine
    def get_subscription_config(self, jid, node=None, *,
                                subscription_jid=None,
                                subid=None):
        """
        Request the current configuration of a subscription to the pubsub
        `node` hosted at `jid`.

        By default, the request will be on behalf of the bare JID of the
        client. It can be overriden using the `subscription_jid` argument.

        If available, the `subid` should also be specified.

        On success, the :class:`~.forms.xso.Data` form is returned.

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

        response = yield from self.client.stream.send_iq_and_wait_for_reply(
            iq
        )
        return response.options.data

    @asyncio.coroutine
    def set_subscription_config(self, jid, data, node=None, *,
                                subscription_jid=None,
                                subid=None):
        """
        Update the subscription configuration of a subscription to the pubsub
        `node` hosted at `jid`.

        By default, the request will be on behalf of the bare JID of the
        client. It can be overriden using the `subscription_jid` argument.

        If available, the `subid` should also be specified.

        The configuration must be given as `data` as a
        :class:`~.forms.xso.Data` instance.

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

        yield from self.client.stream.send_iq_and_wait_for_reply(
            iq
        )

    @asyncio.coroutine
    def get_default_config(self, jid, node=None):
        """
        Request the default configuration of the pubsub `node` hosted at
        `jid`.

        On success, the :class:`~.forms.xso.Data` form is returned.

        If an error occurs, the corresponding :class:`~.errors.XMPPError` is
        raised.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Default(node=node)
        )

        response = yield from self.client.stream.send_iq_and_wait_for_reply(iq)
        return response.payload.data

    @asyncio.coroutine
    def get_items(self, jid, node, *, max_items=None):
        """
        Request the most recent items from the pubsub `node` hosted at `jid`.

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

        return (yield from self.client.stream.send_iq_and_wait_for_reply(iq))

    @asyncio.coroutine
    def get_items_by_id(self, jid, node, ids):
        """
        Request specific items by their IDs from the pubsub `node` hosted at
        `jid`.

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

        return (yield from self.client.stream.send_iq_and_wait_for_reply(iq))

    @asyncio.coroutine
    def get_subscriptions(self, jid, node=None):
        """
        Return a :class:`.xso.Subscriptions` object which contains all the
        subscriptions of the local entity to the `node` located at `jid`.

        If `node` is :data:`None`, subscriptions on all nodes of the entity
        `jid` are listed.
        """

        iq = aioxmpp.stanza.IQ(to=jid, type_=aioxmpp.structs.IQType.GET)
        iq.payload = pubsub_xso.Request(
            pubsub_xso.Subscriptions(node=node)
        )

        response = yield from self.client.stream.send_iq_and_wait_for_reply(iq)
        return response.payload

    @asyncio.coroutine
    def publish(self, jid, node, payload, *, id_=None):
        """
        Publish the given `payload` (which must be a :class:`aioxmpp.xso.XSO`
        registered with :attr:`.xso.Item.registered_payload`).

        The item is published to `node` at `jid`. If `id_` is given, it is used
        as the ID for the item. If an item with the same ID already exists at
        the node, it is replaced. If no ID is given, a ID is generated by the
        server.

        Return the ID of the item as published.
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

        response = yield from self.client.stream.send_iq_and_wait_for_reply(iq)

        if response.payload.item is not None:
            return response.payload.item.id_ or id_
        return id_

    @asyncio.coroutine
    def notify(self, jid, node):
        """
        "Publish" to the `node` at `jid` without any item. This merely fans out
        a notification. The exact semantics can be checked in :xep:`60`.
        """
        yield from self.publish(jid, node, None)

    @asyncio.coroutine
    def retract(self, jid, node, id_, *, notify=False):
        """
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

        yield from self.client.stream.send_iq_and_wait_for_reply(iq)

    @asyncio.coroutine
    def create(self, jid, node=None):
        """
        Create a new pubsub `node` at the given `jid`.

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

        response = yield from self.client.stream.send_iq_and_wait_for_reply(iq)

        if response is not None and response.payload.node is not None:
            return response.payload.node

        return node

    @asyncio.coroutine
    def delete(self, jid, node, *, redirect_uri=None):
        """
        Delete an existing pubsub `node` at the given `jid`.

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

        yield from self.client.stream.send_iq_and_wait_for_reply(iq)

    @asyncio.coroutine
    def get_nodes(self, jid, node=None):
        """
        Request the nodes available at `jid`. If `node` is not :data:`None`,
        the request returns the children of the :xep:`248` collection node
        `node`. Make sure to check for the appropriate server feature first.

        Return a list of tuples consisting of the node names and their
        description (if available, otherwise :data:`None`). If more information
        is needed, use :meth:`.disco.Service.get_items` directly.

        Only nodes whose :attr:`~.disco.xso.Item.jid` match the `jid` are
        returned.
        """

        response = yield from self._disco.query_items(
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

    @asyncio.coroutine
    def get_node_affiliations(self, jid, node):
        """
        Return the affiliations of other jids at the pubsub `node` at `jid`.

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

        return (yield from self.client.stream.send_iq_and_wait_for_reply(iq))

    @asyncio.coroutine
    def get_node_subscriptions(self, jid, node):
        """
        Return the subscriptions of other jids at the pubsub `node` at `jid`.

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

        return (yield from self.client.stream.send_iq_and_wait_for_reply(iq))

    @asyncio.coroutine
    def change_node_affiliations(self, jid, node, affiliations_to_set):
        """
        Update the affiliations of the pubsub `node` at `jid`.

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

        yield from self.client.stream.send_iq_and_wait_for_reply(iq)

    @asyncio.coroutine
    def change_node_subscriptions(self, jid, node, subscriptions_to_set):
        """
        Update the subscriptions of the pubsub `node` at `jid`.

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

        yield from self.client.stream.send_iq_and_wait_for_reply(iq)
