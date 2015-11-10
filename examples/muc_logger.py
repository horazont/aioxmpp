import asyncio
import getpass
import functools
import locale
import logging
import signal

try:
    import readline
except ImportError:
    pass

from datetime import datetime

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs
import aioxmpp.muc.service


language_name = locale.getlocale()[0]
if language_name == "C":
    language_name = "en-gb"
language = aioxmpp.structs.LanguageRange.fromstr(
    language_name.replace("_", "-")
)
any_language = aioxmpp.structs.LanguageRange.fromstr("*")
del language_name


def on_message(message, **kwargs):
    print("{} {}: {}".format(
        datetime.utcnow().isoformat(),
        message.from_.resource,
        message.body.lookup([language, any_language])
    ))


def on_subject_change(message, subject, **kwargs):
    print("{} *** topic set by {}: {}".format(
        datetime.utcnow().isoformat(),
        message.from_.resource,
        subject.lookup([language, any_language])
    ))


def on_enter(client, presence, occupant=None, **kwargs):
    print("{} *** entered room {}".format(
        datetime.utcnow().isoformat(),
        presence.from_.bare()
    ))


def on_exit(presence, occupant=None, **kwargs):
    print("{} *** left room {}".format(
        datetime.utcnow().isoformat(),
        presence.from_.bare()
    ))


def on_join(presence, occupant=None, **kwargs):
    print("{} *** {} [{}] entered room".format(
        datetime.utcnow().isoformat(),
        occupant.nick,
        occupant.jid,
    ))


def on_leave(presence, occupant, mode, **kwargs):
    print("{} *** {} [{}] left room ({})".format(
        datetime.utcnow().isoformat(),
        occupant.nick,
        occupant.jid,
        mode
    ))


@asyncio.coroutine
def main(jid, password, mucjid, nick):
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

    muc = client.summon(aioxmpp.muc.service.Service)
    room, room_future = muc.join(mucjid, nick)

    room.on_message.connect(on_message)
    room.on_subject_change.connect(on_subject_change)
    room.on_enter.connect(functools.partial(on_enter, client))
    room.on_exit.connect(on_exit)
    room.on_leave.connect(on_leave)
    room.on_join.connect(on_join)

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

    print("connected, joining room")

    done, waiting = yield from asyncio.wait(
        [
            room_future,
            failure_future
        ],
        return_when=asyncio.FIRST_COMPLETED
    )

    if failure_future in done:
        print("stream failed")
        yield from failure_future  # this will raise
        return

    print("joined room successfully")

    cancel_future = asyncio.Future()
    asyncio.get_event_loop().add_signal_handler(
        signal.SIGINT,
        cancel_future.set_result,
        None
    )

    done, waiting = yield from asyncio.wait(
        [
            cancel_future,
            failure_future
        ],
        return_when=asyncio.FIRST_COMPLETED
    )

    if failure_future not in done:
        print("disconnecting...")
        disconnected_future = asyncio.Future()
        client.on_stopped.connect(
            disconnected_future,
            client.on_stopped.AUTO_FUTURE
        )
        print("on_stopped future connected")
        client.stop()
        yield from asyncio.wait(
            [disconnected_future, failure_future],
            return_when=asyncio.FIRST_COMPLETED
        )

    print("disconnected")

if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("Account JID: "))
    pwd = getpass.getpass()
    mucjid = aioxmpp.structs.JID.fromstr(input("MUC JID: "))
    nick = input("Nick: ")

    logging.basicConfig(
        level=logging.INFO
    )

    asyncio.get_event_loop().run_until_complete(main(jid, pwd, mucjid, nick))
