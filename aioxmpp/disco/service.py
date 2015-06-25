import asyncio

import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as disco_xso


class Service(service.Service):
    """
    A service implementing XEP-0030. The service provides methods for managing
    the own features and identities as well as querying others features and
    identities.

    Querying other entities’ service discovery information:

    .. automethod:: query_info

    Managing identities:

    .. automethod:: register_identity

    .. automethod:: unregister_identity

    .. note::

       While no other identity is registered, a default identity is used. That
       default identity has a category ``"client"``, a type ``"bot"`` and a
       name referring to the :mod:`aioxmpp` library.

    Managing features:

    .. automethod:: register_feature

    .. automethod:: unregister_feature

    .. note::

       The features which are mandatory per XEP-0030 are always registered and
       cannot be unregistered. For the purpose of unregistration, they behave
       as if they had never been registered; for the purpose of registration,
       they behave as if they had been registered before.

    """

    STATIC_FEATURES = frozenset({namespaces.xep0030_info})
    DEFAULT_IDENTITY = disco_xso.Identity(
        name="aioxmpp default identity",
        lang=structs.LanguageTag.fromstr("en")
    )

    def __init__(self, client, *, logger=None):
        super().__init__(client, logger=logger)

        self._features = set()
        self._identities = {}
        self._info_pending = {}

        self.client.stream.register_iq_request_coro(
            "get",
            disco_xso.InfoQuery,
            self.handle_request)
        self.client.on_stream_destroyed.connect(
            self._clear_cache
        )

    @asyncio.coroutine
    def _shutdown(self):
        self.client.stream.unregister_iq_request_coro(
            "get",
            disco_xso.InfoQuery)
        yield from super()._shutdown()

    def _clear_cache(self):
        for fut in self._info_pending.values():
            if not fut.done():
                fut.cancel()
        self._info_pending.clear()

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
            for (category, type_), names in self._identities.items():
                for lang, name in names.items():
                    response.identities.append(disco_xso.Identity(
                        category=category,
                        type_=type_,
                        lang=lang,
                        name=name
                    ))
                if not names:
                    response.identities.append(disco_xso.Identity(
                        category=category,
                        type_=type_
                    ))
        else:
            response.identities.append(self.DEFAULT_IDENTITY)

        return response

    def register_feature(self, var):
        """
        Register a feature with the namespace variable *var*.

        If the feature is already registered or part of the default XEP-0030
        features, a :class:`ValueError` is raised.
        """
        if var in self._features or var in self.STATIC_FEATURES:
            raise ValueError("feature already claimed: {!r}".format(var))
        self._features.add(var)

    def unregister_feature(self, var):
        """
        Unregister a feature which has previously been registered using
        :meth:`register_feature`.

        If the feature has not been registered previously, :class:`KeyError` is
        raised.
        """
        self._features.remove(var)

    def register_identity(self, category, type_, *, names={}):
        """
        Register an identity with the given *category* and *type_*.

        If there is already a registered identity with the same *category* and
        *type_*, :class:`ValueError` is raised.

        Return a :class:`.service.Identity` instance which can be used to
        manage the names of the identity.
        """
        key = category, type_
        if key in self._identities:
            raise ValueError("identity already claimed: {}".format(key))
        self._identities[category, type_] = names

    def unregister_identity(self, category, type_):
        """
        Unregister an identity previously registered using
        :meth:`register_identity`.

        If no identity with the given *category* and *type_* has been
        registered before, :class:`KeyError` is raised.
        """
        del self._identities[category, type_]

    @asyncio.coroutine
    def query_info(self, jid, *, node=None, require_fresh=False, timeout=None):
        """
        Query the features and identities of the specified entity. The entity
        is identified by the *jid* and the optional *node*.

        Return the :class:`.xso.InfoQuery` instance returned by the peer. If an
        error is returned, that error is raised as :class:`.errors.XMPPError`.

        The requests are cached. This means that only one request is ever fired
        for a given target (identified by the *jid* and the *node*). The
        request is re-used for all subsequent requests to that identity.

        If *require_fresh* is set to true, the above does not hold and a fresh
        request is always created. The new request is the request which will be
        used as alias for subsequent requests to the same identity.

        The visible effects of this are twofold:

        * Caching: Results of requests are implicitly cached
        * Aliasing: Two concurrent requests will be aliased to one request to
          save computing resources

        Both can be turned off by using *require_fresh*. In general, you should
        not need to use *require_fresh*, as all requests are implicitly
        cancelled whenever the underlying session gets destroyed.

        *timeout* is passed to
        :meth:`.StanzaStream.send_iq_and_wait_for_reply`.
        """
        key = jid, node

        if not require_fresh:
            try:
                request = self._info_pending[key]
            except KeyError:
                pass
            else:
                try:
                    return (yield from request)
                except asyncio.CancelledError:
                    pass

        request_iq = stanza.IQ(to=jid, type_="get")
        request_iq.payload = disco_xso.InfoQuery(node=node)

        request = asyncio.async(
            self.client.stream.send_iq_and_wait_for_reply(request_iq)
        )

        self._info_pending[key] = request
        if timeout is not None:
            try:
                result = yield from asyncio.wait_for(request, timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError()
        else:
            result = yield from request

        return result
