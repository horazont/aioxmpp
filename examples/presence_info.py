import asyncio
import functools
import getpass
import itertools
import logging
import pathlib

try:
    import readline  # NOQA
except ImportError:
    pass

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs
import aioxmpp.entitycaps
import aioxmpp.disco
import aioxmpp.presence


@asyncio.coroutine
def show_info(from_, disco):
    info = yield from disco.query_info(from_)
    print("{}:".format(from_))
    print("  features:")
    for feature in info.features:
        print("    {!r}".format(feature))

    print("  identities:")
    identities = list(info.identities)
    identity_key = lambda ident: (ident.category, ident.type_)
    identities.sort(key=identity_key)
    for (category, type_), identities in (
            itertools.groupby(info.identities, identity_key)):
        print("    category={!r} type={!r}".format(category, type_))
        subidentities = list(identities)
        subidentities.sort(key=lambda ident: ident.lang)
        for identity in subidentities:
            print("      [{}] {!r}".format(identity.lang, identity.name))


def on_available(disco, full_jid, stanza):
    asyncio.async(
        show_info(full_jid, disco)
    )


@asyncio.coroutine
def main(jid, password):
    @asyncio.coroutine
    def get_password(client_jid, nattempt):
        if nattempt > 1:
            # abort, as we cannot properly re-ask the user
            return None
        return password

    client = aioxmpp.node.PresenceManagedClient(
        jid,
        aioxmpp.security_layer.tls_with_password_based_authentication(
            get_password,
            certificate_verifier_factory=aioxmpp.security_layer._NullVerifier
        )
    )
    failure_future = asyncio.Future()
    connected_future = asyncio.Future()
    client.on_failure.connect(
        failure_future,
        client.on_failure.AUTO_FUTURE
    )
    client.on_stream_established.connect(
        connected_future,
        client.on_stream_established.AUTO_FUTURE
    )

    # summon the entitycaps service
    caps = client.summon(aioxmpp.entitycaps.Service)

    # set a possible path for the capsdb cache
    caps.cache.set_system_db_path(pathlib.Path("./hashes/").absolute())
    caps.cache.set_user_db_path(pathlib.Path("./user_hashes/").absolute())

    # use the presence service to find targets for querying the info
    presence_tracker = client.summon(aioxmpp.presence.Service)
    presence_tracker.on_available.connect(
        functools.partial(on_available, client.summon(aioxmpp.disco.Service))
    )

    client.presence = aioxmpp.structs.PresenceState(True)

    print("connecting...")
    done, waiting = yield from asyncio.wait(
        [
            connected_future,
            failure_future
        ],
        return_when=asyncio.FIRST_COMPLETED
    )

    if failure_future in done:
        print("failed to connect!")
        yield from failure_future  # this will raise
        return

    print("waiting for the presence rain to start...")
    yield from asyncio.sleep(10)

if __name__ == "__main__":
    import os

    print("""\
Tip: symlink the [capsdb][1] hashes directory to

    {}/hashes

This will allow the implementation to load hashes from the capsdb, improving
performance by not having to query the peers for their capabilities. In
addition, creating a ``user_hashes`` directory in the same directory as the
hashes symlink will allow the implementation to store hashes which were not in
the capsdb for future use.

   [1]: https://github.com/xnyhps/capsdb""".format(
        os.getcwd()
    ))
    print()

    jid = aioxmpp.structs.JID.fromstr(input("Account JID: "))
    pwd = getpass.getpass()

    logging.basicConfig(
        level=logging.INFO
    )

    logging.getLogger("aioxmpp.entitycaps").setLevel(logging.DEBUG)

    asyncio.get_event_loop().run_until_complete(main(jid, pwd))
