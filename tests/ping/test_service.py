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

import aioxmpp.disco
import aioxmpp.service

from aioxmpp.utils import namespaces

import aioxmpp.ping.service as ping_service
import aioxmpp.ping.xso as ping_xso

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
)


TEST_PEER = aioxmpp.JID.fromstr("juliet@capulet.lit/balcony")


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = ping_service.PingService(self.cc)

    def test_is_service(self):
        self.assertTrue(issubclass(
            ping_service.PingService,
            aioxmpp.service.Service,
        ))

    def test_ping_sends_ping(self):
        self.cc.stream.send.return_value = ping_xso.Ping()

        run_coroutine(self.s.ping(TEST_PEER))

        self.cc.stream.send.assert_called_once_with(unittest.mock.ANY)

        _, (iq, ), _ = self.cc.stream.send.mock_calls[0]

        self.assertIsInstance(
            iq,
            aioxmpp.IQ,
        )

        self.assertEqual(
            iq.to,
            TEST_PEER,
        )

        self.assertEqual(
            iq.type_,
            aioxmpp.IQType.GET,
        )

        self.assertIsInstance(
            iq.payload,
            ping_xso.Ping,
        )

    def test_ping_reraises_random_errors_from_send(self):
        class FooException(Exception):
            pass

        self.cc.stream.send.side_effect = FooException()

        with self.assertRaises(FooException):
            run_coroutine(self.s.ping(TEST_PEER))

    def test_ping_reraises_XMPPErrors(self):
        exc = aioxmpp.errors.XMPPError(
            ("condition_ns", "condition_name"),
        )
        exc.TYPE = unittest.mock.sentinel.type_
        self.cc.stream.send.side_effect = exc

        with self.assertRaises(aioxmpp.errors.XMPPError) as ctx:
            run_coroutine(self.s.ping(TEST_PEER))

        self.assertIs(ctx.exception, exc)
