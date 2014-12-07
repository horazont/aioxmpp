import collections
import random
import unittest

import dns

import asyncio_xmpp.network as network

MockSRVRecord = collections.namedtuple(
    "MockRecord",
    [
        "priority",
        "weight",
        "target",
        "port"
    ])

class MockResolver:
    def __init__(self, tester):
        self.actions = []
        self.tester = tester

    def _get_key(self, qname, rdtype, rdclass, tcp):
        result = (qname, rdtype, rdclass)
        if self._strict_tcp:
            result = result + (bool(tcp),)
        return result

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
            key, next_key,
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
