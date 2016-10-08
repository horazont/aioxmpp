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
# General Public License for more details.
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

.. autoclass:: PresenceManagedClient

.. currentmodule:: aioxmpp.node

.. autoclass:: AbstractClient

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

from datetime import timedelta

import dns.resolver

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
)
from .utils import namespaces


logger = logging.getLogger(__name__)


def lookup_addresses(loop, jid):
    addresses = yield from network.find_xmpp_host_addr(
        loop,
        jid.domain)

    return network.group_and_order_srv_records(addresses)


@asyncio.coroutine
def discover_connectors(domain, loop=None, logger=logger):
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

    try:
        starttls_srv_records = yield from network.lookup_srv(
            domain,
            "xmpp-client",
        )
        starttls_srv_disabled = False
    except ValueError:
        starttls_srv_records = []
        starttls_srv_disabled = True

    try:
        tls_srv_records = yield from network.lookup_srv(
            domain,
            "xmpps-client",
        )
        tls_srv_disabled = False
    except ValueError:
        tls_srv_records = []
        tls_srv_disabled = True

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
        (prio, weight, (host, port, connector.STARTTLSConnector()))
        for prio, weight, (host, port) in starttls_srv_records
    ]

    srv_records.extend(
        (prio, weight, (host, port, connector.XMPPOverTLSConnector()))
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


@asyncio.coroutine
def _try_options(options, exceptions,
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
            transport, xmlstream, features = yield from conn.connect(
                loop,
                metadata,
                jid.domain,
                host,
                port,
                negotiation_timeout,
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

        try:
            features = yield from security_layer.negotiate_sasl(
                transport,
                xmlstream,
                metadata.sasl_providers,
                negotiation_timeout,
                jid,
                features,
            )
        except errors.SASLUnavailable as exc:
            protocol.send_stream_error_and_close(
                xmlstream,
                condition=(namespaces.streams, "policy-violation"),
                text=str(exc),
            )
            exceptions.append(exc)
            continue
        except Exception as exc:
            protocol.send_stream_error_and_close(
                xmlstream,
                condition=(namespaces.streams, "undefined-condition"),
                text=str(exc),
            )
            raise

        return transport, xmlstream, features

    return None


@asyncio.coroutine
def connect_xmlstream(
        jid,
        metadata,
        negotiation_timeout=60.,
        override_peer=[],
        loop=None,
        logger=logger):
    """
    Prepare and connect a :class:`aioxmpp.protocol.XMLStream` to a server
    responsible for the given `jid` and authenticate against that server using
    the SASL mechansims described in `metadata`.

    The part of the `metadata` (which must be a
    :class:`.security_layer.SecurityLayer` object) specifying the use of TLS is
    applied. If the security layer does not mandate TLS, the resulting XML
    stream may not be using TLS. TLS is used whenever possible.

    `override_peer` may be a list of triples consisting of ``(host, port,
    connector)``, where `connector` is a
    :class:`aioxmpp.connector.BaseConnector` instance. The options in the list
    are tried first (in the order given), and only if all of them fail,
    automatic discovery of connection options is performed.

    `loop` may be a :class:`asyncio.BaseEventLoop` to use. Defaults to the
    current event loop.

    If `domain` announces that XMPP is not supported at all,
    :class:`ValueError` is raised. If no options are returned from
    :func:`discover_connectors` and `override_peer` is empty,
    :class:`ValueError` is raised, too.

    If all connection attempts fail, :class:`aioxmpp.errors.MultiOSError` is
    raised. The error contains one exception for each of the options discovered
    as well as the elements from `override_peer` in the order they were tried.

    .. note::

       Even though it is a :class:`aioxmpp.errors.MultiOSError`, it may also
       contain instances of :class:`aioxmpp.errors.TLSUnavailable` or
       :class:`aioxmpp.errors.TLSFailed`.

    A TLS problem is treated like any other connection problem and the other
    connection options are considered.

    Return a triple ``(transport, xmlstream, features)``. `transport`
    the underlying :class:`asyncio.Transport` which is used for the `xmlstream`
    :class:`~.protocol.XMLStream` instance. `features` is the
    :class:`aioxmpp.nonza.StreamFeatures` instance describing the features of
    the stream.

    .. versionadded:: 0.6
    """
    loop = asyncio.get_event_loop() if loop is None else loop

    domain = jid.domain.encode("idna")

    options = list(override_peer)

    exceptions = []

    result = yield from _try_options(
        options,
        exceptions,
        jid, metadata, negotiation_timeout, loop, logger,
    )
    if result is not None:
        return result

    options = list((yield from discover_connectors(
        domain,
        loop=loop,
        logger=logger,
    )))

    result = yield from _try_options(
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

    raise errors.MultiOSError(
        "failed to connect to XMPP domain {!r}".format(jid.domain),
        exceptions
    )


class AbstractClient:
    """
    The :class:`AbstractClient` is a base class for implementing XMPP client
    classes. These classes deal with managing the
    :class:`~aioxmpp.stream.StanzaStream` and the underlying
    :class:`~aioxmpp.protocol.XMLStream` instances. The abstract client
    provides functionality for connecting the xmlstream as well as signals
    which indicate changes in the stream state.

    The `jid` must be a :class:`~aioxmpp.JID` for which to connect. The
    `security_layer` is best created using the
    :func:`~aioxmpp.security_layer.security_layer` function and must provide
    authentication for the given `jid`.

    The `negotiation_timeout` argument controls the :attr:`negotiation_timeout`
    attribute.

    If `loop` is given, it must be a :class:`asyncio.BaseEventLoop`
    instance. If it is not given, the current event loop is used.

    `override_peer` is used to initialise the :attr:`override_peer` attribute.

    As a glue between the stanza stream and the XML stream, it also knows about
    stream management and performs stream management negotiation. It is
    specialized on client operations, which implies that it will try to keep
    the stream alive as long as wished by the client.

    In general, there are no fatal errors (aside from stream negotiation
    problems) which stop a :class:`AbstractClient` from working. It makes use
    of stream management as far as possible and abstracts away the gritty low
    level details. In general, it is sufficient to observe the
    :meth:`on_stream_established` and :attr:`on_stream_destroyed` events, which
    notify a user about when a stream becomes available and when it becomes
    unavailable.

    If authentication fails (or another stream negotiation error occurs), the
    client fails and :attr:`on_failure` is fired. :attr:`running` becomes false
    and the client needs to be re-started manually by calling :meth:`start`.

    .. versionchanged:: 0.4

       Since 0.4, support for legacy XMPP sessions has been implemented. Mainly
       for compatiblity with ejabberd.

    Controlling the client:

    .. automethod:: start

    .. automethod:: stop

    .. autoattribute:: running

    .. attribute:: negotiation_timeout = timedelta(seconds=60)

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

    Connection information:

    .. autoattribute:: established

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

    Exponential backoff on interruptions:

    .. attribute:: backoff_start

       When an underlying XML stream fails due to connectivity issues (generic
       :class:`OSError` raised), exponential backoff takes place before
       attempting to reconnect.

       The initial time to wait before reconnecting is described by
       :attr:`backoff_start`.

    .. attribute:: backoff_factor

       Each subsequent time a connection fails, the previous backoff time is
       multiplied with :attr:`backoff_factor`.

    .. attribute:: backoff_cap

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

    .. signal:: on_stream_destroyed()

       This is called whenever a stream is destroyed. The conditions for this
       are the same as for
       :attr:`aioxmpp.stream.StanzaStream.on_stream_destroyed`.

       This event can be used to know when to discard all state about the XMPP
       connection, such as roster information.

    Services:

    .. automethod:: summon

    Miscellaneous:

    .. attribute:: logger

       The :class:`logging.Logger` instance which is used by the
       :class:`AbstractClient`. This is the `logger` passed to the constructor
       or a logger derived from the fully qualified name of the class.

       .. versionadded:: 0.6

          The :attr:`logger` attribute was added.

    """

    on_failure = callbacks.Signal()
    on_stopped = callbacks.Signal()
    on_stream_destroyed = callbacks.Signal()
    on_stream_established = callbacks.Signal()

    before_stream_established = callbacks.SyncSignal()

    def __init__(self,
                 local_jid,
                 security_layer,
                 negotiation_timeout=timedelta(seconds=60),
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

        self._established = False

        self._services = {}

        self.stream_features = None

        self.negotiation_timeout = negotiation_timeout
        self.backoff_start = timedelta(seconds=1)
        self.backoff_factor = 1.2
        self.backoff_cap = timedelta(seconds=60)
        self.override_peer = list(override_peer)

        self.on_stopped.logger = self.logger.getChild("on_stopped")
        self.on_failure.logger = self.logger.getChild("on_failure")
        self.on_stream_established.logger = \
            self.logger.getChild("on_stream_established")
        self.on_stream_destroyed.logger = \
            self.logger.getChild("on_stream_destroyed")

        self.stream = stream.StanzaStream(local_jid.bare())

    def _stream_failure(self, exc):
        if self._failure_future.done():
            self.logger.warning(
                "something is odd: failure future is already done ..."
            )
            return

        self._failure_future.set_result(exc)
        self._failure_future = asyncio.Future()

    def _stream_destroyed(self):
        if self._established:
            self._established = False
            self.on_stream_destroyed()

    def _on_bind_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as err:
            self.logger.error("resource binding failed: %r", err)
            self._main_task.cancel()
            self.on_failure(err)

    def _on_main_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # task terminated normally
            self.on_stopped()
        except Exception as err:
            self.logger.exception("main failed")
            self.on_failure(err)

    @asyncio.coroutine
    def _try_resume_stream_management(self, xmlstream, features):
        try:
            yield from self.stream.resume_sm(xmlstream)
        except errors.StreamNegotiationFailure as exc:
            self.logger.warn("failed to resume stream (%s)",
                             exc)
            return False
        return True

    @asyncio.coroutine
    def _negotiate_legacy_session(self):
        self.logger.debug(
            "remote server announces support for legacy sessions"
        )
        yield from self.stream.send_iq_and_wait_for_reply(
            stanza.IQ(type_=structs.IQType.SET,
                      payload=rfc3921.Session())
        )
        self.logger.debug(
            "legacy session negotiated (upgrade your server!)"
        )

    @asyncio.coroutine
    def _negotiate_stream(self, xmlstream, features):
        server_can_do_sm = True
        try:
            features[nonza.StreamManagementFeature]
        except KeyError:
            if self.stream.sm_enabled:
                self.logger.warn("server isn’t advertising SM anymore")
                self.stream.stop_sm()
            server_can_do_sm = False

        self.logger.debug("negotiating stream (server_can_do_sm=%s)",
                          server_can_do_sm)

        if self.stream.sm_enabled:
            resumed = yield from self._try_resume_stream_management(
                xmlstream, features)
            if resumed:
                return features, resumed
        else:
            resumed = False

        self.stream_features = features
        self.stream.start(xmlstream)

        if not resumed:
            self.logger.debug("binding to resource")
            yield from self._bind()

        if server_can_do_sm:
            self.logger.debug("attempting to start stream management")
            try:
                yield from self.stream.start_sm()
            except errors.StreamNegotiationFailure:
                self.logger.debug("stream management failed to start")
            self.logger.debug("stream management started")

        try:
            features[rfc3921.SessionFeature]
        except KeyError:
            pass  # yay
        else:
            yield from self._negotiate_legacy_session()

        self._established = True

        yield from self.before_stream_established()

        self.on_stream_established()

        return features, resumed

    @asyncio.coroutine
    def _bind(self):
        iq = stanza.IQ(type_=structs.IQType.SET)
        iq.payload = rfc6120.Bind(resource=self._local_jid.resource)
        try:
            result = yield from self.stream.send_iq_and_wait_for_reply(iq)
        except errors.XMPPError as exc:
            raise errors.StreamNegotiationFailure(
                "Resource binding failed: {}".format(exc)
            )

        self._local_jid = result.jid
        self.logger.info("bound to jid: %s", self._local_jid)

    @asyncio.coroutine
    def _main_impl(self):
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

        tls_transport, xmlstream, features = \
            yield from connect_xmlstream(
                self._local_jid,
                self._security_layer,
                negotiation_timeout=self.negotiation_timeout.total_seconds(),
                override_peer=override_peer,
                loop=self._loop,
                logger=self.logger)

        try:
            features, sm_resumed = yield from self._negotiate_stream(
                xmlstream,
                features)

            self._backoff_time = None

            exc = yield from failure_future
            self.logger.error("stream failed: %s", exc)
            raise exc
        except asyncio.CancelledError:
            self.logger.info("client shutting down (on request)")
            # cancelled, this means a clean shutdown is requested
            yield from self.stream.close()
            raise
        finally:
            self.logger.info("stopping stream")
            self.stream.stop()

    @asyncio.coroutine
    def _main(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                self.stream.on_failure.context_connect(self._stream_failure)
            )
            stack.enter_context(
                self.stream.on_stream_destroyed.context_connect(
                    self._stream_destroyed)
            )
            while True:
                self._failure_future = asyncio.Future()
                try:
                    yield from self._main_impl()
                except errors.StreamError as err:
                    if err.condition == (namespaces.streams, "conflict"):
                        self.logger.debug("conflict!")
                        raise
                except (errors.StreamNegotiationFailure,
                        aiosasl.SASLError):
                    if self.stream.sm_enabled:
                        self.stream.stop_sm()
                    raise
                except (OSError, dns.resolver.NoNameservers):
                    if self._backoff_time is None:
                        self._backoff_time = self.backoff_start.total_seconds()
                    yield from asyncio.sleep(self._backoff_time)
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

        self._main_task = asyncio.async(
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

    # services

    def _summon(self, class_):
        try:
            return self._services[class_]
        except KeyError:
            instance = class_(self, logger_base=self.logger)
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
        requirements = sorted(class_.ORDER_AFTER)
        for req in requirements:
            self._summon(req)
        return self._summon(class_)

    # properties

    @property
    def local_jid(self):
        """
        The :class:`~aioxmpp.JID` the client currently has. While the
        client is disconnected, only the bare JID part is authentic, as the
        resource is ultimately determined by the server.

        Writing this attribute is not allowed, as changing the JID introduces a
        lot of issues with respect to reusability of the stream. Instanciate a
        new :class:`AbstractClient` if you need to change the bare part of the
        JID.

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
        return self._established


class PresenceManagedClient(AbstractClient):
    """
    A presence managed XMPP client. The arguments are passed to the
    :class:`~.AbstractClient` constructor.

    While the start/stop interfaces of :class:`~.AbstractClient` are still
    available, it is recommended to control the presence managed client solely
    using the :attr:`presence` property.

    The initial presence is set to `unavailable`, thus, the client will not
    connect immediately.

    .. autoattribute:: presence

    .. automethod:: set_presence

    .. automethod:: connected

    Signals:

    .. attribute:: on_presence_sent

       The event is fired after :meth:`.AbstractClient.on_stream_established`
       and after the current presence has been sent to the server as *initial
       presence*.

    """

    on_presence_sent = callbacks.Signal()

    def __init__(self, jid, security_layer, **kwargs):
        super().__init__(jid, security_layer, **kwargs)
        self._presence = structs.PresenceState(), []
        self.on_stream_established.connect(self._handle_stream_established)

    def _resend_presence(self):
        pres = stanza.Presence()
        state, status = self._presence
        state.apply_to_stanza(pres)
        pres.status.update(status)
        self.stream.enqueue_stanza(pres)

    def _handle_stream_established(self):
        if self._presence[0].available:
            self._resend_presence()
        self.on_presence_sent()

    def _update_presence(self):
        if self._presence[0].available:
            if not self.running:
                self.start()
            elif self.established:
                self._resend_presence()
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
        whatever neccessary to achieve the given presence. If the presence is
        an `available` presence, the client will attempt to connect to the
        server. If the presence is `unavailable` and the client is currently
        connected, it will disconnect.

        Instead of setting the presence to unavailable, :meth:`stop` can also
        be called. The :attr:`presence` attribute is *not* affected by calls to
        :meth:`start` or :meth:`stop`.
        """
        return self._presence[0]

    @presence.setter
    def presence(self, value):
        self._presence = value, []
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
        if isinstance(status, str):
            status = {None: status}
        else:
            status = dict(status)
        self._presence = state, status
        self._update_presence()

    def connected(self, **kwargs):
        """
        Return an asynchronous context manager (:pep:`492`). When it is
        entered, the presence is changed to available. The context manager
        waits until the stream is established, and then the context is entered.

        Upon leaving the context manager, the presence is changed to
        unavailable. The context manager waits until the stream is closed
        fully.

        The keyword arguments are passed to the :class:`UseConnected` context
        manager constructor.

        .. seealso::

           :class:`UseConnected` is the context manager returned here.

        .. versionadded:: 0.6
        """
        return UseConnected(self, **kwargs)


class UseConnected:
    """
    Control the given :class:`PresenceManagedClient` `client` as asynchronous
    context manager (:pep:`492`). :class:`UseConnected` is an asynchronous
    context manager. When the context manager is entered, the `client` is set
    to an available presence (if the stream is not already established) and the
    context manager waits for a connection to establish. If a fatal error
    occurs while the stream is being established, it is re-raised.

    When the context manager is left, the stream is shut down cleanly and the
    context manager waits for the stream to shut down. Any exceptions occuring
    in the context are not swallowed.

    `timeout` is used to initialise the :attr:`timeout` attribute. `presence`
    is used to initialise the :attr:`presence` attribute and defaults to a
    simple available presence. `presence` must be an *available* presence.

    .. versionadded:: 0.6

    The following attributes control the behaviour of the context manager:

    .. attribute:: timeout

       Either :data:`None` or a :class:`datetime.timedelta` instance. If it is
       the latter and it takes longer than that time to establish the stream,
       the process is aborted and :class:`TimeoutError` is raised.

    .. autoattribute:: presence

    """

    def __init__(self, client, *,
                 timeout=None,
                 presence=structs.PresenceState(True)):
        super().__init__()
        self._client = client
        self.timeout = timeout
        self.presence = presence

    @property
    def presence(self):
        """
        This is the presence which is sent when connecting. This may be an
        unavailable presence.
        """
        return self._presence

    @presence.setter
    def presence(self, value):
        self._presence = value

    @asyncio.coroutine
    def __aenter__(self):
        if self._client.established:
            return self._client.stream

        connected_future = asyncio.Future()

        self._client.presence = self.presence

        if not self._client.running:
            self._client.start()

        self._client.on_presence_sent.connect(
            connected_future,
            self._client.on_presence_sent.AUTO_FUTURE
        )
        self._client.on_failure.connect(
            connected_future,
            self._client.on_failure.AUTO_FUTURE
        )

        if self.timeout is not None:
            try:
                yield from asyncio.wait_for(
                    connected_future,
                    timeout=self.timeout.total_seconds()
                )
            except asyncio.TimeoutError:
                self._client.presence = structs.PresenceState(False)
                self._client.stop()
                raise TimeoutError()
        else:
            yield from connected_future

        return self._client.stream

    @asyncio.coroutine
    def __aexit__(self, exc_type, exc_value, exc_traceback):
        self._client.presence = structs.PresenceState(False)

        if not self._client.established:
            return

        disconnected_future = asyncio.Future()

        self._client.on_stopped.connect(
            disconnected_future,
            self._client.on_stopped.AUTO_FUTURE
        )

        self._client.on_failure.connect(
            disconnected_future,
            self._client.on_failure.AUTO_FUTURE
        )

        try:
            yield from disconnected_future
        except:
            if exc_type is None:
                raise
