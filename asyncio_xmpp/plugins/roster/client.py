import asyncio

import asyncio_xmpp.plugins.base as base
import asyncio_xmpp.callbacks as callbacks
import asyncio_xmpp.jid as jid
import asyncio_xmpp.stanza as stanza
import asyncio_xmpp.presence as presence

from .stanza import *

from asyncio_xmpp.utils import *

__all__ = [
    "RosterItemInfo",
    "RosterClient",
    "PresenceClient"
]

class RosterItemInfo:
    jid = None
    subscription = None
    groups = None
    pending_out = False
    name = None
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
            self.in_roster = True
        else:
            self.groups = set()
            self.in_roster = False

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

    def request_subscription(self, peer_jid, pre_approve=True, **kwargs):
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
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="subscribed",
                to=peer_jid.bare,
            ), **kwargs)

    def cancel_subscription(self, peer_jid, **kwargs):
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="unsubscribed",
                to=peer_jid.bare,
            ), **kwargs)

    def unsubscribe(self, peer_jid, **kwargs):
        self.node.enqueue_stanza(
            self.node.make_presence(
                type_="unsubscribe",
                to=peer_jid.bare,
            ), **kwargs)

    def get_roster_item(self, peer_jid):
        return self._roster[peer_jid.bare]

    def replace_roster(self, new_roster):
        """
        Replace the entire stored roster with another. The *new_roster* must be
        a dict mapping bare JIDs to :class:`RosterItemInfo` instances.

        Use case: supply an initial roster to diff against, thus obsoleting the
        ``initial_roster`` event and instead using the ``roster_*`` events.
        """
        self.logger.debug("replacing roster with new roster: %d entries",
                          len(new_roster))
        self._roster = new_roster

    def close(self, emit_events=True):
        self.node.unregister_iq_request_coro(Query.TAG, "set")
        self.node.callbacks.remove_callback_fn(
            "session_started",
            self._session_started)
        self.node.callbacks.remove_callback_fn(
            "session_ended",
            self._session_ended)
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
