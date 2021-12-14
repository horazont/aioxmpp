########################################################################
# File name: security_layer.py
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
:mod:`~aioxmpp.security_layer` --- Implementations to negotiate stream security
####################################################################################

This module provides different implementations of the security layer
(TLS+SASL).

These are coupled, as different SASL features might need different TLS features
(such as channel binding or client cert authentication). The preferred method
to construct a :class:`SecurityLayer` is using the :func:`make` function.
:class:`SecurityLayer` objects are needed to establish an XMPP connection,
for example using :class:`aioxmpp.Client`.

.. autofunction:: make

.. autoclass:: PinType

.. autofunction:: tls_with_password_based_authentication(password_provider, [ssl_context_factory], [max_auth_attempts=3])

.. autoclass:: SecurityLayer(ssl_context_factory, certificate_verifier_factory, tls_required, sasl_providers)

.. autofunction:: negotiate_sasl

Certificate verifiers
=====================

To verify the peer certificate provided by the server, different
:class:`CertificateVerifier`\ s are available:

.. autoclass:: PKIXCertificateVerifier

To implement your own verifiers, see the documentation at the base class for
certificate verifiers:

.. autoclass:: CertificateVerifier

Certificate and key pinning
---------------------------

Often in the XMPP world, we need certificate or public key pinning, as most
XMPP servers do not have certificates trusted by the usual certificate
stores. This module also provide certificate verifiers which can be used for
that purpose, as well as stores for saving the pinned information.

.. autoclass:: PinningPKIXCertificateVerifier

.. autoclass:: CertificatePinStore

.. autoclass:: PublicKeyPinStore

Base classes
^^^^^^^^^^^^

For future expansion or customization, the base classes of the above utilities
can be subclassed and extended:

.. autoclass:: HookablePKIXCertificateVerifier

.. autoclass:: AbstractPinStore

.. _sasl providers:

SASL providers
==============

As elements of the `sasl_providers` argument to :class:`SecurityLayer`,
instances of the following classes can be used:

.. autoclass:: PasswordSASLProvider

.. autoclass:: AnonymousSASLProvider

.. note::

   Patches welcome for additional :class:`SASLProvider` implementations.

Abstract base classes
=====================

For implementation of custom SASL providers, the following base class can be
used:

.. autoclass:: SASLProvider

Deprecated functionality
========================

In pre-0.6 code, you might find use of the following things:

.. autofunction:: security_layer

.. autoclass:: STARTTLSProvider

"""  # NOQA: E501
import abc
import asyncio
import base64
import collections
import enum
import logging
import ssl

import pyasn1
import pyasn1.codec.der.decoder
import pyasn1.codec.der.encoder
import pyasn1_modules.rfc2459

import OpenSSL.SSL

import aiosasl

from . import errors, sasl, nonza, xso, protocol
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

            if hasattr(dNSName, "isValue") and not dNSName.isValue:
                continue

            result.setdefault("subjectAltName", []).append(
                ("DNS", str(dNSName))
            )

    return result


def extract_blob(x509):
    """
    Extract an ASN.1 blob from the given :class:`OpenSSL.crypto.X509`
    certificate. Return the resulting :class:`bytes` object.
    """

    return OpenSSL.crypto.dump_certificate(
        OpenSSL.crypto.FILETYPE_ASN1,
        x509)


def blob_to_pyasn1(blob):
    """
    Convert an ASN.1 encoded certificate (such as obtained from
    :func:`extract_blob`) to a :mod:`pyasn1` structure and return the result.
    """

    return pyasn1.codec.der.decoder.decode(
        blob,
        asn1Spec=pyasn1_modules.rfc2459.Certificate()
    )[0]


def extract_pk_blob_from_pyasn1(pyasn1_struct):
    """
    Extract an ASN.1 encoded public key blob from the given :mod:`pyasn1`
    structure (which must represent a certificate).
    """

    pk = pyasn1_struct.getComponentByName(
        "tbsCertificate"
    ).getComponentByName(
        "subjectPublicKeyInfo"
    )

    return pyasn1.codec.der.encoder.encode(pk)


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
    :class:`aioopenssl.STARTTLSTransport` for certificate verification.

    On the one hand, the verify callback provided by
    :class:`OpenSSL.SSL.Context` is used and forwarded to
    :meth:`verify_callback`. On the other hand, the post handshake coroutine is
    set to :meth:`post_handshake`. See the documentation of
    :class:`aioopenssl.STARTTLSTransport` for the semantics of that
    coroutine.

    In addition to these two hooks into the TLS handshake, a third coroutine
    which is called before STARTTLS is intiiated is provided.

    This baseclass provides a bit of boilerplate.
    """

    async def pre_handshake(self, metadata, domain, host, port):
        pass

    def setup_context(self, ctx, transport):
        self.transport = transport
        ctx.set_verify(OpenSSL.SSL.VERIFY_PEER, self.verify_callback)

    @abc.abstractmethod
    def verify_callback(self, conn, x509, errno, errdepth, returncode):
        return returncode

    @abc.abstractmethod
    async def post_handshake(self, transport):
        pass


