########################################################################
# File name: hashes.py
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
"""
:mod:`~aioxmpp.hashes` --- Hash Functions for use with XMPP (:xep:`300`)
########################################################################

:xep:`300` consolidates the use of hash functions and their digests in XMPP.
Identifiers (usually called `algo`) are defined to refer to specific
implementations and parametrisations of hashes (:func:`hash_from_algo`,
:func:`algo_of_hash`) and there is a defined XML format for carrying hash
digests (:class:`Hash`) and hash algorithms to be used (:class:`HashUsed`).

This allows other extensions to easily embed hash digests in their protocols
(:class:`HashesParent`, :class:`HashesUsedParent`).

The service :class:`HashService` registers the disco features for the
supported hash functions and allows querying hash functions supported by
you and another entity on the Jabber network supporting :xep:`300`.

.. note::

    Compliance with :xep:`300` depends on your build of Python and possibly
    OpenSSL. Version 0.5.1 of :xep:`300` requires support of SHA3 and BLAKE2b,
    which was only introduced in Python 3.6.

Utilities for Working with Hash Algorithm Identifiers
=====================================================

.. autofunction:: hash_from_algo

.. autofunction:: algo_of_hash

.. data:: default_hash_algorithms

    A set of `algo` values which consists of hash functions matching the
    following criteria:

    * They are specified as ``MUST`` or ``SHOULD`` in the supported version of
      :xep:`300`.
    * They are supported by :mod:`hashlib`.
    * Only one function from each matching family is selected. If multiple
      functions apply, ``MUST`` is preferred over ``SHOULD``.

    The set thus varies based on the build of Python and possibly OpenSSL. The
    algorithms in the set are guaranteed to return a valid hash implementation
    when passed to :func:`~aioxmpp.misc.hash_from_algo`.

    In a fully compliant build, this set consists of ``sha-256``, ``sha3-256``
    and ``blake2b-256``.

Service
=======

.. autoclass:: HashService

XSOs
====

.. autoclass:: Hash

.. autoclass:: HashesParent()

.. autoclass:: HashUsed

.. autoclass:: HashesUsedParent()
"""
import asyncio
import hashlib

import aioxmpp.disco as disco
import aioxmpp.service as service
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0300_hashes2 = "urn:xmpp:hashes:2"
namespaces.xep0300_hash_name_prefix = "urn:xmpp:hash-function-text-names:"


_HASH_ALGO_MAPPING = [
    ("md2", (False, ("md2", (), {}))),
    ("md4", (False, ("md4", (), {}))),
    ("md5", (False, ("md5", (), {}))),
    ("sha-1", (True, ("sha1", (), {}))),
    ("sha-224", (True, ("sha224", (), {}))),
    ("sha-256", (True, ("sha256", (), {}))),
    ("sha-384", (True, ("sha384", (), {}))),
    ("sha-512", (True, ("sha512", (), {}))),
    ("sha3-256", (True, ("sha3_256", (), {}))),
    ("sha3-512", (True, ("sha3_512", (), {}))),
    ("blake2b-256", (True, ("blake2b", (), {"digest_size": 32}))),
    ("blake2b-512", (True, ("blake2b", (), {"digest_size": 64}))),
]


_HASH_ALGO_MAP = dict(_HASH_ALGO_MAPPING)
_HASH_ALGO_REVERSE_MAP = {
    fun_name: (enabled, algo)
    for algo, (enabled, (fun_name, fun_args, fun_kwargs)) in _HASH_ALGO_MAPPING
    if not fun_args and not fun_kwargs
}


def is_algo_supported(algo):
    try:
        enabled, (fun_name, _, _) = _HASH_ALGO_MAP[algo]
    except KeyError:
        return False

    return enabled and hasattr(hashlib, fun_name)


SUPPORTED_HASH_FEATURES = set()
for _hash in _HASH_ALGO_MAP:
    if is_algo_supported(_hash):
        SUPPORTED_HASH_FEATURES.add(
            namespaces.xep0300_hash_name_prefix + _hash
        )
del _hash


def hash_from_algo(algo):
    """
    Return a :mod:`hashlib` hash given the :xep:`300` `algo`.

    :param algo: The algorithm identifier as defined in :xep:`300`.
    :type algo: :class:`str`
    :raises NotImplementedError: if the hash algorithm is not supported by
        :mod:`hashlib`.
    :raises ValueError: if the hash algorithm MUST NOT be supported.
    :return: A hash object from :mod:`hashlib` or compatible.

    If the `algo` is not supported by the :mod:`hashlib` module,
    :class:`NotImplementedError` is raised.
    """

    try:
        enabled, (fun_name, fun_args, fun_kwargs) = _HASH_ALGO_MAP[algo]
    except KeyError:
        raise NotImplementedError(
            "hash algorithm {!r} unknown".format(algo)
        ) from None

    if not enabled:
        raise ValueError(
            "support of {} in XMPP is forbidden".format(algo)
        )

    try:
        fun = getattr(hashlib, fun_name)
    except AttributeError as exc:
        raise NotImplementedError(
            "{} not supported by hashlib".format(algo)
        ) from exc

    return fun(*fun_args, **fun_kwargs)


