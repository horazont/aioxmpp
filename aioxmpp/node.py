"""
:mod:`~aioxmpp.node` --- XMPP network nodes (clients, mostly)
#############################################################

This module contains functions to connect to an XMPP server, as well as
maintaining the stream. In addition, a client class which completely manages a
stream based on a presence setting is provided.

Using XMPP
==========

.. autoclass:: PresenceManagedClient

Connecting streams low-level
============================

.. autofunction:: connect_secured_xmlstream

.. autofunction:: connect_to_xmpp_server

Enumerations
============

.. autoclass:: ClientStatus

"""
import asyncio
import itertools
import logging

from enum import Enum
from datetime import timedelta

from . import (
    network,
    ssl_transport,
    protocol,
    errors,
    stream,
    callbacks,
    stream_xsos,
    rfc6120,
    stanza,
)
from .utils import namespaces


def lazy_lookup_addresses(loop, jid):
    addresses = yield from network.find_xmpp_host_addr(
        loop,
        jid.domain)

    yield from network.group_and_order_srv_records(addresses)

@asyncio.coroutine
def connect_to_xmpp_server(jid, *, override_peer=None, loop=None):
    """
    Connect to an XMPP server which serves the domain of the given *jid*.

    *override_peer* may be a tuple of host name (or IP address) and port. If
    given, this will be the first peer the stream tries to connect to. Only if
    that connection fails the usual XMPP server lookup routine takes place.

    *loop* must be either a valid :class:`asyncio.BaseEventLoop` or
    :data:`None`, in which case the current event loop is used.

    Return a triple consisting of the *transport*, the
    :class:`~aioxmpp.protocol.XMLStream` instance and a :class:`asyncio.Future`
    on the first :class:`~aioxmpp.stream_xsos.StreamFeatures` node.

    If the connection fails or the domain does not support XMPP,
    :class:`OSError` is raised. That OSError may in fact be a
    :class:`~aioxmpp.errors.MultiOSError`, which gives more information on the
    different errors which occured.
    """
    loop = loop or asyncio.get_event_loop()


    features_future = asyncio.Future()

    xmlstream = protocol.XMLStream(
        to=jid.domain,
        features_future=features_future)

    exceptions = []

    addresses_iterable = lazy_lookup_addresses(loop, jid)
    if override_peer is not None:
        addresses_iterable = itertools.chain(
            [override_peer],
            addresses_iterable
        )

    for host, port in addresses_iterable:
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
            raise OSError("domain {} does not support XMPP".format(jid.domain))

        if len(exceptions) == 1:
            raise exceptions[0]

        raise errors.MultiOSError(
            "failed to connect to server for {}".format(jid),
            exceptions)

    return transport, xmlstream, features_future


