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
import asyncio
import collections
import json
import logging

import aioxmpp
import aioxmpp.security_layer

from .utils import blocking


_logger = logging.getLogger(__name__)


FeatureInfo = collections.namedtuple(
    "FeatureInfo",
    [
        "supported_at_entity",
    ]
)


class Provisioner(metaclass=abc.ABCMeta):
    def __init__(self, logger=_logger):
        super().__init__()
        self._accounts_to_dispose = []
        self._featuremap = {}
        self._logger = logger

    @abc.abstractmethod
    @asyncio.coroutine
    def _make_client(self):
        """
        :return: Presence managed client
        """

    @asyncio.coroutine
    def get_connected_client(self, presence=aioxmpp.PresenceState(True)):
        """
        :param presence: initial presence to emit
        :type presence: :class:`aioxmpp.PresenceState`
        :raise OSError: if the connection failed
        :raise RuntimeError: if a client could not be provisioned due to
                             resource constraints
        :return: Connected presence managed client
        :rtype: :class:`aioxmpp.PresenceManagedClient`
        """
        client = yield from self._make_client()
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

    @abc.abstractmethod
    def configure(self, section):
        """
        :param section: mapping of config keys to values
        """

    def _configure_security_layer(self, section):
        if "pin_store" in section:
            with open(section.get("pin_store")) as f:
                pin_store = json.load(f)
            pin_type = aioxmpp.security_layer.PinType(
                section.getint("pin_type", fallback=0)
            )
        else:
            pin_store = None
            pin_type = None

        no_verify = section.getboolean(
            "no_verify",
            fallback=False
        )

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
        self._host = aioxmpp.JID.fromstr(section["host"])
        self._security_layer = self._configure_security_layer(
            section
        )

    @asyncio.coroutine
    def _make_client(self):
        return aioxmpp.PresenceManagedClient(
            self._host,
            self._security_layer,
        )
