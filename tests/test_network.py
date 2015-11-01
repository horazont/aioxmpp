import asyncio
import collections
import random
import unittest
import unittest.mock

import dns
import dns.flags

import aioxmpp.network as network

from aioxmpp.testutils import (
    run_coroutine
)


MockSRVRecord = collections.namedtuple(
    "MockRecord",
    [
        "priority",
        "weight",
        "target",
        "port"
    ])

MockTLSARecord = collections.namedtuple(
    "MockRecord",
    [
        "usage",
        "selector",
        "mtype",
        "cert"
    ])

_MockMessage = collections.namedtuple(
    "MockMessage",
    [
        "flags",
    ])


class MockMessage(_MockMessage):
    def __new__(cls, flags=0):
        return _MockMessage.__new__(cls, flags)


class MockAnswer:
    def __init__(self, records, **kwargs):
        self.records = records
        self.response = MockMessage(**kwargs)

    def __iter__(self):
        return iter(self.records)


class MockResolver:
    def __init__(self, tester):
        self.actions = []
        self.tester = tester
        self._flags = None

    def _get_key(self, qname, rdtype, rdclass, tcp):
        result = (qname, rdtype, rdclass)
        if self._strict_tcp:
            result = result + (bool(tcp),)
        if self._flags is not None:
            result += (self._flags,)
        return result

    def set_flags(self, flags):
        self._flags = flags

    def define_actions(self, action_sequence, strict_tcp=True):
        self._strict_tcp = strict_tcp
        self.actions[:] = action_sequence

    def query(self, qname, rdtype=1, rdclass=1, tcp=False,
              raise_on_no_answer=True, **kwargs):
        if kwargs:
            raise TypeError("Invalid arguments to mock resolver: {}".format(
                ", ".join(kwargs.keys())))

        self.tester.assertTrue(
            self.actions,
            "Unexpected client action (no actions left)")

        key = self._get_key(qname, rdtype, rdclass, tcp)

        next_key, response = self.actions.pop(0)
        self.tester.assertEqual(
            next_key,
            key,
            "Client action mismatch")
        if isinstance(response, Exception):
            raise response

        if raise_on_no_answer and not response:
            raise dns.resolver.NoAnswer()

        return response


class Testlookup_srv(unittest.TestCase):
    def setUp(self):
        self.resolver = MockResolver(self)

    def test_simple_lookup(self):
        records = [
            MockSRVRecord(0, 1, "xmpp.foo.test.", 5222),
            MockSRVRecord(2, 1, "xmpp.bar.test.", 5222),
        ]

        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                records
            )
        ])

        self.assertSequenceEqual(
            [
                (0, 1, ("xmpp.foo.test", 5222)),
                (2, 1, ("xmpp.bar.test", 5222)),
            ],
            network.lookup_srv(b"foo.test.", b"xmpp-client",
                               resolver=self.resolver)
        )

    def test_fallback_to_tcp(self):
        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                dns.resolver.Timeout()
            ),
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    True
                ),
                dns.resolver.Timeout()
            )
        ])

        with self.assertRaises(TimeoutError):
            network.lookup_srv(b"foo.test.", b"xmpp-client",
                               nattempts=2,
                               resolver=self.resolver)

    def test_handle_no_answer(self):
        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                dns.resolver.NoAnswer()
            ),
        ])

        self.assertIsNone(
            network.lookup_srv(b"foo.test.", b"xmpp-client",
                               resolver=self.resolver)
        )

    def test_handle_nxdomain(self):
        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                dns.resolver.NXDOMAIN()
            ),
        ])

        self.assertIsNone(
            network.lookup_srv(b"foo.test.", b"xmpp-client",
                               resolver=self.resolver)
        )

    def test_handle_service_disabled(self):
        records = [
            MockSRVRecord(0, 0, ".", 0)
        ]

        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.foo.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                records
            ),
        ])

        with self.assertRaisesRegexp(ValueError,
                                     "Protocol explicitly not supported"):
            network.lookup_srv(b"foo.test.", b"xmpp-client",
                               resolver=self.resolver)

    def test_unicode(self):
        records = [
            MockSRVRecord(0, 1, "xmpp.foo.test.", 5222),
            MockSRVRecord(2, 1, "xmpp.bar.test.", 5222),
        ]

        self.resolver.define_actions([
            (
                (
                    "_xmpp-client._tcp.xn--nicde-lua2b.test.",
                    dns.rdatatype.SRV,
                    dns.rdataclass.IN,
                    False
                ),
                records
            )
        ])

        self.assertSequenceEqual(
            [
                (0, 1, ("xmpp.foo.test", 5222)),
                (2, 1, ("xmpp.bar.test", 5222)),
            ],
            network.lookup_srv("ünicöde.test.".encode("IDNA"),
                               b"xmpp-client",
                               resolver=self.resolver)
        )

    def tearDown(self):
        del self.resolver


