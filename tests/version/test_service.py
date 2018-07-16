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
import unittest.mock

import aioxmpp
import aioxmpp.disco
import aioxmpp.version.service as version_svc
import aioxmpp.version.xso as version_xso
import aioxmpp.service

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
)

try:
    import distro
except ImportError:
    distro = None


class TestVersionServer(unittest.TestCase):
    def setUp(self):
        self.client = make_connected_client()
        self.disco_server = unittest.mock.Mock()
        self.s = version_svc.VersionServer(
            self.client,
            dependencies={
                aioxmpp.disco.DiscoServer: self.disco_server,
            }
        )

    def test_is_service(self):
        self.assertTrue(issubclass(
            version_svc.VersionServer,
            aioxmpp.service.Service,
        ))

    def test_depends_on_DiscoServer(self):
        self.assertIn(
            aioxmpp.disco.DiscoServer,
            version_svc.VersionServer.ORDER_AFTER,
        )

    def test_declares_disco_feature(self):
        self.assertIsInstance(
            version_svc.VersionServer.disco_feature,
            aioxmpp.disco.register_feature,
        )
        self.assertEqual(
            version_svc.VersionServer.disco_feature.feature,
            "jabber:iq:version",
        )

    @unittest.skipIf(distro is not None,
                     "distro package is installed")
    def test_fallback_to_platform_module(self):
        with unittest.mock.patch("platform.system") as system:
            s = version_svc.VersionServer(
                self.client,
                dependencies={
                    aioxmpp.disco.DiscoServer: self.disco_server,
                }
            )

            system.assert_called_once_with()
            system.reset_mock()

            self.assertEqual(s.os, system())

    @unittest.skipIf(distro is None,
                     "distro package not installed")
    def test_try_use_distro_package(self):
        with unittest.mock.patch("distro.name") as name:
            s = version_svc.VersionServer(
                self.client,
                dependencies={
                    aioxmpp.disco.DiscoServer: self.disco_server,
                }
            )

            name.assert_called_once_with()
            name.reset_mock()

            self.assertEqual(s.os, name())

    def test_os_attribute_can_be_set_and_stringifies(self):
        self.s.os = unittest.mock.sentinel.os
        self.assertEqual(self.s.os, str(unittest.mock.sentinel.os))

    def test_os_attribute_can_be_set_to_None(self):
        self.s.os = None
        self.assertIsNone(self.s.os)

    def test_os_attribute_can_be_deleted_to_None(self):
        del self.s.os
        self.assertIsNone(self.s.os)

    def test_name_attribute_init_to_None(self):
        self.assertIsNone(self.s.name)

    def test_name_attribute_can_be_set_and_stringifies(self):
        self.s.name = unittest.mock.sentinel.name
        self.assertEqual(self.s.name, str(unittest.mock.sentinel.name))

    def test_name_attribute_can_be_deleted_to_None(self):
        del self.s.name
        self.assertIsNone(self.s.name)

    def test_version_attribute_init_to_None(self):
        self.assertIsNone(self.s.version)

    def test_version_attribute_can_be_set_and_stringifies(self):
        self.s.version = unittest.mock.sentinel.version
        self.assertEqual(self.s.version, str(unittest.mock.sentinel.version))

    def test_version_attribute_can_be_deleted_to_None(self):
        del self.s.version
        self.assertIsNone(self.s.version)

    def test_handles_query_IQs(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.GET,
                version_xso.Query,
                version_svc.VersionServer.handle_query,
            )
        )

    def test_handler_returns_filled_query_object(self):
        self.s.os = unittest.mock.sentinel.os
        self.s.name = unittest.mock.sentinel.name
        self.s.version = unittest.mock.sentinel.version

        result = run_coroutine(
            self.s.handle_query(unittest.mock.sentinel.request)
        )

        self.assertIsInstance(
            result,
            version_xso.Query,
        )

        self.assertEqual(
            result.os,
            self.s.os,
        )

        self.assertEqual(
            result.name,
            self.s.name,
        )

        self.assertEqual(
            result.version,
            self.s.version,
        )

    def test_handler_returns_unspecified_for_None_version(self):
        self.s.os = unittest.mock.sentinel.os
        self.s.name = unittest.mock.sentinel.name
        self.s.version = None

        result = run_coroutine(
            self.s.handle_query(unittest.mock.sentinel.request)
        )

        self.assertIsInstance(
            result,
            version_xso.Query,
        )

        self.assertEqual(
            result.os,
            self.s.os,
        )

        self.assertEqual(
            result.name,
            self.s.name,
        )

        self.assertEqual(
            result.version,
            "unspecified",
        )

    def test_handler_raises_service_unavailable_if_name_is_unset(self):
        del self.s.name
        self.s.version = "foo"
        self.s.os = "bar"

        with self.assertRaises(aioxmpp.XMPPCancelError) as ctx:
            run_coroutine(self.s.handle_query(unittest.mock.sentinel.request))

        self.assertEqual(
            ctx.exception.condition,
            aioxmpp.ErrorCondition.SERVICE_UNAVAILABLE
        )


class Testquery_version(unittest.TestCase):
    def test_queries_version_over_stream(self):
        test_jid = aioxmpp.JID.fromstr("juliet@capulet.lit")

        stream = unittest.mock.Mock(["send"])
        stream.send = CoroutineMock()
        stream.send.return_value = unittest.mock.sentinel.result

        result = run_coroutine(version_svc.query_version(
            stream,
            test_jid,
        ))

        stream.send.assert_called_once_with(unittest.mock.ANY)

        _, (iq, ), _ = stream.send.mock_calls[0]

        self.assertIsInstance(iq, aioxmpp.IQ)
        self.assertEqual(iq.type_, aioxmpp.IQType.GET)
        self.assertEqual(iq.to, test_jid)

        self.assertIsInstance(iq.payload, version_xso.Query)
        self.assertIsNone(iq.payload.name)
        self.assertIsNone(iq.payload.version)
        self.assertIsNone(iq.payload.os)

        self.assertEqual(
            result,
            unittest.mock.sentinel.result,
        )
