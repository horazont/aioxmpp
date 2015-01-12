import asyncio
import collections

import asyncio_xmpp.plugins.base as base
import asyncio_xmpp.callbacks as callbacks
import asyncio_xmpp.jid as jid
import asyncio_xmpp.stanza as stanza
import asyncio_xmpp.presence as presence
import asyncio_xmpp.errors as errors

from .stanza import *

from asyncio_xmpp.utils import *

__all__ = [
    "RosterItemInfo",
    "RosterItemChange",
    "RosterClient",
    "PresenceClient",
    "compress_changeset",
]

class RosterItemInfo:
    """
    Information regarding a single roster item.
    """

    #: JID of the roster item
    jid = None

    #: Subscription state of the roster item. One of "none", "to", "from" or
    #: "both". This attribute is managed by the server.
    subscription = None

    #: Set of group names of which this element is part.
    groups = None

    #: True if there is a subscription pending to the peer. This attribute is
    #: managed by the server.
    pending_out = False

    #: Label for the roster entry. This may be None if no label is set.
    name = None

    #: True if the item has been pre-approved a clients resource. Not all
    #: servers support pre-approval. This attribute is managed by the server.
    #:
    #: .. seealso::
    #:
    #:     :meth:`RosterClient.request_subscription`
    approved = False

    def __init__(self, item=None):
        super().__init__()
        if item is not None:
            self.jid = item.jid
            self.subscription = item.subscription
            self.groups = set(
                group.name for group in item.groups
            )
            self.name = item.name
            self.pending_out = item.ask
            self.approved = item.approved
        else:
            self.groups = set()

    def make_iq_item(self):
        item = Item()
        item.jid = self.jid
        if self.name:
            item.name = self.name
        for group in self.groups:
            group_el = Group()
            group_el.name = group
            item.append(group_el)
        return item

_RosterItemChange = collections.namedtuple(
    "RosterItemChange",
    [
        "jid",
        "name",
        "add_to_groups",
        "remove_from_groups",
        "delete",
    ])

