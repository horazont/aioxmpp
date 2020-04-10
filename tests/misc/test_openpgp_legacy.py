########################################################################
# File name: test_openpgp_legacy.py
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
import aioxmpp.xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_encrypt(self):
        self.assertEqual(
            namespaces.xep0027_encrypted,
            "jabber:x:encrypted",
        )

    def test_signed(self):
        self.assertEqual(
            namespaces.xep0027_signed,
            "jabber:x:signed",
        )


class TestOpenPGPEncrypted(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.OpenPGPEncrypted,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.OpenPGPEncrypted.TAG,
            (namespaces.xep0027_encrypted, "x")
        )

    def test_payload(self):
        self.assertIsInstance(
            misc_xso.OpenPGPEncrypted.payload,
            aioxmpp.xso.Text,
        )
        self.assertIsInstance(
            misc_xso.OpenPGPEncrypted.payload.type_,
            aioxmpp.xso.String,
        )


class TestOpenPGPSigned(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.OpenPGPSigned,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.OpenPGPSigned.TAG,
            (namespaces.xep0027_signed, "x")
        )

    def test_payload(self):
        self.assertIsInstance(
            misc_xso.OpenPGPSigned.payload,
            aioxmpp.xso.Text,
        )
        self.assertIsInstance(
            misc_xso.OpenPGPSigned.payload.type_,
            aioxmpp.xso.String,
        )


class TestMessageExtension(unittest.TestCase):
    def test_xep0027_encrypted(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0027_encrypted,
            aioxmpp.xso.Child,
        )
        self.assertIn(
            misc_xso.OpenPGPEncrypted,
            aioxmpp.Message.xep0027_encrypted._classes,
        )


class TestPresenceExtension(unittest.TestCase):
    def test_xep0027_signed(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0027_signed,
            aioxmpp.xso.Child,
        )
        self.assertIn(
            misc_xso.OpenPGPSigned,
            aioxmpp.Message.xep0027_signed._classes,
        )
