########################################################################
# File name: test_replace.py
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
import aioxmpp.misc as misc_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0308_replace,
            "urn:xmpp:message-correct:0"
        )


class TestReplace(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.Replace,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.Replace.TAG,
            (namespaces.xep0308_replace, "replace"),
        )

    def test_message_attribute(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0308_replace,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.Message.xep0308_replace._classes,
            {
                misc_xso.Replace,
            }
        )
