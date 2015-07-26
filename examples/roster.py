import asyncio
import getpass
import itertools
import logging

from datetime import timedelta

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs
import aioxmpp.roster


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
        certificate_verifier_factory=aioxmpp.security_layer._NullVerifier
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

    fut = asyncio.Future()

    def print_item(item):
        print("  entry {}:".format(item.jid))
        print("    name={!r}".format(item.name))
        print("    subscription={!r}".format(item.subscription))
        print("    ask={!r}".format(item.ask))
        print("    approved={!r}".format(item.approved))

    def on_initial_roster():
        nonlocal roster, fut
        for group, items in roster.groups.items():
            print("group {}:".format(group))
            for item in items:
                print_item(item)
        print("ungrouped items:")
        for item in roster.items.values():
            if not item.groups:
                print_item(item)
        fut.set_result(None)

    roster = client.summon(aioxmpp.roster.Service)
    roster.on_initial_roster_received.connect(on_initial_roster)

    client.presence = aioxmpp.structs.PresenceState(True)

    yield from connected_future

    try:
        yield from asyncio.wait_for(fut, timeout=10)
    finally:
        client.presence = aioxmpp.structs.PresenceState(False)
        yield from disconnected_future


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("JID: "))
    pwd = getpass.getpass()

    asyncio.get_event_loop().run_until_complete(main(jid, pwd))
