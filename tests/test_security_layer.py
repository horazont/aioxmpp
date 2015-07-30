import asyncio
import contextlib
import socket
import ssl
import unittest

import OpenSSL.crypto
import OpenSSL.SSL

import aioxmpp.errors as errors
import aioxmpp.sasl as sasl
import aioxmpp.structs as structs
import aioxmpp.security_layer as security_layer
import aioxmpp.stream_xsos as stream_xsos

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    XMLStreamMock,
    run_coroutine,
    run_coroutine_with_peer,
    CoroutineMock
)
from aioxmpp import xmltestutils


# class SSLVerificationTestBase(unittest.TestCase):
#     def setUp(self):
#         self.server_ctx = OpenSSL.SSL.Context(
#             OpenSSL.SSL.SSLv23_METHOD,
#         )
#         self.server_raw_sock, self.client_raw_sock = socket.socketpair()
#         self.server_sock = OpenSSL.SSL.Connection(
#             self.server_ctx,
#             self.server_raw_sock
#         )
#         self.server_sock.set_accept_state()

#     def tearDown(self):
#         self.server_sock.close()
#         self.server_raw_sock.close()
#         self.client_raw_sock.close()


crt_zombofant_net = b"""\
-----BEGIN CERTIFICATE-----
MIIGSTCCBDGgAwIBAgIDEFeyMA0GCSqGSIb3DQEBDQUAMHkxEDAOBgNVBAoTB1Jv
b3QgQ0ExHjAcBgNVBAsTFWh0dHA6Ly93d3cuY2FjZXJ0Lm9yZzEiMCAGA1UEAxMZ
Q0EgQ2VydCBTaWduaW5nIEF1dGhvcml0eTEhMB8GCSqGSIb3DQEJARYSc3VwcG9y
dEBjYWNlcnQub3JnMB4XDTE1MDMwNzExMzE1N1oXDTE1MDkwMzExMzE1N1owGDEW
MBQGA1UEAxMNem9tYm9mYW50Lm5ldDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCC
AgoCggIBALzAsX9qMkd2nECtTApw0zMVHs5HUkyGHW0hSRR0Q7MHm4HTm6I8xzD2
yZxX/TyYBDo/JcdOqtVmKSht7l4oxU8xd5QyOFHTnHUGElwxKNhtBTCRf5mIWrd6
8CUWAgvhCmQk2qD2w1z0hiPCl5dVnxQccZRNJlwyNEBAbk5cHajEQjOvT+NxBX3w
q9lVlyJjuFzXaJRTlDNWfBd7mC077ag3LqFiR2D1IHi0R6b6gjSE9rfjAZxyon98
sgKA20nbmVNiSCSmqVBoC6ELQdzCa4HEP0jrw1OrmIqRJVIAjouYQkALGHzozBYy
x/9vIGI8vmG2TFgdLDQ8rr1nXrwY7m/fvnw43vb0nPsCNnFjI8IkB0ind44ajXWP
oBV4FQlg+hx9eL/+XkPhLP5BJ1kHttvda/NXV5zSk8Z6y2dt4tYHWDjXykA1nWMW
7tjwvb6pqp8kahKzlQF9rKCBOL4PpcPctZ9ookwCU1aPGvjCS6H7cRIzM4U+ZKHq
yvlSlFe7KrrUGgR8dx6I6csD0jiOD3d+gbK7Oiu6NG7fxXELCCIAfFQIFEY79yz6
z2qZBjqQaNuNP3QkmZLDPEyvHZCWPpMIyIuUK8k3oWt0OdCUBRV6p+3EYEcPeamt
aMWXc1PQMioj3W1ndCehyOZ9tlXmvVaSHTLuZXyFm6/4+2rKj84jAgMBAAGjggE5
MIIBNTAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIDqDA0BgNVHSUELTArBggr
BgEFBQcDAgYIKwYBBQUHAwEGCWCGSAGG+EIEAQYKKwYBBAGCNwoDAzAzBggrBgEF
BQcBAQQnMCUwIwYIKwYBBQUHMAGGF2h0dHA6Ly9vY3NwLmNhY2VydC5vcmcvMDEG
A1UdHwQqMCgwJqAkoCKGIGh0dHA6Ly9jcmwuY2FjZXJ0Lm9yZy9yZXZva2UuY3Js
MHcGA1UdEQRwMG6CDXpvbWJvZmFudC5uZXSgGwYIKwYBBQUHCAWgDwwNem9tYm9m
YW50Lm5ldIIYY29uZmVyZW5jZS56b21ib2ZhbnQubmV0oCYGCCsGAQUFBwgFoBoM
GGNvbmZlcmVuY2Uuem9tYm9mYW50Lm5ldDANBgkqhkiG9w0BAQ0FAAOCAgEAd7hJ
KdfqC0pdFLlIKzaLSuhK2FbqrZAd+wAZs1OfHPxZ1m0ygvCN3t2fm01DXKk34Wj7
ZTnZSgmsIudFBSco8z+ne6rHKd9qqJd7C/YR/pz53UnZR+ost26shr2ARb1+ve+6
OyCiDi81IV2FxahMzqvYbxzr0XxkOZlmkgNOWNz9Da29wvgvVCyhzbdH8oVohOSw
Vq/aP56vBbTwDK2LKMAU+m3AgDwjauRt96HhBMMS9yH2Ct5S8OFSFHd58AtLu6fP
LIsp75t4RVoShci1HiVudeCCfcPdvzGsxp1BxPx5OnTZerbHZ30WuS4QF9Nfo+yE
4S9reB5qaNQxzlFplmJCoDN6mLshvZ3CMwR9d8Al6Cv6X/sneNOWu5fmAXSAHjdu
jbAg2J/Ohw+WWJ6NfvbUYWVuvO3NPFoSenDopMSWSjM70BeVApl/t3gAgUBHFYgB
DKkO6BDIyEuopYlyVoiBBQbzJTG2/P5/tzHZJGOjy4R9wZERj3Ol4COvVFnM28sU
tv785oJggyTqCsRHxFxv3ouYrC6O3imDdhfuWTBep4o+OwII9K0T2/i3aPsX92Zg
d11q4Mhgsy1A8B1T+cwPzRQ8aa1//QGOa7KQ5lIYRQGq6Clg7XfZWeKsYOAoUGaS
74eNdQYv+etdKem7oSf/oA/aSKGeyVqgvf2/WH0=
-----END CERTIFICATE-----
"""


