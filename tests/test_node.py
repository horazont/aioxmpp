########################################################################
# File name: test_node.py
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
import asyncio
import contextlib
import ipaddress
import itertools
import logging
import unittest
import unittest.mock

from datetime import timedelta

import OpenSSL.SSL

import dns.resolver

import aiosasl

import aioxmpp
import aioxmpp.dispatcher
import aioxmpp.node as node
import aioxmpp.structs as structs
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza
import aioxmpp.rfc3921 as rfc3921
import aioxmpp.rfc6120 as rfc6120
import aioxmpp.service as service

from aioxmpp.utils import namespaces

from aioxmpp import xmltestutils
from aioxmpp.testutils import (
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer,
    make_connected_client,
    make_listener,
    CoroutineMock,
    get_timeout,
)


class Testdiscover_connectors(unittest.TestCase):
    def setUp(self):
        self.hosts = [
            unittest.mock.Mock(spec=bytes)
            for i in range(4)
        ]

        for i, host in enumerate(self.hosts, 1):
            host.decode.return_value = getattr(
                unittest.mock.sentinel, "host{}".format(i)
            )

        self.domain = unittest.mock.Mock(spec=str)
        domain_encoded = unittest.mock.MagicMock(["__add__"])
        domain_encoded.__add__.return_value = unittest.mock.sentinel.domain
        self.domain.encode.return_value = domain_encoded

    def test_request_SRV_records(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (self.hosts[0], unittest.mock.sentinel.port1)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (self.hosts[1], unittest.mock.sentinel.port2)),
            ]
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        for host in self.hosts[:4]:
            host.decode.assert_called_once_with("ascii")

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (unittest.mock.sentinel.host1, unittest.mock.sentinel.port1,
                  unittest.mock.sentinel.starttls0)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (unittest.mock.sentinel.host2, unittest.mock.sentinel.port2,
                  unittest.mock.sentinel.starttls1)),
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.tls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.tls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_can_deal_with_None_from_XEP368_query(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (self.hosts[0], unittest.mock.sentinel.port1)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (self.hosts[1], unittest.mock.sentinel.port2)),
            ]
            yield None

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        for host in self.hosts[:2]:
            host.decode.assert_called_once_with("ascii")

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (unittest.mock.sentinel.host1, unittest.mock.sentinel.port1,
                  unittest.mock.sentinel.starttls0)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (unittest.mock.sentinel.host2, unittest.mock.sentinel.port2,
                  unittest.mock.sentinel.starttls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_can_deal_with_None_from_RFC6120_query(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield None
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        for host in self.hosts[2:4]:
            host.decode.assert_called_once_with("ascii")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.tls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.tls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_fallback_to_domain_name(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.return_value = None

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        self.assertFalse(group_and_order.mock_calls)

        self.assertSequenceEqual(
            result,
            [(self.domain,
              5222,
              unittest.mock.sentinel.starttls0)],
        )

    def test_succeed_if_only_xmpp_client_is_disabled(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield ValueError()
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        for host in self.hosts[2:4]:
            host.decode.assert_called_once_with("ascii")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.tls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.tls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_succeed_if_only_xmpps_client_is_disabled(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]
            yield ValueError()

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        for host in self.hosts[2:4]:
            host.decode.assert_called_once_with("ascii")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.starttls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.starttls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_fail_if_both_disabled(self):
        loop = asyncio.get_event_loop()

        def srv_records():
            yield ValueError()
            yield ValueError()

        with contextlib.ExitStack() as stack:
            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            with self.assertRaisesRegex(ValueError,
                                        "XMPP not enabled on domain .*"):
                run_coroutine(
                    node.discover_connectors(
                        self.domain,
                        loop=loop,
                    )
                )

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

    def test_fail_if_RFC6120_disabled_and_XEP368_empty(self):
        loop = asyncio.get_event_loop()

        def srv_records():
            yield ValueError()
            yield None

        with contextlib.ExitStack() as stack:
            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            with self.assertRaisesRegex(ValueError,
                                        "XMPP not enabled on domain .*"):
                run_coroutine(
                    node.discover_connectors(
                        self.domain,
                        loop=loop,
                    )
                )

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

    def test_succeed_if_only_xmpps_client_fails_with_NoNameservers(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]
            yield dns.resolver.NoNameservers()

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        for host in self.hosts[2:4]:
            host.decode.assert_called_once_with("ascii")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.starttls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.starttls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_succeed_if_only_xmpp_client_fails_with_NoNameservers(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield dns.resolver.NoNameservers()
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (self.hosts[2], unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (self.hosts[3], unittest.mock.sentinel.port4)),
            ]

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(unittest.mock.patch(
                "aioxmpp.network.group_and_order_srv_records"
            ))
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    self.domain,
                    loop=loop,
                )
            )

        self.domain.encode.assert_called_once_with("idna")

        for host in self.hosts[2:4]:
            host.decode.assert_called_once_with("ascii")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.tls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.tls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_propagate_xmpp_client_NoNameservers_if_both_fail(self):
        loop = asyncio.get_event_loop()

        to_propagate = dns.resolver.NoNameservers()

        def srv_records():
            yield to_propagate
            yield dns.resolver.NoNameservers()

        with contextlib.ExitStack() as stack:
            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            with self.assertRaises(dns.resolver.NoNameservers) as ctx:
                run_coroutine(
                    node.discover_connectors(
                        self.domain,
                        loop=loop,
                    )
                )

        self.assertIs(ctx.exception,
                      to_propagate)

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

    def test_propagate_xmpp_client_NoNameservers_if_tls_empty(self):
        loop = asyncio.get_event_loop()

        to_propagate = dns.resolver.NoNameservers()

        def srv_records():
            yield to_propagate
            yield None

        with contextlib.ExitStack() as stack:
            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            with self.assertRaises(dns.resolver.NoNameservers) as ctx:
                run_coroutine(
                    node.discover_connectors(
                        self.domain,
                        loop=loop,
                    )
                )

        self.assertIs(ctx.exception,
                      to_propagate)

        self.domain.encode.assert_called_once_with("idna")

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )


class Testconnect_xmlstream(unittest.TestCase):
    def setUp(self):
        self.discover_connectors = CoroutineMock()
        self.negotiate_sasl = CoroutineMock()
        self.send_stream_error = unittest.mock.Mock()

        self.patches = [
            unittest.mock.patch("aioxmpp.node.discover_connectors",
                                new=self.discover_connectors),
            unittest.mock.patch("aioxmpp.security_layer.negotiate_sasl",
                                new=self.negotiate_sasl),
            unittest.mock.patch("aioxmpp.protocol.send_stream_error_and_close",
                                new=self.send_stream_error),
        ]

        self.negotiate_sasl.return_value = \
            unittest.mock.sentinel.post_sasl_features

        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_uses_discover_connectors_and_tries_them_in_order(self):
        NCONNECTORS = 4

        logger = unittest.mock.Mock()
        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            loop=unittest.mock.sentinel.loop,
            logger=logger,
        ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=logger,
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_negotiate_sasl_after_success(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            negotiation_timeout=unittest.mock.sentinel.timeout,
            loop=unittest.mock.sentinel.loop,
        ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.negotiate_sasl.assert_called_with(
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            base.metadata.sasl_providers,
            negotiation_timeout=None,
            jid=jid,
            features=unittest.mock.sentinel.features,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    unittest.mock.sentinel.timeout,
                    base_logger=node.logger,
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_connect_without_sasl_provider(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]
        base.metadata.sasl_providers = []
        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            negotiation_timeout=unittest.mock.sentinel.timeout,
            loop=unittest.mock.sentinel.loop,
        ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.negotiate_sasl.assert_not_called()

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.features,
            )
        )

    def test_try_next_on_generic_SASL_problem(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.t1,
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.f1,
        )

        base.c3.connect.side_effect = None
        base.c3.connect.return_value = (
            unittest.mock.sentinel.t2,
            unittest.mock.sentinel.p2,
            unittest.mock.sentinel.f2,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        exc = errors.SASLUnavailable("fubar")

        def results():
            yield exc
            yield unittest.mock.sentinel.post_sasl_features

        self.negotiate_sasl.side_effect = results()

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            loop=unittest.mock.sentinel.loop,
        ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            self.negotiate_sasl.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.t1,
                    unittest.mock.sentinel.p1,
                    base.metadata.sasl_providers,
                    negotiation_timeout=None,
                    jid=jid,
                    features=unittest.mock.sentinel.f1,
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.t2,
                    unittest.mock.sentinel.p2,
                    base.metadata.sasl_providers,
                    negotiation_timeout=None,
                    jid=jid,
                    features=unittest.mock.sentinel.f2,
                ),
            ]
        )

        self.send_stream_error.assert_called_with(
            unittest.mock.sentinel.p1,
            condition=errors.StreamErrorCondition.POLICY_VIOLATION,
            text=str(exc)
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger,
                )
                for i in range(NCONNECTORS)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.t2,
                unittest.mock.sentinel.p2,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_abort_on_authentication_failed(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.t1,
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.f1,
        )

        base.c3.connect.side_effect = None
        base.c3.connect.return_value = (
            unittest.mock.sentinel.t2,
            unittest.mock.sentinel.p2,
            unittest.mock.sentinel.f2,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        exc = aiosasl.AuthenticationFailure("fubar")

        def results():
            yield exc
            yield unittest.mock.sentinel.post_sasl_features

        self.negotiate_sasl.side_effect = results()

        with self.assertRaises(aiosasl.AuthenticationFailure) as exc_ctx:
            run_coroutine(node.connect_xmlstream(
                jid,
                base.metadata,
                loop=unittest.mock.sentinel.loop,
            ))

        jid.domain.encode.assert_not_called()

        self.assertEqual(exc_ctx.exception, exc)

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.send_stream_error.assert_called_with(
            unittest.mock.sentinel.p1,
            condition=errors.StreamErrorCondition.UNDEFINED_CONDITION,
            text=str(exc)
        )

        self.assertSequenceEqual(
            self.negotiate_sasl.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.t1,
                    unittest.mock.sentinel.p1,
                    base.metadata.sasl_providers,
                    negotiation_timeout=None,
                    jid=jid,
                    features=unittest.mock.sentinel.f1,
                ),
            ]
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger,
                )
                for i in range(3)
            ]
        )

    def test_uses_override_peer_before_connectors(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        override_peer = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2)
        ]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2, NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            override_peer=override_peer,
            loop=unittest.mock.sentinel.loop,
        ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger,
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_does_not_call_discover_connectors_if_overriden_peer_works(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c1.connect.side_effect = None
        base.c1.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        override_peer = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2)
        ]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2, NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            override_peer=override_peer,
            loop=unittest.mock.sentinel.loop,
        ))

        jid.domain.encode.assert_not_called()

        self.assertFalse(self.discover_connectors.mock_calls)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger
                )
                for i in range(2)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_aggregates_exceptions_and_raises_MultiOSError(self):
        NCONNECTORS = 3

        excs = [
            OSError(),
            OSError(),
            OSError(),
        ]

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            getattr(base, "c{}".format(i)).connect = connect

        base.c0.connect.side_effect = excs[0]
        base.c1.connect.side_effect = excs[1]
        base.c2.connect.side_effect = excs[2]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        with self.assertRaises(errors.MultiOSError) as exc_ctx:
            run_coroutine(node.connect_xmlstream(
                jid,
                base.metadata,
                loop=unittest.mock.sentinel.loop,
            ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger,
                )
                for i in range(3)
            ]
        )

        self.assertSequenceEqual(
            exc_ctx.exception.exceptions,
            excs,
        )

    def test_raises_most_specific_if_any_error_is_TLS_related(self):
        NCONNECTORS = 3

        excs = [
            OSError(),
            errors.TLSUnavailable(
                errors.StreamErrorCondition.POLICY_VIOLATION,
            ),
            errors.TLSFailure(
                errors.StreamErrorCondition.POLICY_VIOLATION,
            ),
        ]

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            getattr(base, "c{}".format(i)).connect = connect

        base.c0.connect.side_effect = excs[0]
        base.c1.connect.side_effect = excs[1]
        base.c2.connect.side_effect = excs[2]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        with self.assertRaisesRegex(
                errors.TLSFailure,
                r"TLS failure"):
            run_coroutine(node.connect_xmlstream(
                jid,
                base.metadata,
                loop=unittest.mock.sentinel.loop,
            ))

        jid.domain.encode.assert_not_called()

        self.discover_connectors.assert_called_with(
            jid.domain,
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                    base_logger=node.logger,
                )
                for i in range(3)
            ]
        )

    def test_handle_no_options(self):
        base = unittest.mock.Mock()

        jid = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            discover_connectors = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.node.discover_connectors",
                    new=CoroutineMock(),
                )
            )
            discover_connectors.return_value = []

            with self.assertRaisesRegex(
                    ValueError,
                    "no options to connect to XMPP domain .+"):
                run_coroutine(node.connect_xmlstream(
                    jid,
                    base.metadata,
                ))


