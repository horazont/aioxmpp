########################################################################
# File name: test_utils.py
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

from aioxmpp.chatstates import (ChatState, ChatStateManager,  # NOQA
                                DoNotEmit, AlwaysEmit, DiscoverSupport)


class TestStrategies(unittest.TestCase):

    def test_DoNotEmit(self):
        strategy = DoNotEmit()
        self.assertFalse(strategy.sending)
        strategy.reset()
        self.assertFalse(strategy.sending)
        strategy.no_reply()
        self.assertFalse(strategy.sending)

    def test_DiscoverSupport(self):
        strategy = DiscoverSupport()
        self.assertTrue(strategy.sending)
        strategy.no_reply()
        self.assertFalse(strategy.sending)
        strategy.reset()
        self.assertTrue(strategy.sending)

    def test_AlwaysEmit(self):
        strategy = AlwaysEmit()
        self.assertTrue(strategy.sending)
        strategy.reset()
        self.assertTrue(strategy.sending)
        strategy.no_reply()
        self.assertTrue(strategy.sending)


class TestChatStateManager(unittest.TestCase):

    def  test_sending(self):
        manager = ChatStateManager(unittest.mock.sentinel)
        self.assertIs(manager.sending, unittest.mock.sentinel.sending)

    def test_no_reply(self):
        manager = ChatStateManager(unittest.mock.Mock())
        manager.no_reply()
        manager._strategy.no_reply.assert_called_once_with()

    def test_reset(self):
        manager = ChatStateManager(unittest.mock.Mock())
        manager.reset()
        manager._strategy.reset.assert_called_once_with()

    def test_handle(self):
        manager = ChatStateManager(unittest.mock.sentinel)

        self.assertIs(manager.handle(ChatState.ACTIVE), False)
        self.assertIs(manager.handle(ChatState.INACTIVE),
                      unittest.mock.sentinel.sending)
        self.assertIs(manager.handle(ChatState.INACTIVE), False)
