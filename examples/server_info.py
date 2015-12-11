import asyncio
import getpass
import itertools
import logging

from datetime import timedelta

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs
import aioxmpp.disco


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

    disco = client.summon(aioxmpp.disco.Service)

    client.presence = aioxmpp.structs.PresenceState(True)

    yield from connected_future

    try:
        try:
            info = yield from disco.query_info(
                jid.replace(resource=None, localpart=None),
                timeout=10)
        except Exception as exc:
            print("could not get info: ")
            print("{}: {}".format(type(exc).__name__, exc))
            raise

        print("features:")
        for feature in info.features:
            print("  {!r}".format(feature))

        print("identities:")
        identities = list(info.identities)
        identity_key = lambda ident: (ident.category, ident.type_)
        identities.sort(key=identity_key)
        for (category, type_), identities in (
                itertools.groupby(info.identities, identity_key)):
            print("  category={!r} type={!r}".format(category, type_))
            subidentities = list(identities)
            subidentities.sort(key=lambda ident: ident.lang)
            for identity in subidentities:
                print("    [{}] {!r}".format(identity.lang, identity.name))

    finally:
        client.presence = aioxmpp.structs.PresenceState(False)
        yield from disconnected_future


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("JID: "))
    pwd = getpass.getpass()

    asyncio.get_event_loop().run_until_complete(main(jid, pwd))
