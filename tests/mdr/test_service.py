########################################################################
# File name: test_service.py
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
import unittest
import unittest.mock

import aioxmpp.disco
import aioxmpp.mdr.service as mdr_service
import aioxmpp.mdr.xso as mdr_xso
import aioxmpp.service
import aioxmpp.tracking

from aioxmpp.testutils import (
    make_connected_client,
)


TEST_TO = aioxmpp.JID.fromstr("romeo@montague.example")


class TestDeliveryReceiptsService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.disco_svr = aioxmpp.DiscoServer(self.cc)
        self.t = aioxmpp.tracking.MessageTracker()
        self.s = mdr_service.DeliveryReceiptsService(self.cc, dependencies={
            aioxmpp.DiscoServer: self.disco_svr,
        })
        self.msg = unittest.mock.Mock(spec=aioxmpp.Message)
        self.msg.xep0184_request_receipt = False
        self.msg.to = TEST_TO
        self.msg.id_ = "foo"

    def tearDown(self):
        del self.s
        del self.cc

    def test_is_service(self):
        self.assertIsInstance(
            self.s,
            aioxmpp.service.Service,
        )

    def test_registers_inbound_message_filter(self):
        self.assertTrue(
            aioxmpp.service.is_inbound_message_filter(
                mdr_service.DeliveryReceiptsService._inbound_message_filter,
            )
        )

    def test_inbound_message_filter_returns_random_stanza(self):
        stanza = unittest.mock.Mock(spec=aioxmpp.Message)
        stanza.xep0184_received = None
        self.assertIs(
            self.s._inbound_message_filter(stanza),
            stanza,
        )

    def test_declares_disco_feature(self):
        self.assertIsInstance(
            mdr_service.DeliveryReceiptsService.disco_feature,
            aioxmpp.disco.register_feature,
        )
        self.assertEqual(
            mdr_service.DeliveryReceiptsService.disco_feature.feature,
            "urn:xmpp:receipts",
        )

    def test_attach_tracker_sets_xep0184_request(self):
        self.s.attach_tracker(self.msg, self.t)
        self.assertTrue(
            self.msg.xep0184_request_receipt,
        )

    def test_attach_tracker_autosets_id(self):
        self.s.attach_tracker(self.msg, self.t)
        self.msg.autoset_id.assert_called_once_with()

    def test_attach_tracker_returns_passed_tracker(self):
        t = self.s.attach_tracker(self.msg, self.t)
        self.assertIs(t, self.t)

    def test_set_tracker_state_to_DTR_on_ack_for_full_match(self):
        self.msg.to = self.msg.to.replace(resource="foo")
        self.s.attach_tracker(self.msg, self.t)

        ack = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_TO.replace(resource="foo")
        )
        ack.xep0184_received = mdr_xso.Received(self.msg.id_)

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )
        self.assertIsNone(
            self.s._inbound_message_filter(ack)
        )

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

    def test_do_not_modify_tracker_state_on_id_mismatch(self):
        self.msg.to = self.msg.to.replace(resource="foo")
        self.s.attach_tracker(self.msg, self.t)

        ack = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_TO.replace(resource="foo")
        )
        ack.xep0184_received = mdr_xso.Received("fnord")

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )
        self.assertIsNone(
            self.s._inbound_message_filter(ack)
        )

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )

    def test_do_not_modify_tracker_state_on_bare_jid_mismatch(self):
        self.msg.to = self.msg.to.replace(resource="foo")
        self.s.attach_tracker(self.msg, self.t)

        ack = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=self.msg.to.replace(localpart="nottheromeo")
        )
        ack.xep0184_received = mdr_xso.Received(self.msg.id_)

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )
        self.assertIsNone(
            self.s._inbound_message_filter(ack)
        )

        self.assertEqual(
            self.t.state,
            aioxmpp.tracking.MessageState.IN_TRANSIT,
        )
