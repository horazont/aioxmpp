"""
XMPP client basement
####################
"""
import asyncio
import binascii
import logging
import random
import ssl

from datetime import datetime, timedelta

from . import network, jid, protocol, stream_plugin, ssl_wrapper, sasl, stanza
from . import plugins, custom_queue
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
                 negotiation_timeout=15,
                 ping_timeout=30,
                 require_tls=True,
                 ssl_context_factory=default_ssl_context,
                 override_addr=None,
                 loop=None,
                 max_auth_attempts=3,
                 max_reconnect_attempts=3,
                 reconnect_interval_start=timedelta(seconds=5)):
        super().__init__()
        self._client_jid = jid.JID.fromstr(client_jid)
        self._loop = loop
        self._password_provider = password_provider
        self._negotiation_timeout = negotiation_timeout
        self._ping_timeout = ping_timeout
        self._require_tls = require_tls
        self._ssl_context_factory = ssl_context_factory
        self._override_addr = override_addr
        self._max_auth_attempts = max_auth_attempts
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_interval_start = reconnect_interval_start
        self._xmlstream = None
        self._ssl_wrapper = None
        self._active_queue = custom_queue.AsyncDeque(loop=self._loop)
        self._hold_queue = list()

        self._callback_registry = {
            "connecting": [],
            "connection_made": [],
            "connection_lost": [],
            "connection_failed": [],
            "closed": []
        }

        self._incoming_queue = asyncio.Queue()

        self._iq_callbacks = {}
        self._message_callbacks = {}
        self._presence_callbacks = {}

        self._disconnect_event = asyncio.Event()
        self._disconnect_event.set()

        self._stanza_broker_task = None
        self._worker_task = asyncio.async(
            self._worker(),
            loop=self._loop)

    @asyncio.coroutine
    def _connect(self):
        """
        Establish the connection to the server and perform stream
        negotiation. Return after the last step of stream negotiation has been
        handled and stanzas can be sent for general use.
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
                logger.warn("low-level connection attempt failed: %s", err)
        else:
            logger.warn("out of options to reach server for %s",
                        self._client_jid)
            raise OSError("Failed to connect to {}".format(
                self._client_jid.domainpart))

        self._ssl_wrapper = wrapper
        self._xmlstream = wrapper._protocol
        future = self._xmlstream.__features_future
        del self._xmlstream.__features_future

        self._disconnect_event.clear()

        self._stanza_broker_task = asyncio.async(
            self._worker_stanza_broker(),
            loop=self._loop)

        try:
            node = yield from future
            yield from self._negotiate_stream(node)
        except Exception as err:
            logger.exception("stream negotiation failed")
            self._disconnect_event.set()
            self._ssl_wrapper.close()
            self._ssl_wrapper = None
            self._xmlstream = None
            self._stanza_broker_task.cancel()
            self._stanza_broker_task = None
            raise

    @asyncio.coroutine
    def _fire_callback(self, callback_name, *args, **kwargs):
        callbacks = list(self._callback_registry[callback_name])
        for callback in callbacks:
            yield from callback(*args, **kwargs)

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
            if starttls_required:
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

        self._register_stanza_queues()

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
                self._xmlstream.E("{{{}}}starttls".format(namespaces.starttls))
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

        The default implementation only negotiates resource binding, using the
        jid passed to :meth:`connect`.
        """

        bind = self._xmlstream.make_iq()
        bind.type = "set"
        bind.data = plugins.rfc6120.Bind()
        if self._client_jid.resource is not None:
            bind.data.resource = self._client_jid.resource
        reply = yield from self.send_iq_and_wait(
            bind,
            timeout=self._negotiation_timeout)
        self._client_jid = reply.data.jid
        logger.info("bound to JID: %s", self._client_jid)

    def _register_stanza_queues(self):
        self._xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}iq",
            self._incoming_queue)
        self._xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}message",
            self._incoming_queue)
        self._xmlstream.stream_level_hooks.add_queue(
            "{jabber:client}presence",
            self._incoming_queue)

    def _reset_stream_and_get_new_features(self):
        future = asyncio.async(
            self._xmlstream.wait_for(
                [
                    "{http://etherx.jabber.org/streams}features",
                ],
                timeout=self._negotiation_timeout
            ),
            loop=self._loop)
        self._xmlstream.reset_stream()
        node = yield from future
        return node

    @asyncio.coroutine
    def _worker(self):
        """
        Worker coroutine which keeps the stream alive and is directly
        responsible for sending all state events events.
        """
        while True:
            self._disconnect_event.clear()
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
                except ConnectionError as err:
                    yield from self._fire_callback(
                        "connection_failed", err)
                except OSError as err:
                    yield from self._fire_callback("connection_failed", err)
                else:
                    break

                nattempt += 1

            else:
                abort = True

            if abort:
                break

            yield from self._fire_callback("connection_made")
            yield from self._disconnect_event.wait()
            yield from self._fire_callback("connection_lost")

            if self._max_reconnect_attempts == 0:
                break

        yield from self.close()

    @asyncio.coroutine
    def _worker_stanza_broker(self):
        disconnect_future = asyncio.async(
            self._disconnect_event.wait(),
            loop=self._loop)
        outgoing_stanza_future = asyncio.async(
            self._active_queue.popleft(),
            loop=self._loop)
        incoming_stanza_future = asyncio.async(
            self._incoming_queue.get(),
            loop=self._loop)

        while True:
            done, pending = yield from asyncio.wait(
                [
                    disconnect_future,
                    outgoing_stanza_future,
                    incoming_stanza_future
                ],
                loop=self._loop,
                return_when=asyncio.FIRST_COMPLETED)

            if disconnect_future in done:
                # disconnect for any reason
                if stanza_future in done:
                    self._active_queue.appendleft(stanza_future.result())
                break

            if outgoing_stanza_future in done:
                stanza = outgoing_stanza_future.result()
                self._xmlstream.send_node(stanza)
                outgoing_stanza_future = asyncio.async(
                    self._active_queue.popleft(),
                    loop=self._loop)

            if incoming_stanza_future in done:
                stanza = incoming_stanza_future.result()
                tag = stanza.tag
                if tag.endswith("}iq"):
                    self._loop.call_soon(self._stanza_iq, stanza)
                elif tag.endswith("}message"):
                    self._loop.call_soon(self._stanza_message, stanza)
                elif tag.endswith("}presence"):
                    self._loop.call_soon(self._stanza_presence, stanza)
                else:
                    # contents have been filtered by XMLStream
                    assert False

                incoming_stanza_future = asyncio.async(
                    self._incoming_queue.get(),
                    loop=self._loop)

    def _xmlstream_factory(self):
        proto = protocol.XMLStream(
            to=self._client_jid.domainpart,
            loop=self._loop)
        proto.__features_future = asyncio.async(
            proto.wait_for(
                [
                    "{http://etherx.jabber.org/streams}features",
                ],
                timeout=self._negotiation_timeout),
            loop=self._loop)
        return ssl_wrapper.STARTTLSableTransportProtocol(self._loop, proto)

    def _stanza_iq(self, iq):
        target = self._iq_callbacks.pop((iq.id, iq.from_, iq.type), None)

        if target is None and iq.type in {"result", "error"}:
            target = self._iq_callbacks.pop((iq.id, iq.from_, None), None)

        if target is None and iq.type in {"set", "get"}:
            reply = iq.make_reply("error")
            reply.error.condition = "feature-not-implemented"
            self.send_stanza(reply)
            return

        self._dispatch_target(iq, target)

    def _stanza_presence(self, presence):
        target = self._presence_callbacks.pop(
            (presence.id, presence.from_), None)

        if target is None:
            target = self._presence_callbacks.pop(
                (None, presence.from_), None)

        if target is None:
            target = self._presence_callbacks.pop(
                (None, presence.from_.bare), None)

        if target is None:
            logger.warn("failed to handle presence: {}".format(presence))
            return

        self._dispatch_target(target)

    def _stanza_message(self, msg):
        target = self._message_callbacks.pop((msg.type, msg.from_), None)
        if target is None:
            target = self._message_callbacks.pop((msg.type, msg.from_.bare),
                                                 None)
        if target is None:
            target = self._message_callbacks.pop((None, msg.from_), None)
        if target is None:
            target = self._message_callbacks.pop((None, msg.from_.bare), None)
        if target is None:
            target = self._message_callbacks.pop((msg.type, None), None)

        if target is None:
            logger.warn("failed to handle message: {}".format(msg))
            return

        self._dispatch_target(msg, target)

    def _dispatch_target(self, msg, target):
        to_call, to_push = target
        to_call_copy = to_call.copy()
        to_call.clear()
        for callback in to_call_copy:
            self._loop.call_soon(callback, msg)
        some_failed = False
        for queue in to_push:
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                some_failed = True
        if some_failed:
            logger.warn("message not pushed to all queues: {}".format(msg))

    @asyncio.coroutine
    def close(self):
        if self._xmlstream is not None:
            self._ssl_wrapper.close()
            self._ssl_wrapper = None
            self._xmlstream = None
        self._disconnect_event.set()

    def send_stanza(self, stanza):
        self.send_stanzas([stanza])

    def send_stanzas(self, stanzas):
        self._active_queue.extend(stanzas)

    @asyncio.coroutine
    def _send_and_wait(self,
                       stanzas,
                       reply_event,
                       timeout):
        disconnect_future = asyncio.async(
            self._disconnect_event.wait(),
            loop=self._loop)
        reply_future = asyncio.async(
            reply_event.wait(),
            loop=self._loop)

        self.send_stanzas(stanzas)

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
    def send_iq_and_wait(self, iq, timeout):
        ev = asyncio.Event()
        reply = None
        def callback(node):
            nonlocal reply
            ev.set()
            reply = node

        to_call, _ = self._iq_callbacks.setdefault(
            (iq.id, iq.to, None),
            ([], []))
        to_call.append(callback)

        yield from self._send_and_wait([iq], ev, timeout)

        return reply
