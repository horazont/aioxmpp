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
import aioxmpp.carbons.xso as carbons_xso
import aioxmpp.muc
import aioxmpp.im.dispatcher as dispatcher
import aioxmpp.service
import aioxmpp.stream

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_LOCAL = aioxmpp.JID.fromstr("foo@service.example")
TEST_PEER = aioxmpp.JID.fromstr("bar@service.example")


class TestIMDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_LOCAL.replace(resource="we")
        self.disco_client = aioxmpp.DiscoClient(self.cc)
        self.carbons = aioxmpp.CarbonsClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client,
        })
        self.s = dispatcher.IMDispatcher(self.cc, dependencies={
            aioxmpp.CarbonsClient: self.carbons,
        })
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

    def test_depends_on_carbons(self):
        self.assertIn(
            aioxmpp.CarbonsClient,
            dispatcher.IMDispatcher.ORDER_AFTER,
        )

    def test_dispatcher_connects_to_before_stream_established(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.Client,
                "before_stream_established",
                dispatcher.IMDispatcher.enable_carbons,
            )
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

    def test_dispatch_unpacks_received_carbon(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_PEER,
            to=TEST_LOCAL,
        )

        wrapper = aioxmpp.Message(
            type_=msg.type_,
            from_=TEST_LOCAL.bare(),
            to=TEST_LOCAL,
        )
        wrapper.xep0280_received = carbons_xso.Received()
        wrapper.xep0280_received.stanza = msg

        self.s.dispatch_message(wrapper)

        self.listener.message_filter.assert_called_once_with(
            msg,
            TEST_PEER,
            False,
            dispatcher.MessageSource.CARBONS,
        )

    def test_dispatch_drops_received_carbon_with_incorrect_from(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )

        wrapper = aioxmpp.Message(
            type_=msg.type_,
            from_=TEST_PEER,
            to=TEST_LOCAL,
        )
        wrapper.xep0280_received = carbons_xso.Received()
        wrapper.xep0280_received.stanza = msg

        self.s.dispatch_message(wrapper)

        self.listener.message_filter.assert_not_called()

    def test_dispatch_unpacks_sent_carbon(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL.replace(resource="other"),
            to=TEST_PEER,
        )

        wrapper = aioxmpp.Message(
            type_=msg.type_,
            from_=TEST_LOCAL.bare(),
            to=TEST_LOCAL,
        )
        wrapper.xep0280_sent = carbons_xso.Sent()
        wrapper.xep0280_sent.stanza = msg

        self.s.dispatch_message(wrapper)

        self.listener.message_filter.assert_called_once_with(
            msg,
            TEST_PEER,
            True,
            dispatcher.MessageSource.CARBONS,
        )

    def test_dispatch_drops_sent_carbon_with_incorrect_from(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )

        wrapper = aioxmpp.Message(
            type_=msg.type_,
            from_=TEST_PEER,
            to=TEST_LOCAL,
        )
        wrapper.xep0280_sent = carbons_xso.Sent()
        wrapper.xep0280_sent.stanza = msg

        self.s.dispatch_message(wrapper)

        self.listener.message_filter.assert_not_called()

    def test_enable_carbons_enables_carbons(self):
        with unittest.mock.patch.object(
                self.carbons,
                "enable",
                new=CoroutineMock()) as enable:
            result = run_coroutine(self.s.enable_carbons())

        enable.assert_called_once_with()
        self.assertTrue(result)

    def test_enable_carbons_does_not_swallow_random_exception(self):
        class FooException(Exception):
            pass

        with unittest.mock.patch.object(
                self.carbons,
                "enable",
                new=CoroutineMock()) as enable:
            enable.side_effect = FooException()
            with self.assertRaises(FooException):
                run_coroutine(self.s.enable_carbons())

        enable.assert_called_once_with()

    def test_enable_carbons_ignores_RuntimeError_from_enable(self):
        with unittest.mock.patch.object(
                self.carbons,
                "enable",
                new=CoroutineMock()) as enable:
            enable.side_effect = RuntimeError()
            run_coroutine(self.s.enable_carbons())

        enable.assert_called_once_with()

    def test_enable_carbons_ignores_XMPPError_from_enable(self):
        with unittest.mock.patch.object(
                self.carbons,
                "enable",
                new=CoroutineMock()) as enable:
            enable.side_effect = aioxmpp.errors.XMPPError(
                (namespaces.stanzas, "foo")
            )
            run_coroutine(self.s.enable_carbons())

        enable.assert_called_once_with()
