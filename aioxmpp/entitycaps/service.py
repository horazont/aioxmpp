import asyncio
import base64
import copy
import functools
import hashlib
import logging
import os
import tempfile
import urllib.parse

from xml.sax.saxutils import escape

import aioxmpp.callbacks
import aioxmpp.disco as disco
import aioxmpp.service
import aioxmpp.xml
import aioxmpp.xso

from . import xso as my_xso


logger = logging.getLogger("aioxmpp.entitycaps")


def build_identities_string(identities):
    identities = [
        b"/".join([
            escape(identity.category).encode("utf-8"),
            escape(identity.type_).encode("utf-8"),
            escape(str(identity.lang or "")).encode("utf-8"),
            escape(identity.name or "").encode("utf-8"),
        ])
        for identity in identities
    ]

    if len(set(identities)) != len(identities):
        raise ValueError("duplicate identity")

    identities.sort()
    identities.append(b"")
    return b"<".join(identities)


def build_features_string(features):
    features = list(escape(feature).encode("utf-8") for feature in features)

    if len(set(features)) != len(features):
        raise ValueError("duplicate feature")

    features.sort()
    features.append(b"")
    return b"<".join(features)


def build_forms_string(forms):
    types = set()
    forms_list = []
    for form in forms:
        try:
            form_types = set(
                value
                for field in form.fields.filter(attrs={"var": "FORM_TYPE"})
                for value in field.values
            )
        except KeyError:
            continue

        if len(form_types) > 1:
            raise ValueError("form with multiple types")
        elif not form_types:
            continue

        type_ = escape(next(iter(form_types))).encode("utf-8")
        if type_ in types:
            raise ValueError("multiple forms of type {!r}".format(type_))
        types.add(type_)
        forms_list.append((type_, form))
    forms_list.sort()

    parts = []

    for type_, form in forms_list:
        parts.append(type_)

        field_list = sorted(
            (
                (escape(field.var).encode("utf-8"), field.values)
                for field in form.fields
                if field.var != "FORM_TYPE"
            ),
            key=lambda x: x[0]
        )

        for var, values in field_list:
            parts.append(var)
            parts.extend(sorted(
                escape(value).encode("utf-8") for value in values
            ))

    parts.append(b"")
    return b"<".join(parts)


def hash_query(query, algo):
    hashimpl = hashlib.new(algo)
    hashimpl.update(
        build_identities_string(query.identities)
    )
    hashimpl.update(
        build_features_string(query.features)
    )
    hashimpl.update(
        build_forms_string(query.exts)
    )

    return base64.b64encode(hashimpl.digest()).decode("ascii")