class _NullVerifier(CertificateVerifier):
    def setup_context(self, ctx, transport):
        self.transport = transport
        ctx.set_verify(OpenSSL.SSL.VERIFY_NONE, self.verify_callback)

    def verify_callback(self, *args):
        return True

    async def post_handshake(self, transport):
        pass


class PKIXCertificateVerifier(CertificateVerifier):
    """
    This verifier enables the default PKIX based verification of certificates
    as implemented by OpenSSL.

    The :meth:`verify_callback` checks that the certificate subject matches the
    domain name of the JID of the connection.
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

    async def post_handshake(self, transport):
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

      Passing :data:`None` to `quick_check` is the same as if a callable passed
      to `quick_check` would return :data:`None` always (i.e. the decision is
      deferred).

    * `post_handshake_deferred_failure` must be a coroutine. It is called after
      the handshake is done but before the STARTTLS negotiation has finished
      and allows the application to take more time to decide on a certificate
      and possibly request user input.

      The coroutine receives the verifier instance as its argument and can make
      use of all the verification attributes to present the user with a
      sensible choice.

      If `post_handshake_deferred_failure` is :data:`None`, the result is
      identical to returning :data:`False` from the callback.

    * `post_handshake_success` is only called if the certificate has passed the
      verification (either because it flawlessly passed by OpenSSL or the
      `quick_check` callback returned :data:`True`).

      You may pass :data:`None` to this argument to disable the callback
      without any further side effects.

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

    # these are the errors for which we allow pinning the certificate
    _DEFERRABLE_ERRORS = {
        (20, None),  # issuer certificate not available locally
        (19, None),  # self-signed cert in chain
        (18, 0),     # depth-zero self-signed cert
        (27, 0),     # cert untrusted
        (21, 0),     # leaf certificate not signed ...
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
        if errno != 0 and errno != 21:
            self.recorded_errors.add((x509, errno, depth))
            return True

        if depth == 0:
            if errno != 0:
                logger.debug(
                    "unsigned certificate; this is odd to say the least"
                )
                self.recorded_errors.add((x509, errno, depth))
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
                logger.warning("non-deferrable certificate error: "
                               "depth=%d, errno=%d",
                               depth, errno)
                return False

        if self._quick_check is not None:
            result = self._quick_check(leaf_x509)
            logger.debug("certificate quick-check returned %r", result)
        else:
            result = None
            logger.debug("no certificate quick-check")

        if result is None:
            self.deferred = True

        return result is not False

    async def post_handshake(self, transport):
        if self.deferred:
            if self._post_handshake_deferred_failure is not None:
                result = await self._post_handshake_deferred_failure(self)
            else:
                result = False

            if not result:
                raise errors.TLSFailure("certificate verification failed")
        else:
            if self._post_handshake_success is not None:
                await self._post_handshake_success()


class AbstractPinStore(metaclass=abc.ABCMeta):
    """
    This is the abstract base class for both :class:`PublicKeyPinStore` and
    :class:`CerificatePinStore`. The interface for both types of pinning is
    identical; the only difference is in which information is stored.

    .. automethod:: pin

    .. automethod:: query

    .. automethod:: get_pinned_for_host

    .. automethod:: export_to_json

    .. automethod:: import_from_json

    For subclasses:

    .. automethod:: _encode_key

    .. automethod:: _decode_key

    .. automethod:: _x509_key


    """

    def __init__(self):
        self._storage = {}

    @abc.abstractmethod
    def _x509_key(self, key):
        """
        Return a hashable value which identifies the given `x509` certificate
        for the purposes of the key store. See the implementations
        :meth:`PublicKeyPinStore._x509_key` and
        :meth:`CertificatePinStore._x509_key` for details on what is stored for
        the respective subclasses.

        This method is abstract and must be implemented in subclasses.
        """

    def _encode_key(self, key):
        """
        Encode the `key` (which has previously been obtained from
        :meth:`_x509_key`) into a string which is both JSON compatible and can
        be used as XML text (which means that it must not contain control
        characters, for example).

        The method is called by :meth:`export_to_json`. The default
        implementation returns `key`.
        """
        return key

    def _decode_key(self, obj):
        """
        Decode the `obj` into a key which is compatible to the values returned
        by :meth:`_x509_key`.

        The method is called by :meth:`import_from_json`. The default
        implementation returns `obj`.
        """
        return obj

    def pin(self, hostname, x509):
        """
        Pin an :class:`OpenSSL.crypto.X509` object `x509` for use with the
        given `hostname`. Which information exactly is used to identify the
        certificate depends :meth:`_x509_key`.
        """

        key = self._x509_key(x509)
        self._storage.setdefault(hostname, set()).add(key)

    def query(self, hostname, x509):
        """
        Return true if the given :class:`OpenSSL.crypto.X509` object `x509` has
        previously been pinned for use with the given `hostname` and
        :data:`None` otherwise.

        Returning :data:`None` allows this method to be used with
        :class:`PinningPKIXCertificateVerifier`.
        """

        key = self._x509_key(x509)
        try:
            pins = self._storage[hostname]
        except KeyError:
            return None

        if key in pins:
            return True

        return None

    def get_pinned_for_host(self, hostname):
        """
        Return the set of hashable values which are used to identify the X.509
        certificates which are accepted for the given `hostname`.

        If no values have previously been pinned, this returns the empty set.
        """
        try:
            return frozenset(self._storage[hostname])
        except KeyError:
            return frozenset()

    def export_to_json(self):
        """
        Return a JSON dictionary which contains all the pins stored in this
        store.
        """

        return {
            hostname: sorted(self._encode_key(key) for key in pins)
            for hostname, pins in self._storage.items()
        }

    def import_from_json(self, data, *, override=False):
        """
        Import a JSON dictionary which must have the same format as exported by
        :meth:`export`.

        If *override* is true, the existing data in the pin store will be
        overridden with the data from `data`. Otherwise, the `data` will be
        merged into the store.
        """

        if override:
            self._storage = {
                hostname: set(self._decode_key(key) for key in pins)
                for hostname, pins in data.items()
            }
            return

        for hostname, pins in data.items():
            existing_pins = self._storage.setdefault(hostname, set())
            existing_pins.update(self._decode_key(key) for key in pins)


class PublicKeyPinStore(AbstractPinStore):
    """
    This pin store stores the public keys of the X.509 objects which are passed
    to its :meth:`pin` method.
    """

    def _x509_key(self, x509):
        blob = extract_blob(x509)
        pyasn1_struct = blob_to_pyasn1(blob)
        return extract_pk_blob_from_pyasn1(pyasn1_struct)

    def _encode_key(self, key):
        return base64.b64encode(key).decode("ascii")

    def _decode_key(self, obj):
        return base64.b64decode(obj.encode("ascii"))


class CertificatePinStore(AbstractPinStore):
    """
    This pin store stores the whole certificates which are passed to its
    :meth:`pin` method.
    """

    def _x509_key(self, x509):
        return extract_blob(x509)

    def _encode_key(self, key):
        return base64.b64encode(key).decode("ascii")

    def _decode_key(self, obj):
        return base64.b64decode(obj.encode("ascii"))


class PinningPKIXCertificateVerifier(HookablePKIXCertificateVerifier):
    """
    The :class:`PinningPKIXCertificateVerifier` is a subclass of the
    :class:`HookablePKIXCertificateVerifier` which uses the hooks to implement
    certificate or public key pinning.

    It does not store the pins itself. Instead, the user must pass a callable
    to the `query_pin` argument. That callable will be called with two
    arguments: the `servername` and the `x509`. The `x509` is a
    :class:`OpenSSL.crypto.X509` instance, which is the leaf certificate which
    attempts to identify the host. The `servername` is the name of the server
    we try to connect to (the identifying name, like the domain part of the
    JID). The callable must return :data:`True` (to accept the certificate),
    :data:`False` (to reject the certificate) or :data:`None` (to defer the
    decision to the `post_handshake_deferred_failure` callback). `query_pin`
    must not block; if it needs to do blocking operations, it should defer.

    The other two arguments are coroutines with semantics identical to those of
    the same-named arguments in :class:`HookablePKIXCertificateVerifier`.

    .. seealso::

       :meth:`AbstractPinStore.query` is a method which can be passed as
       `query_pin` callback.

    """

    def __init__(self,
                 query_pin,
                 post_handshake_deferred_failure,
                 post_handshake_success=None):
        super().__init__(
            self._quick_check_query_pin,
            post_handshake_deferred_failure,
            post_handshake_success
        )

        self._query_pin = query_pin

    def _quick_check_query_pin(self, leaf_x509):
        hostname = self.transport.get_extra_info("server_hostname")
        is_pinned = self._query_pin(hostname, leaf_x509)
        if not is_pinned:
            logger.debug(
                "certificate for %r does not appear in pin store",
                hostname,
            )
        return is_pinned


class ErrorRecordingVerifier(CertificateVerifier):
    def __init__(self):
        super().__init__()
        self._errors = []

    def _record_verify_info(self, x509, errno, depth):
        self._errors.append((x509, errno, depth))

    def verify_callback(self, x509, errno, depth, returncode):
        self._record_verify_info(x509, errno, depth)
        return True

    async def post_handshake(self, transport):
        if self._errors:
            raise errors.TLSFailure(
                "Peer certificate verification failure: {}".format(
                    ", ".join(map(str, self._errors))))


class SASLMechanism(xso.XSO):
    TAG = (namespaces.sasl, "mechanism")

    name = xso.Text()

    def __init__(self, name=None):
        super().__init__()
        self.name = name


@nonza.StreamFeatures.as_feature_class
class SASLMechanisms(xso.XSO):
    TAG = (namespaces.sasl, "mechanisms")

    mechanisms = xso.ChildList([SASLMechanism])

    def get_mechanism_list(self):
        return [
            mechanism.name
            for mechanism in self.mechanisms
        ]


class SASLProvider:
    """
    Base class to implement a SASL provider.

    SASL providers are used in :class:`SecurityLayer` to authenticate the local
    user with a service. The credentials required depend on the specific SASL
    provider, and it is recommended to acquire means to get these credentials
    via constructor parameters (see for example :class:`PasswordSASLProvider`).

    The following methods must be implemented by subclasses:

    .. automethod:: execute

    The following methods are intended to be re-used by subclasses:

    .. automethod:: _execute

    .. automethod:: _find_supported
    """

    def _find_supported(self, features, mechanism_classes):
        """
        Find the first mechanism class which supports a mechanism announced in
        the given stream features.

        :param features: Current XMPP stream features
        :type features: :class:`~.nonza.StreamFeatures`
        :param mechanism_classes: SASL mechanism classes to use
        :type mechanism_classes: iterable of :class:`SASLMechanism`
                                 sub\\ *classes*
        :raises aioxmpp.errors.SASLUnavailable: if the peer does not announce
                                                SASL support
        :return: the :class:`SASLMechanism` subclass to use and a token
        :rtype: pair

        Return a supported SASL mechanism class, by looking the given
        stream features `features`.

        If no matching mechanism is found, ``(None, None)`` is
        returned. Otherwise, a pair consisting of the mechanism class and the
        value returned by the respective
        :meth:`~.sasl.SASLMechanism.any_supported` method is returned. The
        latter is an opaque token which must be passed to the `token` argument
        of :meth:`_execute` or :meth:`aiosasl.SASLMechanism.authenticate`.
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

    async def _execute(self, intf, mechanism, token):
        """
        Execute a SASL authentication process.

        :param intf: SASL interface to use
        :type intf: :class:`~.sasl.SASLXMPPInterface`
        :param mechanism: SASL mechanism to use
        :type mechanism: :class:`aiosasl.SASLMechanism`
        :param token: The opaque token argument for the mechanism
        :type token: not :data:`None`
        :raises aiosasl.AuthenticationFailure: if authentication failed due to
                                               bad credentials
        :raises aiosasl.SASLFailure: on other SASL error conditions (such as
                                     protocol violations)
        :return: true if authentication succeeded, false if the mechanism has
                 to be disabled
        :rtype: :class:`bool`

        This executes the SASL authentication process. The more specific
        exceptions are generated by inspecting the
        :attr:`aiosasl.SASLFailure.opaque_error` on exceptinos raised from the
        :class:`~.sasl.SASLXMPPInterface`. Other :class:`aiosasl.SASLFailure`
        exceptions are re-raised without modification.
        """
        sm = aiosasl.SASLStateMachine(intf)
        try:
            await mechanism.authenticate(sm, token)
            return True
        except aiosasl.SASLFailure as err:
            if err.opaque_error in self.AUTHENTICATION_FAILURES:
                raise aiosasl.AuthenticationFailure(
                    opaque_error=err.opaque_error,
                    text=err.text)
            elif err.opaque_error in self.MECHANISM_REJECTED_FAILURES:
                return False
            raise

    @abc.abstractmethod
    async def execute(self, client_jid, features, xmlstream, tls_transport):
        """
        Perform SASL negotiation.

        :param client_jid: The JID the client attempts to authenticate for
        :type client_jid: :class:`aioxmpp.JID`
        :param features: Current stream features nonza
        :type features: :class:`~.nonza.StreamFeatures`
        :param xmlstream: The XML stream to authenticate over
        :type xmlstream: :class:`~.protocol.XMLStream`
        :param tls_transport: The TLS transport or :data:`None` if no TLS has
                              been negotiated
        :type tls_transport: :class:`asyncio.Transport` or :data:`None`
        :raise aiosasl.AuthenticationFailure: if authentication failed due to
                                              bad credentials
        :raise aiosasl.SASLFailure: on other SASL-related errors
        :return: true if the negotiation was successful, false if no common
                 mechanisms could be found or all mechanisms failed for reasons
                 unrelated to the credentials themselves.
        :rtype: :class:`bool`

        The implementation depends on the specific :class:`SASLProvider`
        subclass in use.

        This coroutine returns :data:`True` if the negotiation was
        successful. If no common mechanisms could be found, :data:`False` is
        returned. This is useful to chain several SASL providers (e.g. a
        provider supporting ``EXTERNAL`` in front of password-based providers).

        Any other error case, such as no SASL support on the remote side or
        authentication failure results in an :class:`aiosasl.SASLFailure`
        exception to be raised.
        """


