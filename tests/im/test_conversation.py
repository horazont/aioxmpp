########################################################################
# File name: test_conversation.py
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
import asyncio
import unittest
import unittest.mock

import aioxmpp.im.conversation as conv

from aioxmpp.testutils import (
    run_coroutine,
)


class DummyConversation(conv.AbstractConversation):
    def __init__(self, mock, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__mock = mock

    @property
    def members(self):
        pass

    @property
    def me(self):
        pass

    @asyncio.coroutine
    def send_message_tracked(self, *args, **kwargs):
        return self.__mock.send_message_tracked(*args, **kwargs)

    @asyncio.coroutine
    def leave(self):
        yield from super().leave()


class TestConversation(unittest.TestCase):
    def setUp(self):
        self.cc = unittest.mock.sentinel.client
        self.parent = unittest.mock.sentinel.parent
        self.svc = unittest.mock.Mock(["client", "_conversation_left"])
        self.svc.client = self.cc
        self.c_mock = unittest.mock.Mock()
        self.c = DummyConversation(self.c_mock, self.svc, parent=self.parent)

    def tearDown(self):
        del self.c
        del self.parent
        del self.cc

    def test__client(self):
        self.assertEqual(
            self.c._client,
            self.cc,
        )

    def test__service(self):
        self.assertEqual(
            self.c._service,
            self.svc,
        )

    def test_parent(self):
        self.assertEqual(
            self.c.parent,
            self.parent,
        )

    def test_parent_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.c.parent = self.c.parent

    def test_leave_calls_conversation_left_on_service(self):
        run_coroutine(self.c.leave())
        self.svc._conversation_left.assert_called_once_with(self.c)

    def test_send_message_calls_send_message_tracked_and_cancels_tracking(self):
        run_coroutine(self.c.send_message(unittest.mock.sentinel.body))
        self.c_mock.send_message_tracked.assert_called_once_with(
            unittest.mock.sentinel.body,
        )
        self.c_mock.send_message_tracked().cancel.assert_called_once_with()
