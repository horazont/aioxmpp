import abc
import asyncio
import base64
import functools
import hashlib
import hmac
import itertools
import logging
import operator
import random
import time

from .stringprep import saslprep
from . import errors, xso, protocol

from .utils import namespaces

logger = logging.getLogger(__name__)

_system_random = random.SystemRandom()

try:
    from hashlib import pbkdf2_hmac as pbkdf2
except ImportError:
    # this is untested if you have pbkdf2_hmac
    def pbkdf2(hashfun_name, input_data, salt, iterations, dklen=None):
        """
        Derivate a key from a password. *input_data* is taken as the bytes
        object resembling the password (or other input). *hashfun* must be a
        callable returning a :mod:`hashlib`-compatible hash function. *salt* is
        the salt to be used in the PBKDF2 run, *iterations* the count of
        iterations. *dklen* is the length in bytes of the key to be derived.

        Return the derived key as :class:`bytes` object.
        """

        if dklen is not None and dklen <= 0:
            raise ValueError("Invalid length for derived key: {}".format(
                dklen))

        hashfun = lambda: hashlib.new(hashfun_name)

        hlen = hashfun().digest_size
        if dklen is None:
            dklen = hlen

        block_count = (dklen + (hlen - 1)) // hlen

        mac_base = hmac.new(input_data, None, hashfun)

        def do_hmac(data):
            mac = mac_base.copy()
            mac.update(data)
            return mac.digest()

        def calc_block(i):
            u_prev = do_hmac(salt + i.to_bytes(4, "big"))
            u_accum = u_prev
            for k in range(1, iterations):
                u_curr = do_hmac(u_prev)
                u_accum = bytes(itertools.starmap(
                    operator.xor,
                    zip(u_accum, u_curr)))
                u_prev = u_curr

            return u_accum

        result = b"".join(
            calc_block(i)
            for i in range(1, block_count + 1))

        return result[:dklen]


class SASLAuth(xso.XSO):
    TAG = (namespaces.sasl, "auth")

    mechanism = xso.Attr("mechanism")
    payload = xso.Text(type_=xso.Base64Binary(empty_as_equal=True))

    def __init__(self, mechanism=None, payload=None):
        super().__init__()
        self.mechanism = mechanism
        self.payload = payload


class SASLChallenge(xso.XSO):
    TAG = (namespaces.sasl, "challenge")

    payload = xso.Text(type_=xso.Base64Binary(empty_as_equal=True))

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


class SASLResponse(xso.XSO):
    TAG = (namespaces.sasl, "response")

    payload = xso.Text(type_=xso.Base64Binary(empty_as_equal=True))

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


class SASLFailure(xso.XSO):
    TAG = (namespaces.sasl, "failure")

    condition = xso.ChildTag(
        tags=[
            "aborted",
            "account-disabled",
            "credentials-expired",
            "encryption-required",
            "incorrect-encoding",
            "invalid-authzid",
            "invalid-mechanism",
            "malformed-request",
            "mechanism-too-weak",
            "not-authorized",
            "temporary-auth-failure",
        ],
        default_ns=namespaces.sasl,
        allow_none=False,
        default=(namespaces.sasl, "temporary-auth-failure"),
        declare_prefix=None,
    )
    text = xso.ChildText(
        tag=(namespaces.sasl, "text"),
        attr_policy=xso.UnknownAttrPolicy.DROP,
        default=None,
        declare_prefix=None)

    def __init__(self, condition=None):
        super().__init__()
        if condition is not None:
            self.condition = condition


class SASLSuccess(xso.XSO):
    TAG = (namespaces.sasl, "success")

    payload = xso.Text(type_=xso.Base64Binary(empty_as_equal=True))


class SASLAbort(xso.XSO):
    TAG = (namespaces.sasl, "abort")