class PasswordSASLProvider(SASLProvider):
    """
    Perform password-based SASL authentication.

    :param password_provider: A coroutine function returning the password to
                              authenticate with.
    :type password_provider: coroutine function
    :param max_auth_attempts: Maximum number of authentication attempts with a
                              single mechanism.
    :type max_auth_attempts: positive :class:`int`

    `password_provider` must be a coroutine taking two arguments, a JID and an
    integer number. The first argument is the JID which is trying to
    authenticate and the second argument is the number of the authentication
    attempt, starting at 0. On each attempt, the number is increased, up to
    `max_auth_attempts`\\ -1. If the coroutine returns :data:`None`, the
    authentication process is aborted. If the number of attempts are exceeded,
    the authentication process is also aborted. In both cases, an
    :class:`aiosasl.AuthenticationFailure` error will be raised.

    The SASL mechanisms used depend on whether TLS has been negotiated
    successfully before. In any case, :class:`aiosasl.SCRAM` is used. If TLS
    has been negotiated, :class:`aiosasl.PLAIN` is also supported.

    .. seealso::

       :class:`SASLProvider`
          for the public interface of this class.
    """

    def __init__(self, password_provider, *,
                 max_auth_attempts=3, **kwargs):
        super().__init__(**kwargs)
        self._password_provider = password_provider
        self._max_auth_attempts = max_auth_attempts

    async def execute(self, client_jid, features, xmlstream, tls_transport):
        client_jid = client_jid.bare()

        password_signalled_abort = False
        nattempt = 0
        cached_credentials = None

        async def credential_provider():
            nonlocal password_signalled_abort, nattempt, cached_credentials
            if cached_credentials is not None:
                return client_jid.localpart, cached_credentials

            password = await self._password_provider(client_jid, nattempt)
            if password is None:
                password_signalled_abort = True
                raise aiosasl.AuthenticationFailure(
                    "user intervention",
                    text="authentication aborted by user")
            cached_credentials = password
            return client_jid.localpart, password

        classes = [
            aiosasl.SCRAM
        ]
        if tls_transport is not None:
            classes.append(aiosasl.PLAIN)

        intf = sasl.SASLXMPPInterface(xmlstream)
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
                    mechanism_worked = await self._execute(
                        intf, mechanism, token)
                except (ValueError, aiosasl.AuthenticationFailure) as err:
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


class AnonymousSASLProvider(SASLProvider):
    """
    Perform the ``ANONYMOUS`` SASL mechanism (:rfc:`4505`).

    :param token: The trace token for the ``ANONYMOUS`` mechanism
    :type token: :class:`str`

    `token` SHOULD be the empty string in the XMPP context (see :xep:`175`).

    .. seealso::

       :class:`SASLProvider`
          for the public interface of this class.

    .. warning::

       Take the security and privacy considerations from :rfc:`4505` (which
       specifies the ANONYMOUS SASL mechanism) and :xep:`175` (which discusses
       the ANONYMOUS SASL mechanism in the XMPP context) into account before
       using this provider.

    .. note::

       This class requires :class:`aiosasl.ANONYMOUS`, which is available with
       :mod:`aiosasl` 0.3 or newer. If :class:`aiosasl.ANONYMOUS` is not
       provided, this class is replaced with :data:`None`.

    .. versionadded:: 0.8
    """

    def __init__(self, token):
        super().__init__()
        self._token = token

    async def execute(self, client_jid, features, xmlstream, tls_transport):
        mechanism_class, token = self._find_supported(
            features,
            [aiosasl.ANONYMOUS]
        )

        if mechanism_class is None:
            return False

        intf = sasl.SASLXMPPInterface(xmlstream)
        mechanism = aiosasl.ANONYMOUS(self._token)

        return await self._execute(
            intf,
            mechanism,
            token,
        )


