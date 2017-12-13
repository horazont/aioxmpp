########################################################################
# File name: test_xso.py
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
import enum
import unittest

import aioxmpp.xso as xso

from aioxmpp.chatstates import ChatState
from aioxmpp.stanza import Message
from aioxmpp.utils import namespaces


class TestNamespace(unittest.TestCase):

    def test_namespace(self):
        self.assertEqual(namespaces.xep0085,
                         "http://jabber.org/protocol/chatstates")


class TestChatState(unittest.TestCase):

    def test_is_enum(self):
        self.assertTrue(issubclass(ChatState, enum.Enum))

    def test_values(self):
        self.assertEqual(
            ChatState.ACTIVE.value, (namespaces.xep0085, "active"),
        )
        self.assertEqual(
            ChatState.COMPOSING.value, (namespaces.xep0085, "composing"),
        )
        self.assertEqual(
            ChatState.PAUSED.value, (namespaces.xep0085, "paused"),
        )
        self.assertEqual(
            ChatState.INACTIVE.value, (namespaces.xep0085, "inactive"),
        )
        self.assertEqual(
            ChatState.GONE.value, (namespaces.xep0085, "gone"),
        )


class TestMessage(unittest.TestCase):

    def test_xep0085_chatstate(self):
        self.assertIsInstance(
            Message.xep0085_chatstate,
            xso.ChildTag
        )
