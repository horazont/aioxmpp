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

import aioxmpp.xso

import aioxmpp.ping.xso as ping_xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0199_ping,
            "urn:xmpp:ping"
        )


class TestPing(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            ping_xso.Ping,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            ping_xso.Ping.TAG,
            (namespaces.xep0199_ping, "ping")
        )

    def test_is_iq_payload(self):
        self.assertIn(
            ping_xso.Ping.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )
