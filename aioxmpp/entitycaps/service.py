import asyncio
import base64
import copy
import functools
import hashlib

from xml.sax.saxutils import escape

import aioxmpp.callbacks
import aioxmpp.disco as disco
import aioxmpp.service

from . import xso as my_xso


def build_identities_string(identities):
    identities = [
        b"/".join([
            escape(identity["category"]).encode("utf-8"),
            escape(identity["type"]).encode("utf-8"),
            escape(identity.get("lang", "")).encode("utf-8"),
            escape(identity.get("name", "")).encode("utf-8"),
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
            form_types = set(form["FORM_TYPE"])
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

    for type_, fields in forms_list:
        parts.append(type_)

        field_list = sorted(
            (
                (escape(var).encode("utf-8"), values)
                for var, values in fields.items()
                if var != "FORM_TYPE"
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
        build_identities_string(query.get("identities", []))
    )
    hashimpl.update(
        build_features_string(query.get("features", []))
    )
    hashimpl.update(
        build_forms_string(query.get("forms", {}))
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

    .. automethod:: load_trusted_from_json

    .. automethod:: load_user_from_json

    .. automethod:: save_user_to_json

    Queries (API intended for :class:`Service`):

    .. automethod:: create_query_future

    .. automethod:: lookup_in_database

    .. automethod:: lookup
    """

    def __init__(self):
        self._trusted = {}
        self._user = {}
        self._lookup_cache = {}

    def _erase_future(self, for_hash, fut):
        try:
            existing = self._lookup_cache[for_hash]
        except KeyError:
            pass
        else:
            if existing is fut:
                del self._lookup_cache[for_hash]

    def load_trusted_from_json(self, json):
        """
        Load the trusted database from the JSON-compatible dict `json`.

        The expected format is identical to the format used by the `capsdb`_.

        .. _capsdb: https://github.com/xnyhps/capsdb

        .. seealso::

           Method :meth:`lookup_in_database`
             for details on the lookup strategy.

        """
        self._trusted = copy.deepcopy(json)

    def load_user_from_json(self, json):
        """
        Load the user-level database from the JSON-compatible dict `json`.

        The expected format is identical to the format used by the `capsdb`_,
        which is also the format used with :meth:`save_user_to_json`.

        .. _capsdb: https://github.com/xnyhps/capsdb

        .. seealso::

           Method :meth:`lookup_in_database`
             for details on the lookup strategy.

        """
        self._user = copy.deepcopy(json)

    def save_user_to_json(self):
        """
        Return a JSON-compatible dict in the `capsdb`_ format which holds the
        user-level database. Any entries which are also in the trusted database
        are omitted from this result.

        .. _capsdb: https://github.com/xnyhps/capsdb
        """
        return {
            key: copy.deepcopy(value)
            for key, value in self._user.items()
            if key not in self._trusted
        }

    def lookup_in_database(self, hash_):
        """
        Look up a hash in the database. This first checks the trusted database
        and only if the hash is not found there, the user-level database is
        checked.

        The first database to return a result is used. If no database contains
        the given `hash_`, :class:`KeyError` is raised.

        The ``"node"`` and ``"hash"`` keys are removed from the result. The
        result is also deep-copied to avoid accidental modification of the
        database.
        """
        try:
            data = self._trusted[hash_]
        except KeyError:
            data = self._user[hash_]
        data = copy.deepcopy(data)
        del data["node"]
        del data["hash"]
        data["forms"] = [
            dict(value,
                 FORM_TYPE=[key])
            for key, value in data["forms"].items()
        ]
        return data

    @asyncio.coroutine
    def lookup(self, hash_):
        """
        Look up the given `hash_` first in the database and then by waiting on
        the futures created with :meth:`create_query_future` for that hash.

        If the hash is not in the database, :meth:`lookup` iterates as long as
        there are pending futures for the given `hash_`. If there are no
        pending futures, :class:`KeyError` is raised. If a future raises a
        :class:`ValueError`, it is ignored. If the future returns a value, it
        is used as the result.
        """
        try:
            result = self.lookup_in_database(hash_)
        except KeyError:
            pass
        else:
            return result

        while True:
            fut = self._lookup_cache[hash_]
            try:
                result = yield from fut
            except ValueError:
                continue
            else:
                return result

    def create_query_future(self, hash_):
        """
        Create and return a :class:`asyncio.Future` for the given `hash_`. The
        future is referenced internally and used by any calls to :meth:`lookup`
        which are made while the future is pending. The future is removed from
        the internal storage automatically when a result or exception is set
        for it.

        This allows for deduplication of queries for the same hash.
        """
        fut = asyncio.Future()
        fut.add_done_callback(
            functools.partial(self._erase_future, hash_)
        )
        self._lookup_cache[hash_] = fut
        return fut

    def add_cache_entry(self, hash_, entry):
        """
        Add the given `entry` to the user-level database keyed with
        `hash_`. The `entry` is **not** validated to actually map to
        `hash_`, it is expected that the caller perfoms the validation. It must
        also contain valid ``"node"`` and ``"hash"`` keys.
        """
        self._user[hash_] = entry


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
                to_save = dict(data)
                to_save["node"] = node
                to_save["hash"] = hash_

                transformed_forms = {}
                for form in to_save["forms"]:
                    new_form = dict(form)
                    transformed_forms[new_form["FORM_TYPE"][0]] = new_form
                    del new_form["FORM_TYPE"]
                to_save["forms"] = transformed_forms

                self.cache.add_cache_entry(ver, to_save)
                fut.set_result(data)
            else:
                fut.set_exception(ValueError("hash mismatch"))

        return data

    @asyncio.coroutine
    def lookup_info(self, jid, node, ver, hash_):
        try:
            info = yield from self.cache.lookup(ver)
        except KeyError:
            pass
        else:
            self.logger.debug("found ver=%r in cache", ver)
            return info

        self.logger.debug("have to query for ver=%r", ver)
        fut = self.cache.create_query_future(ver)
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
            identity_dict = {
                "category": category,
                "type": type_,
            }
            if lang is not None:
                identity_dict["lang"] = lang.match_str
            if name is not None:
                identity_dict["name"] = name
            identities.append(identity_dict)

        new_ver = hash_query(
            {
                "features": list(self.disco.iter_features()),
                "identities": identities,
                "forms": {},
            },
            "sha1",
        )

        if self.ver != new_ver:
            if self.ver is not None:
                self.disco.unmount_node(self.NODE + "#" + self.ver)
            self.ver = new_ver
            self.disco.mount_node(self.NODE + "#" + self.ver, self.disco)
            self.on_ver_changed()
