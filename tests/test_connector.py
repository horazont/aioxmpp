import asyncio
import contextlib
import unittest
import unittest.mock

import aioxmpp.connector as connector
import aioxmpp.errors as errors
import aioxmpp.nonza as nonza
import aioxmpp.security_layer as security_layer

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    run_coroutine,
    CoroutineMock,
)


class TestSTARTTLSConnector(unittest.TestCase):
    def setUp(self):
        self.c = connector.STARTTLSConnector()

    def test_tls_supported(self):
        self.assertTrue(
            self.c.tls_supported
        )

    def test_connect_successful(self):
        captured_features_future = None

        def capture_future(*args, features_future=None, **kwargs):
            nonlocal captured_features_future
            captured_features_future = features_future
            return base.protocol

        features = nonza.StreamFeatures()
        features[...] = nonza.StartTLSFeature()

        features_future = asyncio.Future()
        features_future.set_result(
            features
        )

        base = unittest.mock.Mock()
        base.protocol.starttls = CoroutineMock()
        base.create_starttls_connection = CoroutineMock()
        base.create_starttls_connection.return_value = (
            unittest.mock.sentinel.transport,
            base.protocol,
        )
        base.metadata.tls_required = True
        base.XMLStream.return_value = base.protocol
        base.XMLStream.side_effect = capture_future
        base.Future.return_value = features_future
        base.send_and_wait_for = CoroutineMock()
        base.send_and_wait_for.return_value = unittest.mock.Mock(
            spec=nonza.StartTLSProceed,
        )
        base.certificate_verifier.pre_handshake = CoroutineMock()
        base.metadata.certificate_verifier_factory.return_value = \
            base.certificate_verifier
        base.metadata.ssl_context_factory.return_value = \
            unittest.mock.sentinel.ssl_context
        base.reset_stream_and_get_features.return_value = \
            unittest.mock.sentinel.reset
        base.async_.return_value = unittest.mock.sentinel.features_future

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.Future",
                    new=base.Future,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.ssl_transport.create_starttls_connection",
                    new=base.create_starttls_connection,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.XMLStream",
                    new=base.XMLStream,
                )
            )

            StartTLS_nonza = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.nonza.StartTLS",
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_and_wait_for",
                    new=base.send_and_wait_for,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.reset_stream_and_get_features",
                    new=base.reset_stream_and_get_features,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.async",
                    new=base.async_,
                )
            )

            result = run_coroutine(self.c.connect(
                unittest.mock.sentinel.loop,
                base.metadata,
                unittest.mock.sentinel.domain,
                unittest.mock.sentinel.host,
                unittest.mock.sentinel.port,
                unittest.mock.sentinel.timeout,
            ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.Future(
                    loop=unittest.mock.sentinel.loop,
                ),
                unittest.mock.call.XMLStream(
                    to=unittest.mock.sentinel.domain,
                    features_future=features_future,
                ),
                unittest.mock.call.create_starttls_connection(
                    unittest.mock.sentinel.loop,
                    unittest.mock.ANY,
                    host=unittest.mock.sentinel.host,
                    port=unittest.mock.sentinel.port,
                    peer_hostname=unittest.mock.sentinel.host,
                    server_hostname=unittest.mock.sentinel.domain,
                    use_starttls=True,
                ),
                unittest.mock.call.send_and_wait_for(
                    base.protocol,
                    [
                        StartTLS_nonza(),
                    ],
                    [
                        nonza.StartTLSFailure,
                        nonza.StartTLSProceed,
                    ]
                ),
                unittest.mock.call.metadata.certificate_verifier_factory(),
                unittest.mock.call.certificate_verifier.pre_handshake(
                    unittest.mock.sentinel.transport,
                ),
                unittest.mock.call.metadata.ssl_context_factory(),
                unittest.mock.call.certificate_verifier.setup_context(
                    unittest.mock.sentinel.ssl_context
                ),
                unittest.mock.call.protocol.starttls(
                    ssl_context=unittest.mock.sentinel.ssl_context,
                    post_handshake_callback=base.certificate_verifier.post_handshake,
                ),
                unittest.mock.call.reset_stream_and_get_features(
                    base.protocol,
                    timeout=unittest.mock.sentinel.timeout,
                ),
                unittest.mock.call.async_(
                    unittest.mock.sentinel.reset,
                    loop=unittest.mock.sentinel.loop,
                )
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                base.protocol,
                unittest.mock.sentinel.features_future,
            )
        )

    def test_connect_without_starttls_support_and_with_required(self):
        captured_features_future = None

        def capture_future(*args, features_future=None, **kwargs):
            nonlocal captured_features_future
            captured_features_future = features_future
            return base.protocol

        features = nonza.StreamFeatures()

        features_future = asyncio.Future()
        features_future.set_result(
            features
        )

        base = unittest.mock.Mock()
        base.protocol.starttls = CoroutineMock()
        base.create_starttls_connection = CoroutineMock()
        base.create_starttls_connection.return_value = (
            base.transport,
            base.protocol,
        )
        base.metadata.tls_required = True
        base.XMLStream.return_value = base.protocol
        base.XMLStream.side_effect = capture_future
        base.Future.return_value = features_future

        error_message = (
            "STARTTLS not supported by server, but required by client"
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.Future",
                    new=base.Future,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.ssl_transport.create_starttls_connection",
                    new=base.create_starttls_connection,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.XMLStream",
                    new=base.XMLStream,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_stream_error_and_close",
                    new=base.send_stream_error_and_close,
                )
            )

            with self.assertRaisesRegex(errors.TLSUnavailable, error_message):
                run_coroutine(self.c.connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    unittest.mock.sentinel.domain,
                    unittest.mock.sentinel.host,
                    unittest.mock.sentinel.port,
                    unittest.mock.sentinel.timeout,
                ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.Future(
                    loop=unittest.mock.sentinel.loop,
                ),
                unittest.mock.call.XMLStream(
                    to=unittest.mock.sentinel.domain,
                    features_future=features_future,
                ),
                unittest.mock.call.create_starttls_connection(
                    unittest.mock.sentinel.loop,
                    unittest.mock.ANY,
                    host=unittest.mock.sentinel.host,
                    port=unittest.mock.sentinel.port,
                    peer_hostname=unittest.mock.sentinel.host,
                    server_hostname=unittest.mock.sentinel.domain,
                    use_starttls=True,
                ),
                unittest.mock.call.send_stream_error_and_close(
                    base.protocol,
                    condition=(namespaces.streams, "policy-violation"),
                    text=error_message,
                )
            ]
        )

    def test_connect_without_starttls_support_and_without_required(self):
        captured_features_future = None

        def capture_future(*args, features_future=None, **kwargs):
            nonlocal captured_features_future
            captured_features_future = features_future
            return base.protocol

        features = nonza.StreamFeatures()

        features_future = asyncio.Future()
        features_future.set_result(
            features
        )

        base = unittest.mock.Mock()
        base.protocol.starttls = CoroutineMock()
        base.create_starttls_connection = CoroutineMock()
        base.create_starttls_connection.return_value = (
            unittest.mock.sentinel.transport,
            base.protocol,
        )
        base.metadata.tls_required = False
        base.XMLStream.return_value = base.protocol
        base.XMLStream.side_effect = capture_future
        base.Future.return_value = features_future

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.Future",
                    new=base.Future,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.ssl_transport.create_starttls_connection",
                    new=base.create_starttls_connection,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.XMLStream",
                    new=base.XMLStream,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_stream_error_and_close",
                    new=base.send_stream_error_and_close,
                )
            )

            result = run_coroutine(self.c.connect(
                unittest.mock.sentinel.loop,
                base.metadata,
                unittest.mock.sentinel.domain,
                unittest.mock.sentinel.host,
                unittest.mock.sentinel.port,
                unittest.mock.sentinel.timeout,
            ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.Future(
                    loop=unittest.mock.sentinel.loop,
                ),
                unittest.mock.call.XMLStream(
                    to=unittest.mock.sentinel.domain,
                    features_future=features_future,
                ),
                unittest.mock.call.create_starttls_connection(
                    unittest.mock.sentinel.loop,
                    unittest.mock.ANY,
                    host=unittest.mock.sentinel.host,
                    port=unittest.mock.sentinel.port,
                    peer_hostname=unittest.mock.sentinel.host,
                    server_hostname=unittest.mock.sentinel.domain,
                    use_starttls=True,
                ),
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                base.protocol,
                captured_features_future,
            )
        )

    def test_connect_with_failed_starttls_and_with_required(self):
        captured_features_future = None

        def capture_future(*args, features_future=None, **kwargs):
            nonlocal captured_features_future
            captured_features_future = features_future
            return base.protocol

        features = nonza.StreamFeatures()
        features[...] = nonza.StartTLSFeature()

        features_future = asyncio.Future()
        features_future.set_result(
            features
        )

        base = unittest.mock.Mock()
        base.protocol.starttls = CoroutineMock()
        base.create_starttls_connection = CoroutineMock()
        base.create_starttls_connection.return_value = (
            unittest.mock.sentinel.transport,
            base.protocol,
        )
        base.metadata.tls_required = True
        base.XMLStream.return_value = base.protocol
        base.XMLStream.side_effect = capture_future
        base.Future.return_value = features_future
        base.send_and_wait_for = CoroutineMock()
        base.send_and_wait_for.return_value = unittest.mock.Mock(
            spec=nonza.StartTLSFailure,
        )

        error_message = (
            "server failed to STARTTLS"
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.Future",
                    new=base.Future,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.ssl_transport.create_starttls_connection",
                    new=base.create_starttls_connection,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.XMLStream",
                    new=base.XMLStream,
                )
            )

            StartTLS_nonza = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.nonza.StartTLS",
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_and_wait_for",
                    new=base.send_and_wait_for,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_stream_error_and_close",
                    new=base.send_stream_error_and_close
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.async",
                    new=base.async_,
                )
            )

            with self.assertRaisesRegex(errors.TLSUnavailable, error_message):
                run_coroutine(self.c.connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    unittest.mock.sentinel.domain,
                    unittest.mock.sentinel.host,
                    unittest.mock.sentinel.port,
                    unittest.mock.sentinel.timeout,
                ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.Future(
                    loop=unittest.mock.sentinel.loop,
                ),
                unittest.mock.call.XMLStream(
                    to=unittest.mock.sentinel.domain,
                    features_future=features_future,
                ),
                unittest.mock.call.create_starttls_connection(
                    unittest.mock.sentinel.loop,
                    unittest.mock.ANY,
                    host=unittest.mock.sentinel.host,
                    port=unittest.mock.sentinel.port,
                    peer_hostname=unittest.mock.sentinel.host,
                    server_hostname=unittest.mock.sentinel.domain,
                    use_starttls=True,
                ),
                unittest.mock.call.send_and_wait_for(
                    base.protocol,
                    [
                        StartTLS_nonza(),
                    ],
                    [
                        nonza.StartTLSFailure,
                        nonza.StartTLSProceed,
                    ]
                ),
                unittest.mock.call.send_stream_error_and_close(
                    base.protocol,
                    condition=(namespaces.streams, "policy-violation"),
                    text=error_message,
                )
            ]
        )

    def test_connect_with_failed_starttls_and_without_required(self):
        captured_features_future = None

        def capture_future(*args, features_future=None, **kwargs):
            nonlocal captured_features_future
            captured_features_future = features_future
            return base.protocol

        features = nonza.StreamFeatures()
        features[...] = nonza.StartTLSFeature()

        features_future = asyncio.Future()
        features_future.set_result(
            features
        )

        base = unittest.mock.Mock()
        base.protocol.starttls = CoroutineMock()
        base.create_starttls_connection = CoroutineMock()
        base.create_starttls_connection.return_value = (
            unittest.mock.sentinel.transport,
            base.protocol,
        )
        base.metadata.tls_required = False
        base.XMLStream.return_value = base.protocol
        base.XMLStream.side_effect = capture_future
        base.Future.return_value = features_future
        base.send_and_wait_for = CoroutineMock()
        base.send_and_wait_for.return_value = unittest.mock.Mock(
            spec=nonza.StartTLSFailure,
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.Future",
                    new=base.Future,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.ssl_transport.create_starttls_connection",
                    new=base.create_starttls_connection,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.XMLStream",
                    new=base.XMLStream,
                )
            )

            StartTLS_nonza = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.nonza.StartTLS",
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_and_wait_for",
                    new=base.send_and_wait_for,
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.protocol.send_stream_error_and_close",
                    new=base.send_stream_error_and_close
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "asyncio.async",
                    new=base.async_,
                )
            )

            result = run_coroutine(self.c.connect(
                unittest.mock.sentinel.loop,
                base.metadata,
                unittest.mock.sentinel.domain,
                unittest.mock.sentinel.host,
                unittest.mock.sentinel.port,
                unittest.mock.sentinel.timeout,
            ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.Future(
                    loop=unittest.mock.sentinel.loop,
                ),
                unittest.mock.call.XMLStream(
                    to=unittest.mock.sentinel.domain,
                    features_future=features_future,
                ),
                unittest.mock.call.create_starttls_connection(
                    unittest.mock.sentinel.loop,
                    unittest.mock.ANY,
                    host=unittest.mock.sentinel.host,
                    port=unittest.mock.sentinel.port,
                    peer_hostname=unittest.mock.sentinel.host,
                    server_hostname=unittest.mock.sentinel.domain,
                    use_starttls=True,
                ),
                unittest.mock.call.send_and_wait_for(
                    base.protocol,
                    [
                        StartTLS_nonza(),
                    ],
                    [
                        nonza.StartTLSFailure,
                        nonza.StartTLSProceed,
                    ]
                )
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                base.protocol,
                captured_features_future,
            )
        )

    def tearDown(self):
        del self.c
