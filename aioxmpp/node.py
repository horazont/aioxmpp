"""
:mod:`~aioxmpp.node` --- XMPP network nodes (clients, mostly)
#############################################################

This module contains functions to connect to an XMPP server, as well as
maintaining the stream. In addition, a client class which completely manages a
stream based on a presence setting is provided.

Using XMPP
==========

.. autoclass:: AbstractClient

.. autoclass:: PresenceManagedClient

Connecting streams low-level
============================

.. autofunction:: connect_secured_xmlstream

.. autofunction:: connect_to_xmpp_server

"""
import asyncio
import contextlib
import logging

from datetime import timedelta

import dns.resolver

import aiosasl

from . import (
    network,
    ssl_transport,
    protocol,
    errors,
    stream,
    callbacks,
    nonza,
    rfc3921,
    rfc6120,
    stanza,
    structs,
)
from .utils import namespaces


def lookup_addresses(loop, jid):
    addresses = yield from network.find_xmpp_host_addr(
        loop,
        jid.domain)

    return network.group_and_order_srv_records(addresses)


@asyncio.coroutine
def connect_to_xmpp_server(jid, *, override_peer=None, loop=None):
    """
    Connect to an XMPP server which serves the domain of the given `jid`.

    `override_peer` may be a tuple of host name (or IP address) and port. If
    given, this will be the first peer the stream tries to connect to. Only if
    that connection fails the usual XMPP server lookup routine takes place.

    `loop` must be either a valid :class:`asyncio.BaseEventLoop` or
    :data:`None`, in which case the current event loop is used.

    Return a triple consisting of the `transport`, the
    :class:`~aioxmpp.protocol.XMLStream` instance and a :class:`asyncio.Future`
    on the first :class:`~aioxmpp.nonza.StreamFeatures` node.

    If the connection fails :class:`OSError` is raised. That OSError may in
    fact be a :class:`~aioxmpp.errors.MultiOSError`, which gives more
    information on the different errors which occured.

    If the domain does not support XMPP at all (by indicating that fact in the
    SRV records), :class:`ValueError` is raised.
    """
    loop = loop or asyncio.get_event_loop()

    features_future = asyncio.Future()

    xmlstream = protocol.XMLStream(
        to=jid.domain,
        features_future=features_future)

    exceptions = []

    if override_peer is not None:
        host, port = override_peer
        try:
            transport, _ = yield from ssl_transport.create_starttls_connection(
                loop,
                lambda: xmlstream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=jid.domain,
                use_starttls=True)
        except OSError as exc:
            exceptions.append(exc)
        else:
            return transport, xmlstream, features_future

    for host, port in (yield from lookup_addresses(loop, jid)):
        try:
            transport, _ = yield from ssl_transport.create_starttls_connection(
                loop,
                lambda: xmlstream,
                host=host,
                port=port,
                peer_hostname=host,
                server_hostname=jid.domain,
                use_starttls=True)
        except OSError as exc:
            exceptions.append(exc)
        else:
            break
    else:
        if not exceptions:
            # domain does not support XMPP (no options at all to connect to it)
            raise OSError(
                "no options to connect to {}".format(jid.domain)
            )

        if len(exceptions) == 1:
            raise exceptions[0]

        raise errors.MultiOSError(
            "failed to connect to server for {}".format(jid),
            exceptions)

    return transport, xmlstream, features_future


