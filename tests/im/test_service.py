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

import aioxmpp

import aioxmpp.im.service as im_service

from aioxmpp.testutils import (
    make_connected_client,
    make_listener,
)


class TestConversationService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = im_service.ConversationService(self.cc)
        self.listener = make_listener(self.s)

    def tearDown(self):
        del self.s
        del self.cc

    def test_init(self):
        self.assertSequenceEqual(
            list(self.s.conversations),
            [],
        )

    def test__add_conversation_emits_on_conversation_added(self):
        conv = unittest.mock.Mock()
        self.s._add_conversation(conv)
        self.listener.on_conversation_added.assert_called_once_with(
            conv,
        )

    def test__add_conversation_adds_conversation_to_conversations(self):
        conv = unittest.mock.Mock()
        self.s._add_conversation(conv)

        self.assertCountEqual(
            self.s.conversations,
            [
                conv,
            ]
        )

    def test__add_conversation_makes_it_accessible_by_jid(self):
        conv = unittest.mock.Mock()
        conv.jid = unittest.mock.sentinel.jid
        self.s._add_conversation(conv)

        self.assertIs(self.s.get_conversation(conv.jid), conv)

    def test_conversation_not_accessible_after_exit(self):
        conv = unittest.mock.Mock()
        conv.jid = unittest.mock.sentinel.jid
        self.s._add_conversation(conv)

        _, (cb, ), _ = conv.on_exit.mock_calls[-1]
        cb()

        with self.assertRaises(KeyError):
            self.s.get_conversation(conv.jid)

    def test_forwards_message_events(self):
        conv = unittest.mock.Mock(["on_failure", "on_exit", "jid",
                                   "on_message"])
        conv.jid = unittest.mock.sentinel.jid

        self.s._add_conversation(conv)

        conv.on_message.connect.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (cb, ), _ = conv.on_message.mock_calls[-1]

        cb(unittest.mock.sentinel.message,
           unittest.mock.sentinel.member,
           unittest.mock.sentinel.source,
           tracker=unittest.mock.sentinel.tracker,
           foo_bar=unittest.mock.sentinel.foobar)

        self.listener.on_message.assert_called_once_with(
            conv,
            unittest.mock.sentinel.message,
            unittest.mock.sentinel.member,
            unittest.mock.sentinel.source,
            tracker=unittest.mock.sentinel.tracker,
            foo_bar=unittest.mock.sentinel.foobar
        )

    def test_on_conversation_added_sees_added_conversation(self):
        captured_conversations = None

        def cb(conv):
            nonlocal captured_conversations
            captured_conversations = list(self.s.conversations)

        conv = unittest.mock.Mock()
        self.s.on_conversation_added.connect(cb)
        self.s._add_conversation(conv)

        self.assertIn(
            conv,
            captured_conversations,
        )

    def test_removes_added_conversation_on_exit(self):
        conv = unittest.mock.Mock()
        self.s._add_conversation(conv)

        conv.on_exit.connect.assert_called_once_with(
            unittest.mock.ANY
        )

        _, (cb, ), _ = conv.on_exit.mock_calls[-1]

        # should ignore its arguments
        cb(unittest.mock.sentinel.foo, bar=unittest.mock.sentinel.fnord)

        self.assertCountEqual(
            self.s.conversations,
            [
            ]
        )

    def test_disconnects_handlers_on_exit(self):
        conv = unittest.mock.Mock(["on_exit", "on_failure", "on_message",
                                   "jid"])
        self.s._add_conversation(conv)

        conv.on_exit.connect.assert_called_once_with(
            unittest.mock.ANY
        )

        _, (cb, ), _ = conv.on_exit.mock_calls[-1]

        cb()

        conv.on_exit.disconnect.assert_called_once_with(
            conv.on_exit.connect(),
        )

        conv.on_failure.disconnect.assert_called_once_with(
            conv.on_failure.connect(),
        )

        conv.on_message.disconnect.assert_called_once_with(
            conv.on_message.connect(),
        )

    def test_disconnects_handlers_on_failure(self):
        conv = unittest.mock.Mock(["on_exit", "on_failure", "on_message",
                                   "jid"])
        self.s._add_conversation(conv)

        conv.on_failure.connect.assert_called_once_with(
            unittest.mock.ANY
        )

        _, (cb, ), _ = conv.on_failure.mock_calls[-1]

        cb()

        conv.on_exit.disconnect.assert_called_once_with(
            conv.on_exit.connect(),
        )

        conv.on_failure.disconnect.assert_called_once_with(
            conv.on_failure.connect(),
        )

        conv.on_message.disconnect.assert_called_once_with(
            conv.on_message.connect(),
        )

    def test_removes_added_conversation_on_failure(self):
        conv = unittest.mock.Mock()
        self.s._add_conversation(conv)

        conv.on_failure.connect.assert_called_once_with(
            unittest.mock.ANY
        )

        _, (cb, ), _ = conv.on_failure.mock_calls[-1]

        # should ignore its arguments
        cb(unittest.mock.sentinel.foo, unittest.mock.sentinel.bar,
           bar=unittest.mock.sentinel.fnord)

        self.assertCountEqual(
            self.s.conversations,
            [
            ]
        )
