import asyncio
import getpass

from datetime import timedelta

try:
    import readline  # NOQA
except ImportError:
    pass

import aioxmpp.node
import aioxmpp.security_layer
import aioxmpp.stanza
import aioxmpp.structs


"""
This example connects to the XMPP server, sends a message and goes offline
cleanly.

It’s still a bit of code, but much less than before.

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


async def main(jid, password, recipient):
    @asyncio.coroutine
    def get_password(client_jid, nattempt):
        if nattempt > 1:
            return None
        return password

    print("configuring client")

    client = aioxmpp.node.PresenceManagedClient(
        jid,
        aioxmpp.security_layer.tls_with_password_based_authentication(
            get_password,
        )
    )

    print("going online...")
    async with aioxmpp.node.UseConnected(
            client,
            timeout=timedelta(seconds=30)) as stream:
        print("online! local jid is: {}".format(client.local_jid))

        # compose a message
        msg = aioxmpp.stanza.Message(
            to=recipient,
            type_="chat",
        )
        # [None] is for "no XML language tag"
        msg.body[None] = "Hello World!"

        print("sending message ...")
        await stream.send_and_wait_for_sent(msg)
        print("message sent!")

        print("going offline")

    print("offline!")


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("Login with: "))
    pwd = getpass.getpass()
    recipient = aioxmpp.structs.JID.fromstr(input("Message recipient: "))

    asyncio.get_event_loop().run_until_complete(main(jid, pwd, recipient))