class TestClient(xmltestutils.XMLTestCase):
    async def _connect_xmlstream(self, *args, **kwargs):
        self.connect_xmlstream_rec(*args, **kwargs)
        return None, self.xmlstream, self.features

    @staticmethod
    def _autoset_id(self):
        # self refers to a StanzaBase object!
        self.id_ = "autoset"

    @property
    def xmlstream(self):
        if self._xmlstream is None or self._xmlstream._exception:
            self._xmlstream = XMLStreamMock(self, loop=self.loop)
        return self._xmlstream

    def setUp(self):
        self.connect_xmlstream_rec = unittest.mock.MagicMock()
        self.failure_rec = unittest.mock.MagicMock()
        self.failure_rec.return_value = None
        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.suspended_rec = unittest.mock.MagicMock()
        self.suspended_rec.return_value = None
        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None

        self.security_layer = object()

        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.node.connect_xmlstream",
                                self._connect_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id)
        ]
        self.connect_xmlstream, _ = (patch.start()
                                     for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = nonza.StreamFeatures()
        self.features[...] = rfc6120.BindFeature()

        self.client = node.Client(
            self.test_jid,
            self.security_layer,
            max_initial_attempts=None,
            loop=self.loop)
        self.listener = make_listener(self.client)
        self.failure_rec = self.listener.on_failure
        self.destroyed_rec = self.listener.on_stream_destroyed
        self.established_rec = self.listener.on_stream_established
        self.suspended_rec = self.listener.on_stream_suspended

        # some XMLStreamMock test case parts
        self.sm_negotiation_exchange = [
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=XMLStreamMock.Receive(
                    nonza.SMEnabled(resume=True,
                                    id_="foobar")
                )
            )
        ]

        self.sm_without_resumption = [
            XMLStreamMock.Send(
                nonza.SMEnable(resume=False),
                response=XMLStreamMock.Receive(
                    nonza.SMEnabled(resume=False,
                                    id_="foobar")
                )
            )
        ]

        self.resource_binding = [
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid,
                        ),
                        type_=structs.IQType.RESULT,
                        id_="autoset"
                    )
                )
            )
        ]
        self.sm_request = [
            XMLStreamMock.Send(
                nonza.SMRequest()
            )
        ]

    def test_defaults(self):
        self.assertEqual(
            self.client.negotiation_timeout,
            timedelta(seconds=60)
        )
        self.assertEqual(
            self.client.local_jid.bare(),
            self.client.stream.local_jid
        )

    def test_setup(self):
        def peer_iterator():
            yield unittest.mock.sentinel.p1
            yield unittest.mock.sentinel.p2

        client = node.Client(
            self.test_jid,
            self.security_layer,
            override_peer=peer_iterator(),
            negotiation_timeout=timedelta(seconds=30)
        )
        self.assertEqual(client.local_jid, self.test_jid)
        self.assertEqual(
            client.negotiation_timeout,
            timedelta(seconds=30)
        )
        self.assertEqual(
            client.backoff_start,
            timedelta(seconds=1)
        )
        self.assertEqual(
            client.backoff_cap,
            timedelta(seconds=60)
        )
        self.assertEqual(
            client.backoff_factor,
            1.2
        )
        self.assertEqual(
            client.override_peer,
            [unittest.mock.sentinel.p1, unittest.mock.sentinel.p2],
        )

        self.assertEqual(client.on_stopped.logger,
                         client.logger.getChild("on_stopped"))
        self.assertEqual(client.on_failure.logger,
                         client.logger.getChild("on_failure"))
        self.assertEqual(client.on_stream_established.logger,
                         client.logger.getChild("on_stream_established"))
        self.assertEqual(client.on_stream_destroyed.logger,
                         client.logger.getChild("on_stream_destroyed"))

        self.assertIsInstance(
            client.stream._xxx_message_dispatcher,
            aioxmpp.dispatcher.SimpleMessageDispatcher,
        )

        self.assertIsInstance(
            client.stream._xxx_presence_dispatcher,
            aioxmpp.dispatcher.SimplePresenceDispatcher,
        )

        self.assertIsInstance(client.established_event, asyncio.Event)

        with self.assertRaises(AttributeError):
            client.local_jid = structs.JID.fromstr("bar@bar.example/baz")

    def test_monkeypatches_send_and_warns_on_use(self):
        client = node.Client(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=timedelta(seconds=30)
        )

        with contextlib.ExitStack() as stack:
            client_send = stack.enter_context(unittest.mock.patch.object(
                client,
                "send",
                new=CoroutineMock()
            ))

            with self.assertWarnsRegex(
                    DeprecationWarning,
                    r"send\(\) on StanzaStream is deprecated and "
                    r"will be removed in 1\.0. Use send\(\) on the Client "
                    r"instead."):
                run_coroutine(client.stream.send(
                    unittest.mock.sentinel.foo,
                    unittest.mock.sentinel.bar,
                    fnord=unittest.mock.sentinel.foo,
                ))

            client_send.assert_called_once_with(
                unittest.mock.sentinel.foo,
                unittest.mock.sentinel.bar,
                fnord=unittest.mock.sentinel.foo,
            )

    def test_monkeypatches_enqueue_and_warns_on_use(self):
        client = node.Client(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=timedelta(seconds=30)
        )

        with contextlib.ExitStack() as stack:
            client_enqueue = stack.enter_context(unittest.mock.patch.object(
                client,
                "enqueue",
                new=CoroutineMock()
            ))

            with self.assertWarnsRegex(
                    DeprecationWarning,
                    r"enqueue\(\) on StanzaStream is deprecated and "
                    r"will be removed in 1\.0. Use enqueue\(\) on the Client "
                    r"instead."):
                run_coroutine(client.stream.enqueue(
                    unittest.mock.sentinel.foo,
                    unittest.mock.sentinel.bar,
                    fnord=unittest.mock.sentinel.foo,
                ))

            client_enqueue.assert_called_once_with(
                unittest.mock.sentinel.foo,
                unittest.mock.sentinel.bar,
                fnord=unittest.mock.sentinel.foo,
            )

    def test_enqueue_raises_ConnectionError_if_not_valid(self):
        with contextlib.ExitStack() as stack:
            stream_enqueue = stack.enter_context(unittest.mock.patch.object(
                self.client.stream,
                "_enqueue",
            ))

            with self.assertRaisesRegex(ConnectionError,
                                        r"stream is not ready"):
                self.client.enqueue(unittest.mock.sentinel.stanza)

            stream_enqueue.assert_not_called()

    def test_enqueue_forwards_if_established(self):
        with contextlib.ExitStack() as stack:
            stream_enqueue = stack.enter_context(unittest.mock.patch.object(
                self.client.stream,
                "_enqueue",
            ))
            stream_enqueue.return_value = unittest.mock.sentinel.result

            self.client.established_event.set()

            result = self.client.enqueue(unittest.mock.sentinel.stanza,
                                         foo=unittest.mock.sentinel.kw1,
                                         bar=unittest.mock.sentinel.kw2)
            stream_enqueue.assert_called_once_with(
                unittest.mock.sentinel.stanza,
                foo=unittest.mock.sentinel.kw1,
                bar=unittest.mock.sentinel.kw2
            )
            self.assertEqual(
                result,
                unittest.mock.sentinel.result,
            )

    def test_send_blocks_for_established(self):
        with contextlib.ExitStack() as stack:
            # client needs to be running; fake it here (to avoid interference)
            self.client._main_task = asyncio.ensure_future(asyncio.sleep(1))
            stack.callback(self.client._main_task.cancel)

            stream_send = stack.enter_context(unittest.mock.patch.object(
                self.client.stream,
                "_send_immediately",
                new=CoroutineMock()
            ))
            stream_send.return_value = unittest.mock.sentinel.result

            send_task = asyncio.ensure_future(
                self.client.send(unittest.mock.sentinel.stanza,
                                 timeout=unittest.mock.sentinel.timeout,
                                 cb=unittest.mock.sentinel.cb)
            )

            run_coroutine(asyncio.sleep(0.1))

            stream_send.assert_not_called()

            self.client.established_event.set()

            result = run_coroutine(send_task)
            self.assertEqual(result, unittest.mock.sentinel.result)
            stream_send.assert_called_once_with(
                unittest.mock.sentinel.stanza,
                timeout=unittest.mock.sentinel.timeout,
                cb=unittest.mock.sentinel.cb
            )

        # ensure that the "main task" we faked above gets cancelled before the
        # tearDown runs (which would otherwise try to shut down the stream)
        run_coroutine(asyncio.sleep(0))

    def test_start(self):
        self.assertFalse(self.client.established)
        run_coroutine(asyncio.sleep(0))
        self.connect_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        self.connect_xmlstream_rec.assert_called_once_with(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger,
        )

    def test_start_with_override_peer(self):
        self.assertFalse(self.client.established)
        self.client.override_peer = [
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.p2,
        ]
        run_coroutine(asyncio.sleep(0))
        self.connect_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        self.connect_xmlstream_rec.assert_called_once_with(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=self.client.override_peer,
            loop=self.loop,
            logger=self.client.logger,
        )

    def test_reject_start_twice(self):
        self.client.start()
        with self.assertRaisesRegex(RuntimeError,
                                    "already running"):
            self.client.start()

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_stanza_stream_starts_and_stops_with_client(self):
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.stream.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.established)

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close()
        ]))
        self.assertFalse(self.client.stream.running)

    def test_stop(self):
        cb = unittest.mock.Mock()
        cb.return_value = False

        run_coroutine(asyncio.sleep(0))
        self.connect_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.established)
        self.assertTrue(self.client.running)

        self.client.on_stopped.connect(cb)

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))

        self.client.stop()
        self.assertSequenceEqual([], cb.mock_calls)

        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Close(),
            ],
        ))

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.established)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            cb.mock_calls
        )

        self.suspended_rec.assert_not_called()
        self.destroyed_rec.assert_called_once_with()

    def test_reconnect_on_failure(self):
        self.client.backoff_start = timedelta(seconds=0.008)
        self.client.negotiation_timeout = timedelta(seconds=0.01)
        self.client.start()

        iq = stanza.IQ(structs.IQType.GET)
        iq.autoset_id()

        async def stimulus():
            await self.client.established_event.wait()
            await self.client.enqueue(iq)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=ConnectionError()
                            ),
                        ]
                    ),
                ]
            )
        )

        run_coroutine(
            self.xmlstream.run_test(
                self.resource_binding
            )
        )

        run_coroutine(asyncio.sleep(0.015))

        self.assertTrue(self.client.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    negotiation_timeout=0.01,
                    override_peer=[],
                    loop=self.loop,
                    logger=self.client.logger)
            ]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        # the client has not failed
        self.assertFalse(self.failure_rec.mock_calls)
        self.assertTrue(self.client.established)

    def test_reconnect_on_failure_emits_suspended_resumed_pair(self):
        self.client.backoff_start = timedelta(seconds=0.008)
        self.client.negotiation_timeout = timedelta(seconds=0.01)
        self.client.start()

        iq = stanza.IQ(structs.IQType.GET)
        iq.autoset_id()

        async def stimulus():
            await self.client.established_event.wait()
            await self.client.enqueue(iq)

        self.assertFalse(self.client.suspended)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=ConnectionError()
                            ),
                        ]
                    ),
                ]
            )
        )

        self.listener.on_stream_suspended.assert_called_once_with(
            unittest.mock.ANY,
        )
        self.listener.on_stream_resumed.assert_not_called()
        self.assertTrue(self.client.suspended)

        run_coroutine(
            self.xmlstream.run_test(
                self.resource_binding
            )
        )

        run_coroutine(asyncio.sleep(0.015))

        self.listener.on_stream_resumed.assert_called_once_with()
        self.assertFalse(self.client.suspended)

        self.assertTrue(self.client.running)
        # the client has not failed
        self.assertFalse(self.failure_rec.mock_calls)
        self.assertTrue(self.client.established)

    def test_reconnect_on_failure_unbounded(self):
        self.client = node.Client(
            self.test_jid,
            self.security_layer,
            max_initial_attempts=2,
            loop=self.loop)
        self.client.on_failure.connect(self.failure_rec)
        self.client.on_stream_destroyed.connect(self.destroyed_rec)
        self.client.on_stream_established.connect(self.established_rec)
        self.client.on_stream_suspended.connect(self.suspended_rec)

        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger)

        self.client.backoff_start = timedelta(seconds=0.05)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=1)
        self.client.start()

        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)

        iq = stanza.IQ(structs.IQType.GET)
        iq.autoset_id()

        async def stimulus():
            await self.client.established_event.wait()
            await self.client.enqueue(iq)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=ConnectionError()
                            ),
                        ]
                    ),
                ]
            )
        )

        exc = OSError()
        self.connect_xmlstream_rec.side_effect = exc
        self.connect_xmlstream_rec.mock_calls.clear()

        run_coroutine(asyncio.sleep(0.075))

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.125))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.25))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.5))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(1.0), timeout=1.1)

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_emit_destroyed_on_reconnect_without_sm(self):
        stream_events = unittest.mock.Mock()
        stream_events.suspend.return_value = None
        stream_events.destroy.return_value = None
        self.client.on_stream_suspended.connect(stream_events.suspend)
        self.client.on_stream_destroyed.connect(stream_events.destroy)

        self.client.backoff_start = timedelta(seconds=0.008)
        self.client.negotiation_timeout = timedelta(seconds=0.01)
        self.client.start()

        reason = ConnectionError()

        iq = stanza.IQ(structs.IQType.GET)
        iq.autoset_id()

        async def stimulus():
            await self.client.established_event.wait()
            await self.client.enqueue(iq)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=reason
                            ),
                        ]
                    ),
                ]
            )
        )

        self.assertSequenceEqual(
            stream_events.mock_calls,
            [
                unittest.mock.call.suspend(reason),
                unittest.mock.call.destroy(),
            ]
        )

        run_coroutine(
            self.xmlstream.run_test(
                self.resource_binding
            )
        )

        run_coroutine(asyncio.sleep(0.015))

        self.assertTrue(self.client.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    negotiation_timeout=0.01,
                    override_peer=[],
                    loop=self.loop,
                    logger=self.client.logger)
            ]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        # the client has not failed
        self.assertFalse(self.failure_rec.mock_calls)
        self.assertTrue(self.client.established)

    def test_emit_suspend_on_double_reconnect_without_sm(self):
        stream_events = unittest.mock.Mock()
        stream_events.suspend.return_value = None
        stream_events.destroy.return_value = None
        self.client.on_stream_suspended.connect(stream_events.suspend)
        self.client.on_stream_destroyed.connect(stream_events.destroy)

        self.client.backoff_start = timedelta(seconds=0.008)
        self.client.negotiation_timeout = timedelta(seconds=0.01)
        self.client.start()

        reason = ConnectionError()

        iq = stanza.IQ(structs.IQType.GET)
        iq.autoset_id()

        async def stimulus():
            await self.client.established_event.wait()
            await self.client.enqueue(iq)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=reason
                            ),
                        ]
                    ),
                ]
            )
        )

        self.assertSequenceEqual(
            stream_events.mock_calls,
            [
                unittest.mock.call.suspend(reason),
                unittest.mock.call.destroy(),
            ]
        )

        run_coroutine(
            self.xmlstream.run_test(
                self.resource_binding
            )
        )

        run_coroutine(asyncio.sleep(0.015))

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=reason
                            ),
                        ]
                    ),
                ]
            )
        )

        self.assertSequenceEqual(
            stream_events.mock_calls,
            [
                unittest.mock.call.suspend(reason),
                unittest.mock.call.destroy(),
                unittest.mock.call.suspend(reason),
                unittest.mock.call.destroy(),
            ]
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_fail_on_authentication_failure(self):
        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(exc)
            ],
            self.failure_rec.mock_calls
        )

    def test_fail_on_stream_negotation_failure(self):
        exc = errors.StreamNegotiationFailure("undefined-condition")
        self.connect_xmlstream_rec.side_effect = exc
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(exc)
            ],
            self.failure_rec.mock_calls
        )

    def test_exponential_backoff_on_os_error(self):
        base_timeout = get_timeout(0.01)

        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger)

        exc = OSError()
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=base_timeout)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=base_timeout * 10)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 1.5))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 2))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 4))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 8))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_abort_after_max_initial_attempts(self):
        base_timeout = get_timeout(0.01)

        self.client = node.Client(
            self.test_jid,
            self.security_layer,
            max_initial_attempts=2,
            loop=self.loop)
        self.client.on_failure.connect(self.failure_rec)
        self.client.on_stream_destroyed.connect(self.destroyed_rec)
        self.client.on_stream_established.connect(self.established_rec)
        self.client.on_stream_suspended.connect(self.suspended_rec)

        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger)

        exc = OSError()
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=base_timeout)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=base_timeout * 10)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 1.5))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 2))

        self.failure_rec.assert_called_once_with(exc)
        self.assertFalse(self.client.running)

    def test_exponential_backoff_on_no_nameservers(self):
        base_timeout = get_timeout(0.01)

        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger)

        exc = dns.resolver.NoNameservers()
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=base_timeout)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=base_timeout * 10)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 1.5))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 2))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 4))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 8))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_exponential_backoff_on_SSL_error(self):
        base_timeout = get_timeout(0.01)

        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop,
            logger=self.client.logger)

        exc = OpenSSL.SSL.Error
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=base_timeout)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=base_timeout * 10)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 1.5))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 2))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 4))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 8))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(base_timeout * 10))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_fail_on_value_error_while_live(self):

        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))
        run_coroutine(asyncio.sleep(0))

        exc = ValueError()
        self.client._stream_failure(exc)
        run_coroutine(asyncio.sleep(0))
        self.failure_rec.assert_called_with(exc)

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

    def test_fail_on_conflict_stream_error_while_live(self):
        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))
        run_coroutine(asyncio.sleep(0))

        exc = errors.StreamError(
            condition=errors.StreamErrorCondition.CONFLICT
        )
        # stream would have been terminated normally, so we stop it manually
        # here
        self.client.stream._xmlstream_failed(exc)
        run_coroutine(asyncio.sleep(0))
        self.failure_rec.assert_called_with(exc)

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

        # the XML stream is closed by the StanzaStream
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close(),
        ]))

    def test_negotiate_stream_management(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            self.sm_negotiation_exchange
        ))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.stream.running)
        self.assertTrue(self.client.running)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_default_resumption_timeout(self):
        self.assertIsNone(self.client.resumption_timeout)

    def test_resumption_timeout_checks_type(self):
        with self.assertRaises(TypeError):
            self.client.resumption_timeout = 1.2
        with self.assertRaises(TypeError):
            self.client.resumption_timeout = "2"
        with self.assertRaises(TypeError):
            self.client.resumption_timeout = False
        with self.assertRaises(ValueError):
            self.client.resumption_timeout = -1
        self.client.resumption_timeout = None
        self.assertEqual(self.client.resumption_timeout, None)
        self.client.resumption_timeout = 1
        self.assertEqual(self.client.resumption_timeout, 1)

    def test_negotiate_stream_management_with_timeout_0(self):
        self.features[...] = nonza.StreamManagementFeature()
        self.client.resumption_timeout = 0

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            self.sm_without_resumption
        ))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.stream.running)
        self.assertTrue(self.client.running)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_negotiate_stream_management_with_specific_timeout(self):
        self.features[...] = nonza.StreamManagementFeature()
        self.client.resumption_timeout = 20

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding + [
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True, max_=20),
                    response=XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
                                        id_="foobar")
                    )
                )
            ]
        ))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.stream.running)
        self.assertTrue(self.client.running)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_negotiate_legacy_session(self):
        self.features[...] = rfc3921.SessionFeature()

        iqreq = stanza.IQ(type_=structs.IQType.SET)
        iqreq.payload = rfc3921.Session()
        iqreq.id_ = "autoset"

        iqresp = stanza.IQ(type_=structs.IQType.RESULT)
        iqresp.id_ = "autoset"

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            [
                XMLStreamMock.Send(
                    iqreq,
                )
            ],
        ))

        self.assertFalse(self.client.established)

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            stimulus=[
                XMLStreamMock.Receive(iqresp)
            ]
        ))

        run_coroutine(asyncio.sleep(0))

    def test_do_not_negotiate_legacy_session_if_optional(self):
        feature = rfc3921.SessionFeature()
        feature.optional = True
        self.features[...] = feature

        iqreq = stanza.IQ(type_=structs.IQType.SET)
        iqreq.payload = rfc3921.Session()
        iqreq.id_ = "autoset"

        iqresp = stanza.IQ(type_=structs.IQType.RESULT)
        iqresp.id_ = "autoset"

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding,
        ))

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(self.client.established)

    def test_negotiate_legacy_session_after_stream_management(self):
        self.features[...] = rfc3921.SessionFeature()
        self.features[...] = nonza.StreamManagementFeature()

        iqreq = stanza.IQ(type_=structs.IQType.SET)
        iqreq.payload = rfc3921.Session()
        iqreq.id_ = "autoset"

        iqresp = stanza.IQ(type_=structs.IQType.RESULT)
        iqresp.id_ = "autoset"

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            self.sm_negotiation_exchange +
            [
                XMLStreamMock.Send(
                    iqreq,
                    response=[
                        XMLStreamMock.Receive(iqresp),
                    ]
                ),
                XMLStreamMock.Send(
                    nonza.SMRequest(),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMAcknowledgement(counter=1)
                        ),
                    ]
                )
            ],
        ))

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(self.client.established)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=1)
            ),
            XMLStreamMock.Close()
        ]))

    def test_resume_stream_management(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        with contextlib.ExitStack() as stack:
            _resume_sm = stack.enter_context(
                unittest.mock.patch.object(self.client.stream, "_resume_sm"),
            )

            run_coroutine(self.xmlstream.run_test(self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
                                            id_="foobar"),
                        ),
                        XMLStreamMock.Fail(
                            exc=ConnectionError()
                        ),
                    ]
                ),
            ]))

            # new xmlstream here after failure
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

            _resume_sm.assert_called_once_with(0)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_stop_stream_management_if_remote_stops_providing_support(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
                                        id_="foobar"),
                    ),
                    XMLStreamMock.Fail(
                        exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure

        del self.features[nonza.StreamManagementFeature]

        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ]*2,
            self.established_rec.mock_calls
        )
        self.destroyed_rec.assert_called_once_with()

    def test_reconnect_at_advised_location_for_resumable_stream(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        with unittest.mock.patch("aioxmpp.connector.STARTTLSConnector") as C:
            C.return_value = unittest.mock.sentinel.connector
            run_coroutine(self.xmlstream.run_test([
            ]+self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(
                                resume=True,
                                id_="foobar",
                                location=(
                                    ipaddress.IPv6Address("fe80::"), 5222
                                )),
                        ),
                        XMLStreamMock.Fail(
                            exc=ConnectionError()
                        ),
                    ]
                ),
            ]))
            # new xmlstream after failure
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[],
                    negotiation_timeout=60.0,
                    loop=self.loop,
                    logger=self.client.logger),
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        ("fe80::", 5222, unittest.mock.sentinel.connector)
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop,
                    logger=self.client.logger),
            ],
            self.connect_xmlstream_rec.mock_calls
        )

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_sm_location_takes_precedence_over_override_peer(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()
        self.client.override_peer = [
            unittest.mock.sentinel.p1
        ]

        with unittest.mock.patch("aioxmpp.connector.STARTTLSConnector") as C:
            C.return_value = unittest.mock.sentinel.connector
            run_coroutine(self.xmlstream.run_test([
            ]+self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(
                                resume=True,
                                id_="foobar",
                                location=(
                                    ipaddress.IPv6Address("fe80::"), 5222
                                )),
                        ),
                        XMLStreamMock.Fail(
                            exc=ConnectionError()
                        ),
                    ]
                ),
            ]))
            # new xmlstream after failure
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Send(
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        unittest.mock.sentinel.p1,
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop,
                    logger=self.client.logger),
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        ("fe80::", 5222, unittest.mock.sentinel.connector),
                        unittest.mock.sentinel.p1,
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop,
                    logger=self.client.logger),
            ],
            self.connect_xmlstream_rec.mock_calls
        )

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_degrade_to_non_sm_if_sm_fails(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMFailed(),
                    ),
                ]
            ),
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.client.stream.sm_enabled)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_retry_sm_restart_if_sm_resumption_fails(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
                                        id_="foobar"),
                    ),
                    XMLStreamMock.Fail(
                        exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMResume(counter=0, previd="foobar"),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMFailed()
                    )
                ]
            ),
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
                                        id_="foobar"),
                    ),
                ]
            ),
        ]))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.running)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),  # stream established #1
                unittest.mock.call(),  # resumption failed, so new stream
            ],
            self.established_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(),  # resumption failed
            ],
            self.destroyed_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_fail_on_resource_binding_error(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        error=stanza.Error(
                            condition=aioxmpp.ErrorCondition.RESOURCE_CONSTRAINT,
                            text="too many resources",
                            type_=structs.ErrorType.CANCEL,
                        ),
                        type_=structs.IQType.ERROR,
                        id_="autoset"
                    )
                )
            ),
        ]))
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertEqual(
            1,
            len(self.failure_rec.mock_calls)
        )

        error_call, = self.failure_rec.mock_calls

        self.assertIsInstance(
            error_call[1][0],
            errors.StreamNegotiationFailure
        )

        self.assertFalse(self.established_rec.mock_calls)
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_resource_binding(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid.replace(
                                resource="foobarbaz"),
                        ),
                        type_=structs.IQType.RESULT,
                        id_="autoset",
                    )
                )
            )
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            self.test_jid.replace(resource="foobarbaz"),
            self.client.local_jid
        )

        self.assertEqual(
            self.test_jid.bare(),
            self.client.stream.local_jid
        )

        self.established_rec.assert_called_once_with()

    def test_resource_binding_with_different_jid(self):
        self.client.start()

        bound_jid = self.test_jid.replace(
            resource="foobarbaz",
            localpart="transfnordistan",
        )

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=bound_jid,
                        ),
                        type_=structs.IQType.RESULT,
                        id_="autoset",
                    )
                )
            )
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            bound_jid,
            self.client.local_jid
        )

        self.assertEqual(
            bound_jid.bare(),
            self.client.stream.local_jid
        )

        self.established_rec.assert_called_once_with()

    def test_stream_features_attribute(self):
        self.assertIsNone(self.client.stream_features)

        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid.replace(
                                resource="foobarbaz"),
                        ),
                        type_=structs.IQType.RESULT,
                        id_="autoset",
                    )
                )
            )
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertIs(
            self.features,
            self.client.stream_features
        )

    def test_signals_fire_correctly_on_fail_after_established_connection(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([]))

        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=[
                    XMLStreamMock.Receive(
                        stanza.IQ(
                            payload=rfc6120.Bind(
                                jid=self.test_jid,
                            ),
                            type_=structs.IQType.RESULT,
                            id_="autoset"
                        )
                    ),
                ]
            )
        ]))

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            stimulus=XMLStreamMock.Fail(exc=ConnectionError())
        ))

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.destroyed_rec.assert_called_once_with()
        self.assertFalse(self.client.established)

        # stop the client to avoid tearDown to wait for a close which isn’t
        # gonna happen
        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_signals_fire_correctly_on_fail_after_established_sm_connection(self):  # NOQA
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            self.sm_negotiation_exchange
        ))

        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Fail(exc=ConnectionError())
        ))

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.destroyed_rec.assert_called_once_with()

    def test_summon(self):
        svc_init = unittest.mock.Mock()

        class Svc1(service.Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        class Svc2(service.Service):
            ORDER_BEFORE = [Svc1]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        class Svc3(service.Service):
            ORDER_BEFORE = [Svc2]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        # account for already present services
        order = len(self.client._services)

        svc2 = self.client.summon(Svc2)

        self.assertSequenceEqual(
            svc_init.mock_calls,
            [
                unittest.mock.call.Svc3(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.Client"
                    ),
                    dependencies={},
                    service_order_index=order,
                ),
                unittest.mock.call.Svc2(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.Client"
                    ),
                    dependencies={Svc3: unittest.mock.ANY},
                    service_order_index=order+1,
                ),
            ],
        )

        self.assertIsInstance(
            svc2.dependencies[Svc3],
            Svc3,
        )

        svc_init.mock_calls.clear()

        self.client.summon(Svc3)

        self.assertSequenceEqual(
            [
            ],
            svc_init.mock_calls
        )

        svc_init.mock_calls.clear()

        svc1 = self.client.summon(Svc1)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc1(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.Client"
                    ),
                    dependencies={
                        Svc2: unittest.mock.ANY,
                    },
                    service_order_index=order+2,
                ),
            ],
            svc_init.mock_calls
        )

        self.assertIs(
            svc1.dependencies[Svc2],
            svc2,
        )

    def test_call_before_stream_established(self):
        async def coro():
            self.assertTrue(self.client.established_event.is_set())
            iq = stanza.IQ(
                type_=structs.IQType.SET,
            )
            await self.client.send(iq)

        self.client.before_stream_established.connect(coro)

        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.IQ(type_=structs.IQType.SET,
                          id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(type_=structs.IQType.RESULT,
                              id_="autoset")
                )
            ),
        ]))

    def test_connected(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected()

        UseConnected.assert_called_with(
            self.client,
            presence=aioxmpp.PresenceState(False),
        )

        self.assertEqual(result, UseConnected())

    def test_connected_kwargs(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected(
                foo="bar",
                fnord=10,
                presence=aioxmpp.PresenceState(True),
            )

        UseConnected.assert_called_with(
            self.client,
            foo="bar",
            fnord=10,
            presence=aioxmpp.PresenceState(True),
        )

        self.assertEqual(result, UseConnected())

    def test_send_aborts_with_ConnectionError_if_stopped_while_waiting(self):
        with contextlib.ExitStack() as stack:
            self.client.start()

            send_task = asyncio.ensure_future(self.client.send(stanza))

            run_coroutine(self.xmlstream.run_test(
                [
                    XMLStreamMock.Send(
                        stanza.IQ(
                            payload=rfc6120.Bind(
                                resource=self.test_jid.resource),
                            type_=structs.IQType.SET,
                            id_="autoset"),
                    )
                ]
            ))
            self.assertTrue(self.client.running)
            self.assertFalse(self.client.established)

            self.assertFalse(send_task.done())

            self.client.stop()

            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Close()
            ]))

            self.assertFalse(self.client.running)
            self.listener.on_stopped.assert_called_once_with()

            run_coroutine(asyncio.sleep(0))

            self.assertTrue(send_task.done())

            with self.assertRaisesRegex(
                    ConnectionError,
                    r"client shut down by user request"):
                run_coroutine(send_task)

    def test_send_raises_ConnectionError_on_failure(self):
        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc

        with contextlib.ExitStack() as stack:
            send_task = asyncio.ensure_future(self.client.send(stanza))
            # exploiting here that the coroutine will start on the next
            # schedule; otherwise, client stops too early
            self.client.start()

            self.assertTrue(self.client.running)

            with self.assertRaises(Exception):
                run_coroutine(self.client.on_failure.future())

            self.assertFalse(self.client.running)

            self.listener.on_failure.assert_called_once_with(unittest.mock.ANY)

            run_coroutine(asyncio.sleep(0))

            self.assertTrue(send_task.done())

            with self.assertRaisesRegex(
                    ConnectionError,
                    r"client failed to connect"):
                run_coroutine(send_task)

    def test_send_raises_ConnectionError_if_not_running(self):
        with self.assertRaisesRegex(ConnectionError,
                                    "client is not running"):
            run_coroutine(self.client.send(unittest.mock.sentinel.stanza))

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        if self.client.running:
            self.client.stop()
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Close()
            ]))
        run_coroutine(self.xmlstream.run_test([
        ]))


