import asyncio
import base64
import hashlib
import hmac
import unittest

import lxml.builder

import aioxmpp.sasl as sasl
import aioxmpp.xml as xml
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces

from aioxmpp import xmltestutils
from aioxmpp.testutils import (
    XMLStreamMock,
    run_coroutine_with_peer,
    run_coroutine
)


class SASLStateMachineMock(sasl.SASLStateMachine):
    def __init__(self, testobj, action_sequence, xmlstream=None):
        super().__init__(xmlstream or XMLStreamMock(testobj))
        self._testobj = testobj
        self._action_sequence = action_sequence

    @asyncio.coroutine
    def _send_sasl_node_and_wait_for(self, node):
        if hasattr(node, "payload"):
            payload = node.payload
        else:
            payload = None
        action = node.TAG[1]
        if action == "auth":
            action += ";"+node.mechanism

        try:
            (next_action,
             next_payload,
             new_state,
             result_payload) = self._action_sequence.pop(0)
        except ValueError:
            raise AssertionFailed(
                "SASL action performed unexpectedly: {} with payload {}".format(
                    action,
                    payload))

        self._state = new_state

        self._testobj.assertEqual(
            action,
            next_action,
            "SASL action sequence violated")

        self._testobj.assertEqual(
            payload,
            next_payload,
            "SASL payload expectation violated")

        if new_state == "failure":
            xmpp_error, text = result_payload
            raise errors.SASLFailure(xmpp_error, text=text)

        if result_payload is not None:
            result_payload = result_payload

        return new_state, result_payload

    def finalize(self):
        self._testobj.assertFalse(
            self._action_sequence,
            "Not all actions performed")


class TestSASLAuth(unittest.TestCase):
    def test_init(self):
        obj = sasl.SASLAuth(mechanism="foo", payload=b"bar")
        self.assertEqual("foo", obj.mechanism)
        self.assertEqual(b"bar", obj.payload)

    def test_default_init(self):
        obj = sasl.SASLAuth()
        self.assertIsNone(obj.mechanism)
        self.assertIsNone(obj.payload)


class TestSASLChallenge(unittest.TestCase):
    def test_init(self):
        obj = sasl.SASLChallenge(payload=b"bar")
        self.assertEqual(b"bar", obj.payload)

    def test_default_init(self):
        obj = sasl.SASLChallenge()
        self.assertIsNone(obj.payload)


class TestSASLResponse(unittest.TestCase):
    def test_init(self):
        obj = sasl.SASLResponse(payload=b"bar")
        self.assertEqual(b"bar", obj.payload)

    def test_default_init(self):
        obj = sasl.SASLResponse()
        self.assertIsNone(obj.payload)


class TestSASLFailure(unittest.TestCase):
    def test_init(self):
        obj = sasl.SASLFailure(condition=(namespaces.sasl,
                                          "invalid-mechanism"))
        self.assertEqual(
            (namespaces.sasl, "invalid-mechanism"),
            obj.condition)

    def test_default_init(self):
        obj = sasl.SASLFailure()
        self.assertEqual(
            (namespaces.sasl, "temporary-auth-failure"),
            obj.condition)


