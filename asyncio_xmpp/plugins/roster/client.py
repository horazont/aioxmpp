import asyncio

import asyncio_xmpp.plugins.base as base
import asyncio_xmpp.callbacks as callbacks
import asyncio_xmpp.jid as jid

from .stanza import *

class Client(base.Service):
    def __init__(self, node, loop=None, logger=None):
        super().__init__(node, loop=loop, logger=logger)
        self.callbacks = callbacks.CallbacksWithToken(
            "presence_changed",
            "initial_roster",
            "roster_item_added",
            "roster_item_updated",
            "roster_item_removed",
        )

        self._roster = {}

        self.node.register_iq_request_coro(
            Query.TAG,
            "set",
            self._handle_roster_push)

        self.node.register_callback(
            "session_started",
            self._start_session)
        self.node.register_callback(
            "session_ended",
            self._stop_session)

    def _start_session(self):
        self.logger.debug("roster session starting")
        # FIXME: avoid the _on_task_success message
        self._start_task(self._request_roster())
        self.logger.debug("roster session started (query is on its way)")

    def _stop_session(self):
        self.logger.debug("roster session stopping")
        self._clear_roster()
        self.logger.debug("roster session stopped")

    def _clear_roster(self):
        for item in list(self._roster.values()):
            self._remove_roster_item(item)
        self._roster.clear()

    def _add_roster_item(self, item):
        self._roster[item.jid] = item
        self.callbacks.emit("roster_item_added", item)

    def _update_roster_item(self, item):
        self._roster[item.jid] = item
        self.callbacks.emit("roster_item_updated", item)

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
        del self._roster[item.jid]
        self.callbacks.emit("roster_item_removed", item)

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
        self._roster = {
            item.jid: item
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

    def close(self, emit_events=True):
        self._clear_roster()
        self.node.unregister_iq_request_coro(Query.TAG, "set")
        super().close()
