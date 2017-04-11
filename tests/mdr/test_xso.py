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
import aioxmpp.mdr.xso as mdr_xso

from aioxmpp.utils import namespaces


class TestNamespace(unittest.TestCase):
    def test_receipts(self):
        self.assertEqual(
            namespaces.xep0184_receipts,
            "urn:xmpp:receipts",
        )


class TestReceived(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            mdr_xso.Received,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            mdr_xso.Received.TAG,
            (namespaces.xep0184_receipts, "received"),
        )

    def test_message_id(self):
        self.assertIsInstance(
            mdr_xso.Received.message_id,
            xso.Attr,
        )
        self.assertEqual(
            mdr_xso.Received.message_id.tag,
            (None, "id"),
        )

    def test_init_default(self):
        with self.assertRaisesRegex(TypeError, "message_id"):
            mdr_xso.Received()

    def test_init(self):
        r = mdr_xso.Received("foobar")
        self.assertEqual(r.message_id, "foobar")


class TestMessage(unittest.TestCase):
    def test_xep0184_request_receipt(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0184_request_receipt,
            xso.ChildFlag,
        )
        self.assertEqual(
            aioxmpp.Message.xep0184_request_receipt.tag,
            (namespaces.xep0184_receipts, "request"),
        )

    def test_xep0184_received(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0184_received,
            xso.Child,
        )
        self.assertLessEqual(
            aioxmpp.Message.xep0184_received._classes,
            {
                mdr_xso.Received,
            }
        )

    def test_is_in_child_map(self):
        self.assertIn(
            mdr_xso.Received.TAG,
            aioxmpp.Message.CHILD_MAP,
        )
