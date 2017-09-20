########################################################################
# File name: connector.py
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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.connector` --- Ways to establish XML streams
###########################################################

This module provides classes to establish XML streams. Currently, there are two
different ways to establish XML streams: normal TCP connection which is then
upgraded using STARTTLS, and directly using TLS.

.. versionadded:: 0.6

   The whole module was added in version 0.6.

Abstract base class
===================

The connectors share a common abstract base class, :class:`BaseConnector`:

.. autoclass:: BaseConnector

Specific connectors
===================

.. autoclass:: STARTTLSConnector

.. autoclass:: XMPPOverTLSConnector

"""

import abc
import asyncio

import aioxmpp.errors as errors
import aioxmpp.nonza as nonza
import aioxmpp.protocol as protocol
import aioxmpp.ssl_transport as ssl_transport

from aioxmpp.utils import namespaces


class BaseConnector(metaclass=abc.ABCMeta):
    """
    This is the base class for connectors. It defines the public interface of
    all connectors.

    .. autoattribute:: tls_supported

    .. automethod:: connect

    Existing connectors:

    .. autosummary::

       STARTTLSConnector
       XMPPOverTLSConnector

    """

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
    def connect(self, loop, metadata, domain, host, port, negotiation_timeout,
                base_logger=None):
        """
        Establish a :class:`.protocol.XMLStream` for `domain` with the given
        `host` at the given TCP `port`.

        `metadata` must be a :class:`.security_layer.SecurityLayer` instance to
        use for the connection. `loop` must be a :class:`asyncio.BaseEventLoop`
        to use.

        `negotiation_timeout` must be the maximum time in seconds to wait for
        the server to reply in each negotiation step.

        Return a triple consisting of the :class:`asyncio.Transport`, the
        :class:`.protocol.XMLStream` and the
        :class:`aioxmpp.nonza.StreamFeatures` of the stream.

        To detect the use of TLS on the stream, check whether
        :meth:`asyncio.Transport.get_extra_info` returns a non-:data:`None`
        value for ``"ssl_object"``.

        `base_logger` is passed to :class:`aioxmpp.protocol.XMLStream`.
        """


class STARTTLSConnector(BaseConnector):
    """
    Establish an XML stream using STARTTLS.

    .. automethod:: connect
    """

    @property
    def tls_supported(self):
        return True

    @property
    def dane_supported(self):
        return False

    @asyncio.coroutine
    def connect(self, loop, metadata, domain: str, host, port,
                negotiation_timeout, base_logger=None):
        """
        .. seealso::

           :meth:`BaseConnector.connect`
              For general information on the :meth:`connect` method.

        Connect to `host` at TCP port number `port`. The
        :class:`aioxmpp.security_layer.SecurityLayer` object `metadata` is used
        to determine the parameters of the TLS connection.

        First, a normal TCP connection is opened and the stream header is sent.
        The stream features are waited for, and then STARTTLS is negotiated if
        possible.

        :attr:`~.security_layer.SecurityLayer.tls_required` is honoured: if it
        is true and the server does not offer TLS or TLS negotiation fails,
        :class:`~.errors.TLSUnavailable` is raised.

        :attr:`~.security_layer.SecurityLayer.ssl_context_factory` and
        :attr:`~.security_layer.SecurityLayer.certificate_verifier_factory` are
        used to configure the TLS connection.
        """

        features_future = asyncio.Future(loop=loop)

        stream = protocol.XMLStream(
            to=domain,
            features_future=features_future,
            base_logger=base_logger,
        )

        try:
            transport, _ = yield from ssl_transport.create_starttls_connection(
                loop,
                lambda: stream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=domain,
                use_starttls=True,
            )
        except:
            stream.abort()
            raise

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
                return transport, stream, (yield from features_future)

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
            return transport, stream, (yield from features_future)

        verifier = metadata.certificate_verifier_factory()
        yield from verifier.pre_handshake(
            domain,
            host,
            port,
            metadata,
        )

        ssl_context = metadata.ssl_context_factory()
        verifier.setup_context(ssl_context, transport)

        yield from stream.starttls(
            ssl_context=ssl_context,
            post_handshake_callback=verifier.post_handshake,
        )

        features_future = yield from protocol.reset_stream_and_get_features(
            stream,
            timeout=negotiation_timeout,
        )

        return transport, stream, features_future


class XMPPOverTLSConnector(BaseConnector):
    """
    Establish an XML stream using XMPP-over-TLS, as per :xep:`368`.

    .. automethod:: connect
    """

    @property
    def dane_supported(self):
        return False

    @property
    def tls_supported(self):
        return True

    @asyncio.coroutine
    def connect(self, loop, metadata, domain, host, port,
                negotiation_timeout, base_logger=None):
        """
        .. seealso::

           :meth:`BaseConnector.connect`
              For general information on the :meth:`connect` method.

        Connect to `host` at TCP port number `port`. The
        :class:`aioxmpp.security_layer.SecurityLayer` object `metadata` is used
        to determine the parameters of the TLS connection.

        The connector connects to the server by directly establishing TLS; no
        XML stream is started before TLS negotiation, in accordance to
        :xep:`368` and how legacy SSL was handled in the past.

        :attr:`~.security_layer.SecurityLayer.ssl_context_factory` and
        :attr:`~.security_layer.SecurityLayer.certificate_verifier_factory` are
        used to configure the TLS connection.
        """


        features_future = asyncio.Future(loop=loop)

        stream = protocol.XMLStream(
            to=domain,
            features_future=features_future,
            base_logger=base_logger,
        )

        verifier = metadata.certificate_verifier_factory()
        yield from verifier.pre_handshake(
            domain,
            host,
            port,
            metadata,
        )

        def context_factory(transport):
            ssl_context = metadata.ssl_context_factory()
            verifier.setup_context(ssl_context, transport)
            return ssl_context

        try:
            transport, _ = yield from ssl_transport.create_starttls_connection(
                loop,
                lambda: stream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=domain,
                post_handshake_callback=verifier.post_handshake,
                ssl_context_factory=context_factory,
                use_starttls=False,
            )
        except:
            stream.abort()
            raise

        return transport, stream, (yield from features_future)
