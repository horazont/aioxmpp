########################################################################
# File name: test_core0.py
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
import aioxmpp.mix.xso as mix_xso
import aioxmpp.mix.xso.core0 as core0_xso

from aioxmpp.utils import namespaces


class TestSubscribe0(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            core0_xso.Subscribe0,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            core0_xso.Subscribe0.TAG,
            (namespaces.xep0369_mix_core_0, "subscribe"),
        )

    def test_node(self):
        self.assertIsInstance(
            core0_xso.Subscribe0.node,
            xso.Attr,
        )
        self.assertIsInstance(
            core0_xso.Subscribe0.node.type_,
            xso.EnumCDataType,
        )
        self.assertEqual(
            core0_xso.Subscribe0.node.type_.enum_class,
            mix_xso.Node,
        )
        self.assertTrue(
            core0_xso.Subscribe0.node.type_.allow_unknown,
        )
        self.assertTrue(
            core0_xso.Subscribe0.node.type_.accept_unknown,
        )
        self.assertFalse(
            core0_xso.Subscribe0.node.type_.allow_coerce,
        )

    def test_init_nodefault(self):
        with self.assertRaisesRegexp(TypeError, "node"):
            core0_xso.Subscribe0()

    def test_init_proper_node(self):
        s0 = core0_xso.Subscribe0(mix_xso.Node.MESSAGES)
        self.assertEqual(s0.node, mix_xso.Node.MESSAGES)

    def test_init_unknown_node(self):
        s0 = core0_xso.Subscribe0(aioxmpp.xso.Unknown("foo"))
        self.assertEqual(s0.node, aioxmpp.xso.Unknown("foo"))


class TestSubscribe0Type(unittest.TestCase):
    def test_is_element_type(self):
        self.assertTrue(issubclass(
            core0_xso.Subscribe0Type,
            xso.AbstractElementType,
        ))

    def setUp(self):
        self.t = core0_xso.Subscribe0Type()

    def test_get_xso_types(self):
        self.assertCountEqual(
            [core0_xso.Subscribe0],
            core0_xso.Subscribe0Type.get_xso_types()
        )

    def test_unpack_extracts_node(self):
        s0 = core0_xso.Subscribe0(mix_xso.Node.MESSAGES)
        self.assertEqual(
            self.t.unpack(s0),
            mix_xso.Node.MESSAGES,
        )

    def test_pack_creates_Subscribe0(self):
        s0 = self.t.pack(mix_xso.Node.PARTICIPANTS)
        self.assertIsInstance(s0, core0_xso.Subscribe0)
        self.assertEqual(s0.node, mix_xso.Node.PARTICIPANTS)


class TestJoin0(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            core0_xso.Join0,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            core0_xso.Join0.TAG,
            (namespaces.xep0369_mix_core_0, "join"),
        )

    def test_subscribe(self):
        self.assertIsInstance(
            core0_xso.Join0.subscribe,
            xso.ChildValueList,
        )
        self.assertIsInstance(
            core0_xso.Join0.subscribe.type_,
            core0_xso.Subscribe0Type,
        )

    def test_init_default(self):
        j0 = core0_xso.Join0()
        self.assertSequenceEqual(j0.subscribe, [])

    def test_init(self):
        j0 = core0_xso.Join0(
            [
                mix_xso.Node.MESSAGES,
                mix_xso.Node.PARTICIPANTS,
            ]
        )

        self.assertCountEqual(
            j0.subscribe,
            [
                mix_xso.Node.MESSAGES,
                mix_xso.Node.PARTICIPANTS,
            ]
        )


class TestLeave0(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            core0_xso.Leave0,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            core0_xso.Leave0.TAG,
            (namespaces.xep0369_mix_core_0, "leave")
        )
