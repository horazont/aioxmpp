import asyncio

import aioxmpp.service

import aioxmpp.callbacks as callbacks
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs

from aioxmpp.utils import namespaces

from . import xso as roster_xso


_Sentinel = object()


class Item:
    """
    Represent an entry in the roster. These entries are mutable, see the
    documentation of :class:`Service` for details on the lifetime of
    :class:`Item` instances within a :class:`Service` instance.

    .. attribute:: jid

       The :class:`~aioxmpp.structs.JID` of the entry. This is always a bare
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


class Service(aioxmpp.service.Service):
    """
    A roster client :class:`aioxmpp.service.Service`.

    `client` must be a :class:`~aioxmpp.node.AbstractClient` or
    subclass. Ideally, you create :class:`Service` instances using
    :meth:`.AbstractClient.summon`.

    The interaction with a roster service happens mainly by accessing the
    attributes holding the state and using the events to be notified of state
    changes:

    Attributes for accessing the roster:

    .. attribute:: items

       A dictionary mapping :class:`~.structs.JID` instances to corresponding
       :class:`Item` instances.

    .. attribute:: groups

       A dictionary which allows group-based access to :class:`Item`
       instances. The dictionaries keys are the names of the groups, the values
       are :class:`set` instances, which hold the :class:`Item` instances in
       that group.

       At no point one can observe empty :class:`set` instances in this
       dictionary.

    Signals:

    .. method:: on_initial_roster_received()

       Fires when the initial roster has been received. Note that if roster
       versioning is used, the initial roster may not be up-to-date. The server
       is allowed to tell the client to re-use its local state and deliver
       changes using roster pushes.

       The roster data has already been imported at the time the callback is
       fired.

    .. method:: on_entry_added(item)

       Fires when an `item` has been added to the roster.

    .. method:: on_entry_name_changed(item)

       Fires when a roster update changed the name of the `item`. The new name
       is already applied to the `item`.

    .. method:: on_entry_subscription_state_changed(item)

       Fires when a roster update changes any of the :attr:`Item.subscription`,
       :attr:`Item.ask` or :attr:`Item.approved` attributes. The new values are
       already applied to `item`.

       The event always fires once per update; even if the update changes
       multiple of the above attributes, the event is only fired once.

    .. method:: on_entry_added_to_group(item, group_name)

       Fires when an update adds an `item` to a group. The :attr:`Item.groups`
       attribute is already updated (not only with this, but also other group
       updates, including removals) when this event is fired.

       The event fires for each added group in an update, thus it may fire more
       than once per update.

       The name of the new group is in `group_name`.

    .. method:: on_entry_removed_from_group(item, group_name)

       Fires when an update removes an `item` from a group. The
       :attr:`Item.groups` attribute is already updated (not only with this,
       but also other group updates, including additions) when this event is
       fired.

       The event fires for each removed group in an update, thus it may fire
       more than once per update.

       The name of the new group is in `group_name`.

    .. method:: on_entry_removed(item)

       Fires after an entry has been removed from the roster. The entry is
       already removed from all bookkeeping structures, but the values on the
       `item` object are the same as right before the removal.

    Modifying roster contents:

    .. automethod:: set_entry

    .. automethod:: remove_entry

    Import/Export of roster data:

    .. automethod:: export_as_json

    .. automethod:: import_from_json

    To make use of roster versioning, use the above two methods. The general
    workflow is to :meth:`export_as_json` the roster after disconnecting and
    storing it for the next connection attempt. **Before** connecting, the
    stored data needs to be loaded using :meth:`import_from_json`. This only
    needs to happen after a new :class:`Service` has been created, as roster
    services won’t delete roster contents between two connections on the same
    :class:`.node.AbstractClient` instance.
    """

    on_initial_roster_received = callbacks.Signal()
    on_entry_name_changed = callbacks.Signal()
    on_entry_subscription_state_changed = callbacks.Signal()
    on_entry_removed = callbacks.Signal()
    on_entry_added = callbacks.Signal()
    on_entry_added_to_group = callbacks.Signal()
    on_entry_removed_from_group = callbacks.Signal()

    def __init__(self, client):
        super().__init__(client)

        self._bse_token = client.before_stream_established.connect(
            self._request_initial_roster
        )

        client.stream.register_iq_request_coro(
            "set",
            roster_xso.Query,
            self.handle_roster_push)

        self.items = {}
        self.groups = {}
        self.version = None

    @asyncio.coroutine
    def _shutdown(self):
        self.client.stream.unregister_iq_request_coro(
            "set",
            roster_xso.Query)

    def _update_entry(self, xso_item):
        try:
            stored_item = self.items[xso_item.jid]
        except KeyError:
            stored_item = Item.from_xso_item(xso_item)
            self.items[xso_item.jid] = stored_item
            self.on_entry_added(stored_item)
            for group in stored_item.groups:
                self.groups.setdefault(group, set()).add(stored_item)
            return

        to_call = []

        if stored_item.name != xso_item.name:
            to_call.append(self.on_entry_name_changed)

        if     (stored_item.subscription != xso_item.subscription or
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
            self.groups.setdefault(group, set()).add(stored_item)
            self.on_entry_added_to_group(stored_item, group)

        for group in removed_from_groups:
            groupset = self.groups[group]
            groupset.remove(stored_item)
            if not groupset:
                del self.groups[group]
            self.on_entry_removed_from_group(stored_item, group)

    @asyncio.coroutine
    def handle_roster_push(self, iq):
        if iq.from_:
            raise errors.XMPPAuthError((namespaces.stanzas, "forbidden"))

        request = iq.payload

        for item in request.items:
            if item.subscription == "remove":
                try:
                    old_item = self.items.pop(item.jid)
                except KeyError:
                    pass
                else:
                    for group in old_item.groups:
                        groupset = self.groups[group]
                        groupset.remove(old_item)
                        if not groupset:
                            del self.groups[group]
                    self.on_entry_removed(old_item)
            else:
                self._update_entry(item)

        self.version = request.ver

    @asyncio.coroutine
    def _request_initial_roster(self):
        iq = stanza.IQ(type_="get")
        iq.payload = roster_xso.Query()

        if self.client.stream_features.has_feature(
                roster_xso.RosterVersioningFeature):
            iq.payload.ver = self.version

        response = yield from self.client.stream.send_iq_and_wait_for_reply(
            iq,
            timeout=self.client.negotiation_timeout.total_seconds()
        )

        if response is None:
            self.on_initial_roster_received()
            return True

        self.version = response.ver

        actual_jids = {item.jid for item in response.items}
        known_jids = set(self.items.keys())

        for removed_jid in known_jids - actual_jids:
            old_item = self.items.pop(removed_jid)
            self.on_entry_removed(old_item)

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

    @asyncio.coroutine
    def set_entry(self, jid, *,
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

        `remove_from_groups` takes precedence over `add_to_groups`.

        `timeout` is the time in seconds to wait for a confirmation by the
        server.

        Note that the changes may not be visible immediately after his
        coroutine returns in the :attr:`items` and :attr:`groups`
        attributes. The :class:`Service` waits for the "official" roster push
        from the server for updating the data structures and firing events, to

        This may raise arbitrary :class:`.errors.XMPPError` exceptions if the
        server replies with an error and also any kind of connection error if
        the connection gets fatally terminated while waiting for a response.
        prevent going out-of-sync with other clients.
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

        yield from self.client.stream.send_iq_and_wait_for_reply(
            stanza.IQ(payload=roster_xso.Query(items=[
                item
            ])),
            timeout=timeout
        )

    @asyncio.coroutine
    def remove_entry(self, jid, *, timeout=None):
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
        yield from self.client.stream.send_iq_and_wait_for_reply(
            stanza.IQ(payload=roster_xso.Query(items=[
                roster_xso.Item(
                    jid=jid,
                    subscription="remove"
                )
            ])),
            timeout=timeout
        )