class RosterItemChange(_RosterItemChange):
    """
    Create a record for an individual change on a roster item. The roster item
    is identified by the *itemjid*.

    .. attribute:: RosterItemChange.jid

       The :class:`asyncio_xmpp.jid.JID` of the contact to whose roster entry
       the change shall be applied.

       This attribute is set through the *itemjid* parameter of the
       constructor. The constructor validates the *itemjid* to be a valid bare
       JID (either as string or as JID object).

    .. attribute:: RosterItemChange.name

       A tuple ``(old, new)`` for the name attribute, if it is included in the
       change or :data:`None` otherwise.

       This attribute is set through the *name* parameter of the
       constructor. The constructor validates that it is either :data:`None` or
       a sequence of two elements.

    .. attribute:: RosterItemChange.add_to_groups

       A dict mapping *group names* to *userdata*. The only thing relevant for
       the roster client implementation are the keys, which determine to which
       groups the roster item is added.

       The *userdata* is treated as opaque by the roster code. For an example
       where *userdata* is used, see :meth:`RosterClient.submit_change`.

       This attribute is set through the *add_to_groups* parameter of the
       constructor. The constructor validates that *add_to_groups* is an
       iterable of items for the dictionary or :data:`None`. If *add_to_groups*
       is empty, it is converted to :data:`None`.

    .. attribute:: RosterItemChange.remove_from_groups

       A set of *group names* from which the roster item is to be removed.

       This attribute is set through the *remove_from_groups* parameter of the
       constructor. The constructor validates that it is either an iterable or
       :data:`None`. If the iterable is empty, the value is converted to
       :data:`None`.

    .. attribute:: RosterItemChange.delete

       If this attribute is :data:`True`, the other attributes (except
       :attr:`jid`) must all be boolean :data:`False` (that is, empty dicts,
       sets or :data:`None` respectively).

       The changeset is interpreted as a request to delete the item.

       This attribute is set through the *delete* parameter of the
       constructor. It coerces the value to a boolean. If *delete* is
       :data:`True`, it requires the other values to be :data:`None` (after
       conversion).

    """

    def __new__(cls, itemjid,
                name=None,
                add_to_groups=None,
                remove_from_groups=None,
                delete=False):
        itemjid = jid.JID.fromstr(itemjid)
        if not itemjid.is_bare:
            raise ValueError("roster item JIDs must be bare")
        delete = bool(delete)
        if name is not None and len(name) != 2:
            raise ValueError("If name is set, it must be a tuple of two"
                             " elements")
        name = tuple(name or ()) or None
        add_to_groups = dict(add_to_groups or {})
        remove_from_groups = frozenset(remove_from_groups or set())
        if delete and (name or add_to_groups or remove_from_groups):
            raise ValueError("option conflict: delete and values cannot be given"
                             " at the same time")

        return _RosterItemChange.__new__(
            cls,
            jid=itemjid,
            name=name,
            add_to_groups=add_to_groups,
            remove_from_groups=remove_from_groups,
            delete=delete)

    def apply(self, to_item):
        """
        Apply the change to a given :class:`RosterItemInfo`. This modifies the
        *item* in place.

        Raises :class:`ValueError` if any of the prequisites do not match
        (groups or name). No changes are made to the *item* if
        :class:`ValueError` is raised.

        To avoid the exception, see :meth:`rebase`.
        """
        if self.jid != to_item.jid:
            raise ValueError("apply failed: jid mismatch")

        if self.name and (to_item.name or None) != self.name[0]:
            raise ValueError("apply failed: name mismatch")

        add_to_groups = frozenset(self.add_to_groups)
        remove_from_groups = frozenset(self.remove_from_groups)

        if any(group in to_item.groups
               for group in add_to_groups):
            raise ValueError("apply failed: group conflict")

        if any(group not in to_item.groups
               for group in remove_from_groups):
            raise ValueError("apply failed: group conflict")

        if self.name:
            to_item.name = self.name[1]

        to_item.groups = (to_item.groups - remove_from_groups) | add_to_groups

    def add(self, other_change, strict=True):
        """
        Add another change *other_change* on top of this change. Return a new
        :class:`RosterItemChange` object representing the resulting change.

        The :attr:`jid` attributes of both changes must match.

        Additional checks are employed if *strict* is :data:`True`:

        * If both changes have a non-:data:`None` :attr:`name`, the right hand
          side of this change and the left hand side of the other must be equal.
        * The changes must have no keys in common in :attr:`add_to_groups`.
        * The value of :attr:`delete` must not be :data:`True` in both changes.
        """

        if self.jid != other_change.jid:
            raise ValueError("jids of changes must be equal to merge them")

        if self.delete:
            if strict and other_change.delete:
                raise ValueError("delete/delete conflict")
            return other_change

        if other_change.delete:
            return other_change

        if (strict and self.name and other_change.name and
            self.name != other_change.name):

            if self.name[1] != other_change.name[0]:
                raise ValueError("modify/modify conflict")

        if self.name is None:
            new_name = other_change.name
        elif other_change.name is None:
            new_name = self.name
        else:
            new_name = self.name[0], other_change.name[1]
        new_add_to_groups = self.add_to_groups.copy()

        if strict and any(other_group in new_add_to_groups
                          for other_group in other_change.add_to_groups):
            raise ValueError("add/add conflict")

        new_add_to_groups.update(other_change.add_to_groups)

        new_remove_from_groups = set(self.remove_from_groups)

        for remove_from_group in other_change.remove_from_groups:
            new_add_to_groups.pop(remove_from_group, None)
        for add_to_group in other_change.add_to_groups:
            new_remove_from_groups.discard(add_to_group)

        new_remove_from_groups.update(other_change.remove_from_groups)

        return self._replace(
            jid=self.jid,
            name=new_name,
            add_to_groups=new_add_to_groups,
            remove_from_groups=new_remove_from_groups,
            delete=False)

    def rebase(self, onto_item):
        """
        Rebase the change on a given *item*. This removes any groups from
        :attr:`remove_from_groups` which are not listed in *item* and any groups
        from :attr:`add_to_groups` which are listed in *item*.

        Return a tuple ``(new_change, obsolete_groups)``. *new_change* is the
        resulting :class:`RosterItemChange` object. *obsolete_group* is a
        sequence of *group*-*userdata* tuples of those groups in which the item
        already contained and which has thus been dropped from
        :attr:`add_to_groups`.
        """
        new_name = self.name
        if new_name:
            new_name = (onto_item.name, self.name[1])

        obsolete_groups = []
        new_add_to_groups = self.add_to_groups.copy()
        for group, userdata in self.add_to_groups.items():
            if group in onto_item.groups:
                del new_add_to_groups[group]
                obsolete_groups.append((group, userdata))

        new_remove_from_groups = (
            self.remove_from_groups - (self.remove_from_groups -
                                       onto_item.groups)
        )

        return self._replace(
            name=new_name,
            add_to_groups=new_add_to_groups,
            remove_from_groups=new_remove_from_groups)

