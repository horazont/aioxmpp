import asyncio

import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as disco_xso


class Identity:
    def __init__(self):
        super().__init__()
        self.default_name = None
        self.names = structs.LanguageMap()


class Service(service.Service):
    STATIC_FEATURES = frozenset({namespaces.xep0030_info})
    DEFAULT_IDENTITY = disco_xso.Identity(
        name="aioxmpp default identity",
        lang=structs.LanguageTag.fromstr("en")
    )

    def __init__(self, client, *, logger=None):
        super().__init__(client, logger=logger)

        self._features = set()
        self._identities = {}
        self._info_cache = {}

        self.client.stream.register_iq_request_coro(
            "get",
            disco_xso.InfoQuery,
            self.handle_request)

    @asyncio.coroutine
    def _shutdown(self):
        self.client.stream.unregister_iq_request_coro(
            "get",
            disco_xso.InfoQuery)
        yield from super()._shutdown()

    @asyncio.coroutine
    def handle_request(self, iq):
        request = iq.payload

        if request.node:
            raise errors.XMPPCancelError(
                condition=(namespaces.stanzas, "item-not-found")
            )

        response = disco_xso.InfoQuery()
        for feature in self._features:
            response.features.append(disco_xso.Feature(
                var=feature
            ))
        for feature in self.STATIC_FEATURES:
            response.features.append(disco_xso.Feature(
                var=feature
            ))

        if self._identities:
            for (category, type_), identity in self._identities.items():
                for lang, name in identity.names.items():
                    response.identities.append(disco_xso.Identity(
                        category=category,
                        type_=type_,
                        lang=lang,
                        name=name
                    ))
                if identity.default_name is not None or not identity.names:
                    response.identities.append(disco_xso.Identity(
                        category=category,
                        type_=type_,
                        name=identity.default_name
                    ))
        else:
            response.identities.append(self.DEFAULT_IDENTITY)

        return response

    def register_feature(self, var):
        if var in self._features or var in self.STATIC_FEATURES:
            raise ValueError("feature already claimed: {!r}".format(var))
        self._features.add(var)

    def unregister_feature(self, var):
        self._features.remove(var)

    def register_identity(self, category, type_):
        key = category, type_
        if key in self._identities:
            raise ValueError("identity already claimed: {}".format(key))
        identity = Identity()
        self._identities[category, type_] = identity
        return identity

    def unregister_identity(self, category, type_):
        del self._identities[category, type_]

    @asyncio.coroutine
    def query_info(self, jid, *, node=None, require_fresh=False, timeout=None):
        key = jid, node

        if not require_fresh:
            try:
                return self._info_cache[key]
            except KeyError:
                pass

        request_iq = stanza.IQ(to=jid, type_="get")
        request_iq.payload = disco_xso.InfoQuery(node=node)
        result = yield from self.client.stream.send_iq_and_wait_for_reply(
            request_iq,
            timeout=timeout)

        self._info_cache[key] = result

        return result
