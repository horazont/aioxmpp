########################################################################
# File name: node.py
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
:mod:`~aioxmpp.node` --- XMPP network nodes (clients, mostly)
#############################################################

This module contains functions to connect to an XMPP server, as well as
maintaining the stream. In addition, a client class which completely manages a
stream based on a presence setting is provided.

Using XMPP
==========

.. currentmodule:: aioxmpp

.. autoclass:: Client

.. autoclass:: PresenceManagedClient

.. currentmodule:: aioxmpp.node

.. class:: AbstractClient

   Alias of :class:`Client`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

Connecting streams low-level
============================

.. autofunction:: discover_connectors

.. autofunction:: connect_xmlstream

Utilities
=========

.. autoclass:: UseConnected

"""
import asyncio
import contextlib
import logging
import warnings

from datetime import timedelta

import dns.resolver

import OpenSSL.SSL

import aiosasl

from . import (
    connector,
    network,
    protocol,
    errors,
    stream,
    callbacks,
    nonza,
    rfc3921,
    rfc6120,
    stanza,
    structs,
    security_layer,
    dispatcher,
    presence as mod_presence,
)


logger = logging.getLogger(__name__)


async def lookup_addresses(loop, jid):
    addresses = await network.find_xmpp_host_addr(
        loop,
        jid.domain)

    return network.group_and_order_srv_records(addresses)


async def discover_connectors(domain: str, loop=None, logger=logger):
    """
    Discover all connection options for a domain, in descending order of
    preference.

    This coroutine returns options discovered from SRV records, or if none are
    found, the generic option using the domain name and the default XMPP client
    port.

    Each option is represented by a triple ``(host, port, connector)``.
    `connector` is a :class:`aioxmpp.connector.BaseConnector` instance which is
    suitable to connect to the given host and port.

    `logger` is the logger used by the function.

    The following sources are supported:

    * :rfc:`6120` SRV records. One option is returned per SRV record.

      If one of the SRV records points to the root name (``.``),
      :class:`ValueError` is raised (the domain specifically said that XMPP is
      not supported here).

    * :xep:`368` SRV records. One option is returned per SRV record.

    * :rfc:`6120` fallback process (only if no SRV records are found). One
      option is returned for the host name with the default XMPP client port.

    The options discovered from SRV records are mixed together, ordered by
    priority and then within priorities are shuffled according to their weight.
    Thus, if there are multiple records of equal priority, the result of the
    function is not deterministic.

    .. versionadded:: 0.6
    """

    domain_encoded = domain.encode("idna") + b"."
    starttls_srv_failed = False
    tls_srv_failed = False

    try:
        starttls_srv_records = await network.lookup_srv(
            domain_encoded,
            "xmpp-client",
        )
        starttls_srv_disabled = False
    except dns.resolver.NoNameservers as exc:
        starttls_srv_records = []
        starttls_srv_disabled = False
        starttls_srv_failed = True
        starttls_srv_exc = exc
        logger.debug("xmpp-client SRV lookup for domain %s failed "
                     "(may not be fatal)",
                     domain_encoded,
                     exc_info=True)
    except ValueError:
        starttls_srv_records = []
        starttls_srv_disabled = True

    try:
        tls_srv_records = await network.lookup_srv(
            domain_encoded,
            "xmpps-client",
        )
        tls_srv_disabled = False
    except dns.resolver.NoNameservers:
        tls_srv_records = []
        tls_srv_disabled = False
        tls_srv_failed = True
        logger.debug("xmpps-client SRV lookup for domain %s failed "
                     "(may not be fatal)",
                     domain_encoded,
                     exc_info=True)
    except ValueError:
        tls_srv_records = []
        tls_srv_disabled = True

    if starttls_srv_failed and (tls_srv_failed or tls_srv_records is None):
        # the failure is probably more useful as a diagnostic
        # if we find a good reason to allow this scenario, we might change it
        # later.
        raise starttls_srv_exc

    if starttls_srv_disabled and (tls_srv_disabled or tls_srv_records is None):
        raise ValueError(
            "XMPP not enabled on domain {!r}".format(domain),
        )

    if starttls_srv_records is None and tls_srv_records is None:
        # no SRV records published, fall back
        logger.debug(
            "no SRV records found for %s, falling back",
            domain,
        )
        return [
            (domain, 5222, connector.STARTTLSConnector()),
        ]

    starttls_srv_records = starttls_srv_records or []
    tls_srv_records = tls_srv_records or []

    srv_records = [
        (prio, weight, (host.decode("ascii"), port,
                        connector.STARTTLSConnector()))
        for prio, weight, (host, port) in starttls_srv_records
    ]

    srv_records.extend(
        (prio, weight, (host.decode("ascii"), port,
                        connector.XMPPOverTLSConnector()))
        for prio, weight, (host, port) in tls_srv_records
    )

    options = list(
        network.group_and_order_srv_records(srv_records)
    )

    logger.debug(
        "options for %s: %r",
        domain,
        options,
    )

    return options


async def _try_options(options, exceptions,
                       jid, metadata, negotiation_timeout, loop, logger):
    """
    Helper function for :func:`connect_xmlstream`.
    """
    for host, port, conn in options:
        logger.debug(
            "domain %s: trying to connect to %r:%s using %r",
            jid.domain, host, port, conn
        )
        try:
            transport, xmlstream, features = await conn.connect(
                loop,
                metadata,
                jid.domain,
                host,
                port,
                negotiation_timeout,
                base_logger=logger,
            )
        except OSError as exc:
            logger.warning(
                "connection failed: %s", exc
            )
            exceptions.append(exc)
            continue

        logger.debug(
            "domain %s: connection succeeded using %r",
            jid.domain,
            conn,
        )

        if not metadata.sasl_providers:
            return transport, xmlstream, features

        try:
            features = await security_layer.negotiate_sasl(
                transport,
                xmlstream,
                metadata.sasl_providers,
                negotiation_timeout=None,
                jid=jid,
                features=features,
            )
        except errors.SASLUnavailable as exc:
            protocol.send_stream_error_and_close(
                xmlstream,
                condition=errors.StreamErrorCondition.POLICY_VIOLATION,
                text=str(exc),
            )
            exceptions.append(exc)
            continue
        except Exception as exc:
            protocol.send_stream_error_and_close(
                xmlstream,
                condition=errors.StreamErrorCondition.UNDEFINED_CONDITION,
                text=str(exc),
            )
            raise

        return transport, xmlstream, features

    return None


async def connect_xmlstream(
        jid,
        metadata,
        negotiation_timeout=60.,
        override_peer=[],
        loop=None,
        logger=logger):
    """
    Prepare and connect a :class:`aioxmpp.protocol.XMLStream` to a server
    responsible for the given `jid` and authenticate against that server using
    the SASL mechanisms described in `metadata`.

    :param jid: Address of the user for which the connection is made.
    :type jid: :class:`aioxmpp.JID`
    :param metadata: Connection metadata for configuring the TLS usage.
    :type metadata: :class:`~.security_layer.SecurityLayer`
    :param negotiation_timeout: Timeout for each individual negotiation step.
    :type negotiation_timeout: :class:`float` in seconds
    :param override_peer: Sequence of connection options which take precedence
                          over normal discovery methods.
    :type override_peer: sequence of (:class:`str`, :class:`int`,
                         :class:`~.BaseConnector`) triples
    :param loop: asyncio event loop to use (defaults to current)
    :type loop: :class:`asyncio.BaseEventLoop`
    :param logger: Logger to use (defaults to module-wide logger)
    :type logger: :class:`logging.Logger`
    :raises ValueError: if the domain from the `jid` announces that XMPP is not
                        supported at all.
    :raises aioxmpp.errors.TLSFailure: if all connection attempts fail and one
                                       of them is a :class:`~.TLSFailure`.
    :raises aioxmpp.errors.MultiOSError: if all connection attempts fail.
    :return: Transport, XML stream and the current stream features
    :rtype: tuple of (:class:`asyncio.BaseTransport`, :class:`~.XMLStream`,
            :class:`~.nonza.StreamFeatures`)

    The part of the `metadata` specifying the use of TLS is applied. If the
    security layer does not mandate TLS, the resulting XML stream may not be
    using TLS. TLS is used whenever possible.

    The connection options in `override_peer` are tried before any standardised
    discovery of connection options is made. Only if all of them fail,
    automatic discovery of connection options is performed.

    `loop` may be a :class:`asyncio.BaseEventLoop` to use. Defaults to the
    current event loop.

    If the domain from the `jid` announces that XMPP is not supported at all,
    :class:`ValueError` is raised. If no options are returned from
    :func:`discover_connectors` and `override_peer` is empty,
    :class:`ValueError` is raised, too.

    If all connection attempts fail, :class:`aioxmpp.errors.MultiOSError` is
    raised. The error contains one exception for each of the options discovered
    as well as the elements from `override_peer` in the order they were tried.

    A TLS problem is treated like any other connection problem and the other
    connection options are considered. However, if *all* connection options
    fail and the set of encountered errors includes a TLS error, the TLS error
    is re-raised instead of raising a :class:`aioxmpp.errors.MultiOSError`.

    Return a triple ``(transport, xmlstream, features)``. `transport`
    the underlying :class:`asyncio.Transport` which is used for the `xmlstream`
    :class:`~.protocol.XMLStream` instance. `features` is the
    :class:`aioxmpp.nonza.StreamFeatures` instance describing the features of
    the stream.

    .. versionadded:: 0.6

    .. versionchanged:: 0.8

       The explicit raising of TLS errors has been introduced. Before, TLS
       errors were treated like any other connection error, possibly masking
       configuration problems.
    """
    loop = asyncio.get_event_loop() if loop is None else loop

    options = list(override_peer)

    exceptions = []

    result = await _try_options(
        options,
        exceptions,
        jid, metadata, negotiation_timeout, loop, logger,
    )
    if result is not None:
        return result

    options = list(await discover_connectors(
        jid.domain,
        loop=loop,
        logger=logger,
    ))

    result = await _try_options(
        options,
        exceptions,
        jid, metadata, negotiation_timeout, loop, logger,
    )
    if result is not None:
        return result

    if not options and not override_peer:
        raise ValueError("no options to connect to XMPP domain {!r}".format(
            jid.domain
        ))

    for exc in exceptions:
        if isinstance(exc, errors.TLSFailure):
            raise exc

    raise errors.MultiOSError(
        "failed to connect to XMPP domain {!r}".format(jid.domain),
        exceptions
    )


class Client:
    """
    Base class to implement an XMPP client.

    Args:
        local_jid (:class:`~aioxmpp.JID`): Jabber ID to connect as.
        security_layer (:class:`~aioxmpp.SecurityLayer`): Configuration
            for authentication and TLS.
        negotiation_timeout (:class:`datetime.timedelta`): Timeout for the
            individual stream negotiation steps (bounds initial connect time)
        override_peer: Connection options which take precedence over the
            standardised connection options
        max_inital_attempts (:class:`int`): Maximum number of initial
            connection attempts before giving up.
        loop (:class:`asyncio.BaseEventLoop` or :data:`None`): Override the
            :mod:`asyncio` event loop to use.
        logger (:class:`logging.Logger` or :data:`None`): Override the logger
            to use.

    These classes deal with managing the :class:`~aioxmpp.stream.StanzaStream`
    and the underlying :class:`~aioxmpp.protocol.XMLStream` instances. The
    abstract client provides functionality for connecting the xmlstream as well
    as signals which indicate changes in the stream state.

    The `security_layer` is best created using the
    :func:`aioxmpp.security_layer.make` function and must provide
    authentication for the given `local_jid`.

    If `loop` is given, it must be a :class:`asyncio.BaseEventLoop`
    instance. If it is not given, the current event loop is used.

    As a glue between the stanza stream and the XML stream, it also knows about
    stream management and performs stream management negotiation. It is
    specialized on client operations, which implies that it will try to keep
    the stream alive as long as wished by the client.

    The client will attempt to connect to the server(s) associated with the
    `local_jid`, using the prioritised `override_peer` setting or the
    standardised options for connecting (see :meth:`discover_connectors`). The
    initial connection attempt must succeed within `max_initial_attempts`.

    If the connection breaks after the first connection attempt, the client
    will try to resume the connection transparently. If the server supports
    stream management (:xep:`198`) with resumption, this is entirely
    transparent to all operations over the stream. If the stream is not
    resumable or the resumption fails and `allow_implicit_reconnect` is true,
    the application and services using the stream are notified about that. If,
    in that situation, `allow_implicit_reconnect` is false instead, the client
    stops with an error.

    The number of reconnection attempts is generally unbounded. The application
    is notified that the stream got interrupted with the
    :meth:`on_stream_suspended` is emitted. After reconnection,
    :meth:`on_stream_established` is emitted (possibly preceded by a
    :meth:`on_stream_destroyed` emission if the stream failed to resume). If
    the application wishes to bound the time the stream tries to transparently
    reconnect, it should connect to the :meth:`on_stream_suspended` signal and
    stop the stream as needed.

    The reconnection attempts are throttled using expenential backoff
    controlled by the :attr:`backoff_start`, :attr:`backoff_factor` and
    :attr:`backoff_cap` attributes.

    .. note::

       If `max_initial_attempts` is :data:`None`, the stream will try
       indefinitely to connect to the server even if the connection has
       never succeeded yet. This is may mask problems with the configuration of
       the client itself, because the client cannot successfully distinguish
       permanent problems arising from the configuration (of the client or the
       server) from problems arising from transient problems such as network
       failures.

       This may severely degrade usabilty, because the client is then stuck in
       a connect loop without any usable feedback. Setting a bound for the
       initial connection attempt is usually better, for interactive
       applications an upper bound of 1 might make most sense (possibly the
       interactive application may retry on its own if the user did not
       indicate that they wish to do so after a timeout). We’ll leave the UX
       considerations up to you.

    .. versionchanged:: 0.4

       Since 0.4, support for legacy XMPP sessions has been implemented. Mainly
       for compatibility with ejabberd.

    .. versionchanged:: 0.8

       The amount of initial connection attempts is now bounded by
       `max_initial_attempts`. The :meth:`on_stream_suspended` signal and the
       associated logic has been introduced.

    Controlling the client:

    .. automethod:: connected

    .. automethod:: start

    .. automethod:: stop

    .. autoattribute:: running

    .. attribute:: negotiation_timeout
        :annotation: = timedelta(seconds=60)

        The timeout applied to the connection process and the individual steps
        of negotiating the stream. See the `negotiation_timeout` argument to
        :func:`connect_xmlstream`.

    .. attribute:: override_peer

       A sequence of triples ``(host, port, connector)``, where `host` must be
       a host name or IP as string, `port` must be a port number and
       `connector` must be a :class:`aioxmpp.connector.BaseConnctor` instance.

       These connection options are passed to :meth:`connect_xmlstream` and
       thus take precedence over the options discovered using
       :meth:`discover_connectors`.

       .. note::

          If Stream Management is used and the peer server provided a location
          to connect to on resumption, that location is preferred even over the
          options set here.

       .. versionadded:: 0.6

    .. autoattribute:: resumption_timeout
        :annotation: = None

    Connection information:

    .. autoattribute:: established

    .. attribute:: established_event

        An :class:`asyncio.Event` which indicates that the stream is
        established. A stream is valid after resource binding and before it has
        been destroyed.

        While this event is cleared, :meth:`enqueue` fails with
        :class:`ConnectionError` and :meth:`send` blocks.

    .. autoattribute:: suspended

    .. autoattribute:: local_jid

    .. attribute:: stream

       The :class:`~aioxmpp.stream.StanzaStream` instance used by the node.

    .. attribute:: stream_features

       An instance of :class:`~aioxmpp.nonza.StreamFeatures`. This is the
       most-recently received stream features information (the one received
       right before resource binding).

       While no stream has been established yet, this is :data:`None`. During
       transparent re-negotiation, that information may be obsolete. However,
       when :attr:`before_stream_established` fires, the information is
       up-to-date.

    Sending stanzas:

    .. automethod:: send

    .. automethod:: enqueue

    Configuration of exponential backoff for reconnects:

    .. attribute:: backoff_start
       :annotation: = timedelta(1)

       When an underlying XML stream fails due to connectivity issues (generic
       :class:`OSError` raised), exponential backoff takes place before
       attempting to reconnect.

       The initial time to wait before reconnecting is described by
       :attr:`backoff_start`.

    .. attribute:: backoff_factor
       :annotation: = 1.2

       Each subsequent time a connection fails, the previous backoff time is
       multiplied with :attr:`backoff_factor`.

    .. attribute:: backoff_cap
       :annotation: = timedelta(60)

       The backoff time is capped to :attr:`backoff_cap`, to avoid having
       unrealistically high values.

    Signals:

    .. signal:: on_failure(err)

       This signal is fired when the client fails and stops.

    .. syncsignal:: before_stream_established()

       This coroutine signal is executed right before
       :meth:`on_stream_established` fires.

    .. signal:: on_stopped()

       Fires when the client stops gracefully. This is the counterpart to
       :meth:`on_failure`.

    .. signal:: on_stream_established()

       When the stream is established and resource binding took place, this
       event is fired. It means that the stream can now be used for XMPP
       interactions.

    .. signal:: on_stream_suspended(reason)

       The stream has been suspened due to a connection failure.

       :param reason: The exception which terminated the stream.
       :type reason: :class:`Exception`

       This signal may be immediately followed by a
       :meth:`on_stream_destroyed`, if the stream did not support stream
       resumption. Otherwise, a new connection is attempted transparently.

       In general, this signal exists solely for informational purposes. It
       can be used to drive a user interface which indicates that messages may
       be delivered with delay, because the underlying network is transiently
       interrupted.

       :meth:`on_stream_suspended` is not emitted if the stream was stopped on
       user request.

       After :meth:`on_stream_suspended` is emitted, one of the two following
       signals is emitted:

       - :meth:`on_stream_destroyed` indicates that state was actually lost and
         that others most likely see or saw an unavailable presence broadcast
         for the resource.
       - :meth:`on_stream_resumed` indicates that no state was lost and the
         stream is fully usable again.

       .. versionadded:: 0.8

    .. signal:: on_stream_resumed()

        The stream has been resumed after it has been suspended, without loss
        of data.

        This is the counterpart to :meth:`on_stream_suspended`.

        In general, this signal exists solely for informational purposes. It
        can be used to drive a user interface which indicates that messages may
        be delivered with delay, because the underlying network is transiently
        interrupted.

        .. versionadded:: 0.11

    .. signal:: on_stream_destroyed(reason=None)

       This is called whenever a stream is destroyed. The conditions for this
       are the same as for
       :attr:`aioxmpp.stream.StanzaStream.on_stream_destroyed`.

       :param reason: An optional exception which indicates the reason for the
                      destruction of the stream.
       :type reason: :class:`Exception`

       This event can be used to know when to discard all state about the XMPP
       connection, such as roster information. Services implemented in
       :mod:`aioxmpp` generally subscribe to this signal to discard cached
       state.

       `reason` is optional. It is given if there is has been a specific
       exception which describes the cause for the stream destruction, such as
       a :class:`ConnectionError`.

       .. versionchanged:: 0.8

          The `reason` argument was added.

    Services:

    .. automethod:: summon

    Miscellaneous:

    .. attribute:: logger

       The :class:`logging.Logger` instance which is used by the
       :class:`Client`. This is the `logger` passed to the constructor or a
       logger derived from the fully qualified name of the class.

       .. versionadded:: 0.6

          The :attr:`logger` attribute was added.

    """

    on_failure = callbacks.Signal()
    on_stopped = callbacks.Signal()
    on_stream_destroyed = callbacks.Signal()
    on_stream_suspended = callbacks.Signal()
    on_stream_resumed = callbacks.Signal()
    on_stream_established = callbacks.Signal()

    before_stream_established = callbacks.SyncSignal()

    def __init__(self,
                 local_jid,
                 security_layer,
                 *,
                 negotiation_timeout=timedelta(seconds=60),
                 max_initial_attempts=4,
                 override_peer=[],
                 loop=None,
                 logger=None):
        super().__init__()
        self._local_jid = local_jid
        self._loop = loop or asyncio.get_event_loop()
        self._main_task = None
        self._security_layer = security_layer

        self._failure_future = asyncio.Future()
        self.logger = (logger or
                       logging.getLogger(".".join([
                           type(self).__module__,
                           type(self).__qualname__,
                       ])))

        self._backoff_time = None

        self._is_suspended = False

        # track whether the connection succeeded *at least once*
        # used to enforce max_initial_attempts
        self._had_connection = False
        self._nattempt = 0

        self._services = {}

        self.stream_features = None

        self.negotiation_timeout = negotiation_timeout
        self.backoff_start = timedelta(seconds=1)
        self.backoff_factor = 1.2
        self.backoff_cap = timedelta(seconds=60)
        self.override_peer = list(override_peer)
        self.established_event = asyncio.Event()
        self._max_initial_attempts = max_initial_attempts
        self._resumption_timeout = None

        self.on_stopped.logger = self.logger.getChild("on_stopped")
        self.on_failure.logger = self.logger.getChild("on_failure")
        self.on_stream_established.logger = \
            self.logger.getChild("on_stream_established")
        self.on_stream_destroyed.logger = \
            self.logger.getChild("on_stream_destroyed")
        self.on_stream_suspended.logger = \
            self.logger.getChild("on_stream_suspended")

        if logger is not None:
            stream_base_logger = self.logger
        else:
            stream_base_logger = logging.getLogger("aioxmpp")
        self.stream = stream.StanzaStream(
            local_jid.bare(),
            base_logger=stream_base_logger
        )

        self.stream._xxx_message_dispatcher = self.summon(
            dispatcher.SimpleMessageDispatcher,
        )

        self.stream._xxx_presence_dispatcher = self.summon(
            dispatcher.SimplePresenceDispatcher,
        )

        def send_warner(*args, **kwargs):
            warnings.warn("send() on StanzaStream is deprecated and will "
                          "be removed in 1.0. Use send() on the Client "
                          "instead.",
                          DeprecationWarning,
                          stacklevel=1)
            return self.send(*args, **kwargs)

        self.stream.send = send_warner

        def enqueue_warner(*args, **kwargs):
            warnings.warn("enqueue() on StanzaStream is deprecated and will "
                          "be removed in 1.0. Use enqueue() on the Client "
                          "instead.",
                          DeprecationWarning,
                          stacklevel=1)
            return self.enqueue(*args, **kwargs)

        self.stream.enqueue = enqueue_warner

    def _stream_failure(self, exc):
        if self._failure_future.done():
            self.logger.warning(
                "something is odd: failure future is already done ..."
            )
            return

        if not self._is_suspended:
            self.on_stream_suspended(exc)
            self._is_suspended = True

        self._failure_future.set_result(exc)
        self._failure_future = asyncio.Future()

    def _stream_destroyed(self, reason):
        if not self._is_suspended:
            if not isinstance(reason, stream.DestructionRequested):
                self.on_stream_suspended(reason)
            self._is_suspended = True

        if self.established_event.is_set():
            self.established_event.clear()
            self.on_stream_destroyed()

    def _on_main_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # task terminated normally
            self.on_stopped()
        except Exception as err:
            self.logger.exception("main failed")
            self.on_failure(err)

    async def _try_resume_stream_management(self, xmlstream, features):
        try:
            await self.stream.resume_sm(xmlstream)
        except errors.StreamNegotiationFailure as exc:
            self.logger.warning("failed to resume stream (%s)", exc)
            return False
        return True

    async def _negotiate_legacy_session(self):
        self.logger.debug(
            "remote server announces support for legacy sessions"
        )
        await self.stream._send_immediately(
            stanza.IQ(type_=structs.IQType.SET,
                      payload=rfc3921.Session())
        )
        self.logger.debug(
            "legacy session negotiated (upgrade your server!)"
        )

    async def _negotiate_stream(self, xmlstream, features):
        server_can_do_sm = True
        try:
            features[nonza.StreamManagementFeature]
        except KeyError:
            if self.stream.sm_enabled:
                self.logger.warning("server isn’t advertising SM anymore")
                self.stream.stop_sm()
            server_can_do_sm = False

        self.logger.debug("negotiating stream (server_can_do_sm=%s)",
                          server_can_do_sm)

        if self.stream.sm_enabled:
            resumed = await self._try_resume_stream_management(
                xmlstream, features)
            if resumed:
                return features, resumed
        else:
            resumed = False

        self.stream_features = features
        self.stream.start(xmlstream)

        if not resumed:
            self.logger.debug("binding to resource")
            await self._bind()

        if server_can_do_sm:
            self.logger.debug("attempting to start stream management")
            try:
                await self.stream.start_sm(
                    resumption_timeout=self._resumption_timeout
                )
            except errors.StreamNegotiationFailure:
                self.logger.debug("stream management failed to start")
            self.logger.debug("stream management started")

        try:
            session_feature = features[rfc3921.SessionFeature]
        except KeyError:
            pass  # yay
        else:
            if not session_feature.optional:
                await self._negotiate_legacy_session()
            else:
                self.logger.debug(
                    "skipping optional legacy session negotiation"
                )

        self.established_event.set()

        await self.before_stream_established()

        self.on_stream_established()

        return features, resumed

    async def _bind(self):
        iq = stanza.IQ(type_=structs.IQType.SET)
        iq.payload = rfc6120.Bind(resource=self._local_jid.resource)
        try:
            result = await self.stream._send_immediately(iq)
        except errors.XMPPError as exc:
            raise errors.StreamNegotiationFailure(
                "Resource binding failed: {}".format(exc)
            )

        self._local_jid = result.jid
        self.stream.local_jid = result.jid.bare()
        self.logger.info("bound to jid: %s", self._local_jid)

    async def _main_impl(self):
        failure_future = self._failure_future

        override_peer = []
        if self.stream.sm_enabled:
            sm_location = self.stream.sm_location
            if sm_location:
                override_peer.append((
                    str(sm_location[0]),
                    sm_location[1],
                    connector.STARTTLSConnector(),
                ))
        override_peer += self.override_peer

        tls_transport, xmlstream, features = await connect_xmlstream(
                self._local_jid,
                self._security_layer,
                negotiation_timeout=self.negotiation_timeout.total_seconds(),
                override_peer=override_peer,
                loop=self._loop,
                logger=self.logger)

        self._had_connection = True

        try:
            features, sm_resumed = await self._negotiate_stream(
                xmlstream,
                features)

            if self._is_suspended:
                self.on_stream_resumed()
            self._is_suspended = False
            self._backoff_time = None

            exc = await failure_future
            self.logger.error("stream failed: %s", exc)
            raise exc
        except asyncio.CancelledError:
            self.logger.info("client shutting down (on request)")
            # cancelled, this means a clean shutdown is requested
            await self.stream.close()
            raise
        finally:
            self.logger.info("stopping stream")
            self.stream.stop()

    async def _main(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                self.stream.on_failure.context_connect(self._stream_failure)
            )
            stack.enter_context(
                self.stream.on_stream_destroyed.context_connect(
                    self._stream_destroyed)
            )
            while True:
                self._nattempt += 1
                self._failure_future = asyncio.Future()
                try:
                    await self._main_impl()
                except errors.StreamError as err:
                    if err.condition == errors.StreamErrorCondition.CONFLICT:
                        self.logger.debug("conflict!")
                        raise
                except (errors.StreamNegotiationFailure,
                        aiosasl.SASLError):
                    if self.stream.sm_enabled:
                        self.stream.stop_sm()
                    raise
                except (OSError, dns.resolver.NoNameservers,
                        OpenSSL.SSL.Error) as exc:
                    self.logger.info("connection error: (%s) %s",
                                     type(exc).__qualname__,
                                     exc)
                    if (not self._had_connection and
                            self._max_initial_attempts is not None and
                            self._nattempt >= self._max_initial_attempts):
                        self.logger.warning("out of connection attempts")
                        raise

                    if self._backoff_time is None:
                        self._backoff_time = self.backoff_start.total_seconds()
                    self.logger.debug("re-trying after %.1f seconds",
                                      self._backoff_time)
                    await asyncio.sleep(self._backoff_time)
                    self._backoff_time *= self.backoff_factor
                    if self._backoff_time > self.backoff_cap.total_seconds():
                        self._backoff_time = self.backoff_cap.total_seconds()
                    continue  # retry

    def start(self):
        """
        Start the client. If it is already :attr:`running`,
        :class:`RuntimeError` is raised.

        While the client is running, it will try to keep an XMPP connection
        open to the server associated with :attr:`local_jid`.
        """
        if self.running:
            raise RuntimeError("client already running")

        self._main_task = asyncio.ensure_future(
            self._main(),
            loop=self._loop
        )
        self._main_task.add_done_callback(self._on_main_done)

    def stop(self):
        """
        Stop the client. This sends a signal to the clients main task which
        makes it terminate.

        It may take some cycles through the event loop to stop the client
        task. To check whether the task has actually stopped, query
        :attr:`running`.
        """
        if not self.running:
            return

        self.logger.debug("stopping main task of %r", self, stack_info=True)
        self._main_task.cancel()

    def _summon(self, class_, visited):
        # this is essentially a topological sort algorithm
        try:
            return self._services[class_]
        except KeyError:
            if class_ in visited:
                raise ValueError("dependency loop")
            visited.add(class_)

            # summon dependencies before taking len(self._services) as
            # the instantiation index of the service
            dependencies = {
                depclass: self._summon(depclass, visited)
                for depclass in class_.PATCHED_ORDER_AFTER
            }

            service_order_index = len(self._services)

            instance = class_(
                self,
                logger_base=self.logger,
                dependencies=dependencies,
                service_order_index=service_order_index,
            )
            self._services[class_] = instance
            return instance

    def summon(self, class_):
        """
        Summon a :class:`~aioxmpp.service.Service` for the client.

        If the `class_` has already been summoned for the client, it’s instance
        is returned.

        Otherwise, all requirements for the class are first summoned (if they
        are not there already). Afterwards, the class itself is summoned and
        the instance is returned.
        """
        return self._summon(class_, set())

    # properties

    @property
    def local_jid(self):
        """
        The :class:`~aioxmpp.JID` the client currently has. While the
        client is disconnected, which parts of the :attr:`local_jid` can be
        relied upon depends on the authentication mechanism used. For example,
        using anonymous authentication, the server dictates even the local part
        of the JID and it will change after a reconnect. For more common
        authentication schemes (such as normal password-based authentication),
        the localpart is usually chosen by the client.

        For interoperability with different authentication schemes, code must
        invalidate all copies of this attribute when a
        :meth:`on_stream_established` or :meth:`on_stream_destroyed` event is
        emitted.

        Writing this attribute is not allowed, as changing the JID introduces a
        lot of issues with respect to reusability of the stream. Instantiate a
        new :class:`Client` if you need to change the bare part of the JID.

        .. note::

           Changing the resource between reconnects may be allowed later.
        """
        return self._local_jid

    @property
    def running(self):
        """
        true if the client is currently running, false otherwise.
        """
        return self._main_task is not None and not self._main_task.done()

    @property
    def established(self):
        """
        true if the stream is currently established (as defined in
        :attr:`on_stream_established`) and false otherwise.
        """
        return self.established_event.is_set()

    @property
    def suspended(self):
        """
        true if the stream is currently suspended (see
        :meth:`on_stream_suspended`)

        .. versionadded:: 0.11
        """
        return self._is_suspended

    @property
    def resumption_timeout(self):
        """
        The maximum time as integer in seconds for which the server shall hold
        on to the session if the underlying transport breaks.

        This is only relevant if the server supports
        :xep:`Stream Management <198>` and the server may ignore the request
        for a maximum timeout and/or impose its own maximum. After the
        stream has been negotiated, :attr:`.StanzaStream.sm_max` holds the
        actual timeout announced by the server (may be :data:`None` if the
        server did not specify a timeout).

        The default value of :data:`None` does not request any specific
        timeout from the server and leaves it up to the server to decide.

        Setting a :attr:`resumption_timeout` of zero (0) disables resumption.

        .. versionadded:: 0.9
        """
        return self._resumption_timeout

    @resumption_timeout.setter
    def resumption_timeout(self, value):
        if (value is not None and
                (not isinstance(value, int) or isinstance(value, bool))):
            raise TypeError(
                "resumption_timeout must be int or None, got {!r}".format(
                    value
                )
            )
        if value is not None and value < 0:
            raise ValueError(
                "resumption timeout must be non-negative or None"
            )
        self._resumption_timeout = value

    def connected(self, *, presence=structs.PresenceState(False), **kwargs):
        """
        Return a :class:`.node.UseConnected` context manager which does not
        modify the presence settings.

        The keyword arguments are passed to the :class:`.node.UseConnected`
        context manager constructor.

        .. versionadded:: 0.8
        """
        return UseConnected(self, presence=presence, **kwargs)

    def enqueue(self, stanza, **kwargs):
        """
        Put a `stanza` in the internal transmission queue and return a token to
        track it.

        :param stanza: Stanza to send
        :type stanza: :class:`IQ`, :class:`Message` or :class:`Presence`
        :param kwargs: see :class:`StanzaToken`
        :raises ConnectionError: if the stream is not :attr:`established`
            yet.
        :return: token which tracks the stanza
        :rtype: :class:`StanzaToken`

        The `stanza` is enqueued in the active queue for transmission and will
        be sent on the next opportunity. The relative ordering of stanzas
        enqueued is always preserved.

        Return a fresh :class:`StanzaToken` instance which traks the progress
        of the transmission of the `stanza`. The `kwargs` are forwarded to the
        :class:`StanzaToken` constructor.

        This method calls :meth:`~.stanza.StanzaBase.autoset_id` on the stanza
        automatically.

        .. seealso::

           :meth:`send`
              for a more high-level way to send stanzas.

        .. versionchanged:: 0.10

            This method has been moved from
            :meth:`aioxmpp.stream.StanzaStream.enqueue`.
        """
        if not self.established_event.is_set():
            raise ConnectionError("stream is not ready")

        return self.stream._enqueue(stanza, **kwargs)

    async def send(self, stanza, *, timeout=None, cb=None):
        """
        Send a stanza.

        :param stanza: Stanza to send
        :type stanza: :class:`~.IQ`, :class:`~.Presence` or :class:`~.Message`
        :param timeout: Maximum time in seconds to wait for an IQ response, or
                        :data:`None` to disable the timeout.
        :type timeout: :class:`~numbers.Real` or :data:`None`
        :param cb: Optional callback which is called synchronously when the
            reply is received (IQ requests only!)
        :raise OSError: if the underlying XML stream fails and stream
            management is not disabled.
        :raise aioxmpp.stream.DestructionRequested:
           if the stream is closed while sending the stanza or waiting for a
           response.
        :raise aioxmpp.errors.XMPPError: if an error IQ response is received
        :raise aioxmpp.errors.ErroneousStanza: if the IQ response could not be
            parsed
        :raise ValueError: if `cb` is given and `stanza` is not an IQ request.
        :return: IQ response :attr:`~.IQ.payload` or :data:`None`

        Send the stanza and wait for it to be sent. If the stanza is an IQ
        request, the response is awaited and the :attr:`~.IQ.payload` of the
        response is returned.

        If the stream is currently not ready, this method blocks until the
        stream is ready to send payload stanzas. Note that this may be before
        initial presence has been sent. To synchronise with that type of
        events, use the appropriate signals.

        The `timeout` as well as any of the exception cases referring to a
        "response" do not apply for IQ response stanzas, message stanzas or
        presence stanzas sent with this method, as this method only waits for
        a reply if an IQ *request* stanza is being sent.

        If `stanza` is an IQ request and the response is not received within
        `timeout` seconds, :class:`TimeoutError` (not
        :class:`asyncio.TimeoutError`!) is raised.

        If `cb` is given, `stanza` must be an IQ request (otherwise,
        :class:`ValueError` is raised before the stanza is sent). It must be a
        callable returning an awaitable. It receives the response stanza as
        first and only argument. The returned awaitable is awaited by
        :meth:`send` and the result is returned instead of the original
        payload. `cb` is called synchronously from the stream handling loop
        when the response is received, so it can benefit from the strong
        ordering guarantees given by XMPP XML Streams.

        The `cb` may also return :data:`None`, in which case :meth:`send` will
        simply return the IQ payload as if `cb` was not given. Since the return
        value of coroutine functions is awaitable, it is valid and supported to
        pass a coroutine function as `cb`.

        .. warning::

            Remember that it is an implementation detail of the event loop when
            a coroutine is scheduled after it awaited an awaitable; this
            implies that if the caller of :meth:`send` is merely awaiting the
            :meth:`send` coroutine, the strong ordering guarantees of XMPP XML
            Streams are lost.

            To regain those, use the `cb` argument.

        .. note::

            For the sake of readability, unless you really need the strong
            ordering guarantees, avoid the use of the `cb` argument. Avoid
            using a coroutine function unless you really need to.

        .. versionchanged:: 0.10

            * This method now waits until the stream is ready to send stanza¸
              payloads.
            * This method was moved from
              :meth:`aioxmpp.stream.StanzaStream.send`.

        .. versionchanged:: 0.9

            The `cb` argument was added.

        .. versionadded:: 0.8
        """
        if not self.running:
            raise ConnectionError("client is not running")

        if not self.established:
            self.logger.debug("send(%s): stream not established, waiting",
                              stanza)
            # wait for the stream to be established
            stopped_fut = self.on_stopped.future()
            failure_fut = self.on_failure.future()
            established_fut = asyncio.ensure_future(
                self.established_event.wait()
            )
            done, pending = await asyncio.wait(
                [
                    established_fut,
                    failure_fut,
                    stopped_fut,
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not established_fut.done():
                established_fut.cancel()
            if failure_fut.done():
                if not stopped_fut.done():
                    stopped_fut.cancel()
                failure_fut.exception()
                raise ConnectionError("client failed to connect")
            if stopped_fut.done():
                raise ConnectionError("client shut down by user request")

            self.logger.debug("send(%s): stream established, sending")

        return await self.stream._send_immediately(stanza,
                                                   timeout=timeout,
                                                   cb=cb)


class PresenceManagedClient(Client):
    """
    Client whose connection is controlled by its configured presence.

    .. seealso::

       :class:`Client`
          for a description of the arguments.

    The presence is set using :attr:`presence` or the :class:`PresenceServer`
    service. If the set presence is an *available* presence, the client is
    started (if it is not already running). If the set presence is an
    *unavailable* presence, the unavailable presence is broadcast and the
    client is stopped.

    While the start/stop interfaces of :class:`~.Client` are still available,
    using them may interfere with the behaviour of the presence automagic.

    The initial presence is set to `unavailable`, thus, the client will not
    connect immediately.

    .. autoattribute:: presence

    .. automethod:: set_presence

    .. automethod:: connected

    Signals:

    .. attribute:: on_presence_sent

       The event is fired after :meth:`.Client.on_stream_established` and after
       the current presence has been sent to the server as *initial presence*.

    .. versionchanged:: 0.8

       Since 0.8, the :class:`PresenceManagedClient` is implemented on top of
       :class:`PresenceServer`. Changing the presence via the
       :class:`PresenceServer` has the same effect as writing :attr:`presence`
       or calling :meth:`set_presence`.
    """

    on_presence_sent = callbacks.Signal()

    def __init__(self, jid, security_layer, **kwargs):
        super().__init__(jid, security_layer, **kwargs)
        self._presence_server = self.summon(mod_presence.PresenceServer)
        self._presence_server.on_presence_state_changed.connect(
            self._update_presence
        )
        self.on_stream_established.connect(self._handle_stream_established)

    def _handle_stream_established(self):
        self.on_presence_sent()

    def _update_presence(self):
        if self._presence_server.state.available:
            if not self.running:
                self.start()
        else:
            if self.running:
                self.stop()

    @property
    def presence(self):
        """
        Control or query the current presence state (see
        :class:`~.PresenceState`) of the client. Note that when
        reading, the property only returns the "set" value, not the actual
        value known to the server (and others). This may differ if the
        connection is still being established.

        .. seealso::

           Setting the presence state using :attr:`presence` clears the
           `status` of the presence. To set the status and state at once,
           use :meth:`set_presence`.

        Upon setting this attribute, the :class:`PresenceManagedClient` will do
        whatever necessary to achieve the given presence. If the presence is
        an `available` presence, the client will attempt to connect to the
        server. If the presence is `unavailable` and the client is currently
        connected, it will disconnect.

        Instead of setting the presence to unavailable, :meth:`stop` can also
        be called. The :attr:`presence` attribute is *not* affected by calls to
        :meth:`start` or :meth:`stop`.
        """
        return self._presence_server.state

    @presence.setter
    def presence(self, value):
        call_update = value == self.presence
        self._presence_server.set_presence(value)
        if call_update:
            self._update_presence()

    def set_presence(self, state, status):
        """
        Set the presence `state` and `status` on the client. This has the same
        effects as writing `state` to :attr:`presence`, but the status of the
        presence is also set at the same time.

        `status` must be either a string or something which can be passed to
        :class:`dict`. If it is a string, the string is wrapped in a ``{None:
        status}`` dictionary. Otherwise, the dictionary is set as the
        :attr:`~.Presence.status` attribute of the presence stanza. It
        must map :class:`aioxmpp.structs.LanguageTag` instances to strings.

        The `status` is the text shown alongside the `state` (indicating
        availability such as *away*, *do not disturb* and *free to chat*).
        """
        self._presence_server.set_presence(state, status=status)

    def connected(self, **kwargs):
        """
        Return a :class:`.node.UseConnected` context manager which sets the
        presence to available.

        The keyword arguments are passed to the :class:`.node.UseConnected`
        context manager constructor.

        .. note::

           In contrast to the same method on :class:`Client`, this method
           implies setting an available presence.

        .. versionadded:: 0.6
        """
        return UseConnected(self, **kwargs)


class UseConnected:
    """
    Asynchronous context manager which connects and disconnects a
    :class:`.Client`.

    :param client: The client to manage
    :type client: :class:`.Client`
    :param timeout: Limit on the time it may take to start the client
    :type timeout: :class:`datetime.timedelta` or :data:`None`
    :param presence: Presence state to set on the client (deprecated)
    :type presence: :class:`.PresenceState`

    When the asynchronous context is entered (see :pep:`492`), the client is
    connected. This blocks until the client has finished connecting and the
    stream is established. If the client takes longer than `timeout` to
    connect, :class:`TimeoutError` is raised and the client is stopped. The
    context manager returns the :attr:`~.Client.stream` of the client.

    When the context is exited, the client is disconnected and the context
    manager waits for the client to cleanly shut down the stream.

    If the client is already connected when the context is entered, the
    connection is re-used and not shut down when the context is entered, but
    leaving the context still disconnects the client.

    If the `presence` refers to an available presence, the
    :class:`.PresenceServer` is :meth:`~.Client.summon`\\ -ed on the `client`.
    The presence is set using :meth:`~.PresenceServer.set_presence` (clearing
    the :attr:`~.PresenceServer.status` and resetting
    :attr:`~.PresenceServer.priority` to 0) before the client is connected. If
    the client is already connected, the presence is set when the context is
    entered.

    .. deprecated:: 0.8

       The use of the `presence` argument is deprecated. The deprecation will
       happen in two phases:

       1. Until (but not including the release of) 1.0, passing a presence
          state which refers to an available presence will emit
          :class:`DeprecationWarning`. This *includes* the default of the
          argument, so unless an unavailable presence state is passed
          explicitly, all uses of :class:`UseConnected` emit that warning.

       2. Starting with 1.0, passing an available presence will raise
          :class:`ValueError`.

       3. Starting with a to-be-determined release after 1.0, passing the
          `presence` argument at all will raise :class:`TypeError`.

       Users which previously used the `presence` argument should use the
       :class:`.PresenceServer` service on the client and set the presence
       before using the context manager instead.

    .. autoattribute:: presence

       See the description of the `presence` argument.

       .. deprecated:: 0.8

          Using this attribute (for reading or writing) is deprecated and emits
          a deprecation warning.

    .. autoattribute:: timeout

       See the description of the `timeout` argument.

       .. deprecated:: 0.8

          Using this attribute (for reading or writing) is deprecated and emits
          a deprecation warning.
    """

    def __init__(self, client, *,
                 timeout=None,
                 presence=structs.PresenceState(True)):
        super().__init__()
        self._client = client
        self._timeout = timeout
        self._presence = presence
        if presence.available:
            warnings.warn(
                "using an available presence state for UseConnected is"
                " deprecated and will raise ValueError as of 1.0",
                DeprecationWarning,
                stacklevel=1,
            )

    @property
    def timeout(self):
        warnings.warn(
            "the timeout attribute is deprecated and will be removed in 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        warnings.warn(
            "the timeout attribute is deprecated and will be removed in 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        self._timeout = value

    @property
    def presence(self):
        warnings.warn(
            "the presence attribute is deprecated and will be removed in 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        return self._presence

    @presence.setter
    def presence(self, value):
        warnings.warn(
            "the presence attribute is deprecated and will be removed in 1.0",
            DeprecationWarning,
            stacklevel=1,
        )
        self._presence = value

    async def __aenter__(self):
        if self._presence.available:
            svc = self._client.summon(
                mod_presence.PresenceServer
            )
            svc.set_presence(self._presence)

        if self._client.established:
            return self._client.stream

        conn_future = asyncio.Future()

        self._client.on_stream_established.connect(
            conn_future,
            self._client.on_stream_established.AUTO_FUTURE,
        )

        self._client.on_failure.connect(
            conn_future,
            self._client.on_failure.AUTO_FUTURE,
        )

        if not self._client.running:
            self._client.start()

        if self._timeout is not None:
            try:
                await asyncio.wait_for(
                    conn_future,
                    self._timeout.total_seconds(),
                )
            except asyncio.TimeoutError:
                self._client.stop()
                raise TimeoutError()
        else:
            await conn_future

        return self._client.stream

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        if not self._client.running:
            return

        disconn_future = asyncio.Future()

        self._client.on_stopped.connect(
            disconn_future,
            self._client.on_stopped.AUTO_FUTURE,
        )

        self._client.on_failure.connect(
            disconn_future,
            self._client.on_failure.AUTO_FUTURE,
        )

        self._client.stop()

        try:
            await disconn_future
        except Exception:
            # we don’t want to re-raise that; the stream is dead, goal
            # achieved.
            pass
