import asyncio
import functools
import getpass

try:
    import readline
except ImportError:
    pass

import aioxmpp.node
import aioxmpp.security_layer
import aioxmpp.stanza
import aioxmpp.structs


"""
This example connects to the XMPP server, sends a message and goes offline
cleanly.

It is way more code than I’d like it to be, to be honest. This has a reason
which consists of two parts:

1. The API used in this example is meant for long-running, user facing clients.
   It is cumbersome to use if you just want to send a quick message from an
   application.

2. Part of the reason why no such simple "send a message and be done with it"
   API exists is that for these use cases, the Asynchronous Context Manager
   stuff from :pep:`492` would be **great**. The PEP is only implemented in
   Python 3.5 though. Which is in turn only available on ArchLinux and Debian
   Testing at the time of writing. Possibly Ubuntu 16.04, too. But this is
   still far from wide spread.

   If it can be done without having a hard dependency on PEP 492, it is
   definitely on my TODO.

Suggestions to improve the API for easier use with less code are welcome. I am
myself still in the process of developing *applications* with aioxmpp, so I do
not yet have a clear vision of how the easy-to-use polished front-end API shall
look.

Something I have in mind for these use-cases in the mid-future is::

   # create the client instance
   client = ...
   async with client.connected() as stream:
       # stream is now the StanzaStream

       # construct stanza
       stanza = ...
       await stream.send_and_wait_for_sent(stanza)

The context manager would then take care of all the signal connecting which is
going on in the example below. It would also ensure to disconnect cleanly when
it is left.

Some more work would be needed to ensure that things like that
``send_and_wait_for_sent`` returns with an error if the client fails fatally.

But yeah, here it is, as requested, the example to send a message. Sorry for
the 100+ SLOC.

Tip: If your test server does not have a certificate, take try to pass this as
second argument to the PresenceManagedClient::

    aioxmpp.security_layer.security_layer(
        aioxmpp.security_layer.STARTTLSProvider(
            aioxmpp.security_layer.default_ssl_context,
            aioxmpp.security_layer._NullVerifier
        ),
        [aioxmpp.security_layer.PasswordSASLProvider(get_password)],
    )

This **disables** **all** certificate checks. You would normally not want
this, but for quick test against a local server it’s fine I guess.
"""


@asyncio.coroutine
def main(jid, password, recipient):
    @asyncio.coroutine
    def get_password(client_jid, nattempt):
        if nattempt > 1:
            return None
        return password

    print("configuring client")
    # a future which tells us when connection has succeeded
    connected_future = asyncio.Future()
    # a future which tells us when the connection is terminated
    disconnected_future = asyncio.Future()

    client = aioxmpp.node.PresenceManagedClient(
        jid,
        aioxmpp.security_layer.tls_with_password_based_authentication(
            get_password,
        )
    )

    # connect signals to futures, to be able to wait for some states
    client.on_stream_established.connect(
        connected_future,
        client.on_stream_established.AUTO_FUTURE,
    )

    client.on_stopped.connect(
        disconnected_future,
        client.on_stream_established.AUTO_FUTURE,
    )

    client.on_failure.connect(
        disconnected_future,
        client.on_stream_established.AUTO_FUTURE,
    )

    print("going online...")
    # go online
    client.presence = aioxmpp.structs.PresenceState(True)

    done, _ = yield from asyncio.wait(
        [
            connected_future,
            disconnected_future,
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if disconnected_future in done:
        # connection has failed, with an exception, bail out
        print(disconnected_future.result())
        return

    print("online! local jid is: {}".format(client.local_jid))
    # we are connected now!
    try:
        # compose a message
        msg = aioxmpp.stanza.Message(
            to=recipient,
            type_="chat",
        )
        # [None] is for "no XML language tag"
        msg.body[None] = "Hello World!"

        sent_future = asyncio.Future()

        def on_state_change(token, state):
            if (state == aioxmpp.stream.StanzaState.ACKED or
                    state == aioxmpp.stream.StanzaState.SENT_WITHOUT_SM):
                sent_future.set_result(None)
                return
            if (state == aioxmpp.stream.StanzaState.ABORTED or
                    state == aioxmpp.stream.StanzaState.DROPPED):
                sent_future.set_exception(
                    RuntimeError("stanza aborted or dropped")
                )

        print("sending message ...")
        client.stream.enqueue_stanza(
            msg,
            on_state_change=on_state_change
        )

        _, pending = yield from asyncio.wait(
            [
                sent_future,
                disconnected_future,
            ],
            return_when=asyncio.FIRST_COMPLETED
        )

        if sent_future in pending:
            # we got disconnected fatally, no point in waiting
            sent_future.cancel()
            print("failed to send message")
        else:
            print("message sent!")

    finally:
        # go offline
        print("going offline")
        client.presence = aioxmpp.structs.PresenceState(False)
        yield from disconnected_future


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("Login with: "))
    pwd = getpass.getpass()
    recipient = aioxmpp.structs.JID.fromstr(input("Message recipient: "))

    asyncio.get_event_loop().run_until_complete(main(jid, pwd, recipient))
