import asyncio
import itertools

import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as disco_xso


class Node(object):
    """
    A :class:`Node` holds the information related to a specific node within the
    entity referred to by a JID, with respect to XEP-0030 semantics.

    A :class:`Node` always has at least one identity (or it will return
    as ``<item-not-found/>``). It may have zero or more features beyond the
    XEP-0030 features which are statically included.

    To manage the identities and the features of a node, use the following
    methods:

    .. automethod:: register_feature

    .. automethod:: unregister_feature

    .. automethod:: register_identity

    .. automethod:: unregister_identity
    """
    STATIC_FEATURES = frozenset({namespaces.xep0030_info})

    def __init__(self):
        super().__init__()
        self._identities = {}
        self._features = set()

    def iter_identities(self):
        for (category, type_), names in self._identities.items():
            for lang, name in names.items():
                yield category, type_, lang, name
            if not names:
                yield category, type_, None, None

    def iter_features(self):
        return itertools.chain(
            iter(self.STATIC_FEATURES),
            iter(self._features)
        )

    def register_feature(self, var):
        """
        Register a feature with the namespace variable *var*.

        If the feature is already registered or part of the default XEP-0030
        features, a :class:`ValueError` is raised.
        """
        if var in self._features or var in self.STATIC_FEATURES:
            raise ValueError("feature already claimed: {!r}".format(var))
        self._features.add(var)

    def register_identity(self, category, type_, *, names={}):
        """
        Register an identity with the given *category* and *type_*.

        If there is already a registered identity with the same *category* and
        *type_*, :class:`ValueError` is raised.

        *names* may be a mapping which maps :class:`.structs.LanguageTag`
        instances to strings. This mapping will be used to produce
        ``<identity/>`` declarations with the respective ``xml:lang`` and
        ``name`` attributes.
        """
        key = category, type_
        if key in self._identities:
            raise ValueError("identity already claimed: {!r}".format(key))
        self._identities[key] = names

    def unregister_feature(self, var):
        """
        Unregister a feature which has previously been registered using
        :meth:`register_feature`.

        If the feature has not been registered previously, :class:`KeyError` is
        raised.

        .. note::

           The features which are mandatory per XEP-0030 are always registered
           and cannot be unregistered. For the purpose of unregistration, they
           behave as if they had never been registered; for the purpose of
           registration, they behave as if they had been registered before.

        """
        self._features.remove(var)

    def unregister_identity(self, category, type_):
        """
        Unregister an identity previously registered using
        :meth:`register_identity`.

        If no identity with the given *category* and *type_* has been
        registered before, :class:`KeyError` is raised.

        If the identity to remove is the last identity of the :class:`Node`,
        :class:`ValueError` is raised; a node must always have at least one
        identity.
        """
        key = category, type_
        if key not in self._identities:
            raise KeyError(key)
        if len(self._identities) == 1:
            raise ValueError("cannot remove last identity")
        del self._identities[key]


class Service(service.Service, Node):
    """
    A service implementing XEP-0030. The service provides methods for managing
    the own features and identities as well as querying others features and
    identities.

    Querying other entities’ service discovery information:

    .. automethod:: query_info

    Services inherit from :class:`Node` to manage the identities and features
    of the JID itself. The identities and features declared in the service
    using the :class:`Node` interface on the :class:`Service` instance are
    returned when a query is received for the JID with an empty or unset
    ``node`` attribute. For completeness, the relevant methods are listed
    here. Refer to the :class:`Node` documentation for details.

    .. autosummary::

       Node.register_feature
       Node.unregister_feature
       Node.register_identity
       Node.unregister_identity

    .. note::

       Upon construction, the :class:`Service` adds a default identity with
       category ``"client"`` and type ``"bot"`` to the root :class:`Node`. This
       is to comply with XEP-0030 of always having an identity and not being
       forced to reply with ``<feature-not-implemented/>`` or a similar error.

       After having added another identity, that default identity can be
       removed.

    """

    def __init__(self, client, *, logger=None):
        super().__init__(client, logger=logger)

        self._info_pending = {}

        self.register_identity(
            "client", "bot",
            names={
                structs.LanguageTag.fromstr("en"): "aioxmpp default identity"
            }
        )

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
        for feature in self.iter_features():
            response.features.append(disco_xso.Feature(
                var=feature
            ))

        for category, type_, lang, name in self.iter_identities():
            response.identities.append(disco_xso.Identity(
                category=category,
                type_=type_,
                lang=lang,
                name=name
            ))

        return response

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
