########################################################################
# File name: test_sasl.py
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
import asyncio

import aiosasl

import aioxmpp.nonza as nonza
import aioxmpp.sasl as sasl
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces

from aioxmpp import xmltestutils
from aioxmpp.testutils import (
    XMLStreamMock,
    run_coroutine_with_peer,
)


class TestSASLXMPPInterface(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.sm = sasl.SASLXMPPInterface(self.xmlstream)

    def _run_test(self, coro, actions=[], stimulus=None):
        return run_coroutine_with_peer(
            coro,
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

    def test_setup(self):
        self.assertIsNone(self.sm.timeout)
        self.assertIs(self.xmlstream, self.sm.xmlstream)

    def test_initiate_success(self):
        state, payload = self._run_test(
            self.sm.initiate("foo", b"bar"),
            [
                XMLStreamMock.Send(
                    nonza.SASLAuth(mechanism="foo",
                                   payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        nonza.SASLSuccess()
                    )
                )
            ]
        )
        self.assertEqual(state, "success")
        self.assertIsNone(payload)

    def test_initiate_failure(self):
        with self.assertRaises(aiosasl.SASLFailure) as ctx:
            self._run_test(
                self.sm.initiate("foo", b"bar"),
                [
                    XMLStreamMock.Send(
                        nonza.SASLAuth(mechanism="foo",
                                       payload=b"bar"),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl, "not-authorized")
                            )
                        )
                    )
                ]
            )

        self.assertEqual(
            "not-authorized",
            ctx.exception.opaque_error
        )

    def test_initiate_challenge(self):
        state, payload = self._run_test(
            self.sm.initiate("foo", b"bar"),
            [
                XMLStreamMock.Send(
                    nonza.SASLAuth(mechanism="foo",
                                   payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        nonza.SASLChallenge(payload=b"baz")
                    )
                )
            ]
        )
        self.assertEqual(state, "challenge")
        self.assertEqual(payload, b"baz")

    def test_response_success(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.respond(b"bar"),
            [
                XMLStreamMock.Send(
                    nonza.SASLResponse(payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        nonza.SASLSuccess()
                    )
                )
            ]
        )
        self.assertEqual(state, "success")
        self.assertIsNone(payload)

    def test_response_failure(self):
        self.sm._state = "challenge"

        with self.assertRaises(aiosasl.SASLFailure) as ctx:
            self._run_test(
                self.sm.respond(b"bar"),
                [
                    XMLStreamMock.Send(
                        nonza.SASLResponse(payload=b"bar"),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl,
                                           "credentials-expired")
                            )
                        )
                    )
                ]
            )

        self.assertEqual(
            "credentials-expired",
            ctx.exception.opaque_error
        )

    def test_response_challenge(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.respond(b"bar"),
            [
                XMLStreamMock.Send(
                    nonza.SASLResponse(payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        nonza.SASLChallenge(payload=b"baz")
                    )
                )
            ]
        )
        self.assertEqual(state, "challenge")
        self.assertEqual(payload, b"baz")

    def test_abort_reject_non_failure(self):
        self.sm._state = "challenge"

        with self.assertRaisesRegex(
            aiosasl.SASLFailure,
            "unexpected non-failure"
        ) as ctx:
            self._run_test(
                self.sm.abort(),
                [
                    XMLStreamMock.Send(
                        nonza.SASLAbort(),
                        response=XMLStreamMock.Receive(
                            nonza.SASLSuccess()
                        )
                    )
                ]
            )

        self.assertEqual(
            "aborted",
            ctx.exception.opaque_error
        )

    def test_abort_return_on_aborted_error(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.abort(),
            [
                XMLStreamMock.Send(
                    nonza.SASLAbort(),
                    response=XMLStreamMock.Receive(
                        nonza.SASLFailure(
                            condition=(namespaces.sasl, "aborted")
                        )
                    )
                )
            ]
        )

        self.assertEqual(state, "failure")
        self.assertIsNone(payload)

    def test_abort_re_raise_other_errors(self):
        self.sm._state = "challenge"

        with self.assertRaises(aiosasl.SASLFailure) as ctx:
            self._run_test(
                self.sm.abort(),
                [
                    XMLStreamMock.Send(
                        nonza.SASLAbort(),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl,
                                           "mechanism-too-weak")
                            )
                        )
                    )
                ]
            )

        self.assertEqual(
            "mechanism-too-weak",
            ctx.exception.opaque_error
        )

    def tearDown(self):
        del self.xmlstream
        del self.loop
