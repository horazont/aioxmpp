import asyncio
import functools
import getpass
import json
import logging
import pprint

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
    pprint.pprint(info)


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

    # try to preload the capsdb
    try:
        with open("capsdb.json", "r") as f:
            preloadable = json.load(f)
    except (OSError, ValueError) as exc:
        logging.warn("failed to preload db: %s", exc)
    else:
        caps.cache.load_trusted_from_json(preloadable)
        logging.info("preloaded %d entries", len(preloadable))
        del preloadable

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
Tip: symlink the [capsdb][1] db.json file to

    {}/capsdb.json

This will allow this example to pre-load a huge amount of entitycaps hashes,
saving bandwidth and performance.

   [1]: https://github.com/xnyhps/capsdb/blob/master/db.json""".format(
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
