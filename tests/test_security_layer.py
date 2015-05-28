import asyncio
import unittest

import aioxmpp.errors as errors
import aioxmpp.structs as structs
import aioxmpp.security_layer as security_layer
import aioxmpp.stream_xsos as stream_xsos

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