class Cache:
    """
    This provides a two-level cache for entity capabilities information. The
    idea is to have a trusted database, e.g. installed system-wide or shipped
    with :mod:`aioxmpp` and in addition a user-level database which is
    automatically filled with hashes which have been found by the
    :class:`Service`.

    The trusted database is taken as read-only and overrides the user-collected
    database. When a hash is in both databases, it is removed from the
    user-collected database (to save space).

    In addition to serving the databases, it provides deduplication for queries
    by holding a cache of futures looking up the same hash.

    Database management (user API):

    .. automethod:: set_system_db_path

    .. automethod:: set_user_db_path

    Queries (API intended for :class:`Service`):

    .. automethod:: create_query_future

    .. automethod:: lookup_in_database

    .. automethod:: lookup
    """

    def __init__(self):
        self._lookup_cache = {}
        self._memory_overlay = {}
        self._system_db_path = None
        self._user_db_path = None

    def _erase_future(self, for_hash, for_node, fut):
        try:
            existing = self._lookup_cache[for_hash, for_node]
        except KeyError:
            pass
        else:
            if existing is fut:
                del self._lookup_cache[for_hash, for_node]

    def set_system_db_path(self, path):
        self._system_db_path = path

    def set_user_db_path(self, path):
        self._user_db_path = path

    def lookup_in_database(self, hash_, node):
        try:
            result = self._memory_overlay[hash_, node]
        except KeyError:
            pass
        else:
            logger.debug("memory cache hit: %s %r", hash_, node)
            return result

        quoted = urllib.parse.quote(node, safe="")
        if self._system_db_path is not None:
            try:
                f = (
                    self._system_db_path / "{}_{}.xml".format(hash_, quoted)
                ).open("rb")
            except OSError:
                pass
            else:
                logger.debug("system db hit: %s %r", hash_, node)
                with f:
                    return aioxmpp.xml.read_single_xso(f, disco.xso.InfoQuery)

        if self._user_db_path is not None:
            try:
                f = (
                    self._user_db_path / "{}_{}.xml".format(hash_, quoted)
                ).open("rb")
            except OSError:
                pass
            else:
                logger.debug("user db hit: %s %r", hash_, node)
                with f:
                    return aioxmpp.xml.read_single_xso(f, disco.xso.InfoQuery)

        raise KeyError(node)

    @asyncio.coroutine
    def lookup(self, hash_, node):
        """
        Look up the given `node` URL using the given `hash_` first in the
        database and then by waiting on the futures created with
        :meth:`create_query_future` for that node URL and hash.

        If the hash is not in the database, :meth:`lookup` iterates as long as
        there are pending futures for the given `hash_` and `node`. If there
        are no pending futures, :class:`KeyError` is raised. If a future raises
        a :class:`ValueError`, it is ignored. If the future returns a value, it
        is used as the result.
        """
        try:
            result = self.lookup_in_database(hash_, node)
        except KeyError:
            pass
        else:
            return result

        while True:
            fut = self._lookup_cache[hash_, node]
            try:
                result = yield from fut
            except ValueError:
                continue
            else:
                return result

    def create_query_future(self, hash_, node):
        """
        Create and return a :class:`asyncio.Future` for the given `hash_`
        function and `node` URL. The future is referenced internally and used
        by any calls to :meth:`lookup` which are made while the future is
        pending. The future is removed from the internal storage automatically
        when a result or exception is set for it.

        This allows for deduplication of queries for the same hash.
        """
        fut = asyncio.Future()
        fut.add_done_callback(
            functools.partial(self._erase_future, hash_, node)
        )
        self._lookup_cache[hash_, node] = fut
        return fut

    def add_cache_entry(self, hash_, node, entry):
        """
        Add the given `entry` (which must be a :class:`~.disco.xso.InfoQuery`
        instance) to the user-level database keyed with the hash function type
        `hash_` and the `node` URL. The `entry` is **not** validated to
        actually map to `node` with the given `hash_` function, it is expected
        that the caller perfoms the validation.
        """
        copied_entry = copy.copy(entry)
        copied_entry.node = node
        self._memory_overlay[hash_, node] = copied_entry
        if self._user_db_path is not None:
            asyncio.async(asyncio.get_event_loop().run_in_executor(
                None,
                writeback,
                self._user_db_path,
                hash_,
                node,
                entry.captured_events))


