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
import logging

from datetime import timedelta

import aioxmpp.errors as errors
import aioxmpp.nonza as nonza
import aioxmpp.protocol as protocol
import aioxmpp.ssl_transport as ssl_transport


def to_ascii(s):
    return s.encode("idna").decode("ascii")


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
    async def connect(self, loop, metadata, domain, host, port,
                      negotiation_timeout,
                      base_logger=None):
        """
        Establish a :class:`.protocol.XMLStream` for `domain` with the given
        `host` at the given TCP `port`.

        `metadata` must be a :class:`.security_layer.SecurityLayer` instance to
        use for the connection. `loop` must be a :class:`asyncio.BaseEventLoop`
        to use.

        `negotiation_timeout` must be the maximum time in seconds to wait for
        the server to reply in each negotiation step. The `negotiation_timeout`
        is used as value for
        :attr:`~aioxmpp.protocol.XMLStream.deadtime_hard_limit` in the returned
        stream.

        Return a triple consisting of the :class:`asyncio.Transport`, the
        :class:`.protocol.XMLStream` and the
        :class:`aioxmpp.nonza.StreamFeatures` of the stream.

        To detect the use of TLS on the stream, check whether
        :meth:`asyncio.Transport.get_extra_info` returns a non-:data:`None`
        value for ``"ssl_object"``.

        `base_logger` is passed to :class:`aioxmpp.protocol.XMLStream`.

        .. versionchanged:: 0.10

            Assignment of
            :attr:`~aioxmpp.protocol.XMLStream.deadtime_hard_limit` was added.
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

    async def connect(self, loop, metadata, domain: str, host, port,
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
        is true and TLS negotiation fails, :class:`~.errors.TLSUnavailable` is
        raised. TLS negotiation is always attempted if
        :attr:`~.security_layer.SecurityLayer.tls_required` is true, even if
        the server does not advertise a STARTTLS stream feature. This might
        help to prevent trivial downgrade attacks, and we don’t have anything
        to lose at this point anymore anyways.

        :attr:`~.security_layer.SecurityLayer.ssl_context_factory` and
        :attr:`~.security_layer.SecurityLayer.certificate_verifier_factory` are
        used to configure the TLS connection.

        .. versionchanged:: 0.10

            The `negotiation_timeout` is set as
            :attr:`~.XMLStream.deadtime_hard_limit` on the returned XML stream.
        """

        features_future = asyncio.Future(loop=loop)

        stream = protocol.XMLStream(
            to=domain,
            features_future=features_future,
            base_logger=base_logger,
        )
        if base_logger is not None:
            logger = base_logger.getChild(type(self).__name__)
        else:
            logger = logging.getLogger(".".join([
                __name__, type(self).__qualname__,
            ]))

        try:
            transport, _ = await ssl_transport.create_starttls_connection(
                loop,
                lambda: stream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=to_ascii(domain),
                use_starttls=True,
            )
        except:  # NOQA
            stream.abort()
            raise

        stream.deadtime_hard_limit = timedelta(seconds=negotiation_timeout)

        features = await features_future

        try:
            features[nonza.StartTLSFeature]
        except KeyError:
            if not metadata.tls_required:
                return transport, stream, await features_future
            logger.debug(
                "attempting STARTTLS despite not announced since it is"
                " required")

        try:
            response = await protocol.send_and_wait_for(
                stream,
                [
                    nonza.StartTLS(),
                ],
                [
                    nonza.StartTLSFailure,
                    nonza.StartTLSProceed,
                ]
            )
        except errors.StreamError:
            raise errors.TLSUnavailable(
                "STARTTLS not supported by server, but required by client"
            )

        if not isinstance(response, nonza.StartTLSProceed):
            if metadata.tls_required:
                message = (
                    "server failed to STARTTLS"
                )

                protocol.send_stream_error_and_close(
                    stream,
                    condition=errors.StreamErrorCondition.POLICY_VIOLATION,
                    text=message,
                )

                raise errors.TLSUnavailable(message)
            return transport, stream, await features_future

        verifier = metadata.certificate_verifier_factory()
        await verifier.pre_handshake(
            domain,
            host,
            port,
            metadata,
        )

        ssl_context = metadata.ssl_context_factory()
        verifier.setup_context(ssl_context, transport)

        await stream.starttls(
            ssl_context=ssl_context,
            post_handshake_callback=verifier.post_handshake,
        )

        features = await protocol.reset_stream_and_get_features(
            stream,
            timeout=negotiation_timeout,
        )

        return transport, stream, features


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

    def _context_factory_factory(self, logger, metadata, verifier):
        def context_factory(transport):
            ssl_context = metadata.ssl_context_factory()

            if hasattr(ssl_context, "set_alpn_protos"):
                try:
                    ssl_context.set_alpn_protos([b'xmpp-client'])
                except NotImplementedError:
                    logger.warning(
                        "the underlying OpenSSL library does not support ALPN"
                    )
            else:
                logger.warning(
                    "OpenSSL.SSL.Context lacks set_alpn_protos - "
                    "please update pyOpenSSL to a recent version"
                )

            verifier.setup_context(ssl_context, transport)
            return ssl_context
        return context_factory

    async def connect(self, loop, metadata, domain, host, port,
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

        .. versionchanged:: 0.10

            The `negotiation_timeout` is set as
            :attr:`~.XMLStream.deadtime_hard_limit` on the returned XML stream.
        """

        features_future = asyncio.Future(loop=loop)

        stream = protocol.XMLStream(
            to=domain,
            features_future=features_future,
            base_logger=base_logger,
        )

        if base_logger is not None:
            logger = base_logger.getChild(type(self).__name__)
        else:
            logger = logging.getLogger(".".join([
                __name__, type(self).__qualname__,
            ]))

        verifier = metadata.certificate_verifier_factory()
        await verifier.pre_handshake(
            domain,
            host,
            port,
            metadata,
        )

        context_factory = self._context_factory_factory(logger, metadata,
                                                        verifier)

        try:
            transport, _ = await ssl_transport.create_starttls_connection(
                loop,
                lambda: stream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=to_ascii(domain),
                post_handshake_callback=verifier.post_handshake,
                ssl_context_factory=context_factory,
                use_starttls=False,
            )
        except:  # NOQA
            stream.abort()
            raise

        stream.deadtime_hard_limit = timedelta(seconds=negotiation_timeout)

        return transport, stream, await features_future