class Testextract_python_dict_from_x509(unittest.TestCase):
    def test_zombofant_net(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        d = security_layer.extract_python_dict_from_x509(x509)

        self.assertDictEqual(
            {
                "subject": (
                    (("commonName", "zombofant.net"),),
                ),
                "subjectAltName": [
                    ("DNS", "zombofant.net"),
                    ("DNS", "conference.zombofant.net"),
                ]
            },
            d
        )


class Testcheck_x509_hostname(unittest.TestCase):
    def test_pass(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        hostname = object()

        with contextlib.ExitStack() as stack:
            extract_python_dict_from_x509 = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.extract_python_dict_from_x509"
                )
            )
            match_hostname = stack.enter_context(unittest.mock.patch(
                "ssl.match_hostname"
            ))
            match_hostname.return_value = None

            result = security_layer.check_x509_hostname(
                x509,
                hostname
            )

        self.assertTrue(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509)
            ],
            extract_python_dict_from_x509.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    extract_python_dict_from_x509(),
                    hostname
                )
            ],
            match_hostname.mock_calls
        )

    def test_fail(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        hostname = object()

        with contextlib.ExitStack() as stack:
            extract_python_dict_from_x509 = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.extract_python_dict_from_x509"
                )
            )
            match_hostname = stack.enter_context(unittest.mock.patch(
                "ssl.match_hostname"
            ))
            match_hostname.side_effect = ssl.CertificateError("foo")

            result = security_layer.check_x509_hostname(
                x509,
                hostname
            )

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509)
            ],
            extract_python_dict_from_x509.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    extract_python_dict_from_x509(),
                    hostname
                )
            ],
            match_hostname.mock_calls
        )