class RosterClient(base.Service):
    def __init__(self, node, loop=None, logger=None):
        super().__init__(node, loop=loop, logger=logger)
        self.callbacks = callbacks.CallbacksWithToken(
            "initial_roster",
            "roster_item_added",
            "roster_item_subscription_updated",
            "roster_item_name_updated",
            "roster_item_removed_from_groups",
            "roster_item_added_to_groups",
            "roster_item_other_updated",
            "roster_item_removed",
            "subscription_request",
        )

        self._roster = {}
        self._queued_changes = []

        self._pre_approval_supported = False

        self.node.register_iq_request_coro(
            Query.TAG,
            "set",
            self._handle_roster_push)
        self.node.register_presence_callback(
            "subscribe",
            self._handle_subscription_request)

        self.node.callbacks.add_callback(
            "session_started",
            self._start_session)
        self.node.callbacks.add_callback(
            "session_ended",
            self._stop_session)

    def _start_session(self):
        self.logger.debug("roster session starting")
        self._pre_approval_supported = self.node.stream_features.has_feature(
            "{urn:xmpp:features:pre-approval}sub")
        # FIXME: avoid the _on_task_success message
        self._start_task(self._request_roster())
        self.logger.debug("roster session started (query is on its way)")

    def _stop_session(self):
        pass

    def _add_roster_item(self, item):
        self._roster[item.jid] = RosterItemInfo(item=item)
        self.callbacks.emit("roster_item_added", item)

    def _update_roster_item(self, item):
        existing = self._roster[item.jid]

        subscription_changed = False
        if item.pending_out != existing.pending_out:
            existing.pending_out = item.pending_out
            subscribtion_changed = True
        if item.subscription != existing.subscription:
            existing.subscription = item.subscription
            subscribtion_changed = True
        if item.approved != existing.approved:
            existing.approved = item.approved
            subscribtion_changed = True

        name_changed = False
        if item.name != existing.name:
            existing.name = item.name
            name_changed = True

        new_groups = item.groups
        if not new_groups:
            new_groups |= {None}
        removed_from_groups = existing.groups - new_groups
        added_to_groups = new_groups - existing.groups
        existing.groups = new_groups

        self.logger.debug("item %s updated: "
                          "added_to_groups=%r; "
                          "removed_from_groups=%r; "
                          "name_changed=%s; "
                          "subscription_changed=%s; ",
                          item.jid,
                          added_to_groups,
                          removed_from_groups,
                          name_changed,
                          subscription_changed)

        if removed_from_groups:
            self.callbacks.emit("roster_item_removed_from_groups",
                                item,
                                removed_from_groups)
        if name_changed:
            self.callbacks.emit("roster_item_name_updated", item)
        if subscription_changed:
            self.callbacks.emit("roster_item_subscription_updated", item)
        if added_to_groups:
            self.callbacks.emit("roster_item_added_to_groups",
                                item,
                                added_to_groups)

    def _process_roster_item(self, item, allow_remove=False):
        if item.subscription == "remove":
            if not allow_remove:
                self.logger.info(
                    "ignored roster item with subscription=remove")
                return

            self._remove_roster_item(item)
            return

        if item.jid in self._roster:
            self._update_roster_item(item)
        else:
            self._add_roster_item(item)

    def _remove_roster_item(self, item):
        iteminfo = self._roster.pop(item.jid)
        self.callbacks.emit("roster_item_removed", iteminfo)

    def _handle_subscription_request(self, stanza):
        jid = stanza.from_.bare
        self.callbacks.emit("subscription_request", jid)

    def _diff_initial_roster(self, received_items):
        remote_roster = {
            item.jid: RosterItemInfo(item=item)
            for item in received_items
        }
        self.logger.info("diffing initial roster: "
                         "len(local)=%d, len(remote)=%d",
                         len(self._roster),
                         len(remote_roster))

        local_jids = set(self._roster)
        remote_jids = set(remote_roster)

        deleted_jids = local_jids - remote_jids
        self.logger.debug("removing %d entries", len(deleted_jids))
        for jid in deleted_jids:
            item = self._roster.pop(jid)
            self.callbacks.emit("roster_item_removed", item)

        updated_jids = remote_jids & local_jids
        self.logger.debug("updating %d entries", len(updated_jids))
        for jid in updated_jids:
            self._update_roster_item(remote_roster[jid])

        new_jids = remote_jids - local_jids
        self.logger.debug("adding %d new entries", len(new_jids))
        for jid in new_jids:
            item = remote_roster[jid]
            self._roster[jid] = item
            self.callbacks.emit("roster_item_added", item)

    @asyncio.coroutine
    def _request_roster(self):
        request = self.node.make_iq(type_="get")
        request.data = Query()

        response = yield from self.node.send_iq_and_wait(request)
        if response.type_ == "error":
            raise response.make_exception()

        self.logger.debug(
            "processing initial roster with %d items",
            len(response.data))

        items = list(response.data.items)
        response.data.clear()
        if self._roster:
            self.logger.debug("roster to diff against available, "
                              "diffing roster")
            # diff against existing roster
            self._diff_initial_roster(items)
        else:
            self.logger.debug("no roster to diff against, constructing new"
                              " roster")
            self._roster = {
                item.jid: RosterItemInfo(item=item)
                for item in items
            }
        self.callbacks.emit("initial_roster", self._roster)

    @asyncio.coroutine
    def _handle_roster_push(self, iq):
        if iq.from_ not in [
                None,
                self.node.client_jid.bare]:
            self.logger.info("rouge roster push detected (from=%s)",
                             iq.from_)
            return

        self.logger.debug(
            "processing roster push with %d items", len(item))
        for item in iq.data.items:
            self._process_roster_item(item, allow_remove=True)
        iq.data.clear()

    def request_subscription(self, peer_jid, pre_approve=False, **kwargs):
        """
        Request subscription for presence of *peer_jid*. If *pre_approve* is
        :data:`True` and the server supports pre-approval, subscription requests
        by *peer_jid* for our presence automatically get pre-approved.

        The remaining keyword arguments are passed to
        :meth:`asyncio_xmpp.node.AbstractClient.enqueue_stanza`.
        """
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="subscribe",
                to=peer_jid.bare,
            ), **kwargs)
        if pre_approve and self._pre_approval_supported:
            self.node.enqueue_stanza(
                self.node.make_presence(
                    type_="subscribed",
                    to=peer_jid.bare))

    def confirm_subscription(self, peer_jid, **kwargs):
        """
        Confirm a pending subscription request from *peer_jid* to our presence.

        The remaining keyword arguments are passed to
        :meth:`asyncio_xmpp.node.AbstractClient.enqueue_stanza`.
        """
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="subscribed",
                to=peer_jid.bare,
            ), **kwargs)

    def cancel_subscription(self, peer_jid, **kwargs):
        """
        Cancel the subscription of *peer_jid* to our presence.

        The remaining keyword arguments are passed to
        :meth:`asyncio_xmpp.node.AbstractClient.enqueue_stanza`.
        """
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="unsubscribed",
                to=peer_jid.bare,
            ), **kwargs)

    def unsubscribe(self, peer_jid, **kwargs):
        """
        Unsubscribe from the presence of the given *peer_jid*.

        The remaining keyword arguments are passed to
        :meth:`asyncio_xmpp.node.AbstractClient.enqueue_stanza`.
        """
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="unsubscribe",
                to=peer_jid.bare,
            ), **kwargs)

    def get_roster_item(self, peer_jid):
        """
        Return the :class:`RosterItemInfo` for the given peer JID. Raise
        :class:`KeyError` if no such item exists.
        """
        return self._roster[peer_jid.bare]

    @asyncio.coroutine
    def record_change(self, change, timeout=None):
        """
        Record a change to the roster. The change will be sent to the server
        (using :meth:`submit_change`), if a connection is available. If not, or
        if the change fails to apply at the server side with a non-permanent
        error, the change is stored locally to be re-submitted on the next
        reconnect.

        Any unhandled error is re-raised.

        .. note::

           Currently, no non-permanent error conditions are defined.

        .. seealso::

           :attr:`queued_changes` returns the current list of changes
           which are noted for appliance after the next reconnect.

        """
        self._queue_change(change)
        try:
            yield from self.submit_change(change, timeout=timeout)
        except (asyncio.TimeoutError, ConnectionError):
            logger.warning("temporary error during roster change (%s), queueing"
                           " change for next reconnect",
                           change)
            # temporary error
            pass
        except:
            # change is bad, don’t redo it
            self._unqueue_change(change)
            raise
        else:
            # change is good and got applied, don’t redo it
            self._unqueue_change(change)

    def replace_roster(self, new_roster):
        """
        Replace the entire stored roster with another. The *new_roster* must be
        a dict mapping bare JIDs to :class:`RosterItemInfo` instances.

        The idea is that a user (e.g. for an interactive client caching the
        roster between instances of the program) can provide
        :class:`RosterClient` with an initial version of the roster before the
        actual initial roster is received by the server.

        The same rules as if the roster had been known from a previous session
        are applied. That is, the ``initial_roster`` event is not emitted, but
        instead ``roster_*`` events get fired, for each change between the
        stored and the remote roster.

        .. note::

           This method also clears :attr:`queued_changes`.

        """
        self.logger.debug("replacing roster with new roster: %d entries",
                          len(new_roster))
        self._roster = new_roster

    @asyncio.coroutine
    def submit_change(self, change, timeout=None):
        """
        Submit a single :class:`RosterItemChange` to the server. This process
        happens in several steps. First, the current item (if any) is fetched
        from the stored roster and copied. If no item is present, a new empty
        item is created instead.

        Then the change is rebased onto the item and applied. The result is sent
        to the server as a roster update.

        For deletions, instead of fetching the item and rebasing the change, a
        removal request is simply issued (if the item is still contained in the
        stored roster).

        .. note::

           This coroutine waits until the server returns a confirmation that it
           received the request. There is not much use in that, however, for the
           final user.

           The outcome of the request is not included in the response, and
           another resource might have issued a change request for the same
           roster item inbetween and arbitrary races occur.

           Thus, the user should **not** rely on the result of this function,
           but instead listen for ``roster_*`` events related to the object.

        .. seealso::

           :meth:`record_change`, which would automatically store the change
           locally if the node is currently not connected (or the fails with a
           non-permanent error). This change would then get applied on
           reconnect.

        """
        if change.delete:
            if change.jid not in self._roster:
                # nothing to do
                return
        else:
            try:
                item = self._roster[change.jid]
            except KeyError:
                item = RosterItemInfo()
            change, obsolete_groups = change.rebase(item)
            # TODO: emit events for obsolete groups?
            change.apply(item)

        request = self.node.make_iq(type_="set")
        request.data = Query()

        if change.delete:
            iq_item = Item()
            iq_item.jid = change.jid
            iq_item.subscription = "remove"
        else:
            iq_item = item.make_iq_item()

        request.data.append(iq_item)

        yield from self.node.send_iq_and_wait(request, timeout=timeout)

    def close(self):
        """
        Clear the roster and detach from the
        :class:`asyncio_xmpp.node.AbstractClient` instance.

        Note that there is no way for a client to signal that it is not
        interested into roster changes anymore.
        """
        self.node.unregister_iq_request_coro(Query.TAG, "set")
        self.node.unregister_presence_callback("subscribe")
        self.node.callbacks.remove_callback_fn(
            "session_started",
            self._session_started)
        self.node.callbacks.remove_callback_fn(
            "session_ended",
            self._session_ended)
        self._roster.clear()
        super().close()