if not hasattr(aiosasl, "ANONYMOUS"):
    AnonymousSASLProvider = None  # NOQA


class SecurityLayer(collections.namedtuple(
        "SecurityLayer",
        [
            "ssl_context_factory",
            "certificate_verifier_factory",
            "tls_required",
            "sasl_providers",
        ])):
    """
    A security layer defines the security properties used for an XML stream.
    This includes TLS settings and SASL providers. The arguments are used to
    initialise the attributes of the same name.

    :class:`SecurityLayer` instances are required to construct a
    :class:`aioxmpp.Client`.

    .. versionadded:: 0.6

    .. seealso::

       :func:`make`
          A powerful function which can be used to create a configured
          :class:`SecurityLayer` instance.

    .. attribute:: ssl_context_factory

       This is a callable returning a :class:`OpenSSL.SSL.Context` instance
       which is to be used for any SSL operations for the connection.

       The :class:`OpenSSL.SSL.Context` instances should not be reused between
       connection attempts, as the certificate verifiers may set options which
       cannot be disabled anymore.

    .. attribute:: certificate_verifier_factory

       This is a callable which returns a fresh
       :class:`CertificateVerifier` on each call (it must be a fresh instance
       since :class:`CertificateVerifier` objects are allowed to keep state and
       :class:`SecurityLayer` objects are reusable between connection
       attempts).

    .. attribute:: tls_required

       A boolean which indicates whether TLS is required. If it is set to true,
       connectors (see :mod:`aioxmpp.connector`) will abort the connection if
       TLS (or something equivalent) is not available on the transport.

       .. note::

           Disabling this makes your application vulnerable to STARTTLS
           stripping attacks.

    .. attribute:: sasl_providers

       A sequence of :class:`SASLProvider` instances. As SASL providers are
       stateless, it is not necessary to create new providers for each
       connection.
    """