class Testlookup_tlsa(unittest.TestCase):
    def setUp(self):
        self.resolver = MockResolver(self)

    def test_require_ad(self):
        records = [
            MockTLSARecord(3, 0, 1, b"foo"),
        ]

        self.resolver.define_actions([
            (
                (
                    "_5222._tcp.xmpp.foo.test.",
                    dns.rdatatype.TLSA,
                    dns.rdataclass.IN,
                    False,
                    dns.flags.AD | dns.flags.RD
                ),
                MockAnswer(
                    records,
                    flags=dns.flags.AD
                )
            )
        ])

        self.assertSequenceEqual(
            [
                (3, 0, 1, b"foo"),
            ],
            network.lookup_tlsa("xmpp.foo.test.".encode("IDNA"),
                                5222,
                                resolver=self.resolver)
        )

    def tearDown(self):
        del self.resolver


class Testgroup_and_order_srv_records(unittest.TestCase):
    def _test_monte_carlo_ex(self, hosts, records, N=100):
        rng = random.Random()
        rng.seed(1234)

        host_map = {
            host: collections.Counter()
            for host in hosts
        }

        sum_of_weights = sum(weight for _, weight, _ in records)
        for i in range(0, sum_of_weights*N):
            result = network.group_and_order_srv_records(records, rng=rng)

            for i, host in enumerate(result):
                host_map[host][i] += 1

        return {
            host: {
                index: round(indicies[index]/(N*sum_of_weights), 2)
                for index in range(0, len(records))
            }
            for host, indicies in host_map.items()
        }

    def _test_monte_carlo(self, weights, **kwargs):
        hosts = tuple(i for i, _ in enumerate(weights))
        records = [
            (0, weight, host)
            for host, weight in zip(hosts, weights)
        ]
        return self._test_monte_carlo_ex(hosts, records, **kwargs)

    def test_one_record_with_zero_weight(self):
        h1 = (1,)

        records = [
            (0, 0, h1),
        ]

        self.assertSequenceEqual(
            [h1],
            list(network.group_and_order_srv_records(records))
        )

    def test_zero_weight_mixed(self):
        host_chances = self._test_monte_carlo([0, 0, 5])

        # these values are pretty random

        # note however that the first record always has a much higher chance of
        # being picked
        # the second needs TWO consecutive zeros to get elected to the top,
        # which has a chance in the order of 1/W², with W being the total
        # weight, assuming a equally distributed RNG.
        self.assertEqual(
            0.15,
            host_chances[0][0]
        )

        self.assertEqual(
            0.0,
            host_chances[1][0]
        )

        self.assertEqual(
            0.85,
            host_chances[2][0]
        )

    def test_picking_from_two(self):
        host_chances = self._test_monte_carlo([10, 20])

        self.assertEqual(
            0.35,
            host_chances[0][0]
        )
        self.assertEqual(
            0.65,
            host_chances[0][1]
        )

        # the other host is implied in the values above

    def test_group_by_priority(self):
        hosts = tuple(range(3))

        records = [
            (0, 0, hosts[0]),
            (1, 0, hosts[1]),
            (2, 0, hosts[2]),
        ]

        self.assertSequenceEqual(
            hosts,
            list(network.group_and_order_srv_records(records))
        )

    def test_group_by_priority_with_weight(self):
        hosts = tuple(range(4))

        records = [
            (0, 10, hosts[0]),
            (0, 10, hosts[1]),
            (1, 10, hosts[2]),
            (1, 10, hosts[3]),
        ]

        host_chances = self._test_monte_carlo_ex(hosts, records)

        self.assertEqual(
            0.51,
            host_chances[0][0])
        self.assertEqual(
            0.49,
            host_chances[0][1])
        self.assertEqual(
            0.0,
            host_chances[0][2])
        self.assertEqual(
            0.0,
            host_chances[0][3])

        self.assertEqual(
            0.49,
            host_chances[1][0])
        self.assertEqual(
            0.51,
            host_chances[1][1])
        self.assertEqual(
            0.0,
            host_chances[1][2])
        self.assertEqual(
            0.0,
            host_chances[1][3])

        self.assertEqual(
            0.0,
            host_chances[2][0])
        self.assertEqual(
            0.0,
            host_chances[2][1])
        self.assertEqual(
            0.51,
            host_chances[2][2])
        self.assertEqual(
            0.49,
            host_chances[2][3])

        self.assertEqual(
            0.0,
            host_chances[3][0])
        self.assertEqual(
            0.0,
            host_chances[3][1])
        self.assertEqual(
            0.49,
            host_chances[3][2])
        self.assertEqual(
            0.51,
            host_chances[3][3])


