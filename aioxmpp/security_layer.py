"""
:mod:`~aioxmpp.security_layer` --- Implementations to negotiate stream security
####################################################################################

This module provides different implementations of the security layer
(TLS+SASL).

These are coupled, as different SASL features might need different TLS features
(such as channel binding or client cert authentication).

.. autofunction:: tls_with_password_based_authentication(password_provider, [ssl_context_factory], [max_auth_attempts=3])

.. autofunction:: security_layer

.. autofunction:: negotiate_stream_security

Certificate verifiers
=====================

To verify the peer certificate provided by the server, different
:class:`CertificateVerifier`s are available:

.. autoclass:: PKIXCertificateVerifier

To implement your own verifiers, see the documentation at the base class for
certificate verifiers:

.. autoclass:: CertificateVerifier

Partial security providers
==========================

Partial security providers serve as arguments to pass to
:func:`negotiate_stream_security`.

.. _tls providers:

Transport layer security provider
---------------------------------

As an `tls_provider` argument to :class:`SecurityLayer`, instances of the
following classes can be used:

.. autoclass:: STARTTLSProvider

.. _sasl providers:

SASL providers
--------------

As elements of the `sasl_providers` argument to :class:`SecurityLayer`,
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
import functools
import logging
import ssl

import pyasn1
import pyasn1.codec.der.decoder
import pyasn1_modules.rfc2459

import OpenSSL.SSL

from . import errors, sasl, stream_xsos, xso, protocol
from .utils import namespaces

logger = logging.getLogger(__name__)


def extract_python_dict_from_x509(x509):
    """
    Extract a python dictionary similar to the return value of
    :meth:`ssl.SSLSocket.getpeercert` from the given
    :class:`OpenSSL.crypto.X509` `x509` object.

    Note that by far not all attributes are included; only those required to
    use :func:`ssl.match_hostname` are extracted and put in the result.

    In the future, more attributes may be added.
    """
    result = {
        "subject": (
            (("commonName", x509.get_subject().commonName),),
        )
    }

    for ext_idx in range(x509.get_extension_count()):
        ext = x509.get_extension(ext_idx)
        sn = ext.get_short_name()
        if sn != b"subjectAltName":
            continue

        data = pyasn1.codec.der.decoder.decode(
            ext.get_data(),
            asn1Spec=pyasn1_modules.rfc2459.SubjectAltName())[0]
        for name in data:
            dNSName = name.getComponentByPosition(2)
            if dNSName is None:
                continue

            result.setdefault("subjectAltName", []).append(
                ("DNS", str(dNSName))
            )

    return result


def check_x509_hostname(x509, hostname):
    """
    Check whether the given :class:`OpenSSL.crypto.X509` certificate `x509`
    matches the given `hostname`.

    Return :data:`True` if the name matches and :data:`False` otherwise. This
    uses :func:`ssl.match_hostname` and :func:`extract_python_dict_from_x509`.
    """

    cert_structure = extract_python_dict_from_x509(x509)
    try:
        ssl.match_hostname(cert_structure, hostname)
    except ssl.CertificateError:
        return False
    return True


class CertificateVerifier(metaclass=abc.ABCMeta):
    """
    A certificate verifier hooks into the two mechanisms provided by
    :class:`.ssl_transport.STARTTLSTransport` for certificate verification.

    On the one hand, the verify callback provided by
    :class:`OpenSSL.SSL.Context` is used and forwarded to
    :meth:`verify_callback`. On the other hand, the post handshake coroutine is
    set to :meth:`post_handshake`. See the documentation of
    :class:`.ssl_transport.STARTTLSTransport` for the semantics of that
    coroutine.

    In addition to these two hooks into the TLS handshake, a third coroutine
    which is called before STARTTLS is intiiated is provided.

    This baseclass provides a bit of boilerplate.
    """

    @asyncio.coroutine
    def pre_handshake(self, transport):
        pass

    def setup_context(self, ctx, transport):
        self.transport = transport
        ctx.set_verify(OpenSSL.SSL.VERIFY_PEER, self.verify_callback)

    @abc.abstractmethod
    def verify_callback(self, conn, x509, errno, errdepth, returncode):
        return returncode

    @abc.abstractmethod
    @asyncio.coroutine
    def post_handshake(self, transport):
        pass


class _NullVerifier(CertificateVerifier):
    def setup_context(self, ctx):
        ctx.set_verify(OpenSSL.SSL.VERIFY_NONE, self._callback_wrapper)

    def verify_callback(self, *args):
        return True

    @asyncio.coroutine
    def post_handshake(self, transport):
        pass


class PKIXCertificateVerifier(CertificateVerifier):
    """
    This verifier enables the default PKIX based verification of certificates
    as implemented by OpenSSL.

    .. warning::

       No additional checks are performed, in particular, the host name is not
       matched against the host name. This is TBD.

    """

    def verify_callback(self, ctx, x509, errno, errdepth, returncode):
        logger.info("verifying certificate (preverify=%s)", returncode)

        if not returncode:
            logger.warning("certificate verification failed (by OpenSSL)")
            return returncode

        if errdepth == 0:
            hostname = self.transport.get_extra_info("server_hostname")
            if not check_x509_hostname(
                    x509,
                    hostname):
                logger.warning("certificate hostname mismatch "
                               "(doesn’t match for %r)",
                               hostname)
                return False

        return returncode

    def setup_context(self, ctx, transport):
        super().setup_context(ctx, transport)
        ctx.set_default_verify_paths()

    @asyncio.coroutine
    def post_handshake(self, transport):
        pass


class HookablePKIXCertificateVerifier(CertificateVerifier):
    """
    This PKIX-based verifier has several hooks which allow overriding of the
    checking process, for example to implement key or certificate pinning.

    It provides three callbacks:

    * `quick_check` is a synchronous callback (and must be a plain function)
      which is called from :meth:`verify_callback`. It is only called if the
      certificate fails full PKIX verification, and only for certain cases. For
      example, expired certificates do not get a second chance and are rejected
      immediately.

      It is called with the leaf certificate as its only argument. It must
      return :data:`True` if the certificate is known good and should pass the
      verification. If the certificate is known bad and should fail the
      verification immediately, it must return :data:`False`.

      If the certificate is unknown and the check should be deferred to the
      `post_handshake_deferred_failure` callback, :data:`None` must be
      returned.

    * `post_handshake_deferred_failure` must be a coroutine. It is called after
      the handshake is done but before the STARTTLS negotiation has finished
      and allows the application to take more time to decide on a certificate
      and possibly request user input.

      The coroutine receives the verifier instance as its argument and can make
      use of all the verification attributes to present the user with a
      sensible choice.

    * `post_handshake_success` is only called if the certificate has passed the
      verification (either because it flawlessly passed by OpenSSL or the
      `quick_check` callback returned :data:`True`).

    The following attributes are available when the post handshake callbacks
    are called:

    .. attribute:: recorded_errors

       This is a :class:`set` with tuples consisting of a
       :class:`OpenSSL.crypto.X509` instance, an OpenSSL error number and the
       depth of the certificate in the verification chain (0 is the leaf
       certificate).

       It is a collection of all errors which were passed into
       :meth:`verify_callback` by OpenSSL.

    .. attribute:: hostname_matches

       This is :data:`True` if the host name in the leaf certificate matches
       the domain part of the JID for which we are connecting (i.e. the usual
       server name check).

    .. attribute:: leaf_x509

       The :class:`OpenSSL.crypto.X509` object which represents the leaf
       certificate.

    """

    _DEFERRABLE_ERRORS = {
        (19, None),
        (18, 0),
        (27, 0),
    }

    def __init__(self,
                 quick_check,
                 post_handshake_deferred_failure,
                 post_handshake_success):
        self._quick_check = quick_check
        self._post_handshake_success = post_handshake_success
        self._post_handshake_deferred_failure = post_handshake_deferred_failure

        self.recorded_errors = set()
        self.deferred = True
        self.hostname_matches = False
        self.leaf_x509 = None

    def verify_callback(self, ctx, x509, errno, depth, preverify):
        if errno != 0:
            self.recorded_errors.add((x509, errno, depth))
            return True

        if depth == 0:
            hostname = self.transport.get_extra_info("server_hostname")
            self.hostname_matches = check_x509_hostname(x509, hostname)
            self.leaf_x509 = x509
            return self.verify_recorded(x509, self.recorded_errors)

        return True

    def verify_recorded(self, leaf_x509, records):
        self.deferred = False

        if not records:
            return True

        hostname = self.transport.get_extra_info("server_hostname")
        self.hostname_matches = check_x509_hostname(leaf_x509, hostname)

        for x509, errno, depth in records:
            if     ((errno, depth) not in self._DEFERRABLE_ERRORS and
                    (errno, None) not in self._DEFERRABLE_ERRORS):
                return False

        result = self._quick_check(leaf_x509)
        if result is None:
            self.deferred = True

        return result is not False

    @asyncio.coroutine
    def post_handshake(self, transport):
        if self.deferred:
            result = yield from self._post_handshake_deferred_failure(self)
            if not result:
                raise errors.TLSFailure("certificate verification failed")
        else:
            yield from self._post_handshake_success()


class ErrorRecordingVerifier(CertificateVerifier):
    def __init__(self):
        super().__init__()
        self._errors = []

    def _record_verify_info(self, x509, errno, depth):
        self._errors.append((x509, errno, depth))

    def verify_callback(self, x509, errno, depth, returncode):
        self._record_verify_info(x509, errno, depth)
        return True

    @asyncio.coroutine
    def post_handshake(self, transport):
        if self._errors:
            raise errors.TLSFailure(
                "Peer certificate verification failure: {}".format(
                    ", ".join(map(str, self._errors))))


@stream_xsos.StreamFeatures.as_feature_class
class STARTTLSFeature(xso.XSO):
    class STARTTLSRequired(xso.XSO):
        TAG = (namespaces.starttls, "required")

    TAG = (namespaces.starttls, "starttls")

    required = xso.Child([STARTTLSRequired])


class STARTTLS(xso.XSO):
    TAG = (namespaces.starttls, "starttls")


class STARTTLSFailure(xso.XSO):
    TAG = (namespaces.starttls, "failure")


class STARTTLSProceed(xso.XSO):
    TAG = (namespaces.starttls, "proceed")


class STARTTLSProvider:
    """
    A TLS provider to negotiate STARTTLS on an existing XML stream. This
    requires that the stream uses
    :class:`.ssl_wrapper.STARTTLSableTransportProtocol` as a transport.

    `ssl_context_factory` must be a callable returning a valid
    :class:`ssl.SSLContext` object. It is called without
    arguments.

    `require_starttls` can be set to :data:`False` to allow stream negotiation
    to continue even if STARTTLS fails before it has been started (the stream
    is fatally broken if the STARTTLS command has been sent but SSL negotiation
    fails afterwards).

    `certificate_verifier_factory` must be a callable providing a
    :class:`CertificateVerifer` instance which will hooked up to the transport
    and the SSL context to perform certificate validation.

    .. note::

       Partial DANE support is provided by :mod:`dane`.

    """

    def __init__(self,
                 ssl_context_factory,
                 certificate_verifier_factory=PKIXCertificateVerifier,
                 *,
                 require_starttls=True, **kwargs):
        super().__init__(**kwargs)
        self._certificate_verifier_factory = certificate_verifier_factory
        self._ssl_context_factory = ssl_context_factory
        self._required = require_starttls

    def _fail_if_required(self, msg, peer_requires=False):
        if self._required or peer_requires:
            raise errors.TLSUnavailable(msg)
        return None

    @asyncio.coroutine
    def execute(self, client_jid, features, xmlstream):
        """
        Perform STARTTLS negotiation. If successful, a ``(tls_transport,
        new_features)`` pair is returned. Otherwise, if STARTTLS failed
        non-fatally and is not required (see constructor arguments),
        :data:`False` is returned.

        The `tls_transport` member of the return value is the
        :class:`asyncio.Transport` created by asyncio for SSL. The second
        element are the new stream features received after STARTTLS
        negotiation.
        """

        try:
            feature = features[STARTTLSFeature]
        except KeyError:
            return self._fail_if_required("STARTTLS not supported by peer")

        if not xmlstream.can_starttls():
            return self._fail_if_required(
                "STARTTLS not supported by us",
                peer_requires=bool(feature.required)
            )

        response = yield from protocol.send_and_wait_for(
            xmlstream,
            [
                STARTTLS()
            ],
            [
                STARTTLSFailure,
                STARTTLSProceed,
            ]
        )

        if response.TAG[1] == "proceed":
            logger.info("engaging STARTTLS")
            try:
                verifier = self._certificate_verifier_factory()
                yield from verifier.pre_handshake(xmlstream.transport)
                ctx = self._ssl_context_factory()
                verifier.setup_context(ctx, xmlstream.transport)
                logger.debug("using certificate verifier: %s", verifier)
                yield from xmlstream.starttls(
                    ssl_context=ctx,
                    post_handshake_callback=verifier.post_handshake)
            except errors.TLSFailure:
                # no need to re-wrap that
                logger.exception("STARTTLS failed:")
                raise
            except Exception as err:
                logger.exception("STARTTLS failed:")
                raise errors.TLSFailure(
                    "TLS connection failed: {}".format(err)
                )
            return xmlstream.transport

        return self._fail_if_required("STARTTLS failed on remote side")


class SASLMechanism(xso.XSO):
    TAG = (namespaces.sasl, "mechanism")

    name = xso.Text()

    def __init__(self, name=None):
        super().__init__()
        self.name = name

@stream_xsos.StreamFeatures.as_feature_class
class SASLMechanisms(xso.XSO):
    TAG = (namespaces.sasl, "mechanisms")

    mechanisms = xso.ChildList([SASLMechanism])

    def get_mechanism_list(self):
        return [
            mechanism.name
            for mechanism in self.mechanisms
        ]


class SASLProvider:
    def _find_supported(self, features, mechanism_classes):
        """
        Return a supported SASL mechanism class, by looking the given
        stream features `features`.

        If SASL is not supported at all, :class:`~.errors.SASLFailure` is
        raised. If no matching mechanism is found, ``(None, None)`` is
        returned. Otherwise, a pair consisting of the mechanism class and the
        value returned by the respective
        :meth:`~.sasl.SASLMechanism.any_supported` method is returned.
        """

        try:
            mechanisms = features[SASLMechanisms]
        except KeyError:
            logger.error("No sasl mechanisms: %r", list(features))
            raise errors.SASLUnavailable(
                "Remote side does not support SASL") from None

        remote_mechanism_list = mechanisms.get_mechanism_list()

        for our_mechanism in mechanism_classes:
            token = our_mechanism.any_supported(remote_mechanism_list)
            if token is not None:
                return our_mechanism, token

        return None, None

    AUTHENTICATION_FAILURES = {
        "credentials-expired",
        "account-disabled",
        "invalid-authzid",
        "not-authorized",
        "temporary-auth-failure",
    }

    MECHANISM_REJECTED_FAILURES = {
        "invalid-mechanism",
        "mechanism-too-weak",
        "encryption-required",
    }

    @asyncio.coroutine
    def _execute(self, xmlstream, mechanism, token):
        """
        Execute SASL negotiation using the given `mechanism` instance and
        `token` on the `xmlstream`.
        """
        sm = sasl.SASLStateMachine(xmlstream)
        try:
            yield from mechanism.authenticate(sm, token)
            return True
        except errors.SASLFailure as err:
            if err.xmpp_error in self.AUTHENTICATION_FAILURES:
                raise errors.AuthenticationFailure(
                    xmpp_error=err.xmpp_error,
                    text=err.text)
            elif err.xmpp_error in self.MECHANISM_REJECTED_FAILURES:
                return False
            raise

    @abc.abstractmethod
    @asyncio.coroutine
    def execute(self,
                client_jid,
                features,
                xmlstream,
                tls_transport):
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

    `jid` must be a :class:`~.structs.JID` object for the
    client. `password_provider` must be a coroutine which is called with the
    jid as first and the number of attempt as second argument. It must return
    the password to use, or :data:`None` to abort. In that case, an
    :class:`errors.AuthenticationFailure` error will be raised.

    At most `max_auth_attempts` will be carried out. If all fail, the
    authentication error of the last attempt is raised.

    The SASL mechanisms used depend on whether TLS has been negotiated
    successfully before. In any case, :class:`~.sasl.SCRAM` is used. If TLS has
    been negotiated, :class:`~.sasl.PLAIN` is also supported.
    """

    def __init__(self, password_provider, *,
                 max_auth_attempts=3, **kwargs):
        super().__init__(**kwargs)
        self._password_provider = password_provider
        self._max_auth_attempts = max_auth_attempts

    @asyncio.coroutine
    def execute(self,
                client_jid,
                features,
                xmlstream,
                tls_transport):
        client_jid = client_jid.bare()

        password_signalled_abort = False
        nattempt = 0
        cached_credentials = None

        @asyncio.coroutine
        def credential_provider():
            nonlocal password_signalled_abort, nattempt, cached_credentials
            if cached_credentials is not None:
                return client_jid.localpart, cached_credentials

            password = yield from self._password_provider(
                client_jid, nattempt)
            if password is None:
                password_signalled_abort = True
                raise errors.AuthenticationFailure(
                    "Authentication aborted by user")
            cached_credentials = password
            return client_jid.localpart, password

        classes = [
            sasl.SCRAM
        ]
        if tls_transport is not None:
            classes.append(sasl.PLAIN)

        while classes:
            # go over all mechanisms available. some errors disable a mechanism
            # (like encryption-required or mechansim-too-weak)
            mechanism_class, token = self._find_supported(features, classes)
            if mechanism_class is None:
                return False

            mechanism = mechanism_class(credential_provider)
            last_auth_error = None
            for nattempt in range(self._max_auth_attempts):
                try:
                    mechanism_worked = yield from self._execute(
                        xmlstream, mechanism, token)
                except errors.AuthenticationFailure as err:
                    if password_signalled_abort:
                        # immediately re-raise
                        raise
                    last_auth_error = err
                    # allow the user to re-try
                    cached_credentials = None
                    continue
                else:
                    break
            else:
                raise last_auth_error

            if mechanism_worked:
                return True
            classes.remove(mechanism_class)

        return False