class TestPKIXCertificateVerifier(unittest.TestCase):
    def test_verify_callback_checks_hostname(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = True

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                True)

        self.assertTrue(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509, verifier.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

    def test_verify_callback_returns_false_on_hostname_mismatch(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = False

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                True)

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509, verifier.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

    def test_verify_callback_skip_hostname_check_on_precheck_fail(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = False

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                False)

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            check_x509_hostname.mock_calls
        )


class TestSTARTTLSProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.ssl_context_factory = unittest.mock.Mock()
        self.certificate_verifier_factory = unittest.mock.Mock()

        self.ssl_context = self.ssl_context_factory()
        self.ssl_context_factory.return_value = self.ssl_context
        self.ssl_context_factory.mock_calls.clear()

        self.verifier = self.certificate_verifier_factory()
        self.verifier.pre_handshake = CoroutineMock()
        self.verifier.post_handshake = CoroutineMock()
        self.certificate_verifier_factory.return_value = self.verifier
        self.certificate_verifier_factory.mock_calls.clear()

    def _test_provider(self, provider, features, actions=[], stimulus=None):
        return run_coroutine_with_peer(
            provider.execute(self.client_jid,
                             features,
                             self.xmlstream),
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

    def test_require_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "not supported by peer"):
            self._test_provider(provider, features)

    def test_pass_without_required_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=False)

        features = stream_xsos.StreamFeatures()

        self.assertIsNone(self._test_provider(provider, features))

    def test_fail_if_peer_requires_starttls_but_we_cannot_do_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=False)

        features = stream_xsos.StreamFeatures()
        instance = security_layer.STARTTLSFeature()
        instance.required = security_layer.STARTTLSFeature.STARTTLSRequired()
        features[...] = instance

        self.xmlstream.can_starttls_value = False

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "not supported by us"):
            self._test_provider(provider, features)

    def test_fail_if_peer_reports_failure(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "failed on remote side"):
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSFailure()
                        )
                    )
                ]
            )

    def test_engage_starttls_on_proceed(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        result = self._test_provider(
            provider, features,
            actions=[
                XMLStreamMock.Send(
                    security_layer.STARTTLS(),
                    response=XMLStreamMock.Receive(
                        security_layer.STARTTLSProceed()
                    )
                ),
                XMLStreamMock.STARTTLS(
                    ssl_context=self.ssl_context,
                    post_handshake_callback=self.verifier.post_handshake
                )
            ]
        )

        self.assertIs(result, self.transport)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            self.ssl_context_factory.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
                unittest.mock.call().pre_handshake(self.xmlstream.transport),
                unittest.mock.call().setup_context(
                    self.ssl_context, self.xmlstream.transport),
                unittest.mock.call().post_handshake(
                    self.xmlstream.transport)
            ],
            self.certificate_verifier_factory.mock_calls
        )

    def test_propagate_and_wrap_error(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        exc = ValueError("foobar")
        self.certificate_verifier_factory().post_handshake.side_effect = exc

        with self.assertRaisesRegexp(errors.TLSFailure,
                                     "TLS connection failed: foobar"):
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSProceed()
                        )
                    ),
                    XMLStreamMock.STARTTLS(
                        ssl_context=self.ssl_context_factory(),
                        post_handshake_callback=
                        self.certificate_verifier_factory().post_handshake
                    )
                ]
            )

    def test_propagate_tls_error(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        exc = errors.TLSFailure("foobar")
        self.certificate_verifier_factory().post_handshake.side_effect = exc

        with self.assertRaises(errors.TLSFailure) as ctx:
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSProceed()
                        )
                    ),
                    XMLStreamMock.STARTTLS(
                        ssl_context=self.ssl_context_factory(),
                        post_handshake_callback=
                        self.certificate_verifier_factory().post_handshake
                    )
                ]
            )

        self.assertIs(ctx.exception, exc)

    def tearDown(self):
        del self.ssl_context_factory
        del self.certificate_verifier_factory
        del self.xmlstream
        del self.loop
        del self.client_jid


class TestPasswordSASLProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        sasl._system_random = unittest.mock.MagicMock()
        sasl._system_random.getrandbits.return_value = int.from_bytes(
            b"foo",
            "little")

        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = stream_xsos.StreamFeatures()
        self.mechanisms = security_layer.SASLMechanisms()
        self.features[...] = self.mechanisms

        self.password_provider = unittest.mock.MagicMock()

    @asyncio.coroutine
    def _password_provider_wrapper(self, client_jid, nattempt):
        return self.password_provider(client_jid, nattempt)

    def _test_provider(self, provider,
                       actions=[], stimulus=None,
                       tls_transport=None):
        return run_coroutine_with_peer(
            provider.execute(self.client_jid,
                             self.features,
                             self.xmlstream,
                             tls_transport),
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop
        )

    def test_raise_sasl_unavailable_if_sasl_is_not_supported(self):
        del self.features[security_layer.SASLMechanisms]

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        with self.assertRaisesRegexp(errors.SASLUnavailable,
                                     "does not support SASL"):
            self._test_provider(provider)

    def test_reject_plain_auth_over_non_tls_stream(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.assertFalse(self._test_provider(provider))

    def test_raise_authentication_error_if_password_provider_returns_None(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = None

        with self.assertRaisesRegexp(errors.AuthenticationFailure,
                                     "aborted by user"):
            self._test_provider(provider, tls_transport=True)

    def test_raise_sasl_error_on_permanent_error(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        payload = b"\0foo\0foo"
        self.password_provider.return_value = "foo"

        with self.assertRaisesRegexp(errors.SASLFailure,
                                     "malformed-request"):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(mechanism="PLAIN",
                                      payload=payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "malformed-request")
                            )
                        )
                    )
                ],
                tls_transport=True)

    def test_perform_mechanism_on_match(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                   b"\0"+"foobar".encode("utf-8"))

        self.assertTrue(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLSuccess())
                    )
                ],
                tls_transport=True)
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
            ],
            self.password_provider.mock_calls
        )

    def test_cycle_through_mechanisms_if_mechanisms_fail(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="SCRAM-SHA-1"),
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        self.assertTrue(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "invalid-mechanism")
                            ))
                    ),
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLSuccess()
                        )
                    ),
                ],
                tls_transport=True)
        )

        # make sure that the password provider is called only once when a
        # non-credential-related error occurs
        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
            ],
            self.password_provider.mock_calls
        )

    def test_re_query_for_credentials_on_auth_failure(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper,
            max_auth_attempts=3)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        with self.assertRaises(errors.AuthenticationFailure):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "not-authorized")
                            )
                        )
                    ),
                ]*3,
                tls_transport=True)

        # make sure that the password provider is called each time a
        # not-authorized is received
        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
                unittest.mock.call(self.client_jid.bare(), 1),
                unittest.mock.call(self.client_jid.bare(), 2),
            ],
            self.password_provider.mock_calls
        )

    def test_fail_if_out_of_mechanisms(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="SCRAM-SHA-1"),
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        self.assertFalse(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "invalid-mechanism")
                            )
                        )
                    ),
                    XMLStreamMock.Send(
                        sasl.SASLAuth(mechanism="PLAIN",
                                      payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "mechanism-too-weak")
                            )
                        )
                    )
                ],
                tls_transport=True
            )
        )

    def tearDown(self):
        del self.xmlstream
        del self.transport
        del self.loop
        del self.client_jid

        import random
        sasl._system_random = random.SystemRandom()


