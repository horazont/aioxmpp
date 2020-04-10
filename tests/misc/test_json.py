########################################################################
# File name: test_json.py
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

import aioxmpp.pubsub.xso
import aioxmpp.xso as xso
import aioxmpp.misc as misc_xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_xep0335_json(self):
        self.assertEqual(
            namespaces.xep0335_json,
            "urn:xmpp:json:0"
        )


class TestJSONContainer(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.JSONContainer,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.JSONContainer.TAG,
            ("urn:xmpp:json:0", "json")
        )

    def test_json_data(self):
        self.assertIsInstance(
            misc_xso.JSONContainer.json_data,
            xso.Text,
        )
        self.assertIsInstance(
            misc_xso.JSONContainer.json_data.type_,
            xso.JSON
        )

    def test_init(self):
        jc = misc_xso.JSONContainer()
        self.assertIsNone(jc.json_data)

    def test_init_with_data(self):
        jc = misc_xso.JSONContainer(unittest.mock.sentinel.data)
        self.assertEqual(jc.json_data, unittest.mock.sentinel.data)

    def test_is_pubsub_payload(self):
        self.assertIn(
            misc_xso.JSONContainer.TAG,
            aioxmpp.pubsub.xso.Item.CHILD_MAP,
        )


class TestJSONContainerType(unittest.TestCase):
    def test_is_element_type(self):
        self.assertTrue(issubclass(
            misc_xso.JSONContainerType,
            xso.AbstractElementType,
        ))

    def test_advertises_JSONContainer_xso_on_class(self):
        self.assertIn(
            misc_xso.JSONContainer,
            misc_xso.JSONContainerType.get_xso_types()
        )

    def test_advertises_JSONContainer_xso_on_instance(self):
        self.assertIn(
            misc_xso.JSONContainer,
            misc_xso.JSONContainerType().get_xso_types()
        )

    def test_unpack_extracts_json_data_attribute_via_class(self):
        m = unittest.mock.Mock(spec=misc_xso.JSONContainer)

        self.assertEqual(
            misc_xso.JSONContainerType.unpack(m),
            m.json_data,
        )

    def test_unpack_extracts_json_data_attribute_via_instance(self):
        m = unittest.mock.Mock(spec=misc_xso.JSONContainer)

        self.assertEqual(
            misc_xso.JSONContainerType().unpack(m),
            m.json_data,
        )

    def test_pack_creates_JSONContainer_with_data_via_class(self):
        with contextlib.ExitStack() as stack:
            JSONContainer = stack.enter_context(unittest.mock.patch(
                "aioxmpp.misc.json.JSONContainer",
                return_value=unittest.mock.sentinel.obj
            ))

            result = misc_xso.JSONContainerType.pack(
                unittest.mock.sentinel.data,
            )

        self.assertEqual(
            result,
            unittest.mock.sentinel.obj,
        )

        JSONContainer.assert_called_once_with(unittest.mock.sentinel.data)