def default_verify_callback(conn, x509, errno, errdepth, returncode):
    return errno == 0


def default_ssl_context():
    """
    Return a sensibly configured :class:`OpenSSL.SSL.Context` context.

    The context has SSLv2 and SSLv3 disabled, and supports TLS 1.0+ (depending
    on the version of the SSL library).

    Tries to negotiate an XMPP c2s connection via ALPN (:rfc:`7301`).
    """

    ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
    ctx.set_options(OpenSSL.SSL.OP_NO_SSLv2 | OpenSSL.SSL.OP_NO_SSLv3)
    ctx.set_verify(OpenSSL.SSL.VERIFY_PEER, default_verify_callback)
    return ctx


async def negotiate_sasl(transport, xmlstream,
                         sasl_providers,
                         negotiation_timeout,
                         jid, features):
    """
    Perform SASL authentication on the given :class:`.protocol.XMLStream`
    `stream`. `transport` must be the :class:`asyncio.Transport` over which the
    `stream` runs. It is used to detect whether TLS is used and may be required
    by some SASL mechanisms.

    `sasl_providers` must be an iterable of :class:`SASLProvider` objects. They
    will be tried in iteration order to authenticate against the server. If one
    of the `sasl_providers` fails with a :class:`aiosasl.AuthenticationFailure`
    exception, the other providers are still tried; only if all providers fail,
    the last :class:`aiosasl.AuthenticationFailure` exception is re-raised.

    If no mechanism was able to authenticate but not due to authentication
    failures (other failures include no matching mechanism on the server side),
    :class:`aiosasl.SASLUnavailable` is raised.

    Return the :class:`.nonza.StreamFeatures` obtained after resetting the
    stream after successful SASL authentication.

    .. versionadded:: 0.6

    .. deprecated:: 0.10

        The `negotiation_timeout` argument is ignored. The timeout is
        controlled using the :attr:`~.XMLStream.deadtime_hard_limit` timeout
        of the stream.

        The argument will be removed in version 1.0. To prepare for this,
        please pass `jid` and `features` as keyword arguments.
    """

    if not transport.get_extra_info("sslcontext"):
        transport = None

    last_auth_error = None
    for sasl_provider in sasl_providers:
        try:
            result = await sasl_provider.execute(
                jid, features, xmlstream, transport)
        except ValueError as err:
            raise errors.StreamNegotiationFailure(
                "invalid credentials: {}".format(err)
            ) from err
        except aiosasl.AuthenticationFailure as err:
            last_auth_error = err
            continue

        if result:
            features = await protocol.reset_stream_and_get_features(
                xmlstream
            )
            break
    else:
        if last_auth_error:
            raise last_auth_error
        else:
            raise errors.SASLUnavailable("No common mechanisms")

    return features


class STARTTLSProvider:
    """
    .. deprecated:: 0.6

       Do **not** use this. This is a shim class which provides
       backward-compatibility for versions older than 0.6.
    """

    def __init__(self, ssl_context_factory,
                 certificate_verifier_factory=PKIXCertificateVerifier,
                 *,
                 require_starttls=True):
        self.ssl_context_factory = ssl_context_factory
        self.certificate_verifier_factory = certificate_verifier_factory
        self.tls_required = require_starttls


