import itertools

import aioxmpp.disco

from framework import Example, exec_example


class ServerInfo(Example):
    async def run_simple_example(self):
        disco = self.client.summon(aioxmpp.disco.Service)
        try:
            info = await disco.query_info(
                self.g_jid.replace(resource=None, localpart=None),
                timeout=10
            )
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
    exec_example(ServerInfo())
