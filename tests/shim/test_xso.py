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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import unittest
import unittest.mock

import multidict

import aioxmpp.shim.xso as shim_xso
import aioxmpp.stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_xep0131_shim(self):
        self.assertEqual(
            namespaces.xep0131_shim,
            "http://jabber.org/protocol/shim"
        )


class TestHeader(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            shim_xso.Header,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            shim_xso.Header.TAG,
            (namespaces.xep0131_shim, "header"),
        )

    def test_name(self):
        self.assertIsInstance(
            shim_xso.Header.name,
            xso.Attr
        )
        self.assertEqual(
            shim_xso.Header.name.tag,
            (None, "name")
        )
        self.assertIs(
            shim_xso.Header.name.default,
            xso.NO_DEFAULT
        )

    def test_value(self):
        self.assertIsInstance(
            shim_xso.Header.value,
            xso.Text,
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            shim_xso.Header()

        h = shim_xso.Header("foo", "bar")
        self.assertEqual(h.name, "foo")
        self.assertEqual(h.value, "bar")


class TestHeaderType(unittest.TestCase):
    def test_is_xso_type(self):
        self.assertTrue(issubclass(
            shim_xso.HeaderType,
            xso.AbstractType
        ))

    def setUp(self):
        self.t = shim_xso.HeaderType()

    def tearDown(self):
        del self.t

    def test_get_formatted_type(self):
        self.assertIs(
            self.t.get_formatted_type(),
            shim_xso.Header,
        )

    def test_parse(self):
        h = unittest.mock.Mock()
        h.name = unittest.mock.sentinel.name
        h.value = unittest.mock.sentinel.value

        self.assertEqual(
            self.t.parse(h),
            (
                unittest.mock.sentinel.name,
                unittest.mock.sentinel.value,
            )
        )

    def test_format(self):
        with unittest.mock.patch("aioxmpp.shim.xso.Header") as Header:
            result = self.t.format(
                (
                    unittest.mock.sentinel.name,
                    unittest.mock.sentinel.value,
                )
            )

        Header.assert_called_with(
            unittest.mock.sentinel.name,
            unittest.mock.sentinel.value,
        )

        self.assertEqual(
            result,
            Header()
        )


class TestHeaders(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            shim_xso.Headers,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            shim_xso.Headers.TAG,
            (namespaces.xep0131_shim, "header")
        )

    def test_headers(self):
        self.assertIsInstance(
            shim_xso.Headers.headers,
            xso.ChildValueMultiMap
        )
        self.assertIs(
            shim_xso.Headers.headers.mapping_type,
            multidict.CIMultiDict
        )
        self.assertIsInstance(
            shim_xso.Headers.headers.type_,
            shim_xso.HeaderType,
        )

    def test_headers_attribute_on_Message(self):
        self.assertIsInstance(
            aioxmpp.stanza.Message.xep0131_headers,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.stanza.Message.xep0131_headers._classes,
            {
                shim_xso.Headers,
            }
        )

    def test_headers_attribute_on_Presence(self):
        self.assertIsInstance(
            aioxmpp.stanza.Presence.xep0131_headers,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.stanza.Presence.xep0131_headers._classes,
            {
                shim_xso.Headers,
            }
        )


# foo
