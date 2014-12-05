import asyncio
import base64
import hashlib
import hmac
import unittest

import lxml.builder

import asyncio_xmpp.sasl as sasl
import asyncio_xmpp.xml as xml

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
            raise SASLFailure(xmpp_error, text=text)

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
    def test_rfc(self):
        hashfun_factory = hashlib.sha1
        digest_size = hashfun_factory().digest_size
        user = b"user"
        password = b"pencil"
        salt = b"QSXCR+Q6sek8bf92"

        salted_password = sasl.pbkdf2(hashfun_factory, password, salt, 4096,
                                      digest_size)
        client_key = hmac.new(salted_password,
                              b"Client Key",
                              hashfun_factory).digest()
        stored_key = hashfun_factory(client_key).digest()

        client_first_message_bare = b"n=user,r=Zm9vAAAAAAAAAAAAAAAA"
        server_first_message = b"r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j,s="+base64.b64encode(salt)+b",i=4096"
        client_final_message_without_proof = b"c=biws,r=Zm9vAAAAAAAAAAAAAAAA3rfcNHYJY1ZVvWVs7j"

        auth_message = client_first_message_bare+b","+server_first_message+b","+client_final_message_without_proof

        client_signature = hmac.new(stored_key, auth_message, hashfun_factory).digest()
        client_proof = (int.from_bytes(client_signature, "big") ^
                        int.from_bytes(client_key, "big")).to_bytes(
                            digest_size, "big")

        server_key = hmac.new(salted_password,
                              b"Server Key",
                              hashfun_factory).digest()
        server_signature = hmac.new(server_key,
                                    auth_message,
                                    hashfun_factory).digest()

        smmock = SASLStateMachineMock(
            self,
            [
                ("auth;SCRAM-SHA-1",
                 base64.b64encode(
                     b"n,,"+client_first_message_bare
                 ),
                 "challenge",
                 base64.b64encode(
                     server_first_message
                 )),
                ("response",
                 base64.b64encode(
                     client_final_message_without_proof+
                     b",p="+base64.b64encode(client_proof)),
                 "success",
                 base64.b64encode(
                     b"v="+base64.b64encode(server_signature)))
            ])

        @asyncio.coroutine
        def provide_credentials(*args):
            return ("user", "pencil")

        def run():
            scram = sasl.SCRAM(provide_credentials)
            result = yield from scram.authenticate(
                smmock,
                ("SCRAM-SHA-1", "sha1"))
            self.assertTrue(result)

        asyncio.get_event_loop().run_until_complete(run())

        smmock.finalize()