class SASLStateMachine:
    """
    A state machine to reduce code duplication during SASL handshake.

    The state methods change the state and return the next client state of the
    SASL handshake, optionally with server-supplied payload.

    Valid next states are:
    * ``('challenge', payload)`` (with *payload* being a :class:`bytes` object
      obtained from base64-decoding the servers challenge)
    * ``('success', None)`` – after successful authentication
    * ``('failure', None)`` – after failed authentication (e.g. after a call to
      :meth:`abort`)

    Note that, with the notable exception of :meth:`abort`, ``failure`` states
    are never returned but thrown as :class:`errors.SASLFailure` instead.

    The initial state is never returned.
    """

    def __init__(self, xmlstream):
        super().__init__()
        self.xmlstream = xmlstream
        self._state = "initial"
        self.timeout = None

    @asyncio.coroutine
    def _send_sasl_node_and_wait_for(self, node):
        node = yield from protocol.send_and_wait_for(
            self.xmlstream,
            [node],
            [
                SASLChallenge,
                SASLFailure,
                SASLSuccess
            ],
            timeout=self.timeout
        )

        state = node.TAG[1]

        self._state = state

        if state == "failure":
            xmpp_error = node.condition[1]
            text = node.text
            raise errors.SASLFailure(xmpp_error, text=text)

        if hasattr(node, "payload"):
            payload = node.payload
        else:
            payload = None

        return state, payload

    @asyncio.coroutine
    def initiate(self, mechanism, payload=None):
        """
        Initiate the SASL handshake and advertise the use of the given
        *mechanism*. If *payload* is not :data:`None`, it will be base64
        encoded and sent as initial client response along with the ``<auth />``
        element.

        Return the next state of the state machine as tuple (see
        :class:`SASLStateMachine` for details).
        """

        if self._state != "initial":
            raise RuntimeError("initiate has already been called")

        result = yield from self._send_sasl_node_and_wait_for(
            SASLAuth(mechanism=mechanism,
                     payload=payload))
        return result

    @asyncio.coroutine
    def response(self, payload):
        """
        Send a response to the previously received challenge, with the given
        *payload*. The payload is encoded using base64 and transmitted to the
        server.

        Return the next state of the state machine as tuple (see
        :class:`SASLStateMachine` for details).
        """
        if self._state != "challenge":
            raise RuntimeError(
                "no challenge has been made or negotiation failed")

        result = yield from self._send_sasl_node_and_wait_for(
            SASLResponse(payload=payload)
        )
        return result

    @asyncio.coroutine
    def abort(self):
        """
        Abort an initiated SASL authentication process. The expected result
        state is ``failure``.
        """
        if self._state == "initial":
            raise RuntimeError("SASL authentication hasn't started yet")

        try:
            next_state, payload = yield from self._send_sasl_node_and_wait_for(
                SASLAbort()
            )
        except errors.SASLFailure as err:
            self._state = "failure"
            if err.xmpp_error != "aborted":
                raise
            return "failure", None
        else:
            raise errors.SASLFailure(
                "aborted",
                text="unexpected non-failure after abort: {}".format(self._state)
            )


class SASLMechanism(metaclass=abc.ABCMeta):
    """
    Implementation of a SASL mechanism. Each SASLMechanism *class* must have a
    *class* attribute :attr:`handled_mechanisms`, which must be a container of
    strings holding the SASL mechanism names supported by that class.
    """

    @abc.abstractclassmethod
    def any_supported(cls, mechanisms):
        """
        Return the argument to be passed to :meth:`authenticate`, if any of the
        *mechanisms* (which is a :cls:`set`) is supported.

        Return :data:`None` otherwise.
        """

    @asyncio.coroutine
    @abc.abstractmethod
    def authenticate(self, sm, token):
        """
        Execute the mechanism identified by *token* (the value which has been
        returned by :meth:`any_supported` before) using the given
        :class:`SASLStateMachine` *sm*.

        If authentication fails, an appropriate exception is raised
        (:class:`~.errors.AuthenticationFailure`).
        """


class PLAIN(SASLMechanism):
    """
    The ``PLAIN`` SASL mechanism (see RFC 4616).

    *credential_provider* must be coroutine which returns a ``(user,
    password)`` tuple.
    """
    def __init__(self, credential_provider):
        super().__init__()
        self._credential_provider = credential_provider

    @classmethod
    def any_supported(cls, mechanisms):
        if "PLAIN" in mechanisms:
            return "PLAIN"
        return None

    @asyncio.coroutine
    def authenticate(self, sm, mechanism):
        logger.info("attempting PLAIN mechanism")
        username, password = yield from self._credential_provider()
        username = saslprep(username).encode("utf8")
        password = saslprep(password).encode("utf8")

        state, _ = yield from sm.initiate(
            mechanism="PLAIN",
            payload=b"\0" + username + b"\0" + password)

        if state != "success":
            raise errors.SASLFailure(
                "malformed-request",
                text="SASL protocol violation")

        return True


