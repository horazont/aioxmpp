########################################################################
# File name: test_e2e.py
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
import logging
import unittest
import uuid

import aioxmpp
import aioxmpp.pubsub
import aioxmpp.xso

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    TestCase,
    blocking,
    blocking_timed,
    require_feature_subset,
    require_pep,
)


@aioxmpp.pubsub.xso.as_payload_class
class Payload(aioxmpp.xso.XSO):
    TAG = (namespaces.aioxmpp_test, "foo")

    data = aioxmpp.xso.Text(default=None)


class TestOwnerUseCases(TestCase):
    @require_feature_subset(
        {
            namespaces.xep0060_features.PURGE_NODES.value,
            namespaces.xep0060_features.MODIFY_AFFILIATIONS.value,
            namespaces.xep0060_features.PUBLISH.value,
            namespaces.xep0060_features.PUBLISHER_AFFILIATION.value,
        },
        required_subset={
            namespaces.xep0060_features.CREATE_NODES.value,
            namespaces.xep0060_features.DELETE_NODES.value,
        }
    )
    @blocking
    def setUp(self, pubsub_jid, supported_features):
        logging.info("using pubsub service %s, which provides %r",
                     pubsub_jid, supported_features)

        self.peer = pubsub_jid
        self.peer_features = supported_features

        self.owner = yield from self.provisioner.get_connected_client()
        self.pubsub = self.owner.summon(aioxmpp.PubSubClient)

        self.other = yield from self.provisioner.get_connected_client()

        self.node = str(uuid.uuid4())

        yield from self.pubsub.create(self.peer, self.node)

    @blocking
    def tearDown(self):
        yield from self.pubsub.delete(self.peer, self.node)

    def _require_features(self, features):
        features = set(features)
        if features & self.peer_features != features:
            raise unittest.SkipTest(
                "selected PubSub provider ({!r}) does not provide {!r}".format(
                    self.peer,
                    features,
                )
            )

    @blocking_timed
    def test_publish_and_purge(self):
        self._require_features({
            namespaces.xep0060_features.PURGE_NODES.value
        })

        payload = Payload()

        id_ = yield from self.pubsub.publish(
            self.peer,
            self.node,
            payload,
        )
        items = yield from self.pubsub.get_items(
            self.peer,
            self.node,
        )

        self.assertEqual(len(items.payload.items), 1)
        yield from self.pubsub.purge(self.peer, self.node)

        # using get items instead of get_items_by_id to work around ejabberd
        # #2288
        items = yield from self.pubsub.get_items(
            self.peer,
            self.node,
        )
        self.assertEqual(len(items.payload.items), 0)

    @blocking_timed
    def test_publish_multiple_and_get_by_id(self):
        # configure the node for multiple items
        config = yield from self.pubsub.get_node_config(
            self.peer,
            self.node,
        )
        form = aioxmpp.pubsub.xso.NodeConfigForm.from_xso(config)
        try:
            max_items = int(form.max_items.value)
        except ValueError:
            max_items = 0

        if max_items < 2:
            form.max_items.value = "10"
            yield from self.pubsub.set_node_config(
                self.peer,
                form.render_reply(),
                self.node,
            )

        payload1 = Payload()
        payload1.data = "foo"

        payload2 = Payload()
        payload2.data = "bar"

        id1 = yield from self.pubsub.publish(
            self.peer,
            self.node,
            payload1,
        )
        id2 = yield from self.pubsub.publish(
            self.peer,
            self.node,
            payload2,
        )
        items = yield from self.pubsub.get_items_by_id(
            self.peer,
            self.node,
            [id1, id2]
        )
        yield from self.pubsub.get_items(
            self.peer,
            self.node,
        )

        self.assertEqual(len(items.payload.items), 2)

        data_map = {
            item.id_: item.registered_payload.data
            for item in items.payload.items
        }

        self.assertDictEqual(
            {
                id1: "foo",
                id2: "bar",
            },
            data_map,
        )