@asyncio.coroutine
def connect_secured_xmlstream(jid, security_layer,
                              negotiation_timeout=1.0,
                              override_peer=None,
                              loop=None):
    """
    Connect to an XMPP server which serves the domain of the given `jid` and
    apply the given `security_layer` (see
    :func:`~aioxmpp.security_layer.security_layer`).

    `loop` must be either a valid :class:`asyncio.BaseEventLoop` or
    :data:`None`, in which case the current event loop is used.

    The `negotiation_timeout` is passed to the security layer and used for
    connect timeouts.

    `override_peer` is passed to :func:`connect_to_xmpp_server`.

    Return a triple consisting of the `transport`, the
    :class:`~aioxmpp.protocol.XMLStream` and the current
    :class:`~aioxmpp.nonza.StreamFeatures` node. The `transport` returned
    in the triple is the one returned by the security layer and is :data:`None`
    if no starttls has been negotiated. To gain access to the transport used if
    the transport returned is :data:`None`, use the
    :attr:`~aioxmpp.protocol.XMLStream.transport` of the XML stream.

    If the connection fails :class:`OSError` is raised. That OSError may in
    fact be a :class:`~aioxmpp.errors.MultiOSError`, which gives more
    information on the different errors which occured.

    If the domain does not support XMPP at all (by indicating that fact in the
    SRV records), :class:`ValueError` is raised.

    If SASL or TLS negotiation fails, the corresponding exception type from
    :mod:`aioxmpp.errors` is raised. Most notably, authentication failures
    caused by invalid credentials or a user abort are raised as
    :class:`~aioxmpp.errors.AuthenticationFailure`.
    """

    try:
        transport, xmlstream, features_future = yield from asyncio.wait_for(
            connect_to_xmpp_server(jid,
                                   override_peer=override_peer,
                                   loop=loop),
            timeout=negotiation_timeout,
            loop=loop
        )
    except asyncio.TimeoutError:
        raise TimeoutError("connection to {} timed out".format(jid))

    features = yield from features_future

    try:
        new_transport, features = yield from security_layer(
            negotiation_timeout,
            jid,
            features,
            xmlstream)
    except errors.SASLUnavailable as exc:
        protocol.send_stream_error_and_close(
            xmlstream,
            condition=(namespaces.streams, "policy-violation"),
            text=str(exc)
        )
        raise
    except errors.TLSUnavailable as exc:
        protocol.send_stream_error_and_close(
            xmlstream,
            condition=(namespaces.streams, "policy-violation"),
            text=str(exc)
        )
        raise
    except aiosasl.SASLError as exc:
        protocol.send_stream_error_and_close(
            xmlstream,
            condition=(namespaces.streams, "undefined-condition"),
            text=str(exc)
        )
        raise

    return new_transport, xmlstream, features