class TestPresenceManagedClient(xmltestutils.XMLTestCase):
    async def _connect_xmlstream(self, *args, **kwargs):
        self.connect_xmlstream_rec(*args, **kwargs)
        return None, self.xmlstream, self.features

    @staticmethod
    def _autoset_id(self):
        # self refers to a StanzaBase object!
        self.id_ = "autoset"

    @property
    def xmlstream(self):
        if self._xmlstream is None or self._xmlstream._exception:
            self._xmlstream = XMLStreamMock(self, loop=self.loop)
        return self._xmlstream

    def setUp(self):
        self.connect_xmlstream_rec = unittest.mock.MagicMock()
        self.failure_rec = unittest.mock.MagicMock()
        self.failure_rec.return_value = None
        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None
        self.presence_sent_rec = unittest.mock.MagicMock()
        self.presence_sent_rec.return_value = None
        self.security_layer = object()

        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.node.connect_xmlstream",
                                self._connect_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id),
        ]
        self.connect_xmlstream, _ = (patch.start()
                                     for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = nonza.StreamFeatures()
        self.features[...] = rfc6120.BindFeature()

        self.client = node.PresenceManagedClient(
            self.test_jid,
            self.security_layer,
            loop=self.loop)
        self.client.on_failure.connect(self.failure_rec)
        self.client.on_stream_destroyed.connect(self.destroyed_rec)
        self.client.on_stream_established.connect(self.established_rec)
        self.client.on_presence_sent.connect(self.presence_sent_rec)

        self.resource_binding = [
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_=structs.IQType.SET,
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid,
                        ),
                        type_=structs.IQType.RESULT,
                        id_="autoset"
                    )
                )
            )
        ]

    def _set_stream_established(self):
        self.client.established_event.set()
        run_coroutine(self.client.before_stream_established())
        self.client.on_stream_established()

    def test_setup(self):
        self.assertEqual(
            structs.PresenceState(),
            self.client.presence
        )

    def test_change_presence_to_available(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.CHAT)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.CHAT,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.CHAT,
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_change_presence_while_available(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.CHAT)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.CHAT,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.CHAT,
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.AWAY)

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.AWAY,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.AWAY,
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_change_presence_to_unavailable(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.CHAT)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.CHAT,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.CHAT,
                                    id_="autoset")
                )
            )
        ]))

        self.client.presence = structs.PresenceState()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close(),
            # this is a race-condition of the test suite
            # in a real stream, the Send would not happen as the stream
            # changes state immediately and raises an exception from
            # send_xso
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                                id_="autoset"),
            ),
        ]))

        self.assertFalse(self.client.running)

        self.presence_sent_rec.assert_called_once_with()

    def test_do_not_send_presence_twice_if_changed_while_establishing(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.CHAT)
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.established)

        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.DND)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.DND,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.DND,
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_do_not_send_presence_if_unavailable(self):
        self.client.presence = structs.PresenceState(
            available=False
        )

        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.established)

        run_coroutine(
            self.xmlstream.run_test(self.resource_binding)
        )

        run_coroutine(asyncio.sleep(0.1))

        self.presence_sent_rec.assert_called_once_with()

    def test_re_establish_on_presence_rewrite_if_disconnected(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show=structs.PresenceShow.CHAT)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.CHAT,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.CHAT,
                                    id_="autoset")
                )
            ),
        ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ],
            self.presence_sent_rec.mock_calls
        )
        self.presence_sent_rec.reset_mock()

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close()
        ]))

        self.assertFalse(self.client.running)

        self.client.presence = self.client.presence

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.CHAT,
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                    show=structs.PresenceShow.CHAT,
                                    id_="autoset")
                )
            ),
        ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ],
            self.presence_sent_rec.mock_calls
        )
        self.presence_sent_rec.reset_mock()

    def test_set_presence_with_texts(self):
        status_texts = {
            None: "generic",
            structs.LanguageTag.fromstr("de"): "de"
        }

        expected = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                   show=structs.PresenceShow.CHAT,
                                   id_="autoset")
        expected.status.update(status_texts)

        base = unittest.mock.Mock()
        base.send = CoroutineMock()

        def start_side_effect():
            # fake client to be running
            self.client._main_task = asyncio.ensure_future(asyncio.sleep(10))
            stack.callback(self.client._main_task.cancel)

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "send",
                new=base.send
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))
            base.start.side_effect = start_side_effect

            self.client.set_presence(
                structs.PresenceState(
                    available=True,
                    show=structs.PresenceShow.CHAT),
                status=status_texts
            )

            self._set_stream_established()

        # make fake main task die
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.send(unittest.mock.ANY)
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_with_single_string(self):
        expected = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                   show=structs.PresenceShow.CHAT,
                                   id_="autoset")
        expected.status[None] = "foobar"

        base = unittest.mock.Mock()
        base.send = CoroutineMock()

        def start_side_effect():
            # fake client to be running
            self.client._main_task = asyncio.ensure_future(asyncio.sleep(10))
            stack.callback(self.client._main_task.cancel)

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "send",
                new=base.send
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))
            base.start.side_effect = start_side_effect

            self.client.set_presence(
                structs.PresenceState(
                    available=True,
                    show=structs.PresenceShow.CHAT),
                status="foobar"
            )

            self._set_stream_established()

        # make fake main task die
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.send(unittest.mock.ANY)
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_through_server(self):
        expected = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                   show=structs.PresenceShow.CHAT,
                                   id_="autoset")
        expected.status[None] = "foobar"

        base = unittest.mock.Mock()
        base.send = CoroutineMock()

        def start_side_effect():
            # fake client to be running
            self.client._main_task = asyncio.ensure_future(asyncio.sleep(10))
            stack.callback(self.client._main_task.cancel)

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "send",
                new=base.send
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))
            base.start.side_effect = start_side_effect

            server = self.client.summon(aioxmpp.PresenceServer)

            server.set_presence(
                structs.PresenceState(
                    available=True,
                    show=structs.PresenceShow.CHAT),
                status="foobar"
            )

            self._set_stream_established()

        # ensure that fake main task dies
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.send(
                    unittest.mock.ANY
                )
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_connected(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected()

        UseConnected.assert_called_with(self.client)

        self.assertEqual(result, UseConnected())

    def test_connected_kwargs(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected(foo="bar", fnord=10)

        UseConnected.assert_called_with(
            self.client,
            foo="bar",
            fnord=10,
        )

        self.assertEqual(result, UseConnected())

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        if self.client.running:
            self.client.stop()
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Close()
            ]))
        run_coroutine(self.xmlstream.run_test([
        ]))


