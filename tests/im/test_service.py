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

import aioxmpp.im.service as im_service

from aioxmpp.testutils import (
    make_connected_client,
)


class TestConversationService(unittest.TestCase):
    def setUp(self):
        self.listener = unittest.mock.Mock()
        self.cc = make_connected_client()
        self.s = im_service.ConversationService(self.cc)

        for ev in ["on_conversation_added"]:
            handler = getattr(self.listener, ev)
            handler.return_value = None
            getattr(self.s, ev).connect(handler)

    def tearDown(self):
        del self.s
        del self.cc

    def test_init(self):
        self.assertSequenceEqual(
            list(self.s.conversations),
            [],
        )

    def test__add_conversation(self):
        conv = unittest.mock.Mock()
        self.s._add_conversation(conv)
        self.listener.on_conversation_added.assert_called_once_with(conv)
        conv.on_exit.connect.assert_called_once_with(
            unittest.mock.ANY
        )

        self.assertCountEqual(
            self.s.conversations,
            [
                conv,
            ]
        )

        (_, (cb, ), _), = conv.on_exit.mock_calls

        # should ignore its arguments
        cb(unittest.mock.sentinel.foo, bar=unittest.mock.sentinel.fnord)

        self.assertCountEqual(
            self.s.conversations,
            [
            ]
        )
