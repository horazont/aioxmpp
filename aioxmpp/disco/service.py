########################################################################
# File name: service.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio
import contextlib
import functools
import itertools

import aioxmpp.cache
import aioxmpp.callbacks
import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza

from aioxmpp.utils import namespaces

from . import xso as disco_xso


class Node(object):
    """
    A :class:`Node` holds the information related to a specific node within the
    entity referred to by a JID, with respect to :xep:`30` semantics.

    A :class:`Node` always has at least one identity (or it will return
    as ``<item-not-found/>``). It may have zero or more features beyond the
    :xep:`30` features which are statically included.

    To manage the identities and the features of a node, use the following
    methods:

    .. automethod:: register_feature

    .. automethod:: unregister_feature

    .. automethod:: register_identity

    .. automethod:: set_identity_names

    .. automethod:: unregister_identity

    To access the declared features and identities, use:

    .. automethod:: iter_features

    .. automethod:: iter_identities

    .. automethod:: as_info_xso

    To access items, use:

    .. automethod:: iter_items

    Signals provide information about changes:

    .. signal:: on_info_changed()

       This signal emits when a feature or identity is registered or
       unregistered.

    As mentioned, bare :class:`Node` objects have no items; there are
    subclasses of :class:`Node` which support items:

    ======================  ==================================================
    :class:`StaticNode`     Support for a list of :class:`.xso.Item` instances
    :class:`.DiscoServer`   Support for "mountpoints" for node subtrees
    ======================  ==================================================

    """
    STATIC_FEATURES = frozenset({namespaces.xep0030_info})

    on_info_changed = aioxmpp.callbacks.Signal()

    def __init__(self):
        super().__init__()
        self._identities = {}
        self._features = set()

    def iter_identities(self, stanza=None):
        """
        Return an iterator of tuples describing the identities of the node.

        :param stanza: The IQ request stanza
        :type stanza: :class:`~aioxmpp.IQ` or :data:`None`
        :rtype: iterable of (:class:`str`, :class:`str`, :class:`str` or
            :data:`None`, :class:`str` or :data:`None`) tuples
        :return: :xep:`30` identities of this node

        `stanza` can be the :class:`aioxmpp.IQ` stanza of the request. This can
        be used to hide a node depending on who is asking. If the returned
        iterable is empty, the :class:`~.DiscoServer` returns an
        ``<item-not-found/>`` error.

        `stanza` may be :data:`None` if the identities are queried without
        a specific request context. In that case, implementors should assume
        that the result is visible to everybody.

        .. note::

           Subclasses must allow :data:`None` for `stanza` and default it to
           :data:`None`.

        Return an iterator which yields tuples consisting of the category, the
        type, the language code and the name of each identity declared in this
        :class:`Node`.

        Both the language code and the name may be :data:`None`, if no names or
        a name without language code have been declared.
        """
        for (category, type_), names in self._identities.items():
            for lang, name in names.items():
                yield category, type_, lang, name
            if not names:
                yield category, type_, None, None

    def iter_features(self, stanza=None):
        """
        Return an iterator which yields the features of the node.

        :param stanza: The IQ request stanza
        :type stanza: :class:`~aioxmpp.IQ`
        :rtype: iterable of :class:`str`
        :return: :xep:`30` features of this node

        `stanza` is the :class:`aioxmpp.IQ` stanza of the request. This can be
        used to filter the list according to who is asking (not recommended).

        `stanza` may be :data:`None` if the features are queried without
        a specific request context. In that case, implementors should assume
        that the result is visible to everybody.

        .. note::

           Subclasses must allow :data:`None` for `stanza` and default it to
           :data:`None`.

        The features are returned as strings. The features demanded by
        :xep:`30` are always returned.

        """
        return itertools.chain(
            iter(self.STATIC_FEATURES),
            iter(self._features)
        )

    def iter_items(self, stanza=None):
        """
        Return an iterator which yields the items of the node.

        :param stanza: The IQ request stanza
        :type stanza: :class:`~aioxmpp.IQ`
        :rtype: iterable of :class:`~.disco.xso.Item`
        :return: Items of the node

        `stanza` is the :class:`aioxmpp.IQ` stanza of the request. This can be
        used to localize the list to the language of the stanza or filter it
        according to who is asking.

        `stanza` may be :data:`None` if the items are queried without
        a specific request context. In that case, implementors should assume
        that the result is visible to everybody.

        .. note::

           Subclasses must allow :data:`None` for `stanza` and default it to
           :data:`None`.

        A bare :class:`Node` cannot hold any items and will thus return an
        iterator which does not yield any element.
        """
        return iter([])

    def register_feature(self, var):
        """
        Register a feature with the namespace variable `var`.

        If the feature is already registered or part of the default :xep:`30`
        features, a :class:`ValueError` is raised.
        """
        if var in self._features or var in self.STATIC_FEATURES:
            raise ValueError("feature already claimed: {!r}".format(var))
        self._features.add(var)
        self.on_info_changed()

    def register_identity(self, category, type_, *, names={}):
        """
        Register an identity with the given `category` and `type_`.

        If there is already a registered identity with the same `category` and
        `type_`, :class:`ValueError` is raised.

        `names` may be a mapping which maps :class:`.structs.LanguageTag`
        instances to strings. This mapping will be used to produce
        ``<identity/>`` declarations with the respective ``xml:lang`` and
        ``name`` attributes.
        """
        key = category, type_
        if key in self._identities:
            raise ValueError("identity already claimed: {!r}".format(key))
        self._identities[key] = names
        self.on_info_changed()

    def set_identity_names(self, category, type_, names={}):
        """
        Update the names of an identity.

        :param category: The category of the identity to update.
        :type category: :class:`str`
        :param type_: The type of the identity to update.
        :type type_: :class:`str`
        :param names: The new internationalised names to set for the identity.
        :type names: :class:`~.abc.Mapping` from
            :class:`.structs.LanguageTag` to :class:`str`
        :raises ValueError: if no identity with the given category and type
            is currently registered.
        """
        key = category, type_
        if key not in self._identities:
            raise ValueError("identity not registered: {!r}".format(key))
        self._identities[key] = names
        self.on_info_changed()

    def unregister_feature(self, var):
        """
        Unregister a feature which has previously been registered using
        :meth:`register_feature`.

        If the feature has not been registered previously, :class:`KeyError` is
        raised.

        .. note::

           The features which are mandatory per :xep:`30` are always registered
           and cannot be unregistered. For the purpose of unregistration, they
           behave as if they had never been registered; for the purpose of
           registration, they behave as if they had been registered before.

        """
        self._features.remove(var)
        self.on_info_changed()

    def unregister_identity(self, category, type_):
        """
        Unregister an identity previously registered using
        :meth:`register_identity`.

        If no identity with the given `category` and `type_` has been
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
        self.on_info_changed()

    def as_info_xso(self, stanza=None):
        """
        Construct a :class:`~.disco.xso.InfoQuery` response object for this
        node.

        :param stanza: The IQ request stanza
        :type stanza: :class:`~aioxmpp.IQ`
        :rtype: iterable of :class:`~.disco.xso.InfoQuery`
        :return: The disco#info response for this node.

        The resulting :class:`~.disco.xso.InfoQuery` carries the features and
        identities as returned by :meth:`iter_features` and
        :meth:`iter_identities`. The :attr:`~.disco.xso.InfoQuery.node`
        attribute is at its default value and may need to be set by the caller
        accordingly.

        `stanza` is passed to :meth:`iter_features` and
        :meth:`iter_identities`. See those methods for information on the
        effects.

        .. versionadded:: 0.9
        """

        result = disco_xso.InfoQuery()
        result.features.update(self.iter_features(stanza))
        result.identities[:] = (
            disco_xso.Identity(
                category=category,
                type_=type_,
                lang=lang,
                name=name,
            )
            for category, type_, lang, name in self.iter_identities(stanza)
        )
        return result


class StaticNode(Node):
    """
    A :class:`StaticNode` is a :class:`Node` with a non-dynamic set of items.

    .. attribute:: items

       A list of :class:`.xso.Item` instances. These items will be returned
       when the node is queried for it’s :xep:`30` items.

       It is the responsibility of the user to ensure that the set of items is
       valid. This includes avoiding duplicate items.

    .. automethod:: clone

    """

    def __init__(self):
        super().__init__()
        self.items = []

    def iter_items(self, stanza=None):
        return iter(self.items)

    @classmethod
    def clone(cls, other_node):
        """
        Clone another :class:`Node` and return as :class:`StaticNode`.

        :param other_node: The node which shall be cloned
        :type other_node: :class:`Node`
        :rtype: :class:`StaticNode`
        :return: A static node which has the exact same features, identities
            and items as `other_node`.

        The features and identities are copied over into the resulting
        :class:`StaticNode`. The items of `other_node` are not copied but
        merely referenced, so changes to the item *objects* of `other_node`
        will be reflected in the result.

        .. versionadded:: 0.9
        """

        result = cls()
        result._features = {
            feature for feature in other_node.iter_features()
            if feature not in cls.STATIC_FEATURES
        }
        for category, type_, lang, name in other_node.iter_identities():
            names = result._identities.setdefault(
                (category, type_),
                aioxmpp.structs.LanguageMap()
            )
            names[lang] = name
        result.items = list(other_node.iter_items())
        return result


class DiscoServer(service.Service, Node):
    """
    Answer Service Discovery (:xep:`30`) requests sent to this client.

    This service implements handlers for ``…disco#info`` and ``…disco#items``
    IQ requests. It provides methods to configure the contents of these
    responses.

    .. seealso::

       :class:`DiscoClient`
          for a service which provides methods to query Service Discovery
          information from other entities.

    The :class:`DiscoServer` inherits from :class:`~.disco.Node` to manage the
    identities and features of the client. The identities and features declared
    in the service using the :class:`~.disco.Node` interface on the
    :class:`DiscoServer` instance are returned when a query is received for the
    JID with an empty or unset ``node`` attribute. For completeness, the
    relevant methods are listed here. Refer to the :class:`~.disco.Node`
    documentation for details.

    .. autosummary::

       .disco.Node.register_feature
       .disco.Node.unregister_feature
       .disco.Node.register_identity
       .disco.Node.unregister_identity

    .. note::

       Upon construction, the :class:`DiscoServer` adds a default identity with
       category ``"client"`` and type ``"bot"`` to the root
       :class:`~.disco.Node`. This is to comply with :xep:`30`, which specifies
       that at least one identity must always be returned. Otherwise, the
       service would be forced to send a malformed response or reply with
       ``<feature-not-implemented/>``.

       After having added another identity, that default identity can be
       removed.

    Other :class:`~.disco.Node` instances can be registered with the service
    using the following methods:

    .. automethod:: mount_node

    .. automethod:: unmount_node

    """

    on_info_result = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._node_mounts = {
            None: self
        }

        self.register_identity(
            "client", "bot",
            names={
                structs.LanguageTag.fromstr("en"): "aioxmpp default identity"
            }
        )

    @aioxmpp.service.iq_handler(
        aioxmpp.structs.IQType.GET,
        disco_xso.InfoQuery)
    async def handle_info_request(self, iq):
        request = iq.payload

        try:
            node = self._node_mounts[request.node]
        except KeyError:
            raise errors.XMPPModifyError(
                condition=errors.ErrorCondition.ITEM_NOT_FOUND
            )

        response = node.as_info_xso(iq)
        response.node = request.node

        if not response.identities:
            raise errors.XMPPModifyError(
                condition=errors.ErrorCondition.ITEM_NOT_FOUND,
            )

        return response

    @aioxmpp.service.iq_handler(
        aioxmpp.structs.IQType.GET,
        disco_xso.ItemsQuery)
    async def handle_items_request(self, iq):
        request = iq.payload

        try:
            node = self._node_mounts[request.node]
        except KeyError:
            raise errors.XMPPModifyError(
                condition=errors.ErrorCondition.ITEM_NOT_FOUND
            )

        response = disco_xso.ItemsQuery()
        response.items.extend(node.iter_items(iq))

        return response

    def mount_node(self, mountpoint, node):
        """
        Mount the :class:`Node` `node` to be returned when a peer requests
        :xep:`30` information for the node `mountpoint`.
        """
        self._node_mounts[mountpoint] = node

    def unmount_node(self, mountpoint):
        """
        Unmount the node mounted at `mountpoint`.

        .. seealso::

           :meth:`mount_node`
              for a way for mounting :class:`~.disco.Node` instances.

        """
        del self._node_mounts[mountpoint]


class DiscoClient(service.Service):
    """
    Provide cache-backed Service Discovery (:xep:`30`) queries.

    This service provides methods to query Service Discovery information from
    other entities in the XMPP network. The results are cached transparently.

    .. seealso::

       :class:`.DiscoServer`
          for a service which answers Service Discovery queries sent to the
          client by other entities.
       :class:`.EntityCapsService`
          for a service which uses :xep:`115` to fill the cache of the
          :class:`DiscoClient` with offline information.

    Querying other entities’ service discovery information:

    .. automethod:: query_info

    .. automethod:: query_items

    To prime the cache with information, the following methods can be used:

    .. automethod:: set_info_cache

    .. automethod:: set_info_future

    To control the size of caches, the following properties are available:

    .. autoattribute:: info_cache_size
       :annotation: = 10000

    .. autoattribute:: items_cache_size
       :annotation: = 100

    .. automethod:: flush_cache

    Usage example, assuming that you have a :class:`.node.Client` `client`::

      import aioxmpp.disco as disco
      # load service into node
      sd = client.summon(aioxmpp.DiscoClient)

      # retrieve server information
      server_info = yield from sd.query_info(
          node.local_jid.replace(localpart=None, resource=None)
      )

      # retrieve resources
      resources = yield from sd.query_items(
          node.local_jid.bare()
      )

    """

    on_info_result = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._info_pending = aioxmpp.cache.LRUDict()
        self._info_pending.maxsize = 10000
        self._items_pending = aioxmpp.cache.LRUDict()
        self._items_pending.maxsize = 100

        self.client.on_stream_destroyed.connect(
            self._clear_cache
        )

    @property
    def info_cache_size(self):
        """
        Maximum number of cache entries in the cache for :meth:`query_info`.

        This is mostly a measure to prevent malicious peers from exhausting
        memory by spamming :mod:`aioxmpp.entitycaps` capability hashes.

        .. versionadded:: 0.9
        """
        return self._info_pending.maxsize

    @info_cache_size.setter
    def info_cache_size(self, value):
        self._info_pending.maxsize = value

    @property
    def items_cache_size(self):
        """
        Maximum number of cache entries in the cache for :meth:`query_items`.

        .. versionadded:: 0.9
        """
        return self._items_pending.maxsize

    @items_cache_size.setter
    def items_cache_size(self, value):
        self._items_pending.maxsize = value

    def _clear_cache(self):
        for fut in self._info_pending.values():
            if not fut.done():
                fut.cancel()
        self._info_pending.clear()

        for fut in self._items_pending.values():
            if not fut.done():
                fut.cancel()
        self._items_pending.clear()

    def _handle_info_received(self, jid, node, task):
        try:
            result = task.result()
        except Exception:
            return
        self.on_info_result(jid, node, result)

    def flush_cache(self):
        """
        Clear the cache.

        This clears the internal cache in a way which lets existing queries
        continue, but the next query for each target will behave as if
        `require_fresh` had been set to true.
        """
        self._info_pending.clear()
        self._items_pending.clear()

    async def send_and_decode_info_query(self, jid, node):
        request_iq = stanza.IQ(to=jid, type_=structs.IQType.GET)
        request_iq.payload = disco_xso.InfoQuery(node=node)

        response = await self.client.send(request_iq)

        return response

    async def query_info(self, jid, *,
                         node=None, require_fresh=False, timeout=None,
                         no_cache=False):
        """
        Query the features and identities of the specified entity.

        :param jid: The entity to query.
        :type jid: :class:`aioxmpp.JID`
        :param node: The node to query.
        :type node: :class:`str` or :data:`None`
        :param require_fresh: Boolean flag to discard previous caches.
        :type require_fresh: :class:`bool`
        :param timeout: Optional timeout for the response.
        :type timeout: :class:`float`
        :param no_cache: Boolean flag to forbid caching of the request.
        :type no_cache: :class:`bool`
        :rtype: :class:`.xso.InfoQuery`
        :return: Service discovery information of the `node` at `jid`.

        The requests are cached. This means that only one request is ever fired
        for a given target (identified by the `jid` and the `node`). The
        request is re-used for all subsequent requests to that identity.

        If `require_fresh` is set to true, the above does not hold and a fresh
        request is always created. The new request is the request which will be
        used as alias for subsequent requests to the same identity.

        The visible effects of this are twofold:

        * Caching: Results of requests are implicitly cached
        * Aliasing: Two concurrent requests will be aliased to one request to
          save computing resources

        Both can be turned off by using `require_fresh`. In general, you should
        not need to use `require_fresh`, as all requests are implicitly
        cancelled whenever the underlying session gets destroyed.

        `no_cache` can be set to true to prevent future requests to be aliased
        to this request, i.e. the request is not stored in the internal request
        cache. This does not affect `require_fresh`, i.e. if a cached result is
        available, it is used.

        The `timeout` can be used to restrict the time to wait for a
        response. If the timeout triggers, :class:`TimeoutError` is raised.

        If :meth:`~.Client.send` raises an
        exception, all queries which were running simultaneously for the same
        target re-raise that exception. The result is not cached though. If a
        new query is sent at a later point for the same target, a new query is
        actually sent, independent of the value chosen for `require_fresh`.

        .. versionchanged:: 0.9

            The `no_cache` argument was added.
        """
        key = jid, node

        if not require_fresh:
            try:
                request = self._info_pending[key]
            except KeyError:
                pass
            else:
                try:
                    return await request
                except asyncio.CancelledError:
                    pass

        request = asyncio.ensure_future(
            self.send_and_decode_info_query(jid, node)
        )
        request.add_done_callback(
            functools.partial(
                self._handle_info_received,
                jid,
                node
            )
        )

        if not no_cache:
            self._info_pending[key] = request
        try:
            if timeout is not None:
                try:
                    result = await asyncio.wait_for(
                        request,
                        timeout=timeout)
                except asyncio.TimeoutError:
                    raise TimeoutError()
            else:
                result = await request
        except:  # NOQA
            if request.done():
                try:
                    pending = self._info_pending[key]
                except KeyError:
                    pass
                else:
                    if pending is request:
                        del self._info_pending[key]
            raise

        return result

    async def query_items(self, jid, *,
                          node=None, require_fresh=False, timeout=None):
        """
        Query the items of the specified entity.

        :param jid: The entity to query.
        :type jid: :class:`aioxmpp.JID`
        :param node: The node to query.
        :type node: :class:`str` or :data:`None`
        :param require_fresh: Boolean flag to discard previous caches.
        :type require_fresh: :class:`bool`
        :param timeout: Optional timeout for the response.
        :type timeout: :class:`float`
        :rtype: :class:`.xso.ItemsQuery`
        :return: Service discovery items of the `node` at `jid`.

        The arguments have the same semantics as with :meth:`query_info`, as
        does the caching and error handling.
        """
        key = jid, node

        if not require_fresh:
            try:
                request = self._items_pending[key]
            except KeyError:
                pass
            else:
                try:
                    return await request
                except asyncio.CancelledError:
                    pass

        request_iq = stanza.IQ(to=jid, type_=structs.IQType.GET)
        request_iq.payload = disco_xso.ItemsQuery(node=node)

        request = asyncio.ensure_future(
            self.client.send(request_iq)
        )

        self._items_pending[key] = request
        try:
            if timeout is not None:
                try:
                    result = await asyncio.wait_for(
                        request,
                        timeout=timeout)
                except asyncio.TimeoutError:
                    raise TimeoutError()
            else:
                result = await request
        except:  # NOQA
            if request.done():
                try:
                    pending = self._items_pending[key]
                except KeyError:
                    pass
                else:
                    if pending is request:
                        del self._items_pending[key]
            raise

        return result

    def set_info_cache(self, jid, node, info):
        """
        This is a wrapper around :meth:`set_info_future` which creates a future
        and immediately assigns `info` as its result.

        .. versionadded:: 0.5
        """
        fut = asyncio.Future()
        fut.set_result(info)
        self.set_info_future(jid, node, fut)

    def set_info_future(self, jid, node, fut):
        """
        Override the cache entry (if one exists) for :meth:`query_info` of the
        `jid` and `node` combination with the given :class:`asyncio.Future`
        fut.

        The future must receive a :class:`dict` compatible to the output of
        :meth:`.xso.InfoQuery.to_dict`.

        As usual, the cache can be bypassed and cleared by passing
        `require_fresh` to :meth:`query_info`.

        .. seealso::

           Module :mod:`aioxmpp.entitycaps`
             :xep:`0115` implementation which uses this method to prime the
             cache with information derived from Entity Capability
             announcements.

        .. note::

           If a future is set to exception state, it will still remain and make
           all queries for that target fail with that exception, until a query
           uses `require_fresh`.

        .. versionadded:: 0.5
        """
        self._info_pending[jid, node] = fut


class mount_as_node(service.Descriptor):
    """
    Service descriptor which mounts the :class:`~.service.Service` as
    :class:`.DiscoServer` node.

    :param mountpoint: The mountpoint at which to mount the node.
    :type mountpoint: :class:`str`

    .. versionadded:: 0.8

    When the service is instaniated, it is mounted as :class:`~.disco.Node` at
    the given `mountpoint`; it must thus also inherit from
    :class:`~.disco.Node` or implement a compatible interface.

    .. autoattribute:: mountpoint
    """

    def __init__(self, mountpoint):
        super().__init__()
        self._mountpoint = mountpoint

    @property
    def mountpoint(self):
        """
        The mountpoint at which the node is mounted.
        """
        return self._mountpoint

    @property
    def required_dependencies(self):
        return [DiscoServer]

    @contextlib.contextmanager
    def init_cm(self, instance):
        disco = instance.dependencies[DiscoServer]
        disco.mount_node(self._mountpoint, instance)
        try:
            yield
        finally:
            disco.unmount_node(self._mountpoint)

    @property
    def value_type(self):
        return type(None)


class RegisteredFeature:
    """
    Manage registration of a feature with a :class:`DiscoServer`.

    :param service: The service implementing the service discovery server.
    :type service: :class:`DiscoServer`
    :param feature: The feature to register.
    :type feature: :class:`str`

    .. note::

        Normally, you would not create an instance of this object manually.
        Use the :class:`register_feature` descriptor on your
        :class:`aioxmpp.Service` which will provide a
        :class:`RegisteredFeature` object::

            class Foo(aioxmpp.Service):
                _some_feature = aioxmpp.disco.register_feature(
                    "urn:of:the:feature"
                )

                # after __init__, self._some_feature is a RegisteredFeature
                # instance.

                @property
                def some_feature_enabled(self):
                    # better do not expose the enabled boolean directly; this
                    # gives you the opportunity to do additional things when it
                    # is changed, such as disabling multiple features at once.
                    return self._some_feature.enabled

                @some_feature_enabled.setter
                def some_feature_enabled(self, value):
                    self._some_feature.enabled = value

    .. versionadded:: 0.9

    This object can be used as a context manager. Upon entering the context,
    the feature is registered. When the context is left, the feature is
    unregistered.

    .. note::

        The context-manager use does not nest sensibly. Thus, do not use
        th context-manager feature on :class:`RegisteredFeature` instances
        which are created by :class:`register_feature`, as
        :class:`register_feature` uses the context manager to
        register/unregister the feature on initialisation/shutdown.

    Independently, it is possible to control the registration status of the
    feature using :attr:`enabled`.

    .. autoattribute:: enabled

    .. autoattribute:: feature

    """

    def __init__(self, service, feature):
        self.__service = service
        self.__feature = feature
        self.__enabled = False

    @property
    def enabled(self):
        """
        Boolean indicating whether the feature is registered by this object
        or not.

        When this attribute is changed to :data:`True`, the feature is
        registered. When the attribute is changed to :data:`False`, the feature
        is unregistered.
        """
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        value = bool(value)
        if value == self.__enabled:
            return

        if value:
            self.__service.register_feature(self.__feature)
        else:
            self.__service.unregister_feature(self.__feature)

        self.__enabled = value

    @property
    def feature(self):
        """
        The feature this object is controlling (read-only).
        """
        return self.__feature

    def __enter__(self):
        self.enabled = True
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.enabled = False


class register_feature(service.Descriptor):
    """
    Service descriptor which registers a service discovery feature.

    :param feature: The feature to register.
    :type feature: :class:`str`

    .. versionadded:: 0.8

    When the service is instaniated, the `feature` is registered at the
    :class:`~.DiscoServer`.

    On instances, the attribute which is described with this is a
    :class:`RegisteredFeature` instance.

    .. versionchanged:: 0.9

        :class:`RegisteredFeature` was added; before, the attribute reads as
        :data:`None`.
    """

    def __init__(self, feature):
        super().__init__()
        self._feature = feature

    @property
    def feature(self):
        """
        The feature which is registered.
        """
        return self._feature

    @property
    def required_dependencies(self):
        return [DiscoServer]

    def init_cm(self, instance):
        disco = instance.dependencies[DiscoServer]
        return RegisteredFeature(disco, self._feature)

    @property
    def value_type(self):
        return RegisteredFeature