class TestUseConnected(unittest.TestCase):
    def setUp(self):
        self.presence_server = unittest.mock.Mock()
        self.presence_server.state = aioxmpp.PresenceState(False)
        self.presence_server.status = {}
        self.presence_server.priority = 0
        self.client = make_connected_client()
        self.client.established = False
        self.client.mock_services[aioxmpp.PresenceServer] = \
            self.presence_server
        self.client.established = False
        self.client.running = False

        self.cm = node.UseConnected(
            self.client,
            presence=aioxmpp.PresenceState(False),
        )

    def tearDown(self):
        del self.cm

    def test_aenter_listens_to_on_stream_established_to_detect_success(self):
        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.assertFalse(task.done(), task)

        self.client.on_stream_established()

        self.assertEqual(run_coroutine(task), self.client.stream)

    def test_aenter_listens_to_on_failure_to_detect_failure(self):
        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.assertFalse(task.done(), task)

        exc = Exception()

        self.client.on_failure(exc)

        with self.assertRaises(Exception) as ctx:
            run_coroutine(task)

        self.assertIs(ctx.exception, exc)

    def test_aenter_calls_start_if_client_not_running(self):
        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.client.start.assert_called_once_with()
        self.client.stop.assert_not_called()

        task.cancel()

    def test_aenter_does_not_call_start_but_waits_if_not_established(self):
        self.client.running = True

        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.client.start.assert_not_called()

        self.assertFalse(task.done())

        self.client.on_stream_established()

        self.assertEqual(run_coroutine(task), self.client.stream)

    def test_aenter_does_not_block_if_established(self):
        self.client.running = True
        self.client.established = True

        self.assertEqual(
            run_coroutine(self.cm.__aenter__()),
            self.client.stream,
        )

    def test_aenter_raises_TimeoutError_on_timeout(self):
        self.cm = node.UseConnected(
            self.client,
            presence=aioxmpp.PresenceState(False),
            timeout=timedelta(seconds=0.01),
        )

        with self.assertRaises(TimeoutError):
            run_coroutine(self.cm.__aenter__())

        self.client.start.assert_called_once_with()
        self.client.stop.assert_called_once_with()

    def test_aenter_does_not_set_presence_by_default(self):
        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.presence_server.set_presence.assert_not_called()

        task.cancel()

    def test_aenter_sets_presence_if_not_unavailable(self):
        p = unittest.mock.Mock(spec=aioxmpp.PresenceState)
        p.available = True

        self.cm = node.UseConnected(
            self.client,
            presence=p,
        )

        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.presence_server.set_presence.assert_called_once_with(p)

        task.cancel()

    def test_aenter_sets_presence_on_established_stream(self):
        p = unittest.mock.Mock(spec=aioxmpp.PresenceState)
        p.available = True

        self.client.established = True
        self.client.running = True

        self.cm = node.UseConnected(
            self.client,
            presence=p,
        )

        task = asyncio.ensure_future(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.1))

        self.presence_server.set_presence.assert_called_once_with(p)

        task.cancel()

    def test_aexit_stops_client_waits_for_on_stopped(self):
        self.client.established = True
        self.client.running = True

        task = asyncio.ensure_future(self.cm.__aexit__(None, None, None))
        run_coroutine(asyncio.sleep(0.01))

        self.assertFalse(task.done(), task)
        self.client.stop.assert_called_once_with()

        self.client.on_stopped()

        self.assertFalse(run_coroutine(task))

    def test_aexit_stops_client_waits_for_on_failure_and_swallows_exception(self):  # NOQA
        self.client.established = True
        self.client.running = True

        task = asyncio.ensure_future(self.cm.__aexit__(None, None, None))
        run_coroutine(asyncio.sleep(0.01))

        self.assertFalse(task.done(), task)
        self.client.stop.assert_called_once_with()

        self.client.on_failure(Exception())

        self.assertFalse(run_coroutine(task))

    def test_aexit_does_not_wait_if_client_is_not_running(self):
        run_coroutine(self.cm.__aexit__(None, None, None))

    def test_construction_with_available_presence_warns(self):
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"using an available presence state for UseConnected is "
                r"deprecated and will raise ValueError as of 1.0"):
            node.UseConnected(self.client)

    def test_construction_with_unavailable_presence_does_not_warn(self):
        with unittest.mock.patch("warnings.warn") as warn:
            node.UseConnected(
                self.client,
                presence=aioxmpp.PresenceState(False)
            )

        warn.assert_not_called()

    def test_access_on_timeout_attribute_warns(self):
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"the timeout attribute is deprecated and will be removed "
                r"in 1.0"):
            self.assertIsNone(self.cm.timeout)

        with self.assertWarnsRegex(
                DeprecationWarning,
                r"the timeout attribute is deprecated and will be removed "
                r"in 1.0"):
            self.cm.timeout = timedelta(seconds=0.01)

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(self.cm.timeout, timedelta(seconds=0.01))

    def test_access_on_presence_attribute_warns(self):
        with self.assertWarnsRegex(
                DeprecationWarning,
                r"the presence attribute is deprecated and will be removed "
                r"in 1.0"):
            self.assertEqual(
                self.cm.presence,
                aioxmpp.PresenceState(False),
            )

        with self.assertWarnsRegex(
                DeprecationWarning,
                r"the presence attribute is deprecated and will be removed "
                r"in 1.0"):
            self.cm.presence = aioxmpp.PresenceState(True)

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(
                self.cm.presence,
                aioxmpp.PresenceState(True)
            )
