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
import aioxmpp.ibb.xso as ibb_xso

from aioxmpp.utils import namespaces


class TestNamespace(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0047,
            "http://jabber.org/protocol/ibb"
        )


class TestOpen(unittest.TestCase):

    def test_tag(self):
        self.assertEqual(
            ibb_xso.Open.TAG,
            (namespaces.xep0047, "open")
        )


class TestClose(unittest.TestCase):

    def test_tag(self):
        self.assertEqual(
            ibb_xso.Close.TAG,
            (namespaces.xep0047, "close")
        )


class TestData(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            ibb_xso.Data.TAG,
            (namespaces.xep0047, "data")
        )

    def test_init(self):
        data = ibb_xso.Data("sessionid", 10, b"adsf\x02")
        self.assertEqual(data.sid, "sessionid")
        self.assertEqual(data.seq, 10)
        self.assertEqual(data.content, b"adsf\x02")


class TestMonkeyPatch(unittest.TestCase):

    def test_Message_attribute(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0047_data,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.Message.xep0047_data._classes,
            {
                ibb_xso.Data,
            }
        )