class PresenceClient(base.Service):
    def __init__(self, node, loop=None, logger=None):
        super().__init__(node, loop=loop, logger=logger)
        self.callbacks = callbacks.CallbacksWithToken(
            "presence_changed",
        )

        self._presence_info = {}

        self.node.callbacks.add_callback(
            "session_started",
            self._session_started)
        self.node.callbacks.add_callback(
            "session_ended",
            self._session_ended)

        self.node.register_presence_callback(
            "unavailable",
            self._handle_unavailable_presence)
        self.node.register_presence_callback(
            "error",
            self._handle_error_presence)
        self.node.register_presence_callback(
            None,
            self._handle_available_presence)

    def _session_started(self):
        self.logger.debug("presence session started")

    def _session_ended(self):
        self._presence_info.clear()
        self.logger.debug("presence session ended")

    def _handle_error_presence(self, presence):
        self._handle_unavailable_presence(presence)

    def _handle_unavailable_presence(self, presence):
        jid = presence.from_
        bare = jid.bare
        if bare not in self._presence_info:
            self.logger.info("received unavailable presence from unknown peer"
                             " %s", jid)
            return

        unavailable = presence.get_state()
        if jid.is_bare:
            self.callbacks.emit(
                "presence_changed",
                bare,
                frozenset(self._presence_info[bare]) - {None},
                unavailable
            )
            del self._presence_info[bare]
        else:
            try:
                del self._presence_info[bare][jid.resource]
            except KeyError:
                pass
            else:
                self.callbacks.emit(
                    "presence_changed",
                    bare,
                    {jid.resource},
                    unavailable
                )

    def _handle_available_presence(self, presence):
        jid = presence.from_
        bare = jid.bare
        state = presence.get_state()
        resources = self._presence_info.setdefault(bare, {})
        resources[jid.resource] = state

        self.callbacks.emit(
            "presence_changed",
            bare,
            {jid.resource},
            state)

    def get_presence(self, peer_jid):
        bare = peer_jid.bare
        try:
            resource_map = self._presence_info[bare]
        except KeyError:
            return presence.PresenceState()
        else:
            return resource_map.get(
                peer_jid.resource,
                resource_map.get(
                    None,
                    presence.PresenceState()))

    def get_all_presence(self, peer_jid):
        try:
            return self._presence_info[peer_jid.bare].copy()
        except KeyError:
            return {}

    def dump_state(self, f=None):
        if f is None:
            import sys
            f = sys.stdout

        print("== BEGIN OF PRESENCE DUMP ==", file=f)
        for jid, resource_map in self._presence_info.items():
            print("jid: {!s}".format(jid), file=f)
            try:
                print("  bare presence:", resource_map[None], file=f)
            except KeyError:
                print("  no bare presence")

            for resource, state in resource_map.items():
                if not resource:
                    continue
                print("  resource {!r}: {}".format(resource, state))
        print("== END OF PRESENCE DUMP ==", file=f)


def compress_changeset(changeset, strict=True):
    """
    Return an iterable of :class:`RosterItemChange` objects. These are the
    minimal representation of the changes applied by *changeset*, that is, there
    is exactly one :class:`RosterItemChange` object per peer JID.

    If *strict* is true and any changes inside the changeset are incompatible to
    each other, :class:`ValueError` is raised.
    """

    collected = {}
    for item in changeset:
        try:
            existing = collected[item.jid]
        except KeyError:
            collected[item.jid] = changeset
        else:
            collected[item.jid] = existing.add(changeset)

    return collected.values()
