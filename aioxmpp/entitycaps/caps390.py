########################################################################
# File name: caps390.py
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
import base64
import pathlib
import collections
import urllib.parse

import aioxmpp.hashes

from .common import AbstractKey
from . import xso as caps_xso


def _process_features(features):
    """
    Generate the `Features String` from an iterable of features.

    :param features: The features to generate the features string from.
    :type features: :class:`~collections.abc.Iterable` of :class:`str`
    :return: The `Features String`
    :rtype: :class:`bytes`

    Generate the `Features String` from the given `features` as specified in
    :xep:`390`.
    """
    parts = [
        feature.encode("utf-8")+b"\x1f"
        for feature in features
    ]
    parts.sort()
    return b"".join(parts)+b"\x1c"


def _process_identity(identity):
    category = (identity.category or "").encode("utf-8")+b"\x1f"
    type_ = (identity.type_ or "").encode("utf-8")+b"\x1f"
    lang = str(identity.lang or "").encode("utf-8")+b"\x1f"
    name = (identity.name or "").encode("utf-8")+b"\x1f"

    return b"".join([category, type_, lang, name]) + b"\x1e"


def _process_identities(identities):
    """
    Generate the `Identities String` from an iterable of identities.

    :param identities: The identities to generate the features string from.
    :type identities: :class:`~collections.abc.Iterable` of
        :class:`~.disco.xso.Identity`
    :return: The `Identities String`
    :rtype: :class:`bytes`

    Generate the `Identities String` from the given `identities` as specified
    in :xep:`390`.
    """
    parts = [
        _process_identity(identity)
        for identity in identities
    ]
    parts.sort()
    return b"".join(parts)+b"\x1c"


def _process_field(field):
    parts = [
        (value or "").encode("utf-8") + b"\x1f"
        for value in field.values
    ]

    parts.insert(0, field.var.encode("utf-8")+b"\x1f")
    return b"".join(parts)+b"\x1e"


def _process_form(form):
    parts = [
        _process_field(form)
        for form in form.fields
    ]

    parts.sort()
    return b"".join(parts)+b"\x1d"


def _process_extensions(exts):
    """
    Generate the `Extensions String` from an iterable of data forms.

    :param exts: The data forms to generate the extensions string from.
    :type exts: :class:`~collections.abc.Iterable` of
        :class:`~.forms.xso.Data`
    :return: The `Extensions String`
    :rtype: :class:`bytes`

    Generate the `Extensions String` from the given `exts` as specified
    in :xep:`390`.
    """
    parts = [
        _process_form(form)
        for form in exts
    ]
    parts.sort()
    return b"".join(parts)+b"\x1c"


def _get_hash_input(info):
    return b"".join([
        _process_features(info.features),
        _process_identities(info.identities),
        _process_extensions(info.exts)
    ])


def _calculate_hash(algo, hash_input):
    impl = aioxmpp.hashes.hash_from_algo(algo)
    impl.update(hash_input)
    return impl.digest()


Key = collections.namedtuple("Key", ["algo", "digest"])


class Key(Key, AbstractKey):
    @property
    def node(self):
        return "urn:xmpp:caps#{}.{}".format(
            self.algo,
            base64.b64encode(self.digest).decode("ascii")
        )

    @property
    def path(self):
        encoded = base64.b32encode(
            self.digest
        ).decode("ascii").rstrip("=").lower()
        return (pathlib.Path("caps2") /
                urllib.parse.quote(self.algo, safe="") /
                encoded[:2] /
                encoded[2:4] /
                "{}.xml".format(encoded[4:]))

    def verify(self, info):
        if not isinstance(info, bytes):
            info = _get_hash_input(info)
        digest = _calculate_hash(self.algo, info)
        return digest == self.digest


class Implementation:
    def __init__(self, algorithms, **kwargs):
        super().__init__(**kwargs)
        self.__algorithms = algorithms

    def extract_keys(self, presence):
        if presence.xep0390_caps is None:
            return ()

        return (
            Key(algo, digest)
            for algo, digest in presence.xep0390_caps.digests.items()
            if aioxmpp.hashes.is_algo_supported(algo)
        )

    def put_keys(self, keys, presence):
        presence.xep0390_caps = caps_xso.Caps390()
        presence.xep0390_caps.digests.update({
            key.algo: key.digest
            for key in keys
        })

    def calculate_keys(self, query_response):
        input = _get_hash_input(query_response)
        for algo in self.__algorithms:
            yield Key(algo, _calculate_hash(algo, input))
