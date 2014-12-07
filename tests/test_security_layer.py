import asyncio
import base64
import unittest

import asyncio_xmpp.security_layer as security_layer
import asyncio_xmpp.errors as errors
import asyncio_xmpp.jid as jid

from .mocks import SSLWrapperMock, XMLStreamMock, BangSuccess

from asyncio_xmpp.utils import *

class TestSecurityProvider(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.stream = XMLStreamMock(self, loop=self.loop)
        self.transport = SSLWrapperMock(self.loop, self.stream)
        self.stream.connection_made(self.transport)
        self.Estream = self.stream.tx_context.default_ns_builder(
            namespaces.xmlstream)

    def _test_provider(self, provider, *args):
        try:
            return self.loop.run_until_complete(
                asyncio.wait_for(
                    provider.execute(*args),
                    timeout=2),
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Test timed out") from None

    def tearDown(self):
        del self.transport
        del self.stream
        del self.loop

class TestSTARTTLSProvider(TestSecurityProvider):
    def _fake_ssl_context(self):
        return security_layer.default_ssl_context()

    def _test_provider(self, provider, client_jid, features):
        return super()._test_provider(provider, client_jid, features,
                                      self.stream)

    def test_require_starttls_see_failure(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.starttls)

        self.stream.define_actions([
            (
                E("starttls"),
                (
                    E("failure"),
                )
            )
        ])

        with self.assertRaises(errors.TLSFailure):
            self._test_provider(
                security_layer.STARTTLSProvider(None),
                None,
                self.Estream("features", E("starttls"))
            )

    def test_no_require_starttls_see_failure(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.starttls)

        self.stream.define_actions([
            (
                E("starttls"),
                (
                    E("failure"),
                )
            )
        ])


        self.assertIsNone(
            self._test_provider(
                security_layer.STARTTLSProvider(None, require_starttls=False),
                None,
                self.Estream("features", E("starttls"))
            )
        )

    def test_require_starttls_see_no_support(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.starttls)

        self.stream.define_actions([
            (
                E("starttls"),
                (
                    E("failure"),
                )
            )
        ])

        with self.assertRaises(errors.TLSFailure):
            self._test_provider(
                security_layer.STARTTLSProvider(None),
                None,
                self.Estream("features")
            )

    def test_no_require_starttls_see_no_support(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.starttls)

        self.stream.define_actions([
            (
                E("starttls"),
                (
                    E("failure"),
                )
            )
        ])

        self.assertIsNone(
            self._test_provider(
                security_layer.STARTTLSProvider(None, require_starttls=False),
                None,
                self.Estream("features")
            )
        )

    def test_starttls_success(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.starttls)

        self.stream.define_actions([
            (
                E("starttls"),
                (
                    E("proceed"),
                )
            ),
            (
                "!starttls@bar.invalid",
                None,
            )
        ])

        self.assertIs(
            self.transport,
            self._test_provider(
                security_layer.STARTTLSProvider(self._fake_ssl_context),
                jid.JID("foo", "bar.invalid", None),
                self.Estream("features", E("starttls"))
            )
        )

class TestPasswordSASLProvider(TestSecurityProvider):
    def setUp(self):
        super().setUp()
        self.provider = security_layer.PasswordSASLProvider(
            self.password_provider)
        self.client_jid = jid.JID("user", "bar.invalid", None)
        self.attempt_sequence = []
        self.scram_initial_payload = base64.b64encode(
            b"n,,n=user,r=Zm9vAAAAAAAAAAAAAAAA").decode("ascii")
        self.plain_initial_payload = base64.b64encode(
            b"\0user\0pencil").decode("ascii")

    @asyncio.coroutine
    def password_provider(self, client_jid, nattempt):
        self.attempt_sequence.append(nattempt)
        return "pencil"

    def _test_provider(self, provider, client_jid, features, with_tls):
        return super()._test_provider(
            provider, client_jid, features,
            self.stream,
            self.transport if with_tls else None)

    def test_no_plain_if_no_tls(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.sasl)
        initial_features = self.Estream(
            "features",
            E("mechanisms",
              E("mechanism", "PLAIN")),
        )

        self.assertFalse(
            self._test_provider(
                security_layer.PasswordSASLProvider(self.password_provider),
                self.client_jid,
                initial_features,
                False)
        )
        self.assertSequenceEqual(
            [],
            self.attempt_sequence
        )

    def test_forward_to_sasl_sm(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.sasl)
        initial_features = self.Estream(
            "features",
            E("mechanisms",
              E("mechanism", "PLAIN")),
        )

        self.stream.define_actions([
            (
                E("auth",
                  self.plain_initial_payload,
                  mechanism="PLAIN"),
                (
                    E("success"),
                )
            )
        ])

        self.assertTrue(
            self._test_provider(
                security_layer.PasswordSASLProvider(self.password_provider),
                self.client_jid,
                initial_features,
                True)
        )
        self.assertSequenceEqual(
            [0],
            self.attempt_sequence
        )

    def test_max_auth_attempts(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.sasl)
        initial_features = self.Estream(
            "features",
            E("mechanisms",
              E("mechanism", "PLAIN")),
        )

        auth_exchange = (
            E("auth",
              self.plain_initial_payload,
              mechanism="PLAIN"),
            (
                E(
                    "failure",
                    E("not-authorized")
                ),
            )
        )

        self.stream.define_actions([auth_exchange]*3)

        with self.assertRaises(errors.AuthenticationFailure):
            self._test_provider(
                security_layer.PasswordSASLProvider(self.password_provider),
                self.client_jid,
                initial_features,
                True)
        self.assertSequenceEqual(
            [0, 1, 2],
            self.attempt_sequence
        )

    def test_decay_mechanisms(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.sasl)
        initial_features = self.Estream(
            "features",
            E(
                "mechanisms",
                E("mechanism", "PLAIN"),
                E("mechanism", "SCRAM-SHA-1"),
            )
        )

        self.stream.define_actions([
            # client tries SCRAM first, we reject it
            (
                E("auth",
                  self.scram_initial_payload,
                  mechanism="SCRAM-SHA-1"),
                (
                    E(
                        "failure",
                        E("invalid-mechanism")
                    ),
                )
            ),
            (
                E("auth",
                  self.plain_initial_payload,
                  mechanism="PLAIN"),
                (
                    E("success"),
                )
            ),
        ])

        self.assertTrue(
            self._test_provider(
                security_layer.PasswordSASLProvider(self.password_provider),
                self.client_jid,
                initial_features,
                True)
        )
        self.assertSequenceEqual(
            [0],
            self.attempt_sequence
        )

    def test_scram_first(self):
        E = self.stream.tx_context.default_ns_builder(namespaces.sasl)
        client_first_message_bare = b"n,,n=user,r=Zm9vAAAAAAAAAAAAAAAA"
        initial_features = self.Estream(
            "features",
            E(
                "mechanisms",
                E("mechanism", "PLAIN"),
                E("mechanism", "SCRAM-SHA-1"),
            )
        )

        self.stream.define_actions([
            # client tries SCRAM first, we reject it
            (
                E("auth",
                  self.scram_initial_payload,
                  mechanism="SCRAM-SHA-1"),
                "!success"
            ),
        ])

        with self.assertRaises(BangSuccess):
            self._test_provider(
                security_layer.PasswordSASLProvider(self.password_provider),
                self.client_jid,
                initial_features,
                True)


class TestSecurityLayer(TestSecurityProvider):
    def setUp(self):
        super().setUp()
        self.provider = security_layer.PasswordSASLProvider(
            self.password_provider)
        self.client_jid = jid.JID("user", "bar.invalid", None)
        self.attempt_sequence = []
        self.scram_initial_payload = base64.b64encode(
            b"n,,n=user,r=Zm9vAAAAAAAAAAAAAAAA").decode("ascii")
        self.plain_initial_payload = base64.b64encode(
            b"\0user\0pencil").decode("ascii")

    @asyncio.coroutine
    def password_provider(self, client_jid, nattempt):
        self.attempt_sequence.append(nattempt)
        return "pencil"

    def _fake_ssl_context(self):
        return security_layer.default_ssl_context()

    def _test_layer(self, layer, *args):
        try:
            return self.loop.run_until_complete(
                asyncio.wait_for(
                    layer(*args),
                    timeout=2),
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Test timed out") from None


    def test_negotiate_stream_security(self):
        Etls = self.stream.tx_context.default_ns_builder(namespaces.starttls)
        Esasl = self.stream.tx_context.default_ns_builder(namespaces.sasl)

        layer = security_layer.security_layer(
            tls_provider=security_layer.STARTTLSProvider(
                self._fake_ssl_context),
            sasl_providers=[
                security_layer.PasswordSASLProvider(self.password_provider)
            ])

        initial_features = self.Estream(
            "features",
            Etls("starttls")
        )

        tls_features = self.Estream(
            "features",
            Esasl("mechanisms",
                  Esasl("mechanism", "PLAIN")),
        )

        final_features = self.Estream(
            "features")

        self.stream.define_actions([
            (Etls("starttls"), (Etls("proceed"),)),
            ("!starttls@bar.invalid", None),
            ("!reset", (tls_features,)),
            (Esasl("auth",
                   self.plain_initial_payload,
                   mechanism="PLAIN"),
             (Esasl("success"),)),
            ("!reset", (final_features,))
        ])

        self.assertEqual(
            (self.transport, final_features),
            self._test_layer(layer, 1,
                             self.client_jid, initial_features, self.stream),
        )
