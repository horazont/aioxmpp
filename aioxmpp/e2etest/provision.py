########################################################################
# File name: provision.py
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
import abc
import ast
import asyncio
import collections
import enum
import itertools
import json
import logging

import aioxmpp
import aioxmpp.disco
import aioxmpp.security_layer


_logger = logging.getLogger(__name__)


FeatureInfo = collections.namedtuple(
    "FeatureInfo",
    [
        "supported_at_entity",
    ]
)


class Quirk(enum.Enum):
    MUC_REWRITES_MESSAGE_ID = \
        "https://zombofant.net/xmlns/aioxmpp/e2etest/quirks#muc-id-rewrite"


def fix_quirk_str(s):
    if s.startswith("#"):
        return "https://zombofant.net/xmlns/aioxmpp/e2etest/quirks" + s
    return s


class Provisioner(metaclass=abc.ABCMeta):
    def __init__(self, logger=_logger):
        super().__init__()
        self._accounts_to_dispose = []
        self._featuremap = {}
        self._logger = logger
        self.__counter = 0

    @abc.abstractmethod
    @asyncio.coroutine
    def _make_client(self, logger):
        """
        :param logger: The logger to pass to the client.
        :return: Presence managed client
        """

    @asyncio.coroutine
    def get_connected_client(self, presence=aioxmpp.PresenceState(True),
                             *,
                             services=[]):
        """
        :param presence: initial presence to emit
        :type presence: :class:`aioxmpp.PresenceState`
        :raise OSError: if the connection failed
        :raise RuntimeError: if a client could not be provisioned due to
                             resource constraints
        :return: Connected presence managed client
        :rtype: :class:`aioxmpp.PresenceManagedClient`
        """
        id_ = self.__counter
        self.__counter += 1
        self._logger.debug("obtaining client%d from %r", id_, self)
        logger = self._logger.getChild("client{}".format(id_))
        client = yield from self._make_client(logger)
        for service in services:
            client.summon(service)
        cm = client.connected(presence=presence)
        yield from cm.__aenter__()
        self._accounts_to_dispose.append(cm)
        return client

    def get_feature_info(self, feature_ns):
        """
        :param feature_ns: Namespace URI of the feature (as used in :xep:`30`)
        :return: Feature information or :data:`None`
        :rtype: :class:`FeatureInfo`

        If the feature is not supported, :data:`None` is returned.
        """
        return self._featuremap.get(feature_ns, None)

    def has_quirk(self, quirk):
        return quirk in self._quirks

    @abc.abstractmethod
    def configure(self, section):
        """
        :param section: mapping of config keys to values
        """

    def _configure_security_layer(self, section):
        no_verify = section.getboolean(
            "no_verify",
            fallback=False
        )

        if not no_verify and "pin_store" in section:
            with open(section.get("pin_store")) as f:
                pin_store = json.load(f)
            pin_type = aioxmpp.security_layer.PinType(
                section.getint("pin_type", fallback=0)
            )
        else:
            pin_store = None
            pin_type = None

        self._logger.debug(
            "configured security layer with "
            "pin_store=%r, "
            "pin_type=%r, "
            "no_verify=%r",
            pin_store,
            pin_type,
            no_verify,
        )

        return aioxmpp.make_security_layer(
            None,
            pin_store=pin_store,
            pin_type=pin_type,
            anonymous="",
            no_verify=no_verify,
        )

    def _configure_quirks(self, section):
        quirks = ast.literal_eval(section.get("quirks", fallback="[]"))
        if isinstance(quirks, (str, dict)):
            raise ValueError("incorrect type for quirks setting")
        self._quirks = set(map(Quirk, map(fix_quirk_str, quirks)))

    @asyncio.coroutine
    def _discover_server_features(self, disco, peer, recurse_into_items=True):
        server_info = yield from disco.query_info(peer)

        all_features = {}
        all_features.update({
            feature: FeatureInfo(peer)
            for feature in server_info.features
        })

        if recurse_into_items:
            server_items = yield from disco.query_items(peer)
            features_list = yield from asyncio.gather(
                *(
                    self._discover_server_features(
                        disco,
                        item.jid,
                        recurse_into_items=False,
                    )
                    for item in server_items.items
                    if item.jid is not None and item.node is None
                )
            )

            for features in features_list:
                all_features.update([
                    (feature, info)
                    for feature, info in features.items()
                    if feature not in all_features
                ])

        return all_features

    @asyncio.coroutine
    def initialise(self):
        """
        Called once on test framework startup.
        """

    @asyncio.coroutine
    def finalise(self):
        """
        Called once on test framework shutdown (timeout of 10 seconds applies).
        """

    @asyncio.coroutine
    def setup(self):
        """
        Called before each test run.
        """

    @asyncio.coroutine
    def teardown(self):
        """
        Called after each test run.
        """

        futures = []
        for cm in self._accounts_to_dispose:
            futures.append(asyncio.async(cm.__aexit__(None, None, None)))
        self._accounts_to_dispose.clear()

        self._logger.debug("waiting for %d accounts to shut down",
                           len(futures))
        yield from asyncio.gather(
            *futures,
            return_exceptions=True
        )


class AnonymousProvisioner(Provisioner):
    def configure(self, section):
        self.__host = aioxmpp.JID.fromstr(section["host"])
        self.__security_layer = self._configure_security_layer(
            section
        )
        self._configure_quirks(section)

    @asyncio.coroutine
    def _make_client(self, logger):
        return aioxmpp.PresenceManagedClient(
            self.__host,
            self.__security_layer,
            logger=logger,
        )

    @asyncio.coroutine
    def initialise(self):
        self._logger.debug("initialising anonymous provisioner")

        client = yield from self.get_connected_client()
        disco = client.summon(aioxmpp.disco.Service)

        self._featuremap.update(
            (yield from self._discover_server_features(
                disco,
                self.__host
            ))
        )

        self._logger.debug("found %d features", len(self._featuremap))
        if self._logger.isEnabledFor(logging.DEBUG):
            for jid, items in itertools.groupby(
                    sorted(
                        self._featuremap.items(),
                        key=lambda x: (x[1].supported_at_entity, x[0])),
                    lambda x: x[1].supported_at_entity):
                self._logger.debug(
                    "%s provides %s",
                    jid,
                    ", ".join(item[0] for item in items)
                )

        # clean up state
        del client
        yield from self.teardown()
