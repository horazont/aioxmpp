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
import aioxmpp.version.xso as version_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0092_version,
            "jabber:iq:version",
        )


class TestQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            version_xso.Query,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            version_xso.Query.TAG,
            (namespaces.xep0092_version, "query"),
        )

    def test_version(self):
        self.assertIsInstance(
            version_xso.Query.version.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            version_xso.Query.version.tag,
            (namespaces.xep0092_version, "version")
        )
        self.assertIsNone(
            version_xso.Query.version.default,
        )

    def test_name(self):
        self.assertIsInstance(
            version_xso.Query.name.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            version_xso.Query.name.tag,
            (namespaces.xep0092_version, "name")
        )
        self.assertIsNone(
            version_xso.Query.name.default,
        )

    def test_os(self):
        self.assertIsInstance(
            version_xso.Query.os.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            version_xso.Query.os.tag,
            (namespaces.xep0092_version, "os")
        )
        self.assertIsNone(
            version_xso.Query.os.default,
        )

    def test_is_iq_payload(self):
        self.assertIn(
            version_xso.Query.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )
