import asyncio
import getpass
import logging

from datetime import timedelta

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs


try:
    import readline
except ImportError:
    pass


class PresenceCollector:
    def __init__(self, done_timeout=timedelta(seconds=1)):
        self.presences = []
        self.done_future = asyncio.Future()
        self.done_timeout = done_timeout
        self._reset_timer()

    def _reset_timer(self):
        self._done_task = asyncio.ensure_future(
            asyncio.sleep(self.done_timeout.total_seconds())
        )
        self._done_task.add_done_callback(self._sleep_done)

    def _sleep_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            return
        self.done_future.set_result(self.presences)

    def add_presence(self, pres):
        self.presences.append(pres)
        self._done_task.cancel()
        self._reset_timer()


@asyncio.coroutine
def main(jid, password):
    @asyncio.coroutine
    def get_password(client_jid, nattempt):
        if nattempt > 1:
            # abort, as we cannot properly re-ask the user
            return None
        return password

    connected_future = asyncio.Future()
    disconnected_future = asyncio.Future()

    def connected():
        connected_future.set_result(None)

    def disconnected():
        disconnected_future.set_result(None)

    tls_provider = aioxmpp.security_layer.STARTTLSProvider(
        aioxmpp.security_layer.default_ssl_context,
    )

    sasl_provider = aioxmpp.security_layer.PasswordSASLProvider(
        get_password
    )

    client = aioxmpp.node.PresenceManagedClient(
        jid,
        aioxmpp.security_layer.security_layer(
            tls_provider,
            [sasl_provider]
        )
    )
    client.on_stream_established.connect(connected)
    client.on_stopped.connect(disconnected)

    collector = PresenceCollector()

    client.stream.register_presence_callback(
        None, None, collector.add_presence)
    client.stream.register_presence_callback(
        "unavailable", None, collector.add_presence)

    client.presence = aioxmpp.structs.PresenceState(True)

    yield from connected_future

    presences = yield from collector.done_future

    client.presence = aioxmpp.structs.PresenceState(False)

    yield from disconnected_future

    print("found presences:")
    for i, pres in enumerate(presences):
        print("presence {}".format(i))
        print("  peer: {}".format(pres.from_))
        print("  type: {}".format(pres.type_))
        print("  show: {}".format(pres.show))
        print("  status: ")
        for lang, text in pres.status.items():
            print("    (lang={}) {!r}".format(
                lang,
                text))


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("JID: "))
    pwd = getpass.getpass()

    asyncio.get_event_loop().run_until_complete(main(jid, pwd))
