import asyncio

import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as disco_xso


class Identity:
    """
    A handle to a specific identity represented in a :class:`Service`. It is
    returned by :meth:`Service.register_identity` and can be used to
    comfortably manage different names for an identity.

    .. attribute:: default_name

       The default name of the identity. This must either be a :class:`str` or
       :data:`None`.

       It is used as value for the ``name`` attribute whenever the
       :attr:`names` dictionary is empty.

    .. attribute:: names

       A :class:`.structs.LanguageMap` mapping. For each entry, a language tag
       is created, with the ``lang`` attribute set to the key of the entry and
       the ``name`` attribute set to the value.

       .. warning::

          Care must be taken when using the :data:`None` key. Technically, if
          :data:`None` is used and the parents ``xml:lang`` value is equal to
          one of the other keys in the mapping, the output will be invalid. The
          service cannot check against that as the parent ``xml:lang`` values
          are not known.

          In general, using the :data:`None` key is discouraged; just do not do
          it to avoid problems. Use :attr:`default_name` instead.

    .. warning::

       Do not confuse this class with :class:`aioxmpp.disco.xso.Identity`.

    """
    def __init__(self):
        super().__init__()
        self.default_name = None
        self.names = structs.LanguageMap()


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
        self._info_cache = {}

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
        self._info_cache.clear()

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
                if not identity.names:
                    response.identities.append(disco_xso.Identity(
                        category=category,
                        type_=type_,
                        name=identity.default_name
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

    def register_identity(self, category, type_):
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
        identity = Identity()
        self._identities[category, type_] = identity
        return identity

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

        The result is cached. If you require fresh results, use
        *require_fresh*. Note that the cache is automatically cleared if a
        session ends.

        *timeout* is passed to
        :meth:`.StanzaStream.send_iq_and_wait_for_reply`.
        """
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
