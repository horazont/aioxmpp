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
import aioxmpp.ibr.xso as ibr_xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0077_in_band,
            "jabber:iq:register"
        )


class TestQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            ibr_xso.Query,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            ibr_xso.Query.TAG,
            (namespaces.xep0077_in_band, "query")
        )

    def test_is_iq_payload(self):
        self.assertIn(
            ibr_xso.Query.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )

    def test_username(self):
        self.assertIsInstance(
            ibr_xso.Query.username.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.username.tag,
            (namespaces.xep0077_in_band, "username")
        )
        self.assertIsNone(
            ibr_xso.Query.username.default,
        )

    def test_nick(self):
        self.assertIsInstance(
            ibr_xso.Query.nick.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.nick.tag,
            (namespaces.xep0077_in_band, "nick")
        )
        self.assertIsNone(
            ibr_xso.Query.nick.default,
        )

    def test_password(self):
        self.assertIsInstance(
            ibr_xso.Query.password.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.password.tag,
            (namespaces.xep0077_in_band, "password")
        )
        self.assertIsNone(
            ibr_xso.Query.password.default,
        )

    def test_name(self):
        self.assertIsInstance(
            ibr_xso.Query.name.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.name.tag,
            (namespaces.xep0077_in_band, "name")
        )
        self.assertIsNone(
            ibr_xso.Query.name.default,
        )

    def test_first(self):
        self.assertIsInstance(
            ibr_xso.Query.first.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.first.tag,
            (namespaces.xep0077_in_band, "first")
        )
        self.assertIsNone(
            ibr_xso.Query.first.default,
        )

    def test_last(self):
        self.assertIsInstance(
            ibr_xso.Query.last.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.last.tag,
            (namespaces.xep0077_in_band, "last")
        )
        self.assertIsNone(
            ibr_xso.Query.last.default,
        )

    def test_email(self):
        self.assertIsInstance(
            ibr_xso.Query.email.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.email.tag,
            (namespaces.xep0077_in_band, "email")
        )
        self.assertIsNone(
            ibr_xso.Query.email.default,
        )

    def test_address(self):
        self.assertIsInstance(
            ibr_xso.Query.address.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.address.tag,
            (namespaces.xep0077_in_band, "address")
        )
        self.assertIsNone(
            ibr_xso.Query.address.default,
        )

    def test_city(self):
        self.assertIsInstance(
            ibr_xso.Query.city.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.city.tag,
            (namespaces.xep0077_in_band, "city")
        )
        self.assertIsNone(
            ibr_xso.Query.city.default,
        )

    def test_state(self):
        self.assertIsInstance(
            ibr_xso.Query.state.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.state.tag,
            (namespaces.xep0077_in_band, "state")
        )
        self.assertIsNone(
            ibr_xso.Query.state.default,
        )

    def test_zip(self):
        self.assertIsInstance(
            ibr_xso.Query.zip.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.zip.tag,
            (namespaces.xep0077_in_band, "zip")
        )
        self.assertIsNone(
            ibr_xso.Query.zip.default,
        )

    def test_phone(self):
        self.assertIsInstance(
            ibr_xso.Query.phone.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.phone.tag,
            (namespaces.xep0077_in_band, "phone")
        )
        self.assertIsNone(
            ibr_xso.Query.phone.default,
        )

    def test_url(self):
        self.assertIsInstance(
            ibr_xso.Query.url.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.url.tag,
            (namespaces.xep0077_in_band, "url")
        )
        self.assertIsNone(
            ibr_xso.Query.url.default,
        )

    def test_date(self):
        self.assertIsInstance(
            ibr_xso.Query.date.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.date.tag,
            (namespaces.xep0077_in_band, "date")
        )
        self.assertIsNone(
            ibr_xso.Query.date.default,
        )

    def test_misc(self):
        self.assertIsInstance(
            ibr_xso.Query.misc.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.misc.tag,
            (namespaces.xep0077_in_band, "misc")
        )
        self.assertIsNone(
            ibr_xso.Query.misc.default,
        )

    def test_text(self):
        self.assertIsInstance(
            ibr_xso.Query.text.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.text.tag,
            (namespaces.xep0077_in_band, "text")
        )
        self.assertIsNone(
            ibr_xso.Query.text.default,
        )

    def test_key(self):
        self.assertIsInstance(
            ibr_xso.Query.key.xq_descriptor,
            xso.ChildText,
        )
        self.assertEqual(
            ibr_xso.Query.key.tag,
            (namespaces.xep0077_in_band, "key")
        )
        self.assertIsNone(
            ibr_xso.Query.key.default,
        )

    def test_registered(self):
        self.assertIsInstance(
            ibr_xso.Query.registered.xq_descriptor,
            xso.ChildFlag,
        )
        self.assertEqual(
            ibr_xso.Query.registered.tag,
            (namespaces.xep0077_in_band, "registered")
        )

    def test_remove(self):
        self.assertIsInstance(
            ibr_xso.Query.remove.xq_descriptor,
            xso.ChildFlag,
        )
        self.assertEqual(
            ibr_xso.Query.remove.tag,
            (namespaces.xep0077_in_band, "remove")
        )
