########################################################################
# File name: test_network.py
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
import collections
import concurrent.futures
import random
import unittest
import unittest.mock

import dns
import dns.flags

import aioxmpp.network as network

from aioxmpp.testutils import (
    run_coroutine,
    CoroutineMock
)


class Testthreadlocal_resolver_instance(unittest.TestCase):
    def test_get_resolver_returns_Resolver_instance(self):
        self.assertIsInstance(
            network.get_resolver(),
            dns.resolver.Resolver,
        )

    def test_get_resolver_returns_consistent_Resolver_instance(self):
        i1 = network.get_resolver()
        i2 = network.get_resolver()

        self.assertIs(i1, i2)

    def test_get_resolver_is_not_dnspython_default_resolver(self):
        self.assertIsNot(
            network.get_resolver(),
            dns.resolver.get_default_resolver(),
        )

    def test_get_resolver_is_thread_local(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            fut = executor.submit(network.get_resolver)
            done, waiting = concurrent.futures.wait([fut])
            self.assertSetEqual(done, {fut})
            i1 = fut.result()
        i2 = network.get_resolver()
        self.assertIsNot(i1, i2)

    def test_reconfigure_resolver(self):
        with unittest.mock.patch("dns.resolver.Resolver") as Resolver:
            network.reconfigure_resolver()

        Resolver.assert_called_with()

        self.assertEqual(network.get_resolver(), Resolver())

    def test_set_resolver(self):
        network.set_resolver(unittest.mock.sentinel.resolver)
        self.assertIs(
            network.get_resolver(),
            unittest.mock.sentinel.resolver,
        )

    def test_reconfigure_resolver_works_after_set_resolver(self):
        network.set_resolver(unittest.mock.sentinel.resolver)
        with unittest.mock.patch("dns.resolver.Resolver") as Resolver:
            network.reconfigure_resolver()

        Resolver.assert_called_with()

        self.assertEqual(network.get_resolver(), Resolver())


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
    def __init__(self, tester, actions=[]):
        self.actions = list(actions)
        self.tester = tester
        self.nameservers = ["10.0.0.1"]
        self._flags = None

    def _get_key(self, qname, rdtype, rdclass, tcp):
        result = (qname, rdtype, rdclass)
        if self._strict_tcp:
            result = result + (bool(tcp),)
        if self._flags is not None:
            result += (self._flags,)
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            return
        self.finalize()

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

    def finalize(self):
        self.tester.assertSequenceEqual(
            self.actions,
            [],
            "client did not execute all actions",
        )


class Testrepeated_query(unittest.TestCase):
    def setUp(self):
        self.tlr = MockResolver(self)
        base = unittest.mock.Mock()
        self.base = base
        self.run_in_executor = unittest.mock.Mock()

        @asyncio.coroutine
        def run_in_executor(executor, func, *args):
            self.run_in_executor(executor, func, *args)
            return func(*args)

        self.patches = [
            unittest.mock.patch(
                "aioxmpp.network.get_resolver",
                new=base.get_resolver,
            ),
            unittest.mock.patch(
                "aioxmpp.network.reconfigure_resolver",
                new=base.reconfigure_resolver,
            ),
            unittest.mock.patch.object(
                asyncio.get_event_loop(),
                "run_in_executor",
                new=run_in_executor
            )
        ]

        self.answer = MockAnswer([])

        # ensure consistent state
        network.reconfigure_resolver()

        for patch in self.patches:
            patch.start()

        base.get_resolver.return_value = self.tlr

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

        # ensure consistent state
        network.reconfigure_resolver()

    def test_reject_non_positive_number_of_attempts(self):
        with self.assertRaisesRegex(
                ValueError,
                "query cannot succeed with non-positive amount of attempts"):
            run_coroutine(network.repeated_query(
                unittest.mock.sentinel.name,
                unittest.mock.sentinel.rdtype,
                nattempts=0))

    def test_use_resolver_from_arguments(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer
            )
        ])

        with resolver:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                resolver=resolver,
            ))

        self.assertIs(
            result,
            self.answer,
        )

        self.assertSequenceEqual(self.base.mock_calls, [])

    def test_run_query_in_executor(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer
            )
        ])

        with resolver:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                resolver=resolver,
                executor=unittest.mock.sentinel.executor
            ))

        self.assertIs(
            result,
            self.answer,
        )

        self.assertIn(
            unittest.mock.call(
                unittest.mock.sentinel.executor,
                unittest.mock.ANY,
            ),
            self.run_in_executor.mock_calls,
        )

    def test_run_query_in_default_executor_by_default(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer
            )
        ])

        with resolver:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                resolver=resolver,
            ))

        self.assertIs(
            result,
            self.answer,
        )

        self.run_in_executor.assert_called_with(
            None,
            unittest.mock.ANY,
        )

    def test_retry_with_tcp_on_first_timeout_with_fixed_resolver(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout()
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    True,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer,
            )
        ])

        with resolver:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                resolver=resolver,
            ))

        self.assertIs(
            result,
            self.answer,
        )

        self.assertSequenceEqual(self.base.mock_calls, [])

    def test_retry_up_to_2_times_with_fixed_resolver(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout()
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    True,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout()
            ),
        ])

        with resolver:
            with self.assertRaises(TimeoutError):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                    resolver=resolver,
                ))

        self.assertSequenceEqual(self.base.mock_calls, [])

    def test_use_thread_local_resolver(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer,
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
            ))

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.get_resolver(),
            ]
        )

        self.assertIs(
            result,
            self.answer,
        )

    def test_reconfigure_resolver_after_first_timeout(self):
        def reconfigure():
            self.tlr.set_flags(None)
            self.tlr.define_actions([
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        False,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    self.answer,
                )
            ])

        self.base.reconfigure_resolver.side_effect = reconfigure

        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout(),
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
            ))

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.get_resolver(),
                unittest.mock.call.reconfigure_resolver(),
                unittest.mock.call.get_resolver(),
            ]
        )

        self.assertIs(
            result,
            self.answer,
        )

    def test_use_tcp_after_second_timeout(self):
        def reconfigure():
            self.tlr.set_flags(None)
            self.tlr.define_actions([
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        False,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    dns.resolver.Timeout(),
                ),
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        True,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    self.answer,
                )
            ])

        self.base.reconfigure_resolver.side_effect = reconfigure

        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout(),
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
            ))

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.get_resolver(),
                unittest.mock.call.reconfigure_resolver(),
                unittest.mock.call.get_resolver(),
            ]
        )

        self.assertIs(
            result,
            self.answer,
        )

    def test_retry_up_to_3_times_with_thread_local_resolver(self):
        def reconfigure():
            self.tlr.set_flags(None)
            self.tlr.define_actions([
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        False,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    dns.resolver.Timeout(),
                ),
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        True,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    dns.resolver.Timeout(),
                )
            ])

        self.base.reconfigure_resolver.side_effect = reconfigure

        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout(),
            )
        ])

        with self.tlr:
            with self.assertRaises(TimeoutError):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                ))

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.get_resolver(),
                unittest.mock.call.reconfigure_resolver(),
                unittest.mock.call.get_resolver(),
            ]
        )

    def test_overridden_thread_local_behaves_like_fixed(self):
        resolver = MockResolver(self)
        resolver.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout()
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    True,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.Timeout()
            ),
        ])

        network.set_resolver(resolver)
        self.base.get_resolver.return_value = resolver

        with resolver:
            with self.assertRaises(TimeoutError):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                ))

        self.assertSequenceEqual(
            self.base.mock_calls,
            [
                unittest.mock.call.get_resolver(),
            ]
        )

    def test_raise_ValueError_if_AD_not_present_with_require_ad(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                self.answer,
            )
        ])

        with self.tlr:
            with self.assertRaisesRegex(
                    ValueError,
                    "DNSSEC validation not available"):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                    require_ad=True,
                ))

    def test_pass_if_AD_present_with_require_ad(self):
        answer = MockAnswer(
            [],
            flags=dns.flags.AD,
        )

        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                answer,
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                require_ad=True,
            ))

        self.assertIs(result, answer)

    def test_return_None_on_no_anwser(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoAnswer(),
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                require_ad=True,
            ))

        self.assertIsNone(result)

    def test_return_None_on_NXDOMAIN(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NXDOMAIN(),
            )
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
                require_ad=True,
            ))

        self.assertIsNone(result)

    def test_check_with_CD_set_after_NoNameservers(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoNameservers(),
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD | dns.flags.CD),
                ),
                self.answer,
            ),
        ])

        with self.tlr:
            with self.assertRaisesRegex(
                    network.ValidationError,
                    "nameserver error, most likely DNSSEC validation failed"):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                    require_ad=True,
                ))

    def test_treat_NoAnswer_as_succeeded_query_in_validation_query(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoNameservers(),
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD | dns.flags.CD),
                ),
                dns.resolver.NoAnswer(),
            ),
        ])

        with self.tlr:
            with self.assertRaisesRegex(
                    network.ValidationError,
                    "nameserver error, most likely DNSSEC validation failed"):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                    require_ad=True,
                ))

    def test_treat_NXDOMAIN_as_succeeded_query_in_validation_query(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoNameservers(),
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD | dns.flags.CD),
                ),
                dns.resolver.NXDOMAIN(),
            ),
        ])

        with self.tlr:
            with self.assertRaisesRegex(
                    network.ValidationError,
                    "nameserver error, most likely DNSSEC validation failed"):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                    require_ad=True,
                ))

    def test_continue_as_normal_on_timeout_after_NoNameservers(self):
        def reconfigure():
            self.tlr.set_flags(None)
            self.tlr.define_actions([
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        False,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    dns.resolver.Timeout(),
                ),
                (
                    (
                        "xn--4ca0bs.example.com",
                        dns.rdatatype.A,
                        dns.rdataclass.IN,
                        True,
                        (dns.flags.RD | dns.flags.AD),
                    ),
                    self.answer
                ),
            ])

        self.base.reconfigure_resolver.side_effect = reconfigure

        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoNameservers(),
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD | dns.flags.CD),
                ),
                dns.resolver.Timeout(),
            ),
        ])

        with self.tlr:
            result = run_coroutine(network.repeated_query(
                "äöü.example.com".encode("idna"),
                dns.rdatatype.A,
            ))

        self.assertIs(result, self.answer)

    def test_re_raise_NoNameservers_on_validation_query(self):
        self.tlr.define_actions([
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD),
                ),
                dns.resolver.NoNameservers(),
            ),
            (
                (
                    "xn--4ca0bs.example.com",
                    dns.rdatatype.A,
                    dns.rdataclass.IN,
                    False,
                    (dns.flags.RD | dns.flags.AD | dns.flags.CD),
                ),
                dns.resolver.NoNameservers()
            ),
        ])

        with self.tlr:
            with self.assertRaises(dns.resolver.NoNameservers):
                run_coroutine(network.repeated_query(
                    "äöü.example.com".encode("idna"),
                    dns.rdatatype.A,
                ))