class Service(aioxmpp.service.Service):
    """
    This service implements `XEP-0115`_, transparently. Besides loading the
    service, no interaction is required to get some of the benefits of
    `XEP-0115`_.

    Two additional things need to be done by users to get full support and
    performance:

    1. To make sure that peers are always up-to-date with the current
       capabilities, it is required that users listen on the
       :meth:`on_ver_changed` signal and re-emit their current presence when it
       fires.

       The service takes care of attaching capabilities information on the
       outgoing stanza, using a stanza filter.

    2. Users should use a process-wide :class:`Cache` instance and assign it to
       the :attr:`cache` of each :class:`.entitycaps.Service` they use. This
       improves performance by sharing (verified) hashes among :class:`Service`
       instances.

       In addition, the hashes should be saved and restored on shutdown/start
       of the process. See the :class:`Cache` for details.

    .. _XEP-0115: https://xmpp.org/extensions/xep-0115.html

    .. signal:: on_ver_changed

       The signal emits whenever the ``ver`` of the local client changes. This
       happens when the set of features or identities announced in the
       :class:`.disco.Service` changes.

    .. autoattribute:: cache

    """

    ORDER_AFTER = {disco.Service}

    NODE = "http://aioxmpp.zombofant.net/"

    on_ver_changed = aioxmpp.callbacks.Signal()

    def __init__(self, node):
        super().__init__(node)

        self.ver = None
        self._cache = Cache()

        self.disco = node.summon(disco.Service)
        self._info_changed_token = self.disco.on_info_changed.connect(
            self._info_changed
        )
        self.disco.register_feature(
            "http://jabber.org/protocol/caps"
        )

        self._inbound_filter_token = \
            node.stream.service_inbound_presence_filter.register(
                self.handle_inbound_presence,
                type(self)
            )

        self._outbound_filter_token = \
            node.stream.service_outbound_presence_filter.register(
                self.handle_outbound_presence,
                type(self)
            )

    @property
    def cache(self):
        """
        The :class:`Cache` instance used for this :class:`Service`. Deleting
        this attribute will automatically create a new :class:`Cache` instance.

        The attribute can be used to share a single :class:`Cache` among
        multiple :class:`Service` instances.
        """
        return self._cache

    @cache.setter
    def cache(self, v):
        self._cache = v

    @cache.deleter
    def cache(self):
        self._cache = Cache()

    def _info_changed(self):
        asyncio.get_event_loop().call_soon(
            self.update_hash
        )

    @asyncio.coroutine
    def _shutdown(self):
        self.client.stream.service_outbound_presence_filter.unregister(
            self._outbound_filter_token
        )
        self.client.stream.service_inbound_presence_filter.unregister(
            self._inbound_filter_token
        )
        self.disco.on_info_changed.disconnect(
            self._info_changed_token
        )
        self.disco.unregister_feature(
            "http://jabber.org/protocol/caps"
        )
        if self.ver is not None:
            self.disco.unmount_node(
                self.NODE + "#" + self.ver
            )

    @asyncio.coroutine
    def query_and_cache(self, jid, node, ver, hash_, fut):
        data = yield from self.disco.query_info(
            jid,
            node=node+"#"+ver,
            require_fresh=True)

        try:
            expected = hash_query(data, hash_.replace("-", ""))
        except ValueError as exc:
            fut.set_exception(exc)
        else:
            if expected == ver:
                self.cache.add_cache_entry(hash_, node+"#"+ver, data)
                fut.set_result(data)
            else:
                fut.set_exception(ValueError("hash mismatch"))

        return data

    @asyncio.coroutine
    def lookup_info(self, jid, node, ver, hash_):
        try:
            info = yield from self.cache.lookup(hash_, node+"#"+ver)
        except KeyError:
            pass
        else:
            self.logger.debug("found ver=%r in cache", ver)
            return info

        self.logger.debug("have to query for ver=%r", ver)
        fut = self.cache.create_query_future(hash_, node+"#"+ver)
        info = yield from self.query_and_cache(
            jid, node, ver, hash_,
            fut
        )

        return info

    def handle_outbound_presence(self, presence):
        if self.ver is not None and presence.type_ is None:
            presence.xep0115_caps = my_xso.Caps(
                self.NODE,
                self.ver,
                "sha-1",
            )
        return presence

    def handle_inbound_presence(self, presence):
        caps = presence.xep0115_caps
        presence.xep0115_caps = None

        if caps is not None and caps.hash_ is not None:
            self.logger.debug(
                "inbound presence with ver=%r and hash=%r from %s",
                caps.ver, caps.hash_,
                presence.from_)
            task = asyncio.async(
                self.lookup_info(presence.from_,
                                 caps.node,
                                 caps.ver,
                                 caps.hash_)
            )
            self.disco.set_info_future(presence.from_, None, task)

        return presence

    def update_hash(self):
        identities = []
        for category, type_, lang, name in self.disco.iter_identities():
            identity = disco.xso.Identity(category=category,
                                          type_=type_)
            if lang is not None:
                identity.lang = lang
            if name is not None:
                identity.name = name
            identities.append(identity)

        new_ver = hash_query(
            disco.xso.InfoQuery(
                identities=identities,
                features=self.disco.iter_features(),
            ),
            "sha1",
        )

        if self.ver != new_ver:
            if self.ver is not None:
                self.disco.unmount_node(self.NODE + "#" + self.ver)
            self.ver = new_ver
            self.disco.mount_node(self.NODE + "#" + self.ver, self.disco)
            self.on_ver_changed()


def writeback(base_path, hash_, node, captured_events):
    import pprint
    pprint.pprint(captured_events)
    quoted = urllib.parse.quote(node, safe="")
    dest_path = base_path / "{}_{}.xml".format(hash_, quoted)
    with tempfile.NamedTemporaryFile(dir=str(base_path), delete=False) as tmpf:
        try:
            generator = aioxmpp.xml.XMPPXMLGenerator(
                tmpf,
                short_empty_elements=True)
            generator.startDocument()
            aioxmpp.xso.events_to_sax(captured_events, generator)
            generator.endDocument()
        except:
            os.unlink(tmpf.name)
            raise
        os.replace(tmpf.name, str(dest_path))