class Testnegotiate_stream_security(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = stream_xsos.StreamFeatures()
        self.mechanisms = security_layer.SASLMechanisms()
        self.features[...] = self.mechanisms
        self.features[...] = security_layer.STARTTLSFeature()

        self.post_tls_features = stream_xsos.StreamFeatures()
        self.features[...] = self.mechanisms

        self.post_sasl_features = stream_xsos.StreamFeatures()

        self.password_provider = unittest.mock.MagicMock()

    def _test_provider(self, main_coro,
                       actions=[], stimulus=None):
        return run_coroutine_with_peer(
            main_coro,
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop
        )

    def _coro_return(self, value):
        return value
        yield None

    def test_full_negotiation(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        sasl_provider3 = unittest.mock.MagicMock()
        sasl_provider3.execute.return_value = self._coro_return(True)

        result = self._test_provider(
            security_layer.negotiate_stream_security(
                tls_provider,
                [sasl_provider1,
                 sasl_provider2,
                 sasl_provider3],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features,
                xmlstream=self.xmlstream),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_tls_features
                    )),
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            (self.transport, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider3.execute.assert_not_called()

    def test_sasl_only_negotiation(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(None)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        sasl_provider3 = unittest.mock.MagicMock()
        sasl_provider3.execute.return_value = self._coro_return(True)

        result = self._test_provider(
            security_layer.negotiate_stream_security(
                tls_provider,
                [sasl_provider1,
                 sasl_provider2,
                 sasl_provider3],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features,
                xmlstream=self.xmlstream),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            (None, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            None)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            None)

        sasl_provider3.execute.assert_not_called()

    def test_raise_if_sasl_fails(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        with self.assertRaisesRegexp(errors.SASLUnavailable,
                                     "No common mechanisms"):
            self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        ))
                ]
            )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

    def test_delay_and_propagate_auth_error(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        exc = errors.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(False)

        with self.assertRaises(errors.AuthenticationFailure) as ctx:
            self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        ))
                ]
            )

        self.assertIs(ctx.exception, exc)

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

    def test_swallow_auth_error_if_auth_succeeds_with_different_mech(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        exc = errors.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        result = self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        )),
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_sasl_features
                        ))
                ]
            )

        self.assertEqual(
            (self.transport, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)


class Testsecurity_layer(unittest.TestCase):
    def test_sanity_checks_on_providers(self):
        with self.assertRaises(AttributeError):
            security_layer.security_layer(object(), [unittest.mock.MagicMock()])
        with self.assertRaises(AttributeError):
            security_layer.security_layer(unittest.mock.MagicMock(), [object()])

    def test_require_sasl_provider(self):
        with self.assertRaises(ValueError):
            security_layer.security_layer(unittest.mock.MagicMock(), [])

    @unittest.mock.patch("functools.partial")
    def test_uses_partial(self, partial):
        tls_provider = unittest.mock.MagicMock()
        sasl_providers = [unittest.mock.MagicMock()]
        security_layer.security_layer(tls_provider, sasl_providers)

        partial.assert_called_once_with(
            security_layer.negotiate_stream_security,
            tls_provider,
            sasl_providers)


class Testtls_with_password_based_authentication(unittest.TestCase):
    @unittest.mock.patch("aioxmpp.security_layer.PasswordSASLProvider")
    @unittest.mock.patch("aioxmpp.security_layer.STARTTLSProvider")
    @unittest.mock.patch("aioxmpp.security_layer.security_layer")
    def test_constructs_security_layer(self,
                                       security_layer_fun,
                                       STARTTLSProvider,
                                       PasswordSASLProvider):
        password_provider = object()
        ssl_context_factory = object()
        certificate_verifier_factory = object()
        max_auth_attempts = 4

        security_layer.tls_with_password_based_authentication(
            password_provider,
            ssl_context_factory,
            max_auth_attempts,
            certificate_verifier_factory)

        security_layer_fun.assert_called_once_with(
            tls_provider=STARTTLSProvider(
                ssl_context_factory,
                require_starttls=True,
                certificate_verifier_factory=certificate_verifier_factory),
            sasl_providers=[
                PasswordSASLProvider(
                    password_provider,
                    max_auth_attempts=max_auth_attempts)
            ]
        )