class Testlookup_srv(unittest.TestCase):
    def setUp(self):
        base = unittest.mock.Mock()
        base.repeated_query = CoroutineMock()

        self.base = base
        self.patches = [
            unittest.mock.patch(
                "aioxmpp.network.repeated_query",
                new=base.repeated_query,
            ),
        ]

        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_return_formatted_records(self):
        self.base.repeated_query.return_value = [
            MockSRVRecord(0, 1, "xmpp.foo.test.", 5222),
            MockSRVRecord(2, 1, "xmpp.bar.test.", 5222),
        ]

        self.assertSequenceEqual(
            run_coroutine(network.lookup_srv(
                b"foo.test",
                "xmpp-client",
                executor=unittest.mock.sentinel.executor,
                resolver=unittest.mock.sentinel.resolver,
            )),
            [
                (0, 1, ("xmpp.foo.test", 5222)),
                (2, 1, ("xmpp.bar.test", 5222)),
            ]
        )

        self.base.repeated_query.assert_called_with(
            b"_xmpp-client._tcp.foo.test",
            dns.rdatatype.SRV,
            executor=unittest.mock.sentinel.executor,
            resolver=unittest.mock.sentinel.resolver,
        )

    def test_return_None_on_nxdomain(self):
        self.base.repeated_query.return_value = None

        self.assertIsNone(
            run_coroutine(network.lookup_srv(
                b"foo.test",
                "xmpp-client",
            )),
        )

        self.base.repeated_query.assert_called_with(
            b"_xmpp-client._tcp.foo.test",
            dns.rdatatype.SRV,
        )

    def test_raise_ValueError_if_service_not_supported(self):
        self.base.repeated_query.return_value = [
            MockSRVRecord(0, 1, "xmpp.foo.test.", 5222),
            MockSRVRecord(2, 1, ".", 5222),
        ]

        with self.assertRaisesRegex(
                ValueError,
                r"'xmpp-client' over 'tcp' not supported at b'foo\.test'"):
            run_coroutine(network.lookup_srv(
                b"foo.test",
                "xmpp-client",
            ))


