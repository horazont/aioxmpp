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
import logging

import aioxmpp.service

import aioxmpp.callbacks as callbacks
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs

from . import xso as roster_xso


logger = logging.getLogger(__name__)


_Sentinel = object()


class Item:
    """
    Represent an entry in the roster. These entries are mutable, see the
    documentation of :class:`Service` for details on the lifetime of
    :class:`Item` instances within a :class:`Service` instance.

    .. attribute:: jid

       The :class:`~aioxmpp.JID` of the entry. This is always a bare
       JID.

    .. attribute:: name

       The display name of the entry, if any.

    .. attribute:: groups

       A :class:`set` of names of groups in which the roster entry is.

    .. attribute:: subscription

       The subscription status of the entry. One of ``"none"``, ``"to"``,
       ``"from"`` and ``"both"`` (in contrast to :class:`.xso.Item`,
       ``"remove"`` cannot occur here).

    .. attribute:: ask

       The ``ask`` attribute of the roster entry.

    .. attribute:: approved

       The ``approved`` attribute of the roster entry.

    The data of a roster entry can conveniently be exported to JSON:

    .. automethod:: export_as_json

    To mutate the roster entry, some handy methods are provided:

    .. automethod:: update_from_json

    .. automethod:: update_from_xso_item

    To create a roster entry from a :class:`.xso.Item`, use the
    :meth:`from_xso_item` class method.

    .. automethod:: from_xso_item

    .. note::

       Do not confuse this with the XSO :class:`.xso.Item`.

    """
    def __init__(self, jid, *,
                 approved=False,
                 ask=None,
                 subscription="none",
                 name=None,
                 groups=()):
        super().__init__()
        self.jid = jid
        self.subscription = subscription
        self.approved = approved
        self.ask = ask
        self.name = name
        self.groups = set(groups)

    def update_from_xso_item(self, xso_item):
        """
        Update the attributes (except :attr:`jid`) with the values obtained
        from the gixen `xso_item`.

        `xso_item` must be a valid :class:`.xso.Item` instance.
        """
        self.subscription = xso_item.subscription
        self.approved = xso_item.approved
        self.ask = xso_item.ask
        self.name = xso_item.name
        self.groups = {group.name for group in xso_item.groups}

    @classmethod
    def from_xso_item(cls, xso_item):
        """
        Create a :class:`Item` with the :attr:`jid` set to the
        :attr:`.xso.Item.jid` obtained from `xso_item`. Then update that
        instance with `xso_item` using :meth:`update_from_xso_item` and return
        it.
        """
        item = cls(xso_item.jid)
        item.update_from_xso_item(xso_item)
        return item

    def export_as_json(self):
        """
        Return a :mod:`json`-compatible dictionary which contains the
        attributes of this :class:`Item` except its JID.
        """
        result = {
            "subscription": self.subscription,
        }

        if self.name:
            result["name"] = self.name

        if self.ask is not None:
            result["ask"] = self.ask

        if self.approved:
            result["approved"] = self.approved

        if self.groups:
            result["groups"] = sorted(self.groups)

        return result

    def update_from_json(self, data):
        """
        Update the attributes of this :class:`Item` using the values obtained
        from the dictionary `data`.

        The format of `data` should be the same as the format returned by
        :meth:`export_as_json`.
        """
        self.subscription = data.get("subscription", "none")
        self.approved = bool(data.get("approved", False))
        self.ask = data.get("ask", None)
        self.name = data.get("name", None)
        self.groups = set(data.get("groups", []))