def security_layer(tls_provider, sasl_providers):
    """
    .. deprecated:: 0.6

       Replaced by :class:`SecurityLayer`.

    Return a configured :class:`SecurityLayer`. `tls_provider` must be a
    :class:`STARTTLSProvider`.

    The return value can be passed to the constructor of
    :class:`~.node.Client`.

    Some very basic checking on the input is also performed.
    """

    sasl_providers = tuple(sasl_providers)

    if not sasl_providers:
        raise ValueError("At least one SASL provider must be given.")
    for sasl_provider in sasl_providers:
        sasl_provider.execute  # check that sasl_provider has execute method

    result = SecurityLayer(
        tls_provider.ssl_context_factory,
        tls_provider.certificate_verifier_factory,
        tls_provider.tls_required,
        sasl_providers
    )

    return result


def tls_with_password_based_authentication(
        password_provider,
        ssl_context_factory=default_ssl_context,
        max_auth_attempts=3,
        certificate_verifier_factory=PKIXCertificateVerifier):
    """
    Produce a commonly used :class:`SecurityLayer`, which uses TLS and
    password-based SASL authentication. If `ssl_context_factory` is not
    provided, an SSL context with TLSv1+ is used.

    `password_provider` must be a coroutine which is called with the jid
    as first and the number of attempt as second argument. It must return the
    password to us, or :data:`None` to abort.

    Return a :class:`SecurityLayer` instance.

    .. deprecated:: 0.7

       Use :func:`make` instead.
    """

    tls_kwargs = {}
    if certificate_verifier_factory is not None:
        tls_kwargs["certificate_verifier_factory"] = \
            certificate_verifier_factory

    return SecurityLayer(
        ssl_context_factory,
        certificate_verifier_factory,
        True,
        (
            PasswordSASLProvider(
                password_provider,
                max_auth_attempts=max_auth_attempts),
        )
    )


class PinType(enum.Enum):
    """
    Enumeration to control which pinning is used by :meth:`make`.

    .. attribute:: PUBLIC_KEY

       Public keys are stored in the pin store. :class:`PublicKeyPinStore` is
       used.

    .. attribute:: CERTIFICATE

       Whole certificates are stored in the pin store.
       :class:`CertificatePinStore` is used.
    """

    PUBLIC_KEY = 0
    CERTIFICATE = 1