def default_verify_callback(conn, x509, errno, errdepth, returncode):
    return errno == 0


def default_ssl_context():
    ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
    ctx.set_options(OpenSSL.SSL.OP_NO_SSLv2 | OpenSSL.SSL.OP_NO_SSLv3)
    ctx.set_verify(OpenSSL.SSL.VERIFY_PEER, default_verify_callback)
    return ctx


@asyncio.coroutine
def negotiate_stream_security(tls_provider, sasl_providers,
                              negotiation_timeout, jid, features, xmlstream):
    """
    Negotiate stream security for the given `xmlstream`. For this to work,
    `features` must be the most recent
    :class:`.stream_elements.StreamFeatures` node.

    First, transport layer security is negotiated using `tls_provider`. If that
    fails non-fatally, negotiation continues as normal. Exceptions propagate
    upwards.

    After TLS has been tried, SASL is negotiated, by sequentially attempting
    SASL negotiation using the providers in the `sasl_providers` list. If a
    provider fails to negotiate SASL with an
    :class:`~.errors.AuthenticationFailure` or has no mechanisms in common with
    the peer server, the next provider can continue. Otherwise, the exception
    propagates upwards.

    If no provider succeeds and there was an authentication failure, that error
    is re-raised. Otherwise, a dedicated :class:`~.errors.SASLFailure`
    exception is raised, which states that no common mechanisms were found.

    On success, a pair of ``(tls_transport, features)`` is returned. If TLS has
    been negotiated, `tls_transport` is the SSL :class:`asyncio.Transport`
    created by asyncio (as returned by the `tls_provider`). If no TLS has been
    negotiated, `tls_transport` is :data:`None`. `features` is the latest
    :class:`~.stream_elements.StreamFeatures` element received during
    negotiation.

    On failure, an appropriate exception is raised. Authentication failures
    can be caught as :class:`.errors.AuthenticationFailure`. Errors related
    to SASL or TLS negotiation itself can be caught using
    :class:`~.errors.SASLFailure` and :class:`~.errors.TLSFailure`
    respectively.
    """

    tls_transport = yield from tls_provider.execute(jid, features, xmlstream)

    if tls_transport is not None:
        features = yield from protocol.reset_stream_and_get_features(
            xmlstream,
            timeout=negotiation_timeout)

    last_auth_error = None
    for sasl_provider in sasl_providers:
        try:
            result = yield from sasl_provider.execute(
                jid, features, xmlstream, tls_transport)
        except errors.AuthenticationFailure as err:
            last_auth_error = err
            continue

        if result:
            features = yield from protocol.reset_stream_and_get_features(
                xmlstream,
                timeout=negotiation_timeout)
            break
    else:
        if last_auth_error:
            raise last_auth_error
        else:
            raise errors.SASLUnavailable("No common mechanisms")

    return tls_transport, features