class SCRAM(SASLMechanism):
    """
    The SCRAM SASL mechanism (see RFC 5802).

    *credential_provider* must be coroutine which returns a ``(user,
    password)`` tuple.
    """

    def __init__(self, credential_provider):
        super().__init__()
        self._credential_provider = credential_provider
        self.nonce_length = 15

    _supported_hashalgos = {
        # the second argument is for preference ordering (highest first)
        # if anyone has a better hash ordering suggestion, I’m open for it
        # a value of 1 is added if the -PLUS variant is used
        # -- JWI
        "SHA-1": ("sha1", 1),
        "SHA-224": ("sha224", 224),
        "SHA-512": ("sha512", 512),
        "SHA-384": ("sha384", 384),
        "SHA-256": ("sha256", 256),
    }

    @classmethod
    def any_supported(cls, mechanisms):
        supported = []
        for mechanism in mechanisms:
            if not mechanism.startswith("SCRAM-"):
                continue
            if mechanism.endswith("-PLUS"):
                # channel binding is not supported
                continue

            hashfun_key = mechanism[6:]

            try:
                hashfun_name, quality = cls._supported_hashalgos[hashfun_key]
            except KeyError:
                continue

            supported.append(((1, quality), (mechanism, hashfun_name,)))

        if not supported:
            return None
        supported.sort()

        return supported.pop()[1]

    @classmethod
    def parse_message(cls, msg):
        parts = (
            part
            for part in msg.split(b",")
            if part)

        for part in parts:
            key, _, value = part.partition(b"=")
            if len(key) > 1 or key == b"m":
                raise Exception("SCRAM protocol violation / unknown "
                                "future extension")
            if key == b"n" or key == b"a":
                value = value.replace(b"=2C", b",").replace(b"=3D", b"=")

            yield key, value

    @asyncio.coroutine
    def authenticate(self, sm, token):
        mechanism, hashfun_name, = token
        logger.info("attempting %s mechanism (using %s hashfun)",
                    mechanism,
                    hashfun_name)
        # this is pretty much a verbatim implementation of RFC 5802.

        hashfun_factory = functools.partial(hashlib.new, hashfun_name)
        digest_size = hashfun_factory().digest_size

        # we don’t support channel binding
        gs2_header = b"n,,"
        username, password = yield from self._credential_provider()
        username = saslprep(username).encode("utf8")
        password = saslprep(password).encode("utf8")

        our_nonce = base64.b64encode(_system_random.getrandbits(
            self.nonce_length * 8
        ).to_bytes(
            self.nonce_length, "little"
        ))

        auth_message = b"n=" + username + b",r=" + our_nonce
        _, payload = yield from sm.initiate(
            mechanism,
            gs2_header + auth_message)

        auth_message += b"," + payload

        payload = dict(self.parse_message(payload))

        try:
            iteration_count = int(payload[b"i"])
            nonce = payload[b"r"]
            salt = base64.b64decode(payload[b"s"])
        except (ValueError, KeyError):
            yield from sm.abort()
            raise errors.SASLFailure(
                "Malformed server message: {!r}".format(payload))

        if not nonce.startswith(our_nonce):
            yield from sm.abort()
            raise errors.SASLFailure(
                "Server nonce doesn't fit our nonce")

        t0 = time.time()

        salted_password = pbkdf2(
            hashfun_name,
            password,
            salt,
            iteration_count)

        logger.debug("pbkdf2 timing: %f seconds", time.time() - t0)

        client_key = hmac.new(
            salted_password,
            b"Client Key",
            hashfun_factory).digest()

        stored_key = hashfun_factory(client_key).digest()

        reply = b"c=" + base64.b64encode(b"n,,") + b",r=" + nonce

        auth_message += b"," + reply

        client_proof = (
            int.from_bytes(
                hmac.new(
                    stored_key,
                    auth_message,
                    hashfun_factory).digest(),
                "big") ^
            int.from_bytes(client_key, "big")).to_bytes(digest_size, "big")

        logger.debug("response generation time: %f seconds", time.time() - t0)
        try:
            state, payload = yield from sm.response(
                reply + b",p=" + base64.b64encode(client_proof)
            )
        except errors.SASLFailure as err:
            raise err.promote_to_authentication_failure() from None

        if state != "success":
            raise errors.SASLFailure(
                "malformed-request",
                text="SCRAM protocol violation")

        server_signature = hmac.new(
            hmac.new(
                salted_password,
                b"Server Key",
                hashfun_factory).digest(),
            auth_message,
            hashfun_factory).digest()

        payload = dict(self.parse_message(payload))

        if base64.b64decode(payload[b"v"]) != server_signature:
            raise errors.SASLFailure(
                "Authentication successful, but server signature invalid")

        return True
