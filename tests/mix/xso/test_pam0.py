########################################################################
# File name: test_pam0.py
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
import aioxmpp.mix.xso.core0 as core0_xso
import aioxmpp.mix.xso.pam0 as pam0_xso

from aioxmpp.utils import namespaces


TEST_JID = aioxmpp.JID.fromstr("channel@service")


class TestClientJoin0(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pam0_xso.ClientJoin0,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pam0_xso.ClientJoin0.TAG,
            (namespaces.xep0405_mix_pam_0, "client-join"),
        )

    def test_channel(self):
        self.assertIsInstance(
            pam0_xso.ClientJoin0.channel,
            xso.Attr,
        )
        self.assertEqual(
            pam0_xso.ClientJoin0.channel.tag,
            (None, "channel")
        )
        self.assertIsInstance(
            pam0_xso.ClientJoin0.channel.type_,
            xso.JID,
        )
        self.assertEqual(
            pam0_xso.ClientJoin0.channel.default,
            None,
        )

    def test_join(self):
        self.assertIsInstance(
            pam0_xso.ClientJoin0.join,
            xso.Child,
        )
        self.assertIn(
            core0_xso.Join0,
            pam0_xso.ClientJoin0.join._classes,
        )

    def test_init_nodefault(self):
        cj0 = pam0_xso.ClientJoin0()
        self.assertIsNone(cj0.join)
        self.assertIsNone(cj0.channel)

    def test_init(self):
        with unittest.mock.patch("aioxmpp.mix.xso.core0.Join0") as Join0:
            cj0 = pam0_xso.ClientJoin0(
                TEST_JID,
                unittest.mock.sentinel.subscribe_to_nodes,
            )

        Join0.assert_called_once_with(
            unittest.mock.sentinel.subscribe_to_nodes
        )

        self.assertEqual(cj0.channel, TEST_JID)
        self.assertEqual(cj0.join, Join0())

    def test_is_iq_payload(self):
        aioxmpp.IQ(type_=aioxmpp.IQType.RESULT, payload=pam0_xso.ClientJoin0())


class TestClientLeave0(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            pam0_xso.ClientLeave0,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            pam0_xso.ClientLeave0.TAG,
            (namespaces.xep0405_mix_pam_0, "client-leave"),
        )

    def test_channel(self):
        self.assertIsInstance(
            pam0_xso.ClientLeave0.channel,
            xso.Attr,
        )
        self.assertEqual(
            pam0_xso.ClientLeave0.channel.tag,
            (None, "channel")
        )
        self.assertIsInstance(
            pam0_xso.ClientLeave0.channel.type_,
            xso.JID,
        )
        self.assertEqual(
            pam0_xso.ClientLeave0.channel.default,
            None,
        )

    def test_leave(self):
        self.assertIsInstance(
            pam0_xso.ClientLeave0.leave,
            xso.Child,
        )
        self.assertIn(
            core0_xso.Leave0,
            pam0_xso.ClientLeave0.leave._classes,
        )

    def test_init_default(self):
        cl0 = pam0_xso.ClientLeave0()
        self.assertIsNone(cl0.channel)
        self.assertIsNone(cl0.leave)

    def test_init_channel(self):
        cl0 = pam0_xso.ClientLeave0(TEST_JID)
        self.assertEqual(cl0.channel, TEST_JID)
        self.assertIsInstance(cl0.leave, core0_xso.Leave0)

    def test_is_iq_payload(self):
        aioxmpp.IQ(type_=aioxmpp.IQType.RESULT,
                   payload=pam0_xso.ClientLeave0())