class AbstractClient:
    """
    The :class:`AbstractClient` is a base class for implementing XMPP client
    classes. These classes deal with managing the
    :class:`~aioxmpp.stream.StanzaStream` and the underlying
    :class:`~aioxmpp.protocol.XMLStream` instances. The abstract client
    provides functionality for connecting the xmlstream as well as signals
    which indicate changes in the stream state.

    The `jid` must be a :class:`~aioxmpp.structs.JID` for which to connect. The
    `security_layer` is best created using the
    :func:`~aioxmpp.security_layer.security_layer` function and must provide
    authentication for the given `jid`.

    The `negotiation_timeout` argument controls the :attr:`negotiation_timeout`
    attribute.

    If `loop` is given, it must be a :class:`asyncio.BaseEventLoop`
    instance. If it is not given, the current event loop is used.

    As a glue between the stanza stream and the XML stream, it also knows about
    stream management and performs stream management negotiation. It is
    specialized on client operations, which implies that it will try to keep
    the stream alive as long as wished by the client.

    In general, there are no fatal errors (aside from stream negotiation
    problems) which stop a :class:`AbstractClient` from working. It makes use
    of stream management as far as possible and abstracts away the gritty low
    level details. In general, it is sufficient to observe the
    :attr:`on_stream_established` and :attr:`on_stream_destroyed` events, which
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
       :func:`connect_secured_xmlstream`.

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
       are the same as for :attr:`.StanzaStream.on_stream_destroyed`.

       This event can be used to know when to discard all state about the XMPP
       connection, such as roster information.

    Services:

    .. automethod:: summon

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
                 loop=None):
        super().__init__()
        self._local_jid = local_jid
        self._loop = loop or asyncio.get_event_loop()
        self._main_task = None
        self._security_layer = security_layer

        self._failure_future = asyncio.Future()
        self._logger = logging.getLogger("aioxmpp.AbstractClient")

        self._backoff_time = None

        self._established = False

        self._services = {}

        self.stream_features = None

        self.negotiation_timeout = negotiation_timeout
        self.backoff_start = timedelta(seconds=1)
        self.backoff_factor = 1.2
        self.backoff_cap = timedelta(seconds=60)

        self.on_stopped.logger = self._logger.getChild("on_stopped")
        self.on_failure.logger = self._logger.getChild("on_failure")
        self.on_stream_established.logger = \
            self._logger.getChild("on_stream_established")
        self.on_stream_destroyed.logger = \
            self._logger.getChild("on_stream_destroyed")

        self.stream = stream.StanzaStream(local_jid.bare())

    def _stream_failure(self, exc):
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
            self._logger.error("resource binding failed: %r", err)
            self._main_task.cancel()
            self.on_failure(err)

    def _on_main_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # task terminated normally
            self.on_stopped()
        except Exception as err:
            self._logger.exception("main failed")
            self.on_failure(err)

    @asyncio.coroutine
    def _try_resume_stream_management(self, xmlstream, features):
        try:
            yield from self.stream.resume_sm(xmlstream)
        except errors.StreamNegotiationFailure:
            return False
        return True

    @asyncio.coroutine
    def _negotiate_legacy_session(self):
        self._logger.debug(
            "remote server announces support for legacy sessions"
        )
        yield from self.stream.send_iq_and_wait_for_reply(
            stanza.IQ(type_="set",
                      payload=rfc3921.Session())
        )
        self._logger.debug(
            "legacy session negotiated (upgrade your server!)"
        )

    @asyncio.coroutine
    def _negotiate_stream(self, xmlstream, features):
        server_can_do_sm = True
        try:
            features[nonza.StreamManagementFeature]
        except KeyError:
            if self.stream.sm_enabled:
                self._logger.warn("server isn’t advertising SM anymore")
                self.stream.stop_sm()
            server_can_do_sm = False

        self._logger.debug("negotiating stream (server_can_do_sm=%s)",
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
            self._logger.debug("binding to resource")
            yield from self._bind()

        if server_can_do_sm:
            self._logger.debug("attempting to start stream management")
            try:
                yield from self.stream.start_sm()
            except errors.StreamNegotiationFailure:
                self._logger.debug("stream management failed to start")
            self._logger.debug("stream management started")

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
        iq = stanza.IQ(type_="set")
        iq.payload = rfc6120.Bind(resource=self._local_jid.resource)
        try:
            result = yield from self.stream.send_iq_and_wait_for_reply(iq)
        except errors.XMPPError as exc:
            raise errors.StreamNegotiationFailure(
                "Resource binding failed: {}".format(exc)
            )

        self._local_jid = result.jid
        self._logger.info("bound to jid: %s", self._local_jid)

    @asyncio.coroutine
    def _main_impl(self):
        failure_future = self._failure_future

        override_peer = None
        if self.stream.sm_enabled:
            override_peer = self.stream.sm_location
            if override_peer:
                override_peer = str(override_peer[0]), override_peer[1]

        tls_transport, xmlstream, features = \
            yield from connect_secured_xmlstream(
                self._local_jid,
                self._security_layer,
                negotiation_timeout=self.negotiation_timeout.total_seconds(),
                override_peer=override_peer,
                loop=self._loop)

        try:
            features, sm_resumed = yield from self._negotiate_stream(
                xmlstream,
                features)

            self._backoff_time = None

            exc = yield from failure_future
            self._logger.error("stream failed: %s", exc)
            raise exc
        except asyncio.CancelledError:
            self._logger.info("client shutting down")
            # cancelled, this means a clean shutdown is requested
            yield from self.stream.close()
            raise
        finally:
            self._logger.info("stopping stream")
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
                        self._logger.debug("conflict!")
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

        self._main_task.cancel()

    # services

    def _summon(self, class_):
        try:
            return self._services[class_]
        except KeyError:
            instance = class_(self)
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
        The :class:`~aioxmpp.structs.JID` the client currently has. While the
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
    :class:`AbstractClient` constructor.

    While the start/stop interfaces of :class:`AbstractClient` are still
    available, it is recommended to control the presence managed client solely
    using the :attr:`presence` property.

    The initial presence is set to `unavailable`, thus, the client will not
    connect immediately.

    .. autoattribute:: presence

    .. automethod:: set_presence

    Signals:

    .. attribute:: on_presence_sent

       The event is fired after :attr:`~AbstractClient.on_stream_established`
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
        pres.autoset_id()
        self.stream.enqueue_stanza(pres)

    def _handle_stream_established(self):
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
        :class:`~.structs.PresenceState`) of the client. Note that when
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

        `status` must be either a string or an iterable containing
        :class:`.stanza.Status` objects. The :class:`.stanza.Status` instances
        are saved and added to the presence stanza when it is time to send it.

        The `status` is the text shown alongside the `state` (indicating
        availability such as *away*, *do not disturb* and *free to chat*).
        """
        if isinstance(status, str):
            status = {None: status}
        else:
            status = dict(status)
        self._presence = state, status
        self._update_presence()
