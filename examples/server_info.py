import asyncio
import getpass
import itertools

import aioxmpp.security_layer
import aioxmpp.node
import aioxmpp.structs
import aioxmpp.disco

try:
    import readline  # NOQA
except ImportError:
    pass


async def main(jid, password):
    @asyncio.coroutine
    def get_password(client_jid, nattempt):
        if nattempt > 1:
            # abort, as we cannot properly re-ask the user
            return None
        return password

    client = aioxmpp.node.PresenceManagedClient(
        jid,
        aioxmpp.security_layer.SecurityLayer(
            aioxmpp.security_layer.default_ssl_context,
            aioxmpp.security_layer._NullVerifier,
            aioxmpp.security_layer.STARTTLSProvider(
                aioxmpp.security_layer.default_ssl_context,
                aioxmpp.security_layer._NullVerifier
            ),
            [aioxmpp.security_layer.PasswordSASLProvider(get_password)],
        )
    )

    disco = client.summon(aioxmpp.disco.Service)

    async with client.connected():
        try:
            info = await disco.query_info(
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

        def identity_key(ident):
            return (ident.category, ident.type_)

        identities.sort(key=identity_key)
        for (category, type_), identities in (
                itertools.groupby(info.identities, identity_key)):
            print("  category={!r} type={!r}".format(category, type_))
            subidentities = list(identities)
            subidentities.sort(key=lambda ident: ident.lang)
            for identity in subidentities:
                print("    [{}] {!r}".format(identity.lang, identity.name))


if __name__ == "__main__":
    jid = aioxmpp.structs.JID.fromstr(input("JID: "))
    pwd = getpass.getpass()

    asyncio.get_event_loop().run_until_complete(main(jid, pwd))