class TestSASLStateMachine(xmltestutils.XMLTestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.sm = sasl.SASLStateMachine(self.xmlstream)

    def _run_test(self, coro, actions=[], stimulus=None):
        return run_coroutine_with_peer(
            coro,
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

    def test_initiate_success(self):
        state, payload = self._run_test(
            self.sm.initiate("foo", b"bar"),
            [
                XMLStreamMock.Send(
                    sasl.SASLAuth(mechanism="foo",
                                  payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        sasl.SASLSuccess()
                    )
                )
            ]
        )
        self.assertEqual(state, "success")
        self.assertIsNone(payload)

    def test_initiate_failure(self):
        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run_test(
                self.sm.initiate("foo", b"bar"),
                [
                    XMLStreamMock.Send(
                        sasl.SASLAuth(mechanism="foo",
                                      payload=b"bar"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "not-authorized")
                            )
                        )
                    )
                ]
            )

        self.assertEqual(
            "not-authorized",
            ctx.exception.xmpp_error
        )

    def test_initiate_challenge(self):
        state, payload = self._run_test(
            self.sm.initiate("foo", b"bar"),
            [
                XMLStreamMock.Send(
                    sasl.SASLAuth(mechanism="foo",
                                  payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        sasl.SASLChallenge(payload=b"baz")
                    )
                )
            ]
        )
        self.assertEqual(state, "challenge")
        self.assertEqual(payload, b"baz")

    def test_reject_double_initiate(self):
        self._run_test(
            self.sm.initiate("foo", b"bar"),
            [
                XMLStreamMock.Send(
                    sasl.SASLAuth(mechanism="foo",
                                  payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        sasl.SASLSuccess()
                    )
                )
            ]
        )

        with self.assertRaisesRegexp(RuntimeError,
                                     "has already been called"):
            run_coroutine(self.sm.initiate("foo"))

    def test_reject_response_without_challenge(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     "no challenge"):
            run_coroutine(self.sm.response(b"bar"))

    def test_response_success(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.response(b"bar"),
            [
                XMLStreamMock.Send(
                    sasl.SASLResponse(payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        sasl.SASLSuccess()
                    )
                )
            ]
        )
        self.assertEqual(state, "success")
        self.assertIsNone(payload)

    def test_response_failure(self):
        self.sm._state = "challenge"

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run_test(
                self.sm.response(b"bar"),
                [
                    XMLStreamMock.Send(
                        sasl.SASLResponse(payload=b"bar"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "credentials-expired")
                            )
                        )
                    )
                ]
            )

        self.assertEqual(
            "credentials-expired",
            ctx.exception.xmpp_error
        )

    def test_response_challenge(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.response(b"bar"),
            [
                XMLStreamMock.Send(
                    sasl.SASLResponse(payload=b"bar"),
                    response=XMLStreamMock.Receive(
                        sasl.SASLChallenge(payload=b"baz")
                    )
                )
            ]
        )
        self.assertEqual(state, "challenge")
        self.assertEqual(payload, b"baz")

    def test_reject_abort_without_initiate(self):
        with self.assertRaises(RuntimeError):
            run_coroutine(self.sm.abort())

    def test_abort_reject_non_failure(self):
        self.sm._state = "challenge"

        with self.assertRaisesRegexp(
                errors.SASLFailure,
                "unexpected non-failure"
        ) as ctx:
            self._run_test(
                self.sm.abort(),
                [
                    XMLStreamMock.Send(
                        sasl.SASLAbort(),
                        response=XMLStreamMock.Receive(
                            sasl.SASLSuccess()
                        )
                    )
                ]
            )

        self.assertEqual(
            "aborted",
            ctx.exception.xmpp_error
        )

    def test_abort_return_on_aborted_error(self):
        self.sm._state = "challenge"

        state, payload = self._run_test(
            self.sm.abort(),
            [
                XMLStreamMock.Send(
                    sasl.SASLAbort(),
                    response=XMLStreamMock.Receive(
                        sasl.SASLFailure(
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

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run_test(
                self.sm.abort(),
                [
                    XMLStreamMock.Send(
                        sasl.SASLAbort(),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "mechanism-too-weak")
                            )
                    )
                    )
                ]
            )

        self.assertEqual(
            "mechanism-too-weak",
            ctx.exception.xmpp_error
        )


    def tearDown(self):
        del self.xmlstream
        del self.loop


class TestPLAIN(unittest.TestCase):
    def test_rfc(self):
        user = "tim"
        password = "tanstaaftanstaaf"

        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;PLAIN",
                 b"\0tim\0tanstaaftanstaaf",
                 "success",
                 None)
            ])

        @asyncio.coroutine
        def provide_credentials(*args):
            return user, password

        def run():
            plain = sasl.PLAIN(provide_credentials)
            result = yield from plain.authenticate(
                smmock,
                "PLAIN")
            self.assertTrue(result)

        asyncio.get_event_loop().run_until_complete(run())

        smmock.finalize()

    def test_fail_on_protocol_violation(self):
        user = "tim"
        password = "tanstaaftanstaaf"

        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;PLAIN",
                 b"\0tim\0tanstaaftanstaaf",
                 "challenge",
                 b"foo")
            ])

        @asyncio.coroutine
        def provide_credentials(*args):
            return user, password

        def run():
            plain = sasl.PLAIN(provide_credentials)
            result = yield from plain.authenticate(
                smmock,
                "PLAIN")

        with self.assertRaisesRegexp(errors.SASLFailure,
                                     "protocol violation") as ctx:
            asyncio.get_event_loop().run_until_complete(run())

        self.assertEqual(
            "malformed-request",
            ctx.exception.xmpp_error
        )

        smmock.finalize()

    def test_reject_NUL_bytes_in_username(self):
        smmock = SASLStateMachineMock(
            self,
            [
            ])

        @asyncio.coroutine
        def provide_credentials(*args):
            return "\0", "foo"

        with self.assertRaises(ValueError):
            run_coroutine(
                sasl.PLAIN(provide_credentials).authenticate(smmock, "PLAIN")
            )

    def test_reject_NUL_bytes_in_password(self):
        smmock = SASLStateMachineMock(
            self,
            [
            ])

        @asyncio.coroutine
        def provide_credentials(*args):
            return "foo", "\0"

        with self.assertRaises(ValueError):
            run_coroutine(
                sasl.PLAIN(provide_credentials).authenticate(smmock, "PLAIN")
            )

    def test_supports_PLAIN(self):
        self.assertEqual(
            "PLAIN",
            sasl.PLAIN.any_supported(["PLAIN"])
        )

    def test_does_not_support_SCRAM(self):
        self.assertIsNone(
            sasl.PLAIN.any_supported(["SCRAM-SHA-1"])
        )


