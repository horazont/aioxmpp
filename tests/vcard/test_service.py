########################################################################
# File name: test_service.py
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
import aioxmpp.service as service

from aioxmpp.utils import namespaces

import aioxmpp.vcard.service as vcard_service
import aioxmpp.vcard.xso as vcard_xso

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_JID1 = aioxmpp.JID.fromstr("foo@baz.bar")
TEST_JID2 = aioxmpp.JID.fromstr("foo@baz.bar/quux")

class TestService(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.s = vcard_service.VCardService(
            self.cc,
            dependencies={},
        )
        self.cc.mock_calls.clear()

    def tearDown(self):
        del self.cc
        del self.s

    def test_is_service(self):
        self.assertTrue(issubclass(
            vcard_service.VCardService,
            service.Service,
        ))

    def test_get_vcard_own(self):
        with unittest.mock.patch.object(self.cc, "send",
                                        new=CoroutineMock()) as mock_send:
            mock_send.return_value = unittest.mock.sentinel.result
            res = run_coroutine(self.s.get_vcard())

        self.assertEqual(len(mock_send.mock_calls), 1)
        try:
            (_, (arg,), kwargs), = mock_send.mock_calls
        except ValueError:
            self.fail("send called with wrong signature")
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.IQ)
        self.assertEqual(arg.type_, aioxmpp.IQType.GET)
        self.assertEqual(arg.to, None)
        self.assertIsInstance(arg.payload, vcard_xso.VCard)
        self.assertEqual(len(arg.payload.elements), 0)
        self.assertEqual(res, unittest.mock.sentinel.result)

    def test_get_vcard_other(self):
        with unittest.mock.patch.object(self.cc, "send",
                                        new=CoroutineMock()) as mock_send:
            mock_send.return_value = unittest.mock.sentinel.result
            res = run_coroutine(self.s.get_vcard(TEST_JID1))

        self.assertEqual(len(mock_send.mock_calls), 1)
        try:
            (_, (arg,), kwargs), = mock_send.mock_calls
        except ValueError:
            self.fail("send called with wrong signature")
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.IQ)
        self.assertEqual(arg.type_, aioxmpp.IQType.GET)
        self.assertEqual(arg.to, TEST_JID1)
        self.assertIsInstance(arg.payload, vcard_xso.VCard)
        self.assertEqual(len(arg.payload.elements), 0)
        self.assertEqual(res, unittest.mock.sentinel.result)

    def test_get_vcard_mask_cancel_error(self):
        with unittest.mock.patch.object(self.cc, "send",
                                        new=CoroutineMock()) as mock_send:
            mock_send.side_effect = aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
            res = run_coroutine(self.s.get_vcard(TEST_JID1))

        self.assertIsInstance(res, vcard_xso.VCard)
        self.assertEqual(len(res.elements), 0)

        with unittest.mock.patch.object(self.cc, "send",
                                        new=CoroutineMock()) as mock_send:
            mock_send.side_effect = aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.ITEM_NOT_FOUND
            )
            res = run_coroutine(self.s.get_vcard(TEST_JID1))

        self.assertIsInstance(res, vcard_xso.VCard)
        self.assertEqual(len(res.elements), 0)

        with self.assertRaises(aioxmpp.XMPPCancelError):
            with unittest.mock.patch.object(self.cc, "send",
                                            new=CoroutineMock()) as mock_send:
                mock_send.side_effect = aioxmpp.XMPPCancelError(
                    aioxmpp.ErrorCondition.REMOTE_SERVER_NOT_FOUND
                )
                res = run_coroutine(self.s.get_vcard(TEST_JID1))

    def test_set_vcard(self):
        with unittest.mock.patch.object(self.cc, "send",
                                        new=CoroutineMock()) as mock_send:
            vcard = vcard_xso.VCard()
            run_coroutine(self.s.set_vcard(vcard))

        self.assertEqual(len(mock_send.mock_calls), 1)
        try:
            (_, (arg,), kwargs), = mock_send.mock_calls
        except ValueError:
            self.fail("send called with wrong signature")
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.IQ)
        self.assertEqual(arg.type_, aioxmpp.IQType.SET)
        self.assertEqual(arg.to, None)
        self.assertIs(arg.payload, vcard)
