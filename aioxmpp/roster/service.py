import asyncio

import aioxmpp.service

import aioxmpp.callbacks as callbacks
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as roster_xso


class Item:
    def __init__(self, jid, *,
                 approved=False,
                 ask=None,
                 subscription="none",
                 name=None):
        super().__init__()
        self.jid = jid
        self.subscription = subscription
        self.approved = approved
        self.ask = ask
        self.name = name

    def update_from_xso_item(self, xso_item):
        self.subscription = xso_item.subscription
        self.approved = xso_item.approved
        self.ask = xso_item.ask
        self.name = xso_item.name

    @classmethod
    def from_xso_item(cls, xso_item):
        item = cls(xso_item.jid)
        item.update_from_xso_item(xso_item)
        return item

    def export_as_json(self):
        result = {
            "subscription": self.subscription,
        }

        if self.name:
            result["name"] = self.name

        if self.ask is not None:
            result["ask"] = self.ask

        if self.approved:
            result["approved"] = self.approved

        return result

    def update_from_json(self, data):
        self.subscription = data.get("subscription", "none")
        self.approved = bool(data.get("approved", False))
        self.ask = data.get("ask", None)
        self.name = data.get("name", None)


class Service(aioxmpp.service.Service):
    on_entry_name_changed = callbacks.Signal()
    on_entry_subscription_state_changed = callbacks.Signal()
    on_entry_removed = callbacks.Signal()
    on_entry_added = callbacks.Signal()

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
            return

        to_call = []

        if stored_item.name != xso_item.name:
            to_call.append(self.on_entry_name_changed)

        if     (stored_item.subscription != xso_item.subscription or
                stored_item.approved != xso_item.approved or
                stored_item.ask != xso_item.ask):
            to_call.append(self.on_entry_subscription_state_changed)

        stored_item.update_from_xso_item(xso_item)

        for cb in to_call:
            cb(stored_item)

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
                    self.on_entry_removed(old_item)
            else:
                self._update_entry(item)

        self.version = request.ver

    @asyncio.coroutine
    def _request_initial_roster(self):
        iq = stanza.IQ(type_="get")
        iq.payload = roster_xso.Query()

        response = yield from self.client.stream.send_iq_and_wait_for_reply(
            iq,
            timeout=self.client.negotiation_timeout.total_seconds()
        )

        self.version = response.ver

        actual_jids = {item.jid for item in response.items}
        known_jids = set(self.items.keys())

        for removed_jid in known_jids - actual_jids:
            old_item = self.items.pop(removed_jid)
            self.on_entry_removed(old_item)

        for item in response.items:
            self._update_entry(item)

        return True
