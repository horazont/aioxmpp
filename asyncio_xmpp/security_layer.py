"""
:mod:`~asyncio_xmpp.security_layer` --- Implementations to negotiate stream security
####################################################################################

This module provides different implementations of the security layer (TLS+SASL).

These are coupled, as different SASL features might need different TLS features
(such as channel binding or client cert authentication).

.. autofunction:: negotiate_stream_security

Partial security providers
==========================

Partial security providers serve as arguments to pass to
:func:`negotiate_stream_security`.

.. _tls providers:

Transport layer security provider
---------------------------------

As an *tls_provider* argument to :class:`SecurityLayer`, instances of the
following classes can be used:

.. autoclass:: STARTTLSProvider

.. _sasl providers:

SASL providers
--------------

As elements of the *sasl_providers* argument to :class:`SecurityLayer`,
instances of the following classes can be used:

.. autoclass:: PasswordSASLProvider

Abstract base classes
=====================

For implementation of custom SASL providers, the following base class can be
used:

.. autoclass:: SASLProvider
   :members:

"""
import abc
import asyncio
import logging

from . import errors, sasl
from .utils import *

logger = logging.getLogger(__name__)

class STARTTLSProvider:
    """
    A TLS provider to negotiate STARTTLS on an existing XML stream. This
    requires that the stream uses
    :class:`.ssl_wrapper.STARTTLSableTransportProtocol` as a transport.

    *ssl_context_factory* must be a callable returning a valid
    :class:`ssl.SSLContext` object. It is called without
    arguments. *server_hostname* must be the host name to validate the
    certificate against.

    *require_starttls* can be set to :data:`False` to allow stream negotiation
    to continue even if STARTTLS fails before it has been started (the stream is
    fatally broken if the STARTTLS command has been sent but SSL negotiation
    fails afterwards).

    .. warning::

       Certificate validation requires Python 3.4 to work properly!

    .. note::

       Support for DANE has not been implemented yet, as this also requires
       Python 3.4 and the main developer does not have Python 3.4 yet.

    """

    def __init__(self, ssl_context_factory, server_hostname, *,
                 require_starttls=True, **kwargs):
        super().__init__(**kwargs)
        self._ssl_context_factory = ssl_context_factory
        self._server_hostname = server_hostname
        self._required = require_starttls

    def _fail_if_required(self, msg):
        if self._required:
            raise errors.TLSFailure(msg)
        return False

    @asyncio.coroutine
    def execute(self, features, xmlstream):
        """
        Perform STARTTLS negotiation. If successful, a ``(tls_transport,
        new_features)`` pair is returned. Otherwise, if STARTTLS failed
        non-fatally and is not required (see constructor arguments),
        :data:`False` is returned.

        The *tls_transport* member of the return value is the
        :class:`asyncio.Transport` created by asyncio for SSL. The second
        element are the new stream features received after STARTTLS
        negotiation.
        """

        try:
            feature = features.require_feature(
                "{{{}}}starttls".format(namespaces.starttls)
            )
        except KeyError:
            return self._fail_if_required("STARTTLS not supported by peer")

        if not hasattr(xmlstream.transport, "starttls"):
            return self._fail_if_required("STARTTLS not supported by us")

        node = yield from xmlstream.send_and_wait_for(
            [
                xmlstream.tx_context("{{{}}}starttls".format(
                    namespaces.starttls))
            ],
            [
                "{{{}}}proceed".format(namespaces.starttls),
                "{{{}}}failure".format(namespaces.starttls),
            ]
        )

        proceed = node.tag.endswith("}proceed")

        if proceed:
            logger.info("engaging STARTTLS")
            try:
                tls_transport, _ = yield from xmlstream.transport.starttls(
                    ssl_context=self._ssl_context_factory(),
                    server_hostname=self._server_hostname)
            except Exception as err:
                logger.exception("STARTTLS failed:")
                raise errors.TLSFailure("TLS connection failed: {}".format(err))
            new_features = yield from xmlstream.reset_stream_and_get_features()
            return tls_transport, new_features

        return self._fail_if_required("STARTTLS failed on remote side")

class SASLProvider:
    def __init__(self, jid, **kwargs):
        super().__init__(**kwargs)
        self._jid = jid.bare if hasattr("jid", "bare") else str(jid)

    def _find_supported(self, features, mechanism_classes):
        try:
            mechanisms = features.require_feature("{{{}}}mechanisms".format(
                namespaces.sasl))
        except KeyError:
            raise SASLFailure("Remote side does not support SASL") from None

        for our_mechanism in self._mechansim_classes:
            token = our_mechanism.any_supported(mechanisms)
            if token is not None:
                return our_mechanism, token

        return None, None

    @asyncio.coroutine
    def _execute(self, xmlstream, mechanism, token):
        sm = sasl.SASLStateMachine(xmlstream)
        yield from mechanism.authenticate(sm, token)

    @abc.abstractmethod
    @asyncio.coroutine
    def execute(self, features, xmlstream, tls_transport):
        """
        Perform SASL negotiation. The implementation depends on the specific
        :class:`SASLProvider` subclass in use.

        This coroutine returns :data:`True` if the negotiation was
        successful. If no common mechanisms could be found, :data:`False` is
        returned. This is useful to chain several SASL providers (e.g. a
        provider supporting ``EXTERNAL`` in front of password-based providers).

        Any other error case, such as no SASL support on the remote side or
        authentication failure results in an :class:`~.errors.SASLFailure`
        exception to be raised.
        """

