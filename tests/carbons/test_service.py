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
import contextlib
import unittest

import aioxmpp
import aioxmpp.carbons.service as carbons_service
import aioxmpp.carbons.xso as carbons_xso
import aioxmpp.service

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_JID = aioxmpp.JID.fromstr("romeo@montague.lit/foo")


class TestCarbonsClient(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_JID
        self.disco_client = aioxmpp.DiscoClient(self.cc)
        self.s = carbons_service.CarbonsClient(
            self.cc,
            dependencies={
                aioxmpp.DiscoClient: self.disco_client,
            }
        )

    def test_is_service(self):
        self.assertTrue(issubclass(
            carbons_service.CarbonsClient,
            aioxmpp.service.Service,
        ))

    def test_requires_DiscoClient(self):
        self.assertLess(
            aioxmpp.DiscoClient,
            carbons_service.CarbonsClient,
        )

    def test__check_for_feature_uses_disco(self):
        info = unittest.mock.Mock()
        info.features = {namespaces.xep0280_carbons_2}

        with contextlib.ExitStack() as stack:
            query_info = stack.enter_context(unittest.mock.patch.object(
                self.disco_client,
                "query_info",
                new=CoroutineMock(),
            ))

            query_info.return_value = info

            run_coroutine(
                self.s._check_for_feature()
            )

            query_info.assert_called_once_with(
                self.cc.local_jid.replace(
                    localpart=None,
                    resource=None
                )
            )

    def test__check_for_feature_raises_if_feature_not_present(self):
        info = unittest.mock.Mock()
        info.features = set()

        with contextlib.ExitStack() as stack:
            query_info = stack.enter_context(unittest.mock.patch.object(
                self.disco_client,
                "query_info",
                new=CoroutineMock(),
            ))

            query_info.return_value = info

            with self.assertRaisesRegex(
                    RuntimeError,
                    r"Message Carbons \({}\) are not supported by "
                    "the server".format(
                        namespaces.xep0280_carbons_2
                    )):
                run_coroutine(
                    self.s._check_for_feature()
                )

            query_info.assert_called_once_with(
                self.cc.local_jid.replace(
                    localpart=None,
                    resource=None
                )
            )

    def test_enable_checks_for_feature_and_sends_iq(self):
        with contextlib.ExitStack() as stack:
            check_for_feature = stack.enter_context(unittest.mock.patch.object(
                self.s,
                "_check_for_feature",
                new=CoroutineMock()
            ))

            run_coroutine(self.s.enable())

            check_for_feature.assert_called_once_with()

            self.cc.send.assert_called_once_with(
                unittest.mock.ANY,
            )

            _, (iq,), _ = self.cc.send.mock_calls[0]

            self.assertIsInstance(iq, aioxmpp.IQ)
            self.assertEqual(iq.type_, aioxmpp.IQType.SET)
            self.assertIsInstance(iq.payload, carbons_xso.Enable)

    def test_enable_does_not_send_if_feature_not_available(self):
        with contextlib.ExitStack() as stack:
            check_for_feature = stack.enter_context(unittest.mock.patch.object(
                self.s,
                "_check_for_feature",
                new=CoroutineMock()
            ))
            check_for_feature.side_effect = RuntimeError()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s.enable())

            check_for_feature.assert_called_once_with()

            self.cc.send.assert_not_called()

    def test_disable_checks_for_feature_and_sends_iq(self):
        with contextlib.ExitStack() as stack:
            check_for_feature = stack.enter_context(unittest.mock.patch.object(
                self.s,
                "_check_for_feature",
                new=CoroutineMock()
            ))

            run_coroutine(self.s.disable())

            check_for_feature.assert_called_once_with()

            self.cc.send.assert_called_once_with(
                unittest.mock.ANY,
            )

            _, (iq,), _ = self.cc.send.mock_calls[0]

            self.assertIsInstance(iq, aioxmpp.IQ)
            self.assertEqual(iq.type_, aioxmpp.IQType.SET)
            self.assertIsInstance(iq.payload, carbons_xso.Disable)

    def test_disable_does_not_send_if_feature_not_available(self):
        with contextlib.ExitStack() as stack:
            check_for_feature = stack.enter_context(unittest.mock.patch.object(
                self.s,
                "_check_for_feature",
                new=CoroutineMock()
            ))
            check_for_feature.side_effect = RuntimeError()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s.disable())

            check_for_feature.assert_called_once_with()

            self.cc.send.assert_not_called()