def make(
        password_provider,
        *,
        pin_store=None,
        pin_type=PinType.PUBLIC_KEY,
        post_handshake_deferred_failure=None,
        anonymous=False,
        ssl_context_factory=default_ssl_context,
        no_verify=False):
    """
    Construct a :class:`SecurityLayer`. Depending on the arguments passed,
    different features are enabled or disabled.

    .. warning::

        When using any argument except `password_provider`, be sure to read
        its documentation below the following overview **carefully**. Many
        arguments can be used to shoot yourself in the foot easily, while
        violating all security expectations.

    Args:

        password_provider (:class:`str` or coroutine function):
            Password source to authenticate with.

    Keyword Args:
        pin_store (:class:`dict` or :class:`AbstractPinStore`):
            Enable use of certificate/public key pinning. `pin_type` controls
            the type of store used when a dict is passed instead of a pin store
            object.
        pin_type (:class:`~aioxmpp.security_layer.PinType`):
            Type of pin store to create when `pin_store` is a dict.
        post_handshake_deferred_failure (coroutine function):
            Coroutine callback to invoke when using certificate pinning and the
            verification of the certificate was not possible using either PKIX
            or the pin store.
        anonymous (:class:`str`, :data:`None` or :data:`False`):
            trace token for SASL ANONYMOUS (:rfc:`4505`); passing a
            non-:data:`False` value enables ANONYMOUS authentication.
        ssl_context_factory (function): Factory function to create the SSL
            context used to establish transport layer security. Defaults to
            :func:`aioxmpp.security_layer.default_ssl_context`.
        no_verify (:class:`bool`): *Disable* all certificate verification.
            Usage is **strongly discouraged** outside controlled test
            environments. See below for alternatives.

    Raises:

        RuntimeError: if `anonymous` is not :data:`False` and the version of
            :mod:`aiosasl` does not support ANONYMOUS authentication.

    Returns:
        :class:`SecurityLayer`: object holding the entire security layer
            configuration

    `password_provider` must either be a coroutine function or a :class:`str`.
    As a coroutine function, it is called during authentication with the JID we
    are trying to authenticate against as the first, and the sequence number of
    the authentication attempt as second argument. The sequence number starts
    at 0. The coroutine is expected to return :data:`None` or a password. See
    :class:`PasswordSASLProvider` for details. If `password_provider` is a
    :class:`str`, a coroutine which returns the string on the first and
    :data:`None` on subsequent attempts is created and used.

    If `pin_store` is not :data:`None`, :class:`PinningPKIXCertificateVerifier`
    is used instead of the default :class:`PKIXCertificateVerifier`. The
    `pin_store` argument determines the pinned certificates: if it is a
    dictionary, a :class:`AbstractPinStore` according to the :class:`PinType`
    passed as `pin_type` argument is created and initialised with the data from
    the dictionary using its :meth:`~AbstractPinStore.import_from_json` method.
    Otherwise, `pin_store` must be a :class:`AbstractPinStore` instance which
    is passed to the verifier.

    `post_handshake_deferred_callback` is used only if `pin_store` is not
    :data:`None`. It is passed to the equally-named argument of
    :class:`PinningPKIXCertificateVerifier`, see the documentation there for
    details on the semantics. If `post_handshake_deferred_callback` is
    :data:`None` while `pin_store` is not, a coroutine which returns
    :data:`False` is substituted.

    `ssl_context_factory` can be a callable taking no arguments and returning
    a :class:`OpenSSL.SSL.Context` object. If given, the factory will be used
    to obtain an SSL context when the stream negotiates transport layer
    security via TLS. By default,
    :func:`aioxmpp.security_layer.default_ssl_context` is used, which should be
    fine for most applications.

    .. warning::

        The :func:`~.default_ssl_context` implementation sets important
        defaults. It is **strongly recommended** to use the context returned
        by :func:`~.default_ssl_context` and modify it, instead of creating
        a new context from scratch when implementing your own factory.

    If `no_verify` is true, none of the above regarding certificate verifiers
    matters. The internal null verifier is used, which **disables certificate
    verification completely**.

    .. warning::

        Disabling certificate verification makes your application vulnerable to
        trivial Man-in-the-Middle attacks. Do **not** use this outside
        controlled test environments or when you know **exactly** what you’re
        doing!

        If you need to handle certificates which cannot be verified using the
        public key infrastructure, consider making use of the `pin_store`
        argument instead.

    `anonymous` may be a string or :data:`False`. If it is not :data:`False`,
    :class:`AnonymousSASLProvider` is used before password based authentication
    is attempted. In addition, it is allowed to set `password_provider` to
    :data:`None`. `anonymous` is the trace token to use, and SHOULD be the
    empty string (as specified by :xep:`175`). This requires :mod:`aiosasl` 0.3
    or newer.

    .. note::

        :data:`False` and ``""`` are treated differently for the `anonymous`
        argument, despite both being false-y values!

    .. note::

        If `anonymous` is not :data:`False` and `password_provider` is not
        :data:`None`, both authentication types are attempted. Anonymous
        authentication is, in that case, preferred over password-based
        authentication.

        If you need to reverse the order, you have to construct your own
        :class:`SecurityLayer` object.

    .. warning::

        Take the security and privacy considerations from :rfc:`4505` (which
        specifies the ANONYMOUS SASL mechanism) and :xep:`175` (which discusses
        the ANONYMOUS SASL mechanism in the XMPP context) into account before
        using `anonymous`.

    The versatility and simplicity of use of this function make (pun intended)
    it the preferred way to construct :class:`SecurityLayer` instances.

    .. versionadded:: 0.8

        Support for SASL ANONYMOUS was added.

    .. versionadded:: 0.11

        Support for `ssl_context_factory`.
    """

    if isinstance(password_provider, str):
        static_password = password_provider

        async def password_provider(jid, nattempt):
            if nattempt == 0:
                return static_password
            return None

    if pin_store is not None:
        if post_handshake_deferred_failure is None:
            async def post_handshake_deferred_failure(verifier):
                return False

        if not isinstance(pin_store, AbstractPinStore):
            pin_data = pin_store
            if pin_type == PinType.PUBLIC_KEY:
                logger.debug("using PublicKeyPinStore")
                pin_store = PublicKeyPinStore()
            else:
                logger.debug("using CertificatePinStore")
                pin_store = CertificatePinStore()
            pin_store.import_from_json(pin_data)

        def certificate_verifier_factory():
            return PinningPKIXCertificateVerifier(
                pin_store.query,
                post_handshake_deferred_failure,
            )
    elif no_verify:
        certificate_verifier_factory = _NullVerifier
    else:
        certificate_verifier_factory = PKIXCertificateVerifier

    sasl_providers = []
    if anonymous is not False:
        if AnonymousSASLProvider is None:
            raise RuntimeError(
                "aiosasl does not support ANONYMOUS, please upgrade"
            )
        sasl_providers.append(
            AnonymousSASLProvider(anonymous)
        )

    if password_provider is not None:
        sasl_providers.append(
            PasswordSASLProvider(
                password_provider,
            ),
        )

    return SecurityLayer(
        ssl_context_factory,
        certificate_verifier_factory,
        True,
        tuple(sasl_providers),
    )
