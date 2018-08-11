########################################################################
# File name: test_markers.py
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

import aioxmpp.misc as misc_xso
import aioxmpp.misc.markers as markers_xso
import aioxmpp.xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0333_markers,
            "urn:xmpp:chat-markers:0",
        )


class TestMarker(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            markers_xso.Marker,
            aioxmpp.xso.XSO
        ))

    def test_id_(self):
        self.assertIsInstance(
            markers_xso.Marker.id_,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            markers_xso.Marker.id_.tag,
            (None, "id")
        )


class TestReceived(unittest.TestCase):
    def test_is_marker(self):
        self.assertTrue(issubclass(
            misc_xso.ReceivedMarker,
            markers_xso.Marker,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.ReceivedMarker.TAG,
            (namespaces.xep0333_markers, "received"),
        )


class TestDisplayed(unittest.TestCase):
    def test_is_marker(self):
        self.assertTrue(issubclass(
            misc_xso.DisplayedMarker,
            markers_xso.Marker,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.DisplayedMarker.TAG,
            (namespaces.xep0333_markers, "displayed"),
        )


class TestAcknowledged(unittest.TestCase):
    def test_is_marker(self):
        self.assertTrue(issubclass(
            misc_xso.AcknowledgedMarker,
            markers_xso.Marker,
        ))

    def test_tag(self):
        self.assertEqual(
            misc_xso.AcknowledgedMarker.TAG,
            (namespaces.xep0333_markers, "acknowledged"),
        )


class TestMessage(unittest.TestCase):
    def test_xep0333_marker(self):
        self.assertIsInstance(
            aioxmpp.Message.xep0333_marker,
            aioxmpp.xso.Child,
        )
        self.assertLessEqual(
            {
                misc_xso.ReceivedMarker,
                misc_xso.DisplayedMarker,
                misc_xso.AcknowledgedMarker,
            },
            set(aioxmpp.Message.xep0333_marker._classes)
        )
