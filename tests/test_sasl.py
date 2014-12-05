import asyncio
import base64
import hashlib
import hmac
import unittest

import lxml.builder

import asyncio_xmpp.sasl as sasl
import asyncio_xmpp.xml as xml
import asyncio_xmpp.errors as errors

from . import mocks

class XMLStreamMock:
    def __init__(self):
        self.tx_context = xml.default_tx_context
        self.E = self.tx_context

class SASLStateMachineMock(sasl.SASLStateMachine):
    def __init__(self, testobj, action_sequence, xmlstream=None):
        super().__init__(xmlstream or XMLStreamMock())
        self._testobj = testobj
        self._action_sequence = action_sequence

    @asyncio.coroutine
    def _send_sasl_node_and_wait_for(self, node):
        payload = node.text
        if payload is not None:
            payload = payload.encode("ascii")
        action = node.tag.partition("}")[2]
        if action == "auth":
            action += ";"+node.get("mechanism", "")

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
            result_payload = base64.b64decode(result_payload)

        return new_state, result_payload

    def finalize(self):
        self._testobj.assertFalse(
            self._action_sequence,
            "Not all actions performed")

class TestPLAIN(unittest.TestCase):
    def test_rfc(self):
        user = "tim"
        password = "tanstaaftanstaaf"

        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;PLAIN",
                 base64.b64encode(b"\0tim\0tanstaaftanstaaf"),
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

class TestSCRAM(unittest.TestCase):
    def setUp(self):
        self.hashfun_factory = hashlib.sha1
        self.digest_size = self.hashfun_factory().digest_size
        self.user = b"user"
        self.password = b"pencil"
        self.salt = b"QSXCR+Q6sek8bf92"

        self.salted_password = sasl.pbkdf2(
            self.hashfun_factory,
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
                 base64.b64encode(
                     b"n,,"+self.client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     self.server_first_message
                 )),
                ("response",
                 base64.b64encode(
                     self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof)),
                 "success",
                 base64.b64encode(
                     b"v="+base64.b64encode(self.server_signature)))
            ])

        self.assertTrue(self._run(smmock))

    def test_malformed_reply(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 base64.b64encode(
                     b"n,,"+self.client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     b"s=hut,t=hefu,c=kup,d=onny")),
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
                 base64.b64encode(
                     b"n,,"+self.client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     b"i=sometext,s=ABC,r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j"
                 )),
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
                 base64.b64encode(
                     b"n,,"+self.client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     b"r=foobar,s="+base64.b64encode(self.salt)+b",i=4096")),
                ("abort", None,
                 "failure", ("aborted", None))
            ])

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run(smmock)

        self.assertIn(
            "nonce",
            str(ctx.exception).lower()
        )

    def test_invalid_signature(self):
        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 base64.b64encode(
                     b"n,,"+self.client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     self.server_first_message
                 )),
                ("response",
                 base64.b64encode(
                     self.client_final_message_without_proof+
                     b",p="+base64.b64encode(self.client_proof)),
                 "success",
                 base64.b64encode(
                     b"v="+base64.b64encode(b"fnord")))
            ])

        with self.assertRaises(errors.SASLFailure) as ctx:
            self._run(smmock)

        self.assertIn(
            "signature",
            str(ctx.exception).lower()
        )
