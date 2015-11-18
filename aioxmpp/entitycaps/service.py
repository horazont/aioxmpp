import asyncio
import base64
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
    forms = sorted(
        (
            (escape(key).encode("utf-8"), value)
            for key, value in forms.items()
        ),
        key=lambda x: x[0]
    )

    parts = []

    for type_, fields in forms:
        parts.append(type_)

        field_list = sorted(
            (
                (escape(var).encode("utf-8"), values)
                for var, values in fields.items()
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

    2. Users should save and load the database of hashes using
       :meth:`db_to_json` and :meth:`db_from_json`. This increases performance
       and accuracy, especially if a source such as the `capsdb`_ is used.

       .. _capsdb: https://github.com/xnyhps/capsdb

    .. _XEP-0115: https://xmpp.org/extensions/xep-0115.html

    .. automethod:: db_to_json

    .. automethod:: db_from_json

    .. signal:: on_ver_changed

       The signal emits whenever the ``ver`` of the local client changes. This
       happens when the set of features or identities announced in the
       :class:`.disco.Service` changes.

    """

    ORDER_AFTER = {disco.Service}

    NODE = "http://aioxmpp.zombofant.net/"

    on_ver_changed = aioxmpp.callbacks.Signal()

    def __init__(self, node):
        super().__init__(node)

        self.ver = None

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

        self._lookup_future_cache = {}
        self._hash_cache = {}

    def _info_changed(self):
        asyncio.get_event_loop().call_soon(
            self.update_hash
        )

    def lookup_in_cache(self, ver, hash_):
        item = dict(self._hash_cache[ver])
        if item["hash"] != hash_:
            raise KeyError(ver)
        del item["hash"]
        del item["node"]
        return item

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
                self._hash_cache[ver] = to_save
                fut.set_result(to_save)
            else:
                fut.set_exception(ValueError("hash mismatch"))

        return data

    @asyncio.coroutine
    def lookup_info(self, jid, node, ver, hash_):
        key = ver, hash_

        try:
            info = self.lookup_in_cache(*key)
        except KeyError:
            pass
        else:
            self.logger.debug("found ver=%r in cache", ver)
            return info

        while True:
            # check if a lookup is currently going on
            try:
                fut = self._lookup_future_cache[key]
            except KeyError:
                # no lookup going on, we have to start our own
                break
            self.logger.debug("attaching to existing query")
            try:
                # try to use the value from the lookup
                info = yield from fut
            except ValueError:
                # lookup did not pass the check to be valid for all
                # instances of this hash, retry
                self.logger.debug("existing query failed, retrying")
            else:
                # lookup did pass the validity check, return result
                self.logger.debug("re-used result from existing query")
                return info

        self.logger.debug("have to query for ver=%r", ver)
        fut = asyncio.Future()
        self._lookup_future_cache[key] = fut
        info = yield from self.query_and_cache(
            jid, node, ver, hash_,
            fut
        )

        if self._lookup_future_cache[key] == fut:
            del self._lookup_future_cache[key]

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

    def db_to_json(self):
        """
        Return the internal hash cache as JSON-serialisable dict. The format is
        compatible with the capsdb format.
        """
        return self._hash_cache

    def db_from_json(self, data):
        """
        Import data from a capsdb-compatible source.
        """
        self._hash_cache.update(data)

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