class TestSCRAM(unittest.TestCase):
    def setUp(self):
        self.hashfun_factory = hashlib.sha1
        self.digest_size = self.hashfun_factory().digest_size
        self.user = b"user"
        self.password = b"pencil"
        self.salt = b"QSXCR+Q6sek8bf92"

        sasl._system_random = unittest.mock.MagicMock()
        sasl._system_random.getrandbits.return_value = int.from_bytes(
            b"foo",
            "little")

        self.salted_password = sasl.pbkdf2(
            "sha1",
            self.password,
            self.salt,
            4096,
            self.digest_size)

        self.client_key = hmac.new(
            self.salted_password,
            b"Client Key",
            self.hashfun_factory).digest()
        self.stored_key = self.hashfun_factory(
            self.client_key).digest()

        self.client_first_message_bare = b"n=user,r=Zm9vAAAAAAAAAAAAAAAA"
        self.server_first_message = b"".join([
            b"r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j,s=",
            base64.b64encode(self.salt),
            b",i=4096"
        ])
        self.client_final_message_without_proof = b"c=biws,r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j"

        self.auth_message = b",".join([
            self.client_first_message_bare,
            self.server_first_message,
            self.client_final_message_without_proof
        ])

        self.client_signature = hmac.new(
            self.stored_key,
            self.auth_message,
            self.hashfun_factory).digest()

        self.client_proof = (
            int.from_bytes(self.client_signature, "big") ^
            int.from_bytes(self.client_key, "big")).to_bytes(
                self.digest_size, "big")

        self.server_key = hmac.new(
            self.salted_password,
            b"Server Key",
            self.hashfun_factory).digest()
        self.server_signature = hmac.new(
            self.server_key,
            self.auth_message,
            self.hashfun_factory).digest()

    @asyncio.coroutine
    def _provide_credentials(self, *args):
        return ("user", "pencil")

    def _run(self, smmock):
        scram = sasl.SCRAM(self._provide_credentials)
        result = asyncio.get_event_loop().run_until_complete(
            scram.authenticate(smmock, ("SCRAM-SHA-1", "sha1"))
        )
        smmock.finalize()
        return result

    def test_rfc(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 self.server_first_message
                ),
                ("response",
                 self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof),
                 "success",
                 b"v="+base64.b64encode(self.server_signature))
            ])

        self.assertTrue(self._run(smmock))

    def test_malformed_reply(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 b"s=hut,t=hefu,c=kup,d=onny"),
                ("abort", None,
                 "failure", ("aborted", None))
            ])

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run(smmock)

        self.assertIn(
            "malformed",
            str(ctx.exception).lower()
        )

    def test_malformed_reply(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 b"i=sometext,s=ABC,r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j"),
                ("abort", None,
                 "failure", ("aborted", None))
            ])

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run(smmock)

        self.assertIn(
            "malformed",
            str(ctx.exception).lower()
        )

    def test_incorrect_nonce(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 b"r=foobar,s="+base64.b64encode(self.salt)+b",i=4096"),
                ("abort", None,
                 "failure", ("aborted", None))
            ])

        with self.assertRaisesRegexp(errors.SASLFailure, "nonce"):
            self._run(smmock)

    def test_invalid_signature(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 self.server_first_message),
                ("response",
                 self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof),
                 "success",
                 b"v="+base64.b64encode(b"fnord"))
            ])

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run(smmock)

        self.assertIn(
            "signature",
            str(ctx.exception).lower()
        )

    def test_supports_SCRAM_famliy(self):
        hashes = ["SHA-1", "SHA-224", "SHA-256",
                  "SHA-512", "SHA-384", "SHA-256"]

        for hashname in hashes:
            mechanism = "SCRAM-{}".format(hashname)
            self.assertEqual(
                (mechanism, hashname.replace("-", "").lower()),
                sasl.SCRAM.any_supported([mechanism])
            )

    def test_pick_longest_hash(self):
        self.assertEqual(
            ("SCRAM-SHA-512", "sha512"),
            sasl.SCRAM.any_supported([
                "SCRAM-SHA-1",
                "SCRAM-SHA-512",
                "SCRAM-SHA-224",
                "PLAIN",
            ])
        )

        self.assertEqual(
            ("SCRAM-SHA-256", "sha256"),
            sasl.SCRAM.any_supported([
                "SCRAM-SHA-1",
                "SCRAM-SHA-256",
                "SCRAM-SHA-224",
                "PLAIN",
            ])
        )

    def test_reject_scram_plus(self):
        hashes = ["SHA-1", "SHA-224", "SHA-256",
                  "SHA-512", "SHA-384", "SHA-256"]

        for hashname in hashes:
            mechanism = "SCRAM-{}-PLUS".format(hashname)
            self.assertIsNone(
                sasl.SCRAM.any_supported([mechanism])
            )

    def test_reject_md5(self):
        self.assertIsNone(
            sasl.SCRAM.any_supported(["SCRAM-MD5"])
        )

    def test_reject_unknown_hash_functions(self):
        self.assertIsNone(
            sasl.SCRAM.any_supported(["SCRAM-FOOBAR"])
        )

    def test_parse_message_reject_long_keys(self):
        with self.assertRaisesRegexp(Exception, "protocol violation"):
            list(sasl.SCRAM.parse_message(b"foo=bar"))

    def test_parse_message_reject_m_key(self):
        with self.assertRaisesRegexp(Exception, "protocol violation"):
            list(sasl.SCRAM.parse_message(b"m=bar"))

    def test_parse_message_unescape_n_and_a_payload(self):
        data = list(sasl.SCRAM.parse_message(b"n=foo=2Cbar=3Dbaz,"
                                             b"a=fnord=2Cfunky=3Dfunk"))
        self.assertSequenceEqual(
            [
                (b"n", b"foo,bar=baz"),
                (b"a", b"fnord,funky=funk")
            ],
            data
        )

    def test_promote_failure_to_authentication_failure(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 self.server_first_message
                ),
                ("response",
                 self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof),
                 "failure",
                 ("credentials-expired", None))
            ])

        with self.assertRaises(errors.AuthenticationFailure) as ctx:
            self._run(smmock)

        self.assertEqual(
            "credentials-expired",
            ctx.exception.xmpp_error
        )

    def test_reject_protocol_violation(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 b"n,,"+self.client_first_message_bare,
                 "challenge",
                 self.server_first_message
                ),
                ("response",
                 self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof),
                 "challenge",
                 b"foo")
            ])

        with self.assertRaisesRegexp(errors.SASLFailure,
                                     "protocol violation") as ctx:
            self._run(smmock)

        self.assertEqual(
            "malformed-request",
            ctx.exception.xmpp_error
        )

    def tearDown(self):
        import random
        sasl._system_random = random.SystemRandom()
