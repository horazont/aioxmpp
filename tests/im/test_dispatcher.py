########################################################################
# File name: test_dispatcher.py
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

import aioxmpp.callbacks
import aioxmpp.muc
import aioxmpp.im.dispatcher as dispatcher
import aioxmpp.service
import aioxmpp.stream

from aioxmpp.testutils import (
    make_connected_client,
)


TEST_LOCAL = aioxmpp.JID.fromstr("foo@service.example")
TEST_PEER = aioxmpp.JID.fromstr("bar@service.example")


class TestIMDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = dispatcher.IMDispatcher(self.cc)
        self.listener = unittest.mock.Mock()

        for filter_ in ["message_filter", "presence_filter"]:
            cb = getattr(self.listener, filter_)
            cb.side_effect = lambda x, *args, **kwargs: x
            filter_chain = getattr(self.s, filter_)
            filter_chain.register(cb, 0)

    def tearDown(self):
        del self.s
        del self.cc

    def test_message_filter_is_filter(self):
        self.assertIsInstance(
            self.s.message_filter,
            aioxmpp.callbacks.Filter,
        )

    def test_presence_filter_is_filter(self):
        self.assertIsInstance(
            self.s.presence_filter,
            aioxmpp.callbacks.Filter,
        )

    def test_orders_after_simple_presence_dispatcher(self):
        self.assertIn(
            aioxmpp.dispatcher.SimplePresenceDispatcher,
            dispatcher.IMDispatcher.ORDER_AFTER,
        )

    def test_dispatch_message_listens_to_on_message_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_message_received",
                dispatcher.IMDispatcher.dispatch_message,
            )
        )

    def test_dispatch_presence_listens_to_on_presence_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_presence_received",
                dispatcher.IMDispatcher.dispatch_presence,
            )
        )

    def test_dispatch_presences(self):
        types = [
            (aioxmpp.PresenceType.AVAILABLE, True),
            (aioxmpp.PresenceType.UNAVAILABLE, True),
            (aioxmpp.PresenceType.ERROR, True),
            (aioxmpp.PresenceType.SUBSCRIBE, False),
            (aioxmpp.PresenceType.UNSUBSCRIBE, False),
            (aioxmpp.PresenceType.SUBSCRIBED, False),
            (aioxmpp.PresenceType.UNSUBSCRIBED, False),
        ]

        for type_, dispatch in types:
            pres = aioxmpp.Presence(
                type_=type_,
                from_=TEST_PEER,
                to=TEST_LOCAL,
            )

        self.s.dispatch_presence(pres)

        self.listener.presence_filter.assert_called_once_with(
            pres,
            TEST_PEER,
            False,
        )


    def test_dispatch_simple_messages(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_PEER,
            to=TEST_LOCAL,
        )

        self.s.dispatch_message(msg)

        self.listener.message_filter.assert_called_once_with(
            msg,
            TEST_PEER,
            False,
            dispatcher.MessageSource.STREAM,
        )

    def test_dispatch_sent_messages(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )

        self.s.dispatch_message(msg, sent=True)

        self.listener.message_filter.assert_called_once_with(
            msg,
            TEST_PEER,
            True,
            dispatcher.MessageSource.STREAM,
        )