class Testlookup_tlsa(unittest.TestCase):
    def setUp(self):
        base = unittest.mock.Mock()
        base.repeated_query = CoroutineMock()

        self.base = base
        self.patches = [
            unittest.mock.patch(
                "aioxmpp.network.repeated_query",
                new=base.repeated_query,
            ),
        ]

        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_return_formatted_records(self):
        self.base.repeated_query.return_value = [
            MockTLSARecord(3, 0, 1, b"foo"),
            MockTLSARecord(3, 2, 1, b"bar"),
        ]

        self.assertSequenceEqual(
            run_coroutine(network.lookup_tlsa(
                b"foo.test",
                5222,
                executor=unittest.mock.sentinel.executor,
                resolver=unittest.mock.sentinel.resolver,
            )),
            [
                (3, 0, 1, b"foo"),
                (3, 2, 1, b"bar"),
            ]
        )

        self.base.repeated_query.assert_called_with(
            b"_5222._tcp.foo.test",
            dns.rdatatype.TLSA,
            require_ad=True,
            executor=unittest.mock.sentinel.executor,
            resolver=unittest.mock.sentinel.resolver,
        )

    def test_return_None_on_nxdomain(self):
        self.base.repeated_query.return_value = None

        self.assertIsNone(
            run_coroutine(network.lookup_tlsa(
                b"foo.test",
                5222,
            )),
        )

        self.base.repeated_query.assert_called_with(
            b"_5222._tcp.foo.test",
            dns.rdatatype.TLSA,
            require_ad=True,
        )


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
                    service="xmpp-client",
                    domain=base.domain.encode(),
                    nattempts=nattempts
                )
            ]
        )

        self.assertIs(result, items)

    def test_creates_fake_srv_if_no_srvs_available(self):
        base = unittest.mock.Mock()

        nattempts = object()

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
                    service="xmpp-client",
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
