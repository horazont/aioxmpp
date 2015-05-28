import asyncio
import unittest

import aioxmpp.errors as errors
import aioxmpp.sasl as sasl
import aioxmpp.structs as structs
import aioxmpp.security_layer as security_layer
import aioxmpp.stream_xsos as stream_xsos

from aioxmpp.utils import namespaces

from .testutils import XMLStreamMock, run_coroutine
from . import xmltestutils


class TestSTARTTLSProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.ssl_context_factory = unittest.mock.MagicMock()
        self.certificate_verifier_factory = unittest.mock.MagicMock()

    def _test_provider(self, provider, features, actions=[], stimulus=None):
        result1, result2 = run_coroutine(
            asyncio.gather(
                provider.execute(self.client_jid,
                                 features,
                                 self.xmlstream),
                self.xmlstream.run_test(actions, stimulus=stimulus),
                return_exceptions=True),
        )
        if isinstance(result1, Exception):
            raise result1
        if isinstance(result2, Exception):
            raise result2
        return result1

    def test_require_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "not supported by peer"):
            self._test_provider(provider, features)

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
                    ssl_context=self.ssl_context_factory(),
                    post_handshake_callback=
                    self.certificate_verifier_factory().post_handshake
                )
            ]
        )

        self.assertIs(result, self.transport)

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
        provider_future = asyncio.async(
            provider.execute(self.client_jid,
                             self.features,
                             self.xmlstream,
                             tls_transport),
            loop=self.loop)
        test_future = asyncio.async(
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

        done, pending = run_coroutine(
            asyncio.wait(
                [
                    provider_future,
                    test_future,
                ],
                return_when=asyncio.FIRST_EXCEPTION),
        )

        if pending:
            next(iter(pending)).cancel()
            # this must throw
            next(iter(done)).result()
            assert False

        if provider_future.exception():
            # re-throw the exception properly
            provider_future.result()

        # throw if any
        test_future.result()

        # return correct result
        return provider_future.result()

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
        provider_future = asyncio.async(main_coro,
                                        loop=self.loop)
        test_future = asyncio.async(
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

        done, pending = run_coroutine(
            asyncio.wait(
                [
                    provider_future,
                    test_future,
                ],
                return_when=asyncio.FIRST_EXCEPTION),
        )

        if pending:
            next(iter(pending)).cancel()
            # this must throw
            next(iter(done)).result()
            assert False

        if provider_future.exception():
            # re-throw the exception properly
            provider_future.result()

        # throw if any
        test_future.result()

        # return correct result
        return provider_future.result()

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