@asyncio.coroutine
def connect_secured_xmlstream(jid, security_layer,
                              negotiation_timeout=1.0,
                              loop=None):
    """
    Connect to an XMPP server which serves the domain of the given *jid* and
    apply the given *security_layer* (see
    :func:`~aioxmpp.security_layer.security_layer`).

    *loop* must be either a valid :class:`asyncio.BaseEventLoop` or
    :data:`None`, in which case the current event loop is used.

    The *negotiation_timeout* is passed to the security layer and used for
    connect timeouts.

    Return a triple consisting of the *transport*, the
    :class:`~aioxmpp.protocol.XMLStream` and the current
    :class:`~aioxmpp.stream_xsos.StreamFeatures` node. The *transport* returned
    in the triple is the one returned by the security layer and is :data:`None`
    if no starttls has been negotiated. To gain access to the transport used if
    the transport returned is :data:`None`, use the
    :attr:`~aioxmpp.protocol.XMLStream.transport` of the XML stream.

    If the connection fails or the domain does not support XMPP,
    :class:`OSError` is raised. That OSError may in fact be a
    :class:`~aioxmpp.errors.MultiOSError`, which gives more information on the
    different errors which occured.

    If SASL or TLS negotiation fails, the corresponding exception type from
    :mod:`aioxmpp.errors` is raised. Most notably, authentication failures
    caused by invalid credentials or a user abort are raised as
    :class:`~aioxmpp.errors.AuthenticationFailure`.
    """

    try:
        transport, xmlstream, features_future = yield from asyncio.wait_for(
            connect_to_xmpp_server(jid, loop=loop),
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
    except errors.SASLFailure as exc:
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

    As a glue between the stanza stream and the XML stream, it also knows about
    stream management and performs stream management negotiation. It is
    specialized on client operations, which implies that it will try to keep
    the stream alive as long as wished by the client.

    .. autoattribute:: local_jid

    .. attribute:: negotiation_timeout = timedelta(seconds=60)

       The timeout applied to the connection process and the individual steps
       of negotiating the stream. See the *negotiation_timeout* argument to
       :func:`connect_secured_xmlstream`.

    .. attribute:: on_failure

       A :class:`~aioxmpp.callbacks.Signal` which is fired when the client
       fails and stops.

    .. autoattribute:: running


    Exponential backoff on failure:

    .. attribute:: backoff_start

       When connecting a stream fails due to connectivity issues (generic
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

    """

    on_failure = callbacks.Signal()

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
        self._sm_id = None
        self._sm_location = None
        self._sm_bound = False

        self.negotiation_timeout = negotiation_timeout
        self.backoff_start = timedelta(seconds=1)
        self.backoff_factor = 1.2
        self.backoff_cap = timedelta(seconds=60)
        self.stream = stream.StanzaStream()

    def _stream_failure(self, exc):
        self._failure_future.set_result(exc)
        self._failure_future = asyncio.Future()

    def _on_main_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # task terminated normally
            pass
        except Exception as err:
            self._logger.exception("main failed")
            self.on_failure(err)

    @asyncio.coroutine
    def _start_stream_management(self, xmlstream, features, ctx):
        ctx.start_sm()
        node = yield from protocol.send_and_wait_for(
            xmlstream,
            [
                stream_xsos.SMEnable(resume=True),
            ],
            [
                stream_xsos.SMEnabled,
                stream_xsos.SMFailure
            ]
        )

        if isinstance(node, stream_xsos.SMFailure):
            # failed
            ctx.stop_sm()
            return

        self._sm_id = node.id_
        if node.resume:
            if node.location:
                self._sm_location = str(node.location[0]), node.location[1]

    @asyncio.coroutine
    def _resume_stream_management(self, xmlstream, features, ctx):
        node = yield from protocol.send_and_wait_for(
            xmlstream,
            [
                stream_xsos.SMResume(previd=self._sm_id,
                                     counter=self.stream.sm_inbound_ctr),
            ],
            [
                stream_xsos.SMResumed,
                stream_xsos.SMFailure
            ]
        )
        if isinstance(node, stream_xsos.SMFailure):
            ctx.stop_sm()
            return False
        ctx.resume_sm(node.counter)
        return True

    @asyncio.coroutine
    def _negotiate_stream_management(self, xmlstream, features, ctx):
        if self.stream.sm_enabled:
            resumed = yield from self._resume_stream_management(
                xmlstream, features, ctx)
            if resumed:
                return True

        yield from self._start_stream_management(
            xmlstream, features, ctx)
        return False

    @asyncio.coroutine
    def _negotiate_stream(self, xmlstream, features, ctx):
        try:
            features[stream_xsos.StreamManagementFeature]
        except KeyError:
            if self.stream.sm_enabled:
                self._logger.warn("server isn’t advertising SM anymore")
                ctx.stop_sm()
            resumed = False
        else:
            resumed = yield from self._negotiate_stream_management(
                xmlstream, features, ctx)

        return features, resumed

    @asyncio.coroutine
    def _bind(self, xmlstream, features, failure_future):
        try:
            features[rfc6120.BindFeature]
        except KeyError:
            raise errors.StreamNegotiationFailure(
                "undefined-condition",
                text="Server does not support resource binding"
            )

        iq = stanza.IQ(type_="set")
        iq.payload = rfc6120.Bind(resource=self._local_jid.resource)
        done, pending = yield from asyncio.wait(
            [
                self.stream.send_iq_and_wait_for_reply(iq),
                failure_future
            ],
            timeout=self.negotiation_timeout.total_seconds(),
            return_when=asyncio.FIRST_EXCEPTION,
        )
        if failure_future in done:
            failure_future.result()
        if not done:
            # timeout! raise a TimeoutError...
            raise TimeoutError()

        self._sm_bound = True

    @asyncio.coroutine
    def _main_impl(self):
        failure_future = self._failure_future
        tls_transport, xmlstream, features = \
            yield from connect_secured_xmlstream(
                self._local_jid,
                self._security_layer,
                negotiation_timeout=self.negotiation_timeout.total_seconds(),
                override_peer=self._sm_location,
                loop=self._loop)

        with self.stream.transactional_start(xmlstream) as ctx:
            features, sm_resumed = yield from self._negotiate_stream(
                xmlstream,
                features,
                ctx)

        try:
            if not sm_resumed or not self._sm_bound:
                yield from self._bind(xmlstream, features, failure_future)

            self._backoff_time = None

            exc = yield from failure_future
            self._logger.error("stream failed: %s", exc)
        finally:
            self.stream.stop()

    @asyncio.coroutine
    def _main(self):
        with self.stream.on_failure.context_connect(self._stream_failure):
            while True:
                self._failure_future = asyncio.Future()
                try:
                    yield from self._main_impl()
                except errors.StreamNegotiationFailure as exc:
                    raise
                except OSError as exc:
                    if self._backoff_time is None:
                        self._backoff_time = self.backoff_start.total_seconds()
                    yield from asyncio.sleep(self._backoff_time)
                    self._backoff_time *= self.backoff_factor
                    if self._backoff_time > self.backoff_cap.total_seconds():
                        self._backoff_time = self.backoff_cap.total_seconds()
                    continue  # retry


    def start(self):
        if self.running:
            raise RuntimeError("client already running")

        self._main_task = asyncio.async(
            self._main(),
            loop=self._loop
        )
        self._main_task.add_done_callback(self._on_main_done)

    def stop(self):
        if not self.running:
            return
        self._main_task.cancel()

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
        return self._main_task is not None and not self._main_task.done()


class ClientStatus(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3


class PresenceManagedClient:
    """
    A presence managed XMPP client.

    The *jid* must be a :class:`~aioxmpp.structs.JID` for which to connect. The
    *security_layer* is best created using the
    :func:`~aioxmpp.security_layer.security_layer` function and must provide
    authentication for the given *jid*.

    The basic workflow is to set the presence using the :meth:`set_presence`
    coroutine and send and receive stanzas using :attr:`broker`, which is a
    :class:`~aioxmpp.stream.StanzaBroker` instance.

    When an available presence is set, the client maintains a connection to the
    server. This includes enabling stream management if possible, periodically
    checking the stream liveness and re-connecting the underlying XML stream if
    neccessary.

    In general, there are no fatal errors (aside from security layer
    negotiation problems) which stop a :class:`PresenceManagedClient` from
    working; however, if no stream can be established, the :attr:`status` of
    the client will never turn :attr:`ClientStatus.CONNECTED` and no stanzas
    will be received.

    If authentication fails, the client enters :attr:`ClientStatus.FAILED`
    status and the :attr:`exception` attribute will hold the corresponding
    exception; the corresponding event will also be fired. No reconnection
    attempts will be made.

    There are events which allow a user to be notified about connectivity
    changes.

    Note that when stream management is enabled, the client is shown as
    :attr:`ClientStatus.CONNECTED` even if no underlying XML stream is
    currently available; this is consistent with the model of Stream Management
    which tries to cover disconnects as good as possible. On a reconnect, it is
    assumed that a retransmission of anything the client would want to re-fetch
    on a reconnect will occur anyways.

    If during a reconnect an SM session is terminated (because resumption
    fails), a proper disconnect and connect event sequence is fired to allow
    users to synchronize their state accordingly.
    """