def security_layer(tls_provider, sasl_providers):
    """
    .. seealso::

       Use this function only if you need more customization than provided by
       :func:`tls_with_password_based_authentication`.

    Return a partially applied :func:`negotiate_stream_security` function,
    where the `tls_provider` and `sasl_providers` arguments are already bound.

    The return value can be passed to the constructor of
    :class:`~.node.Client`.

    Some very basic checking on the input is also performed.
    """

    tls_provider.execute  # check that tls_provider has execute method
    sasl_providers = list(sasl_providers)
    if not sasl_providers:
        raise ValueError("At least one SASL provider must be given.")
    for sasl_provider in sasl_providers:
        sasl_provider.execute  # check that sasl_provider has execute method

    return functools.partial(negotiate_stream_security,
                             tls_provider, sasl_providers)


def tls_with_password_based_authentication(
        password_provider,
        ssl_context_factory=default_ssl_context,
        max_auth_attempts=3,
        certificate_verifier_factory=None):
    """
    Produce a commonly used security layer, which uses TLS and password
    authentication. If `ssl_context_factory` is not provided, an SSL context
    with TLSv1+ is used.

    `password_provider` must be a coroutine which is called with the jid
    as first and the number of attempt as second argument. It must return the
    password to us, or :data:`None` to abort.

    Return a security layer which can be passed to :class:`~.node.Client`.
    """

    tls_kwargs = {}
    if certificate_verifier_factory is not None:
        tls_kwargs["certificate_verifier_factory"] = \
            certificate_verifier_factory

    return security_layer(
        tls_provider=STARTTLSProvider(ssl_context_factory,
                                      require_starttls=True,
                                      **tls_kwargs),
        sasl_providers=[PasswordSASLProvider(
            password_provider,
            max_auth_attempts=max_auth_attempts)]
    )
