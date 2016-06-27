import abc
import asyncio
import collections

import aioxmpp.errors as errors
import aioxmpp.nonza as nonza
import aioxmpp.protocol as protocol
import aioxmpp.security_layer as security_layer
import aioxmpp.ssl_transport as ssl_transport

from aioxmpp.utils import namespaces


class ConnectionMetadata(collections.namedtuple(
        "ConnectionMetadata",
        [
            "ssl_context_factory",
            "certificate_verifier_factory",
            "tls_required",
        ])):
    """
    `ssl_context_factory` must be callable returning a
    :class:`OpenSSL.SSL.Context` instance which is to be used for any SSL
    operations for the connection. It is legit to return the same context for
    all calls to `ssl_context_factory`.

    `certificate_verifier_factory` must be a callable which returns a fresh
    :class:`aioxmpp.security_layer.CertificateVerifier` on each call (it must
    be a fresh instance since :class:`~.security_layer.CertificateVerifier`
    objects are allowed to keep state and :class:`ConnectionMetadata` objects
    are reusable between connection attempts).

    `tls_required` must be a boolean; it indicates whether failure to negotiate
    or establish TLS is critical. Note that setting this to false will not
    cause invalid TLS sessions (e.g. with invalid certificates) to be used.
    This only affects situations where the server is not offering TLS or where
    STARTTLS fails.
    """


class BaseConnector(metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def tls_supported(self):
        """
        Boolean which indicates whether TLS is supported by this connector.
        """

    @abc.abstractproperty
    def dane_supported(self):
        """
        Boolean which indicates whether DANE is supported by this connector.
        """

    @abc.abstractmethod
    @asyncio.coroutine
    def connect(self, loop, metadata, domain, host, port):
        """
        Establish a :class:`.protocol.XMLStream` for `domain` with the given
        `host` at the given TCP `port`.

        `metadata` must be a :class:`ConnectionMetadata` instance to use for
        the connection. `loop` must be a :class:`asyncio.BaseEventLoop` to use.

        Return a triple consisting of the :class:`asyncio.Transport`, the
        :class:`.protocol.XMLStream` and a :class:`asyncio.Future` on the
        :class:`aioxmpp.nonza.StreamFeatures` of the stream.

        To detect the use of TLS on the stream, check whether
        :meth:`asyncio.Transport.get_extra_info` returns a non-:data:`None`
        value for ``"ssl_object"``.
        """


class STARTTLSConnector(BaseConnector):
    @property
    def tls_supported(self):
        return True

    @property
    def dane_supported(self):
        return False

    @asyncio.coroutine
    def connect(self, loop, metadata, domain, host, port,
                negotiation_timeout):
        features_future = asyncio.Future(loop=loop)

        stream = protocol.XMLStream(
            to=domain,
            features_future=features_future,
        )

        transport, _ = yield from ssl_transport.create_starttls_connection(
            loop,
            lambda: stream,
            host=host,
            port=port,
            peer_hostname=host,
            server_hostname=domain,
            use_starttls=True,
        )

        features = yield from features_future

        try:
            features[nonza.StartTLSFeature]
        except KeyError:
            if metadata.tls_required:
                message = (
                    "STARTTLS not supported by server, but required by client"
                )

                protocol.send_stream_error_and_close(
                    stream,
                    condition=(namespaces.streams, "policy-violation"),
                    text=message,
                )

                raise errors.TLSUnavailable(message)
            else:
                return transport, stream, features_future

        response = yield from protocol.send_and_wait_for(
            stream,
            [
                nonza.StartTLS(),
            ],
            [
                nonza.StartTLSFailure,
                nonza.StartTLSProceed,
            ]
        )

        if not isinstance(response, nonza.StartTLSProceed):
            if metadata.tls_required:
                message = (
                    "server failed to STARTTLS"
                )

                protocol.send_stream_error_and_close(
                    stream,
                    condition=(namespaces.streams, "policy-violation"),
                    text=message,
                )

                raise errors.TLSUnavailable(message)
            return transport, stream, features_future

        verifier = metadata.certificate_verifier_factory()
        yield from verifier.pre_handshake(transport)

        ssl_context = metadata.ssl_context_factory()
        verifier.setup_context(ssl_context)

        yield from stream.starttls(
            ssl_context=ssl_context,
            post_handshake_callback=verifier.post_handshake,
        )

        features_future = asyncio.async(
            protocol.reset_stream_and_get_features(
                stream,
                timeout=negotiation_timeout,
            ),
            loop=loop,
        )

        return transport, stream, features_future


class XMPPOverTLSConnector:
    """
    The XMPP-over-TLS connector implements the connection part of :xep:`368`.
    """
