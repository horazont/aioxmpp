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
import unittest.mock

import lxml.etree

import aioxmpp.xso as xso
import aioxmpp.vcard.xso as vcard_xso

from aioxmpp.utils import namespaces


class TestNamespace(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0054,
            "vcard-temp"
        )


class TestVCard(unittest.TestCase):

    def test_is_xso(self):
        self.assertTrue(issubclass(vcard_xso.VCard, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            vcard_xso.VCard.TAG,
            (namespaces.xep0054, "vCard"),
        )

    def test_elements(self):
        self.assertIsInstance(
            vcard_xso.VCard.elements,
            xso.Collector
        )

    def test_get_photo_data(self):
        vcard = vcard_xso.VCard()
        vcard.elements.append(
            lxml.etree.fromstring("""
<ns0:PHOTO xmlns:ns0="vcard-temp"><ns0:BINVAL>Zm9vCg==</ns0:BINVAL></ns0:PHOTO>
            """)
        )
        self.assertEqual(vcard.get_photo_data(), b'foo\n')

    def test_set_photo_data(self):
        vcard = vcard_xso.VCard()
        vcard.elements.append(
            lxml.etree.fromstring("""
<ns0:PHOTO xmlns:ns0="vcard-temp"><ns0:BINVAL>Zm9vCg==</ns0:BINVAL></ns0:PHOTO>
            """)
        )
        vcard.set_photo_data("image/png", b'bar')
        self.assertEqual(
            vcard.get_photo_data(),
            b'bar'
        )

        vcard.clear_photo_data()
        vcard.set_photo_data("image/png", b'quux')
        self.assertEqual(
            vcard.get_photo_data(),
            b'quux'
        )

    def test_clear_photo_data(self):
        vcard = vcard_xso.VCard()
        vcard.elements.append(
            lxml.etree.fromstring("""
<ns0:PHOTO xmlns:ns0="vcard-temp"><ns0:BINVAL>Zm9vCg==</ns0:BINVAL></ns0:PHOTO>
            """)
        )
        vcard.clear_photo_data()
        self.assertEqual(
            vcard.get_photo_data(),
            None
        )
