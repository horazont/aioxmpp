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
import aioxmpp.carbons.xso as carbons_xso
import aioxmpp.misc as misc_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0280_carbons_2,
            "urn:xmpp:carbons:2",
        )


class TestEnable(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(
            issubclass(carbons_xso.Enable, xso.XSO)
        )

    def test_tag(self):
        self.assertEqual(
            carbons_xso.Enable.TAG,
            (namespaces.xep0280_carbons_2, "enable"),
        )

    def test_is_iq_payload(self):
        self.assertIn(
            carbons_xso.Enable,
            aioxmpp.IQ.payload._classes,
        )


class TestDisable(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(
            issubclass(carbons_xso.Disable, xso.XSO)
        )

    def test_tag(self):
        self.assertEqual(
            carbons_xso.Disable.TAG,
            (namespaces.xep0280_carbons_2, "disable"),
        )

    def test_is_iq_payload(self):
        self.assertIn(
            carbons_xso.Disable,
            aioxmpp.IQ.payload._classes,
        )


class Test_CarbonsWrapper(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(
            issubclass(carbons_xso._CarbonsWrapper, xso.XSO)
        )

    def test_has_no_tag(self):
        self.assertFalse(hasattr(carbons_xso._CarbonsWrapper, "TAG"))

    def test_forwarded(self):
        self.assertIsInstance(
            carbons_xso._CarbonsWrapper.forwarded,
            xso.Child
        )

    def test_stanza_returns_None_if_forwarded_is_None(self):
        s = carbons_xso._CarbonsWrapper()
        self.assertIsNone(s.forwarded)
        self.assertIsNone(s.stanza)

    def test_stanza_returns_stanza_from_forwarded(self):
        s = carbons_xso._CarbonsWrapper()
        s.forwarded = misc_xso.Forwarded()
        s.forwarded.stanza = unittest.mock.sentinel.foo

        self.assertEqual(
            s.stanza,
            s.forwarded.stanza,
        )

    def test_setting_stanza_creates_forwarded(self):
        s = carbons_xso._CarbonsWrapper()
        self.assertIsNone(s.forwarded)

        s.stanza = unittest.mock.sentinel.foo

        self.assertIsInstance(
            s.forwarded,
            misc_xso.Forwarded,
        )

        self.assertEqual(
            s.forwarded.stanza,
            unittest.mock.sentinel.foo,
        )

    def test_setting_stanza_reuses_forwarded(self):
        forwarded = misc_xso.Forwarded()
        s = carbons_xso._CarbonsWrapper()
        s.forwarded = forwarded
        s.stanza = unittest.mock.sentinel.foo

        self.assertIs(
            s.forwarded,
            forwarded,
        )

        self.assertEqual(
            s.forwarded.stanza,
            unittest.mock.sentinel.foo,
        )


class TestSent(unittest.TestCase):
    def test_is_carbons_wrapper(self):
        self.assertTrue(
            issubclass(carbons_xso.Sent, carbons_xso._CarbonsWrapper)
        )

    def test_tag(self):
        self.assertEqual(
            carbons_xso.Sent.TAG,
            (namespaces.xep0280_carbons_2, "sent"),
        )


class TestReceived(unittest.TestCase):
    def test_is_carbons_wrapper(self):
        self.assertTrue(
            issubclass(carbons_xso.Received, carbons_xso._CarbonsWrapper)
        )

    def test_tag(self):
        self.assertEqual(
            carbons_xso.Received.TAG,
            (namespaces.xep0280_carbons_2, "received"),
        )


class TestMessage(unittest.TestCase):
    def test_xep0280_sent(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0280_sent,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.Message.xep0280_sent._classes,
            {
                carbons_xso.Sent,
            }
        )

    def test_xep0280_received(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0280_received,
            xso.Child,
        )
        self.assertSetEqual(
            aioxmpp.Message.xep0280_received._classes,
            {
                carbons_xso.Received,
            }
        )
