########################################################################
# File name: test_delay.py
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
import aioxmpp.misc.stanzaid as stanzaid_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0359_stanza_ids,
            "urn:xmpp:sid:0"
        )


class TestStanzaID(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.StanzaID,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.StanzaID.TAG,
            (namespaces.xep0359_stanza_ids, "stanza-id"),
        )

    def test_default(self):
        si = misc_xso.StanzaID()
        self.assertIsNone(si.id_)
        self.assertIsNone(si.by)

    def test_init(self):
        si = misc_xso.StanzaID(id_="foo", by=aioxmpp.JID.fromstr("bar@baz"))
        self.assertEqual(si.id_, "foo")
        self.assertEqual(si.by, aioxmpp.JID.fromstr("bar@baz"))

    def test_message_attribute(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0359_stanza_ids,
            xso.ChildValueMultiMap,
        )
        self.assertEqual(
            aioxmpp.Message.xep0359_stanza_ids.type_,
            stanzaid_xso.StanzaIDType,
        )


class TestStanzaIDType(unittest.TestCase):
    def test_is_xso_element_type(self):
        self.assertTrue(issubclass(
            stanzaid_xso.StanzaIDType,
            xso.AbstractElementType,
        ))

    def test_xso_classes(self):
        self.assertCountEqual(
            stanzaid_xso.StanzaIDType.get_xso_types(),
            [
                misc_xso.StanzaID,
            ],
        )

    def test_unpack_extracts_by_and_id(self):
        si = misc_xso.StanzaID(
            id_="some-id",
            by=aioxmpp.JID.fromstr("foo@bar/baz"),
        )
        self.assertEqual(
            (aioxmpp.JID.fromstr("foo@bar/baz"), "some-id"),
            stanzaid_xso.StanzaIDType.unpack(si),
        )

    def test_pack_packs_by_and_id_into_stanza_id_object(self):
        si = stanzaid_xso.StanzaIDType.pack(
            (aioxmpp.JID.fromstr("local@domain/res"), "some-id"),
        )
        self.assertIsInstance(si, misc_xso.StanzaID)
        self.assertEqual(si.id_, "some-id")
        self.assertEqual(si.by, aioxmpp.JID.fromstr("local@domain/res"))


class TestOriginID(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            misc_xso.OriginID,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.OriginID.TAG,
            (namespaces.xep0359_stanza_ids, "origin-id"),
        )

    def test_default(self):
        oi = misc_xso.OriginID()
        self.assertIsNone(oi.id_)

    def test_init(self):
        oi = misc_xso.OriginID(id_="foo")
        self.assertEqual(oi.id_, "foo")

    def test_message_attribute(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0359_origin_id,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.Message.xep0359_origin_id._classes,
            {
                misc_xso.OriginID,
            }
        )
