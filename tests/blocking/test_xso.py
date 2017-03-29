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

import unittest

import aioxmpp
import aioxmpp.xso as xso
import aioxmpp.blocking.xso as blocking_xso

from aioxmpp.utils import namespaces

TEST_JID1 = aioxmpp.JID.fromstr("foo@exmaple.com")
TEST_JID2 = aioxmpp.JID.fromstr("spam.example.com")

class TestNamespace(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0191,
            "urn:xmpp:blocking"
        )


class TestBlockList(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(blocking_xso.BlockList, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            blocking_xso.BlockList.TAG,
            (namespaces.xep0191, "blocklist"),
        )


class TestBlockCommand(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(blocking_xso.BlockCommand, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            blocking_xso.BlockCommand.TAG,
            (namespaces.xep0191, "block"),
        )

    def test_init(self):
        block_command = blocking_xso.BlockCommand([TEST_JID1, TEST_JID2])
        self.assertCountEqual(
            block_command.items,
            [TEST_JID1, TEST_JID2]
        )

        block_command = blocking_xso.BlockCommand()
        self.assertCountEqual(
            block_command.items,
            []
        )

class TestUnblockCommand(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(blocking_xso.UnblockCommand, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            blocking_xso.UnblockCommand.TAG,
            (namespaces.xep0191, "unblock"),
        )

    def test_init(self):
        unblock_command = blocking_xso.UnblockCommand([TEST_JID1, TEST_JID2])
        self.assertCountEqual(
            unblock_command.items,
            [TEST_JID1, TEST_JID2]
        )

        unblock_command = blocking_xso.UnblockCommand()
        self.assertCountEqual(
            unblock_command.items,
            []
        )