class RosterClient(aioxmpp.service.Service):
    """
    A roster client :class:`aioxmpp.service.Service`.

    The interaction with a roster service happens mainly by accessing the
    attributes holding the state and using the events to be notified of state
    changes:

    Attributes for accessing the roster:

    .. attribute:: items

       A dictionary mapping :class:`~aioxmpp.JID` instances to corresponding
       :class:`Item` instances.

    .. attribute:: groups

       A dictionary which allows group-based access to :class:`Item`
       instances. The dictionaries keys are the names of the groups, the values
       are :class:`set` instances, which hold the :class:`Item` instances in
       that group.

       At no point one can observe empty :class:`set` instances in this
       dictionary.

    The :class:`Item` instances stay the same, as long as they represent the
    identical roster entry on the remote side. That is, if the name or
    subscription state are changed in the server side roster, the :class:`Item`
    instance stays the same, but the attributes are mutated. However, if the
    entry is removed from the server roster and re-added later for the same
    JID, it will be a different :class:`Item` instance.

    Signals:

    .. signal:: on_initial_roster_received()

       Fires when the initial roster has been received. Note that if roster
       versioning is used, the initial roster may not be up-to-date. The server
       is allowed to tell the client to re-use its local state and deliver
       changes using roster pushes. In that case, the
       :meth:`on_initial_roster_received` event fires immediately, so that the
       user sees whatever roster has been set up for versioning before the
       stream was established; updates pushed by the server are delivered using
       the normal events.

       The roster data has already been imported at the time the callback is
       fired.

       Note that the initial roster is diffed against whatever is in the local
       store and events are fired just like for normal push updates. Thus, in
       general, you won’t need this signal; it might be better to listen for
       the events below.

    .. signal:: on_entry_added(item)

       Fires when an `item` has been added to the roster. The attributes of the
       `item` are up-to-date when this callback fires.

       When the event fires, the bookkeeping structures are already updated.
       This implies that :meth:`on_group_added` is called before
       :meth:`on_entry_added` if the entry adds a new group.

    .. signal:: on_entry_name_changed(item)

       Fires when a roster update changed the name of the `item`. The new name
       is already applied to the `item`.

    .. signal:: on_entry_subscription_state_changed(item)

       Fires when a roster update changes any of the :attr:`Item.subscription`,
       :attr:`Item.ask` or :attr:`Item.approved` attributes. The new values are
       already applied to `item`.

       The event always fires once per update, even if the update changes
       more than one of the above attributes.

    .. signal:: on_entry_added_to_group(item, group_name)

       Fires when an update adds an `item` to a group. The :attr:`Item.groups`
       attribute is already updated (not only with this, but also other group
       updates, including removals) when this event is fired.

       The event fires for each added group in an update, thus it may fire more
       than once per update.

       The name of the new group is in `group_name`.

       At the time the event fires, the bookkeeping structures for the group
       are already updated; this implies that :meth:`on_group_added` fires
       *before* :meth:`on_entry_added_to_group` if the entry added a new group.

    .. signal:: on_entry_removed_from_group(item, group_name)

       Fires when an update removes an `item` from a group. The
       :attr:`Item.groups` attribute is already updated (not only with this,
       but also other group updates, including additions) when this event is
       fired.

       The event fires for each removed group in an update, thus it may fire
       more than once per update.

       The name of the new group is in `group_name`.

       At the time the event fires, the bookkeeping structures are already
       updated; this implies that :meth:`on_group_removed` fires *before*
       :meth:`on_entry_removed_from_group` if the removal of an entry from a
       group causes the group to vanish.

    .. signal:: on_entry_removed(item)

       Fires after an entry has been removed from the roster. The entry is
       already removed from all bookkeeping structures, but the values on the
       `item` object are the same as right before the removal.

       This implies that :meth:`on_group_removed` fires *before*
       :meth:`on_entry_removed` if the removal of an entry causes a group to
       vanish.

    .. signal:: on_group_added(group)

        Fires after a new group has been added to the bookkeeping structures.

        :param group: Name of the new group.
        :type group: :class:`str`

        At the time the event fires, the group is empty.

        .. versionadded:: 0.9

    .. signal:: on_group_removed(group)

        Fires after a new group has been removed from the bookkeeping
        structures.

        :param group: Name of the old group.
        :type group: :class:`str`

        At the time the event fires, the group is empty.

        .. versionadded:: 0.9

    Modifying roster contents:

    .. automethod:: set_entry

    .. automethod:: remove_entry

    Managing presence subscriptions:

    .. automethod:: approve

    .. automethod:: subscribe

    .. signal:: on_subscribe(stanza)

       Fires when a peer requested a subscription. The whole stanza received is
       included as `stanza`.

       .. seealso::

          To approve a subscription request, use :meth:`approve`.

    .. signal:: on_subscribed(stanza)

       Fires when a peer has confirmed a previous subscription request. The
       ``"subscribed"`` stanza is included as `stanza`.

    .. signal:: on_unsubscribe(stanza)

       Fires when a peer cancelled their subscription for our presence. As per
       :rfc:`6121`, the server forwards the ``"unsubscribe"`` presence stanza
       (which is included as `stanza` argument) *before* sending the roster
       push.

       Unless your application is interested in the specific cause of a
       subscription state change, it is not necessary to use this signal; the
       subscription state change will be covered by
       :meth:`on_entry_subscription_state_changed`.

    .. signal:: on_unsubscribed(stanza)

       Fires when a peer cancelled our subscription. As per :rfc:`6121`, the
       server forwards the ``"unsubscribed"`` presence stanza (which is
       included as `stanza` argument) *before* sending the roster push.

       Unless your application is interested in the specific cause of a
       subscription state change, it is not necessary to use this signal; the
       subscription state change will be covered by
       :meth:`on_entry_subscription_state_changed`.

    Import/Export of roster data:

    .. automethod:: export_as_json

    .. automethod:: import_from_json

    To make use of roster versioning, use the above two methods. The general
    workflow is to :meth:`export_as_json` the roster after disconnecting and
    storing it for the next connection attempt. **Before** connecting, the
    stored data needs to be loaded using :meth:`import_from_json`. This only
    needs to happen after a new :class:`Service` has been created, as roster
    services won’t delete roster contents between two connections on the same
    :class:`.Client` instance.

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.roster.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.
    """

    ORDER_AFTER = [
        aioxmpp.dispatcher.SimplePresenceDispatcher,
    ]

    on_initial_roster_received = callbacks.Signal()
    on_entry_name_changed = callbacks.Signal()
    on_entry_subscription_state_changed = callbacks.Signal()
    on_entry_removed = callbacks.Signal()
    on_entry_added = callbacks.Signal()
    on_entry_added_to_group = callbacks.Signal()
    on_entry_removed_from_group = callbacks.Signal()

    on_group_added = callbacks.Signal()
    on_group_removed = callbacks.Signal()

    on_subscribed = callbacks.Signal()
    on_subscribe = callbacks.Signal()
    on_unsubscribed = callbacks.Signal()
    on_unsubscribe = callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._bse_token = client.before_stream_established.connect(
            self._request_initial_roster
        )

        self.__roster_lock = asyncio.Lock()

        self.items = {}
        self.groups = {}
        self.version = None

    def _update_entry(self, xso_item):
        try:
            stored_item = self.items[xso_item.jid]
        except KeyError:
            stored_item = Item.from_xso_item(xso_item)
            self.items[xso_item.jid] = stored_item
            for group in stored_item.groups:
                try:
                    group_members = self.groups[group]
                except KeyError:
                    group_members = self.groups.setdefault(group, set())
                    self.on_group_added(group)
                group_members.add(stored_item)
            self.on_entry_added(stored_item)
            return

        to_call = []

        if stored_item.name != xso_item.name:
            to_call.append(self.on_entry_name_changed)

        if (stored_item.subscription != xso_item.subscription or
                stored_item.approved != xso_item.approved or
                stored_item.ask != xso_item.ask):
            to_call.append(self.on_entry_subscription_state_changed)

        old_groups = set(stored_item.groups)

        stored_item.update_from_xso_item(xso_item)

        new_groups = set(stored_item.groups)

        removed_from_groups = old_groups - new_groups
        added_to_groups = new_groups - old_groups

        for cb in to_call:
            cb(stored_item)

        for group in added_to_groups:
            try:
                group_members = self.groups[group]
            except KeyError:
                group_members = self.groups.setdefault(group, set())
                self.on_group_added(group)
            group_members.add(stored_item)
            self.on_entry_added_to_group(stored_item, group)

        for group in removed_from_groups:
            groupset = self.groups[group]
            groupset.remove(stored_item)
            if not groupset:
                del self.groups[group]
                self.on_group_removed(group)
            self.on_entry_removed_from_group(stored_item, group)

    @aioxmpp.service.iq_handler(
        aioxmpp.structs.IQType.SET,
        roster_xso.Query)
    async def handle_roster_push(self, iq):
        if iq.from_ and iq.from_ != self.client.local_jid.bare():
            raise errors.XMPPAuthError(errors.ErrorCondition.FORBIDDEN)

        request = iq.payload

        async with self.__roster_lock:
            for item in request.items:
                if item.subscription == "remove":
                    try:
                        old_item = self.items.pop(item.jid)
                    except KeyError:
                        pass
                    else:
                        self._remove_from_groups(old_item, old_item.groups)
                        self.on_entry_removed(old_item)
                else:
                    self._update_entry(item)

            self.version = request.ver

    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.SUBSCRIBE,
        None)
    def handle_subscribe(self, stanza):
        self.on_subscribe(stanza)

    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.SUBSCRIBED,
        None)
    def handle_subscribed(self, stanza):
        self.on_subscribed(stanza)

    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.UNSUBSCRIBED,
        None)
    def handle_unsubscribed(self, stanza):
        self.on_unsubscribed(stanza)

    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.UNSUBSCRIBE,
        None)
    def handle_unsubscribe(self, stanza):
        self.on_unsubscribe(stanza)

    def _remove_from_groups(self, item_to_remove, groups):
        for group in groups:
            try:
                group_members = self.groups[group]
            except KeyError:
                continue
            group_members.remove(item_to_remove)
            if not group_members:
                del self.groups[group]
                self.on_group_removed(group)

    async def _request_initial_roster(self):
        iq = stanza.IQ(type_=structs.IQType.GET)
        iq.payload = roster_xso.Query()

        async with self.__roster_lock:
            logger.debug("requesting initial roster")
            if self.client.stream_features.has_feature(
                    roster_xso.RosterVersioningFeature):
                logger.debug("requesting incremental updates (old ver = %s)",
                             self.version)
                iq.payload.ver = self.version

            response = await self.client.send(
                iq,
                timeout=self.client.negotiation_timeout.total_seconds()
            )

            if response is None:
                logger.debug("roster will be updated incrementally")
                self.on_initial_roster_received()
                return True

            self.version = response.ver
            logger.debug("roster update received (new ver = %s)", self.version)

            actual_jids = {item.jid for item in response.items}
            known_jids = set(self.items.keys())

            removed_jids = known_jids - actual_jids
            logger.debug("jids dropped: %r", removed_jids)

            for removed_jid in removed_jids:
                old_item = self.items.pop(removed_jid)
                self._remove_from_groups(old_item, old_item.groups)
                self.on_entry_removed(old_item)

            logger.debug("jids updated: %r", actual_jids - removed_jids)
            for item in response.items:
                self._update_entry(item)

            self.on_initial_roster_received()
            return True

    def export_as_json(self):
        """
        Export the whole roster as currently stored on the client side into a
        JSON-compatible dictionary and return that dictionary.
        """
        return {
            "items": {
                str(jid): item.export_as_json()
                for jid, item in self.items.items()
            },
            "ver": self.version
        }

    def import_from_json(self, data):
        """
        Replace the current roster with the :meth:`export_as_json`-compatible
        dictionary in `data`.

        No events are fired during this activity. After this method completes,
        the whole roster contents are exchanged with the contents from `data`.

        Also, no data is transferred to the server; this method is intended to
        be used for roster versioning. See below (in the docs of
        :class:`Service`).
        """
        self.version = data.get("ver", None)

        self.items.clear()
        self.groups.clear()
        for jid, data in data.get("items", {}).items():
            jid = structs.JID.fromstr(jid)
            item = Item(jid)
            item.update_from_json(data)
            self.items[jid] = item
            for group in item.groups:
                self.groups.setdefault(group, set()).add(item)

    async def set_entry(self, jid, *,
                  name=_Sentinel,
                  add_to_groups=frozenset(),
                  remove_from_groups=frozenset(),
                  timeout=None):
        """
        Set properties of a roster entry or add a new roster entry. The roster
        entry is identified by its bare `jid`.

        If an entry already exists, all values default to those stored in the
        existing entry. For example, if no `name` is given, the current name of
        the entry is re-used, if any.

        If the entry does not exist, it will be created on the server side.

        The `remove_from_groups` and `add_to_groups` arguments have to be based
        on the locally cached state, as XMPP does not support sending
        diffs. `remove_from_groups` takes precedence over `add_to_groups`.

        `timeout` is the time in seconds to wait for a confirmation by the
        server.

        Note that the changes may not be visible immediately after his
        coroutine returns in the :attr:`items` and :attr:`groups`
        attributes. The :class:`Service` waits for the "official" roster push
        from the server for updating the data structures and firing events, to
        ensure that consistent state with other clients is achieved.

        This may raise arbitrary :class:`.errors.XMPPError` exceptions if the
        server replies with an error and also any kind of connection error if
        the connection gets fatally terminated while waiting for a response.
        """

        existing = self.items.get(jid, Item(jid))

        post_groups = (existing.groups | add_to_groups) - remove_from_groups
        post_name = existing.name
        if name is not _Sentinel:
            post_name = name

        item = roster_xso.Item(
            jid=jid,
            name=post_name,
            groups=[
                roster_xso.Group(name=group_name)
                for group_name in post_groups
            ])

        await self.client.send(
            stanza.IQ(
                structs.IQType.SET,
                payload=roster_xso.Query(items=[
                    item
                ])
            ),
            timeout=timeout
        )

    async def remove_entry(self, jid, *, timeout=None):
        """
        Request removal of the roster entry identified by the given bare
        `jid`. If the entry currently has any subscription state, the server
        will send the corresponding unsubscribing presence stanzas.

        `timeout` is the maximum time in seconds to wait for a reply from the
        server.

        This may raise arbitrary :class:`.errors.XMPPError` exceptions if the
        server replies with an error and also any kind of connection error if
        the connection gets fatally terminated while waiting for a response.
        """
        await self.client.send(
            stanza.IQ(
                structs.IQType.SET,
                payload=roster_xso.Query(items=[
                    roster_xso.Item(
                        jid=jid,
                        subscription="remove"
                    )
                ])
            ),
            timeout=timeout
        )

    def approve(self, peer_jid):
        """
        (Pre-)approve a subscription request from `peer_jid`.

        :param peer_jid: The peer to (pre-)approve.

        This sends a ``"subscribed"`` presence to the peer; if the peer has
        previously asked for a subscription, this will seal the deal and create
        the subscription.

        If the peer has not requested a subscription (yet), it is marked as
        pre-approved by the server. A future subscription request by the peer
        will then be confirmed by the server automatically.

        .. note::

            Pre-approval is an OPTIONAL feature in :rfc:`6121`. It is announced
            as a stream feature.
        """
        self.client.enqueue(
            stanza.Presence(type_=structs.PresenceType.SUBSCRIBED,
                            to=peer_jid)
        )

    def subscribe(self, peer_jid):
        """
        Request presence subscription with the given `peer_jid`.

        This is deliberately not a coroutine; we don’t know whether the peer is
        online (usually) and they may defer the confirmation very long, if they
        confirm at all. Use :meth:`on_subscribed` to get notified when a peer
        accepted a subscription request.
        """
        self.client.enqueue(
            stanza.Presence(type_=structs.PresenceType.SUBSCRIBE,
                            to=peer_jid)
        )

    def unsubscribe(self, peer_jid):
        """
        Unsubscribe from the presence of the given `peer_jid`.
        """
        self.client.enqueue(
            stanza.Presence(type_=structs.PresenceType.UNSUBSCRIBE,
                            to=peer_jid)
        )
