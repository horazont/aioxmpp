"""
XMPP client basement
####################
"""

import abc
import asyncio
import binascii
import hashlib
import logging
import random
import ssl

from datetime import datetime, timedelta

from . import network, jid, protocol, stream_plugin, ssl_wrapper, sasl, stanza
from . import plugins, custom_queue, stream_worker, xml
from .utils import *

logger = logging.getLogger(__name__)

class StreamNegotiationFailure(ConnectionError):
    pass

class AuthError(StreamNegotiationFailure):
    # special case, as AuthErrors are treated as fatal (no-retry)
    pass

def default_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    return ctx

class Client:
    """
    Manage an XMPP client.

    Connects to the appropriate server using the given *client_jid*. If
    *override_addr* is given, it must be a tuple pointing to the hostname and
    port to connect to. Otherwise, the RFC specified process of picking the
    destination host and port is used.

    For authentication, the *password_provider* coroutine is called with two
    arguments: The JID provided through *client_jid* and the number of the
    authentication attempt (up to *max_auth_attempts* attempts are made to
    authenticate before aborting). If authentication fails more than
    *max_auth_attempts* times, the connection fails.

    During stream negotiation, up to *negotiation_timeout* seconds of time may
    pass between sending a stream negotiation command and receiving the reply
    from the server. If the timeout is surpassed, the connection fails.

    If *require_tls* is :data:`True`, ``STARTTLS`` is required upon connecting
    and a failure in ``STARTTLS`` negotiation will make the connection fail. The
    *ssl_context_factory* is called without arguments to provide a
    :class:`ssl.SSLContext` object for the connection.

    As long as the object exists and :meth:`close` has not been called, it will
    maintain an open connection to the server, as far as possible. Reconnects
    will be handled under the cover.

    If the connection fails for a reason different than authentication or
    unsupported features on the remote side, the following procedure is engaged:

    * The ``connection_lost`` event is fired.
    * Up to *max_reconnect_attempts* times, the client attempts to re-establish
      the connection. Each time an attempt is made, the ``connecting`` event is
      fired. The time between reconnect attempts starts with
      *reconnect_interval_start* and is doubled for each attempt, to take load
      off a possibly overloaded server.

      For each failed attempt, a ``connection_failed`` event is fired, with the
      exception which occured as argument.

      If *max_reconnect_attempts* is :data:`None`, reconnection is attempted
      indefinietly.
    * If the maximum reconnection attempts has been reached, reconnecting is
      stopped. No more ``connecting`` events will be fired. The client moves
      into ``closed`` state.

    No matter what, unless the object is destroyed, stream management
    information is preserved to be able to re-engage a previous session if
    possible in any way. If stream management can not be resumed, outgoing
    stanzas are put in the *hold* queue.

    The client uses the given :mod:`asyncio` event *loop*, but if none is given,
    it uses the current default :mod:`asyncio` loop.
    """

    def __init__(self,
                 client_jid,
                 password_provider,
                 negotiation_timeout=timedelta(seconds=15),
                 ping_timeout=timedelta(seconds=30),
                 require_tls=True,
                 ssl_context_factory=default_ssl_context,
                 override_addr=None,
                 loop=None,
                 max_auth_attempts=3,
                 max_reconnect_attempts=3,
                 reconnect_interval_start=timedelta(seconds=5),
                 use_sm=True):
        super().__init__()
        self._client_jid = jid.JID.fromstr(client_jid)
        self._loop = loop
        self._password_provider = password_provider
        self._negotiation_timeout = negotiation_timeout
        self._require_tls = require_tls
        self._ssl_context_factory = ssl_context_factory
        self._override_addr = override_addr
        self._max_auth_attempts = max_auth_attempts
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_interval_start = reconnect_interval_start
        self._xmlstream = None
        self._ssl_wrapper = None

        self._tx_context = xml.default_tx_context

        # stream management state
        self._use_sm = use_sm

        self._callback_registry = {
            "connecting": [],
            "connection_made": [],
            "connection_lost": [],
            "connection_failed": [],
            "internal_error": [],
            "closed": []
        }

        self._iq_request_callbacks = {}
        self._message_callbacks = {}
        self._presence_callbacks = {}

        self.disconnect_event = asyncio.Event()
        self.disconnect_event.set()

        self._stanza_broker = stream_worker.StanzaBroker(
            self._loop,
            self.disconnect_event,
            ping_timeout,
            self._handle_ping_timeout,
            (self._handle_iq_request,
             self._handle_message,
             self._handle_presence))

        self._worker_task = asyncio.async(
            self._worker(),
            loop=self._loop)

    @asyncio.coroutine
    def _connect_xmlstream(self):
        """
        Handle the establishment of the low-level connection. Return the
        transport and the xmlstream as tuple.
        """
        if self._override_addr:
            record_iterable = [self._override_addr]
            logger.info("user-provided address is used: %s", self._override_addr)
        else:
            logger.info("discovering usable addresses from SRV records")
            host = self._client_jid.domainpart
            srv_records = yield from network.find_xmpp_host_addr(
                self._loop, host)
            record_iterable = network.group_and_order_srv_records(srv_records)

        for host, port in record_iterable:
            logger.info("trying to connect to %s at port %s", host, port)
            try:
                _, wrapper = yield from self._loop.create_connection(
                    self._xmlstream_factory,
                    host=host,
                    port=port)
                break
            except OSError as err:
                logger.warning("low-level connection attempt failed: %s", err)
        else:
            logger.warning("out of options to reach server for %s",
                           self._client_jid)
            raise OSError("Failed to connect to {}".format(
                self._client_jid.domainpart))

        return wrapper, wrapper._protocol

    @asyncio.coroutine
    def _connect(self):
        """
        Establish the connection to the server and perform stream
        negotiation. Return after the last step of stream negotiation has been
        handled and stanzas can be sent for general use.
        """
        wrapper, xmlstream = yield from self._connect_xmlstream()
        self._ssl_wrapper = wrapper
        self._xmlstream = xmlstream
        self._stanza_broker.setup(xmlstream)

        future = self._xmlstream.__features_future
        del self._xmlstream.__features_future

        self.disconnect_event.clear()
        self._stanza_broker.start().add_done_callback(
            self._task_done_handler)

        logger.debug("negotiating stream")
        try:
            node = yield from future
            yield from self._negotiate_stream(node)
        except:
            self.disconnect_event.set()
            self._stanza_broker.stop()
            self._xmlstream.close()
            self._ssl_wrapper = None
            self._xmlstream = None
            raise

        self._stanza_broker.start_liveness_handler()

    def _dispatch_stanza(self, callback_map, keys, stanza):
        for key in keys:
            try:
                cbs, queues = callback_map[key]
                if not cbs and not queues:
                    del callback_map[key]
                    continue
            except KeyError:
                continue

            self._dispatch_target(stanza, cbs, queues)
            if not queues and not cbs:
                del callback_map[key]
            break
        else:
            return False
        return True

    def _dispatch_target(self, msg, cbs, queues):
        to_call = cbs.copy()
        cbs.clear()
        for callback in to_call:
            self._loop.call_soon(callback, msg)
        some_failed = False
        for queue in queues:
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                some_failed = True
        if some_failed:
            logger.warning("stanza not pushed to all queues: {}".format(msg))

    @asyncio.coroutine
    def _fire_callback(self, callback_name, *args, **kwargs):
        logger.debug("firing event: %s (args=%r, kwargs=%r)",
                     callback_name, args, kwargs)
        callbacks = list(self._callback_registry[callback_name])
        for callback in callbacks:
            yield from callback(*args, **kwargs)

    @asyncio.coroutine
    def _handle_ping_timeout(self):
        logger.warning("ping timeout, disconnecting")
        yield from self.disconnect()

    def _handle_iq_request(self, iq):
        # handle this, or reply with error
        if iq.data is not None:
            tag = iq.data.tag
        else:
            tag = iq.tag

        namespace, local = split_tag(tag)

        keys = [
            (namespace, local, iq.type),
            (namespace, local, None),
        ]


        if not self._dispatch_stanza(self._iq_request_callbacks, keys, iq):
            logger.warning("no handler for %s ({%s}%s)", iq, namespace, local)
            response = iq.make_reply(error=True)
            response.error.type = "cancel"
            response.error.condition = "feature-not-implemented"
            response.error.text = ("No handler registered for this request"
                                   " pattern")
            self.enqueue_stanza(response)

    def _handle_message(self, message):
        from_ = message.from_
        id = message.id
        type = message.type

        keys = [
            (str(from_), type),
            (str(from_.bare), type),
            (None, type),
        ]
        if not self._dispatch_stanza(self._message_callbacks, keys, message):
            logger.warning("unhandled message stanza: %r", message)
            return

    def _handle_presence(self, presence):
        from_ = presence.from_
        id = presence.id
        type = presence.type

        keys = [
            (type, )
        ]

        if not self._dispatch_stanza(self._presence_callbacks, keys, presence):
            logger.warning("unhandled presence stanza: %r", presence)
            return

    @asyncio.coroutine
    def _negotiate_stream(self, features_node):
        """
        Handle stream negotiation, by calling
        :meth:`_negotiate_stream_starttls`, :meth:`_negotiate_stream_auth` and
        :meth:`_negotiate_stream_features` accordingly.
        """
        # steps to do:
        # 1. negotiate STARTTLS if required and available (fail if not available
        #    but required)
        # 2. authenticate
        # 3. all other stream features

        starttls_node = features_node.find("{{{}}}starttls".format(
            namespaces.starttls))
        if starttls_node is None:
            if self._require_tls:
                raise StreamNegotiationFailure(
                    "STARTTLS not supported by remote end")
            tls_engaged = False
        else:
            tls_engaged = yield from self._negotiate_stream_starttls(
                starttls_node)
            if not tls_engaged:
                raise StreamNegotiationFailure(
                    "STARTTLS required, but negotiation failed")

        self._tls_engaged = tls_engaged

        if tls_engaged:
            features_node = yield from self._reset_stream_and_get_new_features()

        mechanisms_node = features_node.find("{{{}}}mechanisms".format(
            namespaces.sasl))
        if mechanisms_node is None:
            raise StreamNegotiationFailure("No authentication supported")

        yield from self._negotiate_stream_auth(mechanisms_node)
        features_node = yield from self._reset_stream_and_get_new_features()

        yield from self._negotiate_stream_features(features_node)

    @asyncio.coroutine
    def _negotiate_stream_starttls(self, starttls_node):
        """
        Negotiate STARTTLS with the remote side, using the information from
        *starttls_node*. Return :data:`True` if STARTTLS negotiation was
        successful, :data:`False` if negotiation failed, but the stream is still
        usable.

        Raise an appropriate exception if negotiation failed irrecoverably.

        This is called during :meth:`connect`, if the server offers STARTTLS.
        """

        node = yield from self._xmlstream.send_and_wait_for(
            [
                self._tx_context("{{{}}}starttls".format(namespaces.starttls))
            ],
            [
                "{urn:ietf:params:xml:ns:xmpp-tls}proceed",
                "{urn:ietf:params:xml:ns:xmpp-tls}failure",
            ]
        )

        status = node.tag.endswith("}proceed")

        if status:
            logger.info("engaging STARTTLS")
            try:
                yield from self._ssl_wrapper.starttls(
                    ssl_context=self._ssl_context_factory(),
                    server_hostname=self._client_jid.domainpart)
            except Exception as err:
                logger.exception("STARTTLS failed")
                raise StreamNegotiationFailure(
                    "STARTTLS failed on our side")
            return True
        else:
            return False

    @asyncio.coroutine
    def _negotiate_stream_auth(self, sasl_mechanisms_node):
        """
        Negotiate authentication with the remote side, using the information
        from the *sasl_mechanisms_node*.

        The default implementation will attempt SCRAM and (only on TLS secured
        transports) PLAIN authentication using the *password_provider* passed to
        :meth:`connect`.

        Authentication is retried using the credentials from *password_provider*
        until the stream is terminated by the remote end or *password_provider*
        returns :data:`None` or more than *max_auth_attempts* attempts were
        made.

        For each new retry (that is, starting again with the first SASL
        mechanism supported), a new password request is sent to the
        *password_provider*.

        To apply custom authentication methods, subclassing is the preferred
        method, as it is assumed that you will also need to customize other
        parts of the negotiation process (e.g. the TLS part for SASL EXTERNAL).

        Raise an appropriate exception if authentication fails irrecoverably
        (e.g. after a certain amount of retries has failed).

        This is called during :meth:`connect`, if the server offers SASL
        authentication.
        """

        cached_password = None
        nattempt = 0
        @asyncio.coroutine
        def credential_provider():
            nonlocal cached_password, nattempt
            if cached_password is None:
                cached_password = yield from self._password_provider(
                    self._client_jid,
                    nattempt)
            return self._client_jid.localpart, cached_password

        mechanisms = [
            sasl.SCRAM(credential_provider)
        ]

        if self._tls_engaged:
            mechanisms.append(
                sasl.PLAIN(credential_provider))

        remote_mechanisms = frozenset(
            node.text
            for node in sasl_mechanisms_node.iter("{{{}}}mechanism".format(
                    namespaces.sasl))
        )

        if not remote_mechanisms:
            raise StreamNegotiationFailure("Remote didn’t advertise any SASL "
                                           "mechanism")

        for i in range(self._max_auth_attempts):
            nattempt = i
            made_attempt = False
            for mechanism in mechanisms:
                token = mechanism.any_supported(remote_mechanisms)
                if token is None:
                    continue

                made_attempt = True
                sm = sasl.SASLStateMachine(self._xmlstream)
                success = yield from mechanism.authenticate(sm, token)
                if success:
                    break
            if success:
                break

            cached_password = None

            if not made_attempt:
                raise StreamNegotiationFailure("No supported SASL mechanism "
                                               "available")
        else:
            raise StreamNegotiationFailure("Authentication failed")

    @asyncio.coroutine
    def _negotiate_stream_features(self, features_node):
        """
        Negotiate any further stream features, after STARTTLS and SASL have been
        negotiated, using the stream:features node from *features_node*.

        The default implementation negotiates (or possibly resumes) Stream
        Management and performs resource binding (if no session was resumed).

        Return :data:`True` if a Stream Management session was resumed (thus, no
        further stream feature negotiation should happen) and :data:`False`
        otherwise.
        """

        sm_node = features_node.find("{{{}}}sm".format(
            namespaces.stream_management))

        # check for _sm_id, as that’s whats needed for resumption
        if self._stanza_broker.sm_session_id is not None:
            # we are resuming a stream-management session
            success = yield from self._resume_stream_management(sm_node)
            if success:
                return True

        bind_node = features_node.find("{{{}}}bind".format(
            namespaces.bind))
        if bind_node is None:
            raise StreamNegotiationFailure("Server does not support resource "
                                           "binding")

        bind = self.make_iq()
        bind.type = "set"
        bind.data = plugins.rfc6120.Bind()
        if self._client_jid.resource is not None:
            bind.data.resource = self._client_jid.resource
        reply = yield from self.send_iq_and_wait(
            bind,
            timeout=self._negotiation_timeout.total_seconds())
        self._client_jid = reply.data.jid
        logger.info("bound to JID: %s", self._client_jid)

        if self._use_sm:
            try:
                yield from self._negotiate_stream_management(sm_node)
            except StreamNegotiationFailure as err:
                # this is not neccessarily fatal
                logger.warning(err)

        return False

    @asyncio.coroutine
    def _negotiate_stream_management(self, feature_node):
        if feature_node is None:
            logger.info("server is not willing to do sm")
            self._stanza_broker.sm_reset()
            return

        with self._stanza_broker.sm_init() as ctx:
            node = yield from self._xmlstream.send_and_wait_for(
                [
                    self._tx_context("{{{}}}enable".format(
                        namespaces.stream_management))
                ],
                [
                    "{{{}}}enabled".format(namespaces.stream_management),
                    "{{{}}}failed".format(namespaces.stream_management)
                ])

            if node.tag.endswith("}failed"):
                logger.error("sm negotiation failed")
                raise StreamNegotiationFailure(
                    "Could not negotiate stream management")

        if node.get("resume", "").lower() in {"true", "1"}:
            ctx.set_session_id(sm_id)

    def _reset_stream_and_get_new_features(self):
        future = self._xmlstream.wait_for(
            [
                "{http://etherx.jabber.org/streams}features",
            ],
            timeout=self._negotiation_timeout.total_seconds()
        )
        self._xmlstream.reset_stream()
        node = yield from future
        return node

    @asyncio.coroutine
    def _resume_stream_management(self, feature_node):
        if feature_node is None:
            # we previously had an SM session, but the server doesn’t support SM
            # anymore. this sucks
            logger.warning("sorry, have to quit SM -- server won’t play along"
                           " anymore")
            self._stanza_broker.sm_reset()
            return False

        node = yield from self._xmlstream.send_and_wait_for(
            [
                self._tx_context(
                    "{{{}}}resume".format(namespaces.stream_management),
                    h=str(self._acked_remote_ctr),
                    previd=self._sm_id)
            ],
            [
                "{{{}}}resumed".format(namespaces.stream_management),
                "{{{}}}failed".format(namespaces.stream_management)
            ])

        if node.tag.endswith("}failed"):
            logger.error("stream management resumption failed")
            self._stanza_broker.sm_reset()
            return False

        try:
            acked_ctr = int(node.get("h"))
            if acked_ctr < 0:
                raise ValueError("must be non-negative")
        except ValueError as err:
            logger.error("received incorrect counter value on resumption: "
                         "%r (%s)",
                         node.get("h"), err)
            self._stanza_broker.sm_reset()
            raise StreamNegotiationFailure("Stream management counter has"
                                           " invalid value")

        self._stanza_broker.sm_resume(acked_ctr)

        return True

    def _starttls_check_peer(self, transport):
        pass
        # base_transport = transport.get_extra_info("transport")
        # ssl_sock = base_transport.get_extra_info("socket")
        # cert = ssl_sock.getpeercert(binary_form=True)
        # for hashfun_name in ["sha256", "sha1", "sha512"]:
        #     hashfun = hashlib.new(hashfun_name)
        #     hashfun.update(cert)
        #     print(binascii.b2a_hex(hashfun.digest()).decode("ascii"))

    def _task_done_handler(self, future):
        import traceback
        if future.cancelled():
            return
        exc = future.exception()
        if exc:
            logger.error("A task terminated unexpectedly: %s",
                         "".join(
                             traceback.format_exception(
                                 type(exc),
                                 exc,
                                 exc.__traceback__)))
            # FIXME: do something sensible here.
            self._fire_callback("internal_error", exc)
            asyncio.async(
                self.disconnect(),
                loop=self._loop)

    @asyncio.coroutine
    def _worker(self):
        """
        Worker coroutine which keeps the stream alive and is directly
        responsible for sending all state events events.
        """
        while True:
            self.disconnect_event.clear()
            nattempt = 0
            abort = False

            while self._max_reconnect_attempts is None or (
                    self._max_reconnect_attempts > nattempt):

                if nattempt > 0:
                    wait_time = (self._reconnect_interval_start.total_seconds() *
                                 (2**(nattempt-1)))
                    logger.debug("attempt no. %d failed, sleeping %d seconds until"
                                 " next attempt",
                                 nattempt+1,
                                 wait_time)
                    yield from asyncio.sleep(wait_time)

                yield from self._fire_callback("connecting", nattempt)
                try:
                    yield from self._connect()
                except AuthError as err:
                    abort = True
                    yield from self._fire_callback(
                        "connection_failed", err)
                except StreamNegotiationFailure as err:
                    yield from self._fire_callback("connection_failed", err)
                except Exception as err:
                    logger.exception("unexpected connection error")
                    yield from self._fire_callback("connection_failed", err)
                else:
                    break

                nattempt += 1

            else:
                abort = True

            if abort:
                break

            yield from self._fire_callback("connection_made")
            yield from self.disconnect_event.wait()
            yield from self._fire_callback("connection_lost")

            yield from self.disconnect()

            if self._max_reconnect_attempts == 0:
                break

    def _xmlstream_factory(self):
        proto = protocol.XMLStream(
            to=self._client_jid.domainpart,
            loop=self._loop,
            tx_context=self._tx_context)
        proto.__features_future = proto.wait_for(
            [
                "{http://etherx.jabber.org/streams}features",
            ],
            timeout=self._negotiation_timeout.total_seconds())
        proto.on_starttls_engaged = self._starttls_check_peer
        return ssl_wrapper.STARTTLSableTransportProtocol(self._loop, proto)

    @asyncio.coroutine
    def disconnect(self):
        if self._xmlstream is not None:
            self._stanza_broker.stop()
            self._xmlstream.close()
            self._xmlstream = None
            self._ssl_wrapper.close()
            self._ssl_wrapper = None
        self.disconnect_event.set()

    @asyncio.coroutine
    def close(self):
        self._max_reconnect_attempts = 0
        yield from self.disconnect()

    @asyncio.coroutine
    def _wait_for_reply_future(self, reply_future, timeout):
        disconnect_future = asyncio.async(
            self.disconnect_event.wait(),
            loop=self._loop)

        done, pending = yield from asyncio.wait(
            [
                disconnect_future,
                reply_future
            ],
            return_when=asyncio.FIRST_COMPLETED,
            loop=self._loop,
            timeout=timeout)

        for f in pending:
            f.cancel()

        if reply_future in done:
            return

        if disconnect_future in done:
            raise ConnectionError("Disconnected")

        raise TimeoutError()

    @asyncio.coroutine
    def _send_token_and_wait(self, token, timeout):
        self._stanza_broker.enqueue_token(token)
        return (yield from self._wait_for_reply_future(token.response_future,
                                                       timeout))

    @asyncio.coroutine
    def send_iq_and_wait(self, iq, timeout):
        future = asyncio.Future()

        token = self._stanza_broker.make_stanza_token(
            iq,
            response_future=future)

        yield from self._send_token_and_wait(token, timeout)

        return future.result()

    @property
    def client_jid(self):
        return self._client_jid

    def register_callback(self, at, cb):
        cblist = self._callback_registry[at]
        cblist.append(cb)

    def make_iq(self, **kwargs):
        iq = self._tx_context.make_iq(**kwargs)
        return iq

    def make_presence(self, **kwargs):
        presence = self._tx_context.make_presence(**kwargs)
        return presence

    def make_message(self, **kwargs):
        message = self._tx_context.make_message(**kwargs)
        return message

    def enqueue_stanza(self, stanza, **kwargs):
        self._stanza_broker.enqueue_token(
            self._stanza_broker.make_stanza_token(stanza, **kwargs)
        )

    def add_presence_queue(self, queue, type):
        cbs, queues = self._presence_callbacks.setdefault(
            (type,),
            ([], set())
        )
        queues.add(queue)

    def add_message_queue(self, queue, type="chat", from_=None):
        cbs, queues = self._message_callbacks.setdefault(
            (from_, type),
            ([], set())
        )
        queues.add(queue)
