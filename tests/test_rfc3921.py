########################################################################
# File name: test_rfc3921.py
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

import aioxmpp.rfc3921 as rfc3921
import aioxmpp.stanza as stanza
import aioxmpp.nonza as nonza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_session_namespace(self):
        self.assertEqual(
            "urn:ietf:params:xml:ns:xmpp-session",
            namespaces.rfc3921_session
        )


class TestSession(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rfc3921.Session,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rfc3921.Session.TAG,
            (namespaces.rfc3921_session, "session")
        )

    def test_declare_ns(self):
        self.assertDictEqual(
            rfc3921.Session.DECLARE_NS,
            {
                None: namespaces.rfc3921_session
            }
        )

    def test_is_iq_payload(self):
        self.assertIn(
            rfc3921.Session.TAG,
            stanza.IQ.CHILD_MAP
        )
        self.assertIs(
            stanza.IQ.CHILD_MAP[rfc3921.Session.TAG],
            stanza.IQ.payload.xq_descriptor
        )

    def test_child_policy(self):
        self.assertEqual(
            rfc3921.Session.UNKNOWN_CHILD_POLICY,
            xso.UnknownChildPolicy.DROP
        )

    def test_attr_policy(self):
        self.assertEqual(
            rfc3921.Session.UNKNOWN_ATTR_POLICY,
            xso.UnknownAttrPolicy.DROP
        )


class TestSessionFeature(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rfc3921.SessionFeature,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rfc3921.SessionFeature.TAG,
            (namespaces.rfc3921_session, "session")
        )

    def test_is_stream_feature(self):
        self.assertTrue(nonza.StreamFeatures.is_feature(
            rfc3921.SessionFeature
        ))

    def test_child_policy(self):
        self.assertEqual(
            rfc3921.SessionFeature.UNKNOWN_CHILD_POLICY,
            xso.UnknownChildPolicy.DROP
        )

    def test_attr_policy(self):
        self.assertEqual(
            rfc3921.SessionFeature.UNKNOWN_ATTR_POLICY,
            xso.UnknownAttrPolicy.DROP
        )

# foo