class PasswordSASLProvider(SASLProvider):
    """
    Perform password-based SASL authentication.

    *jid* must be a :class:`~.jid.JID` object for the
    client. *password_provider* must be a coroutine which is called with the jid
    as first and the number of attempt as second argument. It must return the
    password to us, or :data:`None` to abort. In that case, an
    :class:`errors.AuthenticationFailure` error will be raised.

    At most *max_auth_attempts* will be carried out. If all fail, the
    authentication error of the last attempt is raised.

    The SASL mechanisms used depend on whether TLS has been negotiated
    successfully before. In any case, :class:`~.sasl.SCRAM` is used. If TLS has
    been negotiated, :class:`~.sasl.PLAIN` is also supported.
    """

    def __init__(self, jid, password_provider, *,
                 max_auth_attempts=3, **kwargs):
        super().__init__(jid, **kwargs)
        self._password_provider = password_provider
        self._nattempt = 0
        self._max_auth_attempts = max_auth_attempts

    @asyncio.coroutine
    def _credential_provider(self):
        password = yield from self._password_provider(self._jid, self._nattempt)
        if password is None:
            self._password_signalled_abort = True
            raise errors.AuthenticationFailure("Authentication aborted by user")
        return self._jid.localpart, password

    @asyncio.coroutine
    def execute(self, features, xmlstream, tls_transport):
        self._password_signalled_abort = False

        classes = [
            sasl.SCRAM
        ]
        if xmlstream.tls_engaged:
            classes.append(sasl.PLAIN)

        mechanism_class, token = self._find_supported(features, classes)
        if mechanism_class is None:
            return False

        mechanism = mechanism_class(self._credential_provider)
        last_auth_error = None
        for i in range(self._max_auth_attempts):
            try:
                yield from self._execute(xmlstream, mechanism, token)
            except sasl.AuthenticationError as err:
                if self._password_signalled_abort:
                    # immediately re-raise
                    raise
                last_auth_error = err
                # allow the user to re-try
                continue
            else:
                break
        else:
            raise last_auth_error

        return True

@asyncio.coroutine
def negotiate_stream_security(tls_provider, sasl_providers,
                              features, xmlstream):
    """
    Negotiate stream security for the given *xmlstream*. For this to work,
    *features* must be the most recent
    :class:`.stream_elements.StreamFeatures` node.

    First, transport layer security is negotiated using *tls_provider*. If that
    fails non-fatally, negotiation continues as normal. Exceptions propagate
    upwards.

    After TLS has been tried, SASL is negotiated, by sequentially attempting
    SASL negotiation using the providers in the *sasl_providers* list. If a
    provider fails to negotiate SASL with an
    :class:`~.errors.AuthenticationFailure` or has no mechanisms in common with
    the peer server, the next provider can continue. Otherwise, the exception
    propagates upwards.

    If no provider succeeds and there was an authentication failure, that error
    is re-raised. Otherwise, a dedicated :class:`~.errors.SASLFailure` exception
    is raised, which states that no common mechanisms were found.

    On success, a pair of ``(tls_transport, features)`` is returned. If TLS has
    been negotiated, *tls_transport* is the SSL :class:`asyncio.Transport`
    created by asyncio (as returned by the *tls_provider*). If no TLS has been
    negotiated, *tls_transport* is :data:`None`. *features* is the latest
    :class:`~.stream_elements.StreamFeatures` element received during
    negotiation.

    On failure, an appropriate exception is raised. Authentication failures
    can be caught as :class:`.errors.AuthenticationFailure`. Errors related
    to SASL or TLS negotiation itself can be caught using
    :class:`~.errors.SASLFailure` and :class:`~.errors.TLSFailure`
    respectively.
    """

    tls_transport = None
    result = yield from self._tls_provider.execute(
        features, xmlstream)

    if result:
        tls_transport, features = result

    last_auth_error = None
    for sasl_provider in self._sasl_providers:
        try:
            result = yield from sasl_provider.execute(
                features, tls_transport, xmlstream)
        except errors.AuthenticationFailure as err:
            last_auth_error = err
            continue

        if result is not False:
            features = result
            break
    else:
        if last_auth_error:
            raise last_auth_error
        else:
            raise errors.SASLFailure("No common mechanisms")

    return tls_transport, features