def algo_of_hash(h):
    """
    Return a :xep:`300` `algo` from a given :mod:`hashlib` hash.

    :param h: Hash object from :mod:`hashlib`.
    :raises ValueError: if `h` does not have a defined `algo` value.
    :raises ValueError: if the hash function MUST NOT be supported.
    :return: The `algo` value for the given hash.
    :rtype: :class:`str`

    .. warning::

        Use with caution for :func:`hashlib.blake2b` hashes.
        :func:`algo_of_hash` cannot safely determine whether blake2b was
        initialised with a salt, personality, key or other non-default
        :xep:`300` mode.

        In such a case, the return value will be the matching ``blake2b-*``
        `algo`, but the digest will not be compatible with the results of other
        implementations.

    """
    try:
        enabled, algo = _HASH_ALGO_REVERSE_MAP[h.name]
    except KeyError:
        pass
    else:
        if not enabled:
            raise ValueError("support of {} in XMPP is forbidden".format(
                algo
            ))
        return algo

    if h.name == "blake2b":
        return "blake2b-{}".format(h.digest_size * 8)

    raise ValueError(
        "unknown hash implementation: {!r}".format(h)
    )


class Hash(xso.XSO):
    """
    Represent a single hash digest.

    .. attribute:: algo

        The hash algorithm used. The name is as specified in :xep:`300`.

    .. attribute:: digest

        The digest as :class:`bytes`.

    """

    TAG = namespaces.xep0300_hashes2, "hash"

    algo = xso.Attr(
        "algo",
    )

    digest = xso.Text(
        type_=xso.Base64Binary()
    )

    def __init__(self, algo, digest):
        super().__init__()
        self.algo = algo
        self.digest = digest

    def get_impl(self):
        """
        Return a new :mod:`hashlib` hash for the :attr:`algo` set on this
        object.

        See :func:`hash_from_algo` for details and exceptions.
        """
        return hash_from_algo(self.algo)


class HashUsed(xso.XSO):
    """
    Represent a single hash-used algorithm spec.

    .. attribute:: algo

        The hash algorithm used. The name is as specified in :xep:`300`.

    """
    TAG = namespaces.xep0300_hashes2, "hash-used"

    algo = xso.Attr(
        "algo",
    )

    def __init__(self, algo):
        super().__init__()
        self.algo = algo

    def get_impl(self):
        """
        Return a new :mod:`hashlib` hash for the :attr:`algo` set on this
        object.

        See :func:`hash_from_algo` for details and exceptions.
        """
        return hash_from_algo(self.algo)


class HashType(xso.AbstractElementType):
    @classmethod
    def get_xso_types(cls):
        return [Hash]

    def unpack(self, obj):
        return obj.algo, obj.digest

    def pack(self, pair):
        return Hash(*pair)


class HashesParent(xso.XSO):
    """
    Mix-in class for XSOs which use :class:`Hash` children.

    .. attribute:: digests

        A mapping which maps from the :attr:`Hash.algo` to the
        :attr:`Hash.digest`.
    """

    digests = xso.ChildValueMap(
        type_=HashType(),
    )


class HashUsedType(xso.AbstractElementType):
    @classmethod
    def get_xso_types(cls):
        return [HashUsed]

    def unpack(self, obj):
        return obj.algo

    def pack(self, item):
        return HashUsed(item)


class HashesUsedParent(xso.XSO):
    """
    Mix-in class for XSOs which use :class:`HashUsed` children.

    .. attribute:: algos

        A list of hash algorithms.
    """

    algos = xso.ChildValueList(
        type_=HashUsedType(),
    )


default_hash_algorithms = {
    algo
    for algo in ["sha-256", "sha3-256", "blake2b-256"]
    if is_algo_supported(algo)
}


class HashService(service.Service):
    """
    The service component of the :xep:`300` support. This service registers
    the features and allows to query the hash functions supported by us and
    a remote entity:

    .. automethod:: select_common_hashes
    """
    ORDER_AFTER = [
        disco.DiscoClient,
        disco.DiscoServer,
    ]

    hashes_feature = disco.register_feature(namespaces.xep0300_hashes2)

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._disco_client = self.dependencies[disco.DiscoClient]
        self._disco_server = self.dependencies[disco.DiscoServer]

        for feature in SUPPORTED_HASH_FEATURES:
            self._disco_server.register_feature(feature)

    async def _shutdown(self):
        for feature in SUPPORTED_HASH_FEATURES:
            self._disco_server.unregister_feature(feature)
        await super()._shutdown()

    async def select_common_hashes(self, other_entity):
        """
        Return the list of algos supported by us and `other_entity`. The
        algorithms are represented by their :xep:`300` URNs
        (`urn:xmpp:hash-function-text-names:...`).

        :param other_entity: the address of another entity
        :type other_entity: :class:`aioxmpp.JID`
        :returns: the identifiers of the hash algorithms supported by
           both us and the other entity
        :rtype: :class:`set`
        :raises RuntimeError: if the other entity does not support the
           :xep:`300` feature nor does not publish hash functions
           URNs we support.

        Note: This assumes the protocol is supported if valid hash
        function features are detected, even if `urn:xmpp:hashes:2` is
        not listed as a feature.
        """
        disco_info = await self._disco_client.query_info(other_entity)
        intersection = disco_info.features & SUPPORTED_HASH_FEATURES
        if (not intersection and
                namespaces.xep0300_hashes2 not in disco_info.features):
            raise RuntimeError(
                "Remote does not support the urn:xmpp:hashes:2 feature.")
        return intersection