class Testfind_xmpp_host_addr(unittest.TestCase):
    def test_returns_items_if_available(self):
        base = unittest.mock.Mock()

        nattempts = object()
        items = object()

        with unittest.mock.patch(
                "aioxmpp.network.lookup_srv",
                new=base.lookup_srv) as lookup_srv:
            lookup_srv.return_value = items

            result = run_coroutine(network.find_xmpp_host_addr(
                asyncio.get_event_loop(),
                base.domain,
                attempts=nattempts
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.domain.encode("IDNA"),
                unittest.mock.call.lookup_srv(
                    service=b"xmpp-client",
                    domain=base.domain.encode(),
                    nattempts=nattempts
                )
            ]
        )

        self.assertIs(result, items)

    def test_creates_fake_srv_if_no_srvs_available(self):
        base = unittest.mock.Mock()

        nattempts = object()
        items = object()

        with unittest.mock.patch(
                "aioxmpp.network.lookup_srv",
                new=base.lookup_srv) as lookup_srv:
            lookup_srv.return_value = None

            result = run_coroutine(network.find_xmpp_host_addr(
                asyncio.get_event_loop(),
                base.domain,
                attempts=nattempts
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.domain.encode("IDNA"),
                unittest.mock.call.lookup_srv(
                    service=b"xmpp-client",
                    domain=base.domain.encode(),
                    nattempts=nattempts
                )
            ]
        )

        self.assertSequenceEqual(
            result,
            [
                (0, 0, (base.domain.encode(), 5222)),
            ]
        )

    def test_propagates_OSError_from_lookup_srv(self):
        base = unittest.mock.Mock()

        nattempts = object()
        items = object()

        with unittest.mock.patch(
                "aioxmpp.network.lookup_srv",
                new=base.lookup_srv) as lookup_srv:
            lookup_srv.side_effect = OSError()

            with self.assertRaises(OSError):
                run_coroutine(network.find_xmpp_host_addr(
                    asyncio.get_event_loop(),
                    base.domain,
                    attempts=nattempts
                ))

    def test_propagates_ValueError_from_lookup_srv(self):
        base = unittest.mock.Mock()

        nattempts = object()
        items = object()

        with unittest.mock.patch(
                "aioxmpp.network.lookup_srv",
                new=base.lookup_srv) as lookup_srv:
            lookup_srv.side_effect = ValueError()

            with self.assertRaises(ValueError):
                run_coroutine(network.find_xmpp_host_addr(
                    asyncio.get_event_loop(),
                    base.domain,
                    attempts=nattempts
                ))
