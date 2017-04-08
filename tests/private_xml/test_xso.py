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
import contextlib
import unittest
import unittest.mock

import aioxmpp.private_xml.xso as private_xml_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestQuery(unittest.TestCase):

    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0049,
            "jabber:iq:private"
        )

    def test_is_xso(self):
        self.assertTrue(issubclass(private_xml_xso.Query, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            private_xml_xso.Query.TAG,
            (namespaces.xep0049, "query")
        )

    def test_init(self):
        query = private_xml_xso.Query(unittest.mock.sentinel.payload)
        self.assertEqual(
            query.registered_payload,
            unittest.mock.sentinel.payload
        )

    def test_as_payload_class(self):
        with contextlib.ExitStack() as stack:
            at_Query = stack.enter_context(
                unittest.mock.patch.object(
                    private_xml_xso.Query,
                    "register_child"
                )
            )

            result = private_xml_xso.Query.as_payload_class(
                unittest.mock.sentinel.cls
            )

        self.assertIs(result, unittest.mock.sentinel.cls)

        at_Query.assert_called_with(
            private_xml_xso.Query.registered_payload,
            unittest.mock.sentinel.cls
        )
