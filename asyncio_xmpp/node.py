"""
:mod:`~asyncio_xmpp.node` --- Basement for XMPP peers
#####################################################

.. currentmodule:: asyncio_xmpp.node

.. note::

   Currently, only an implementation for an XMPP client exists.

.. autoclass:: Client(client_jid, security_layer, *, [negotiatgion_timeout], [ping_timeout], [override_addr], [max_reconnect_attempts], [reconnect_interval_start], [use_sm], [loop])

.. rubric:: Footnotes

.. [#xep0199] See also `XEP-0198 --- Stream Management <https://xmpp.org/extensions/xep-0198.html>`_

"""

import abc
import asyncio
import binascii
import contextlib
import functools
import hashlib
import logging
import random
import ssl

from datetime import datetime, timedelta

from . import network, jid, protocol, stream_plugin, ssl_wrapper, sasl, stanza
from . import custom_queue, stream_worker, xml, errors
from .utils import *

from .plugins import rfc6120

logger = logging.getLogger(__name__)

class Client:
    """
    Provide an XMPP client.

    *client_jid* must be a string or a :class:`~.jid.JID` with a valid JID. It
    may be either a bare or a full jid (including a resource part). If a full
    jid is specified, the client will attempt to bind to the given resource. If
    that fails or a bare jid has been specified, the resource suggested by the
    server is used.

    *security_layer* specifies which security features are enabled. To create an
    object suitable for this argument, see
    :mod:`asyncio_xmpp.security_layer` and the functions referenced there.

    *negotiation_timeout*, *max_reconnect_attempts*, *reconnect_interval_start*,
    *use_sm* and *ping_timeout* are initial values for the respective
    attributes.

    *loop* must be an :class:`asyncio.BaseEventLoop` or :data:`None`. In the
    latter case, the current event loop is used.

    .. attribute:: max_reconnect_attempts

       The maximum number of reconnect attempts before the
       :meth:`stay_connected` or :meth:`connect` method exits with an
       error. Note that for :meth:`stay_connected`, the reconnect counter is
       reset whenever a connection was successful (including stream
       negotiation).

    .. autoattribute:: ping_timeout

    .. attribute:: negotiation_timeout

       A :class:`datetime.timedelta` which specifies the timeout to apply for
       each transaction during stream negotiation. This is the maximum time the
       server has to send new stream features after the stream has been reset.

    .. attribute:: reconnect_interval_start

       A :class:`datetime.timedelta` which specifies the initial time to wait
       before reconneting after a connection attempt failed. With each
       connection attempt, the time to wait is doubled, implementing exponential
       back off.

    .. attribute:: use_sm

       A boolean value to indicate whether the use of Stream
       Management [#xep0199]_ is to be used, if available. It is generally
       recommended to have this set to :data:`True`.

    The following three methods are used to manage the state of the connection.

    .. automethod:: stay_connected([override_addr])

    .. automethod:: connect([override_addr])

    .. automethod:: disconnect

    To get notified about connection-related events, the following two methods
    can be used to register and unregister callbacks:

    .. automethod:: register_callback

    .. automethod:: unregister_callback

    For sending and receiving stanzas, there are several helper functions. First
    of all, stanzas need to be constructed to be sent.

    .. note::

       Always use these methods instead of the constructors of the classes in
       :mod:`asyncio_xmpp.stanza`. The advantage is that these methods ensure
       that the correct lxml context is used, allowing consistent access to the
       fancy classes around the XML elements.

    .. automethod:: make_iq(*, [to], [from_], [type_])

    .. automethod:: make_presence(*, [to], [from_], [type_])

    .. automethod:: make_message(*, [to], [from_], [type_])

    To send stanzas, use :meth:`enqueue_stanza`.

    .. automethod:: enqueue_stanza

    To receive IQ requests with specific masks, use:

    .. automethod:: register_iq_request_coro

    .. automethod:: unregister_iq_request_coro

    There is a shorthand function to send an IQ stanza and wait for a reply:

    .. automethod:: send_iq_and_wait

    """

    def __init__(self,
                 client_jid,
                 security_layer,
                 *,
                 negotiation_timeout=timedelta(seconds=15),
                 ping_timeout=timedelta(seconds=30),
                 max_reconnect_attempts=3,
                 reconnect_interval_start=timedelta(seconds=5),
                 use_sm=True,
                 loop=None):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._client_jid = jid.JID.fromstr(client_jid)
        self._security_layer = security_layer

        self._request_disconnect = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._override_addr = None

        self.tx_context = xml.default_tx_context

        self._callbacks = {
            "connecting": set(),
            "connection_made": set(),
            "connection_lost": set(),
            "connection_failed": set(),
        }

        self._iq_request_coros = {}
        self._message_callbacks = {}
        self._presence_callbacks = {}

        self._disconnecting = False

        self.negotiation_timeout = negotiation_timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_interval_start = reconnect_interval_start
        self.use_sm = use_sm

        self._stanza_broker = stream_worker.StanzaBroker(
            self._loop,
            self._disconnect_event,
            ping_timeout,
            self._handle_ping_timeout,
            (self._handle_iq_request,
             self._handle_message,
             self._handle_presence))

    def _fire_callback(self, name, *args):
        logger.debug("firing event %r with arguments %r",
                     name, args)
        for cb in self._callbacks[name]:
            self._loop.call_soon(cb, *args)

    def _service_done_handler(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # this is requested and thus fine
            pass
        except Exception as err:
            logger.exception("Task %s failed", task)
            self._mark_stream_dead()
        else:
            logger.error("Task %s unexpectedly exited")
            self._mark_stream_dead()

    # ################ #
    # Connection setup
    # ################ #

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
                xmlstream = wrapper._protocol
                xmlstream.on_connection_lost = \
                    self._handle_xmlstream_connection_lost
                break
            except OSError as err:
                logger.warning("low-level connection attempt failed: %s", err)
        else:
            logger.warning("out of options to reach server for %s",
                           self._client_jid)
            raise OSError("Failed to connect to {}".format(
                self._client_jid.domainpart))

        return wrapper, xmlstream

    @asyncio.coroutine
    def _connect_once(self):
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

        self._disconnect_event.clear()

        logger.debug("negotiating stream")
        try:
            node = yield from future
            yield from self._negotiate_stream(node)
        except:
            self._disconnect_event.set()
            self._stanza_broker.stop()
            if not self._xmlstream.closed:
                self._xmlstream.close()
            self._ssl_wrapper = None
            self._xmlstream = None
            raise

        self._stanza_broker.start_liveness_handler()

    @asyncio.coroutine
    def _connect(self):
        """
        Try to connect to the XMPP server using at most
        :attr:`max_reconnect_attempts` attempts. Raise :class:`ConnectionError`
        if reconnection fails more often than that, except if disconnect has
        been requested by the user.
        """

        last_error = None
        nattempt = 0
        while (self.max_reconnect_attempts is None or
               self.max_reconnect_attempts > nattempt):
            if nattempt > 0:
                wait_time = (self.reconnect_interval_start.total_seconds() *
                             (2**(nattempt-1)))
                logger.debug("connection attempt number %d failed, sleeping %d"
                             " seconds before the next attempt",
                             nattempt+1,
                             wait_time)
                try:
                    yield from asyncio.wait_for(self._request_disconnect.wait())
                except asyncio.TimeoutError:
                    pass
                else:
                    return False

            self._fire_callback("connecting")
            try:
                yield from self._connect_once()
            except errors.AuthenticationFailure as err:
                self._fire_callback("connection_failed", nattempt, err, True)
                raise
            except OSError as err:
                last_error = err
                logger.exception("connection failed:")
                self._fire_callback("connection_failed", nattempt, err, False)
            else:
                self._fire_callback("connection_made")
                return True

            nattempt += 1

        if self._request_disconnect.is_set():
            return False

        if last_error:
            raise last_error
        raise ConnectionError("Connection terminated")

    def _starttls_check_peer(self, tls_transport):
        pass

    def _xmlstream_factory(self):
        proto = protocol.XMLStream(
            to=self._client_jid.domainpart,
            loop=self._loop,
            tx_context=self.tx_context)
        proto.__features_future = proto.wait_for(
            [
                "{http://etherx.jabber.org/streams}features",
            ],
            timeout=self.negotiation_timeout.total_seconds())
        proto.on_starttls_engaged = self._starttls_check_peer
        return ssl_wrapper.STARTTLSableTransportProtocol(self._loop, proto)

    # ################## #
    # Stream negotiation #
    # ################## #

    @asyncio.coroutine
    def _negotiate_stream(self, features_node):
        """
        Handle stream negotiation, by first establishing the security layer and
        then negotiate the remaining stream features.
        """
        try:
            _, features_node = yield from self._security_layer(
                self.negotiation_timeout.total_seconds(),
                self._client_jid, features_node, self._xmlstream)
        except errors.TLSFailure as err:
            # This means that either TLS has failed to negotiate, or that TLS is
            # not available.
            # both stops us from continuing, let’s put a policy violation on the
            # stream and let it bubble up.
            self._xmlstream.stream_error(
                "policy-violation",
                str(err),
                custom_error="{{{}}}tls-failure".format(namespaces.asyncio_xmpp)
            )
            raise
        except errors.SASLUnavailable as err:
            # special form of SASL error telling us that SASL failed due to
            # mismatch of our and the servers preferences. we let the server
            # know about that and re-raise
            self._xmlstream.stream_error(
                "policy-violation",
                str(err),
                custom_error="{{{}}}sasl-failure".format(
                    namespaces.asyncio_xmpp)
            )
            raise
        except errors.SASLFailure as err:
            # other, generic SASL failure. this can be an issue e.g. with SCRAM,
            # if the server replies with an odd value
            self._xmlstream.stream_error(
                "undefined-condition",
                str(err),
                custom_error="{{{}}}sasl-failure".format(namespaces.asyncio_xmpp)
            )
            raise
        except Exception as err:
            self._xmlstream.stream_error("internal-server-error")
            raise

        self._stanza_broker.start().add_done_callback(
            self._service_done_handler)

        sm_node = features_node.get_feature("{{{}}}sm".format(
            namespaces.stream_management))

        # check for _sm_id, as that’s whats needed for resumption
        if self._stanza_broker.sm_session_id is not None:
            # we are resuming a stream-management session
            success = yield from self._resume_stream_management(sm_node)
            if success:
                return True

        bind_node = features_node.get_feature("{{{}}}bind".format(
            namespaces.bind))
        if bind_node is None:
            raise errors.StreamNegotiationFailure(
                "Server does not support resource binding")

        bind = self.make_iq()
        bind.type_ = "set"
        bind.data = rfc6120.Bind()
        if self._client_jid.resource is not None:
            bind.data.resource = self._client_jid.resource
        reply = yield from self.send_iq_and_wait(
            bind,
            timeout=self.negotiation_timeout.total_seconds())
        self._client_jid = reply.data.jid
        logger.info("bound to JID: %s", self._client_jid)

        if self.use_sm:
            try:
                yield from self._negotiate_stream_management(sm_node)
            except errors.StreamNegotiationFailure as err:
                # this is not neccessarily fatal
                logger.warning(err)

    @asyncio.coroutine
    def _negotiate_stream_management(self, feature_node):
        if feature_node is None:
            logger.info("server is not willing to do sm")
            self._stanza_broker.sm_reset()
            return

        with self._stanza_broker.sm_init() as ctx:
            node = yield from self._xmlstream.send_and_wait_for(
                [
                    self.tx_context.makeelement(
                        "{{{}}}enable".format(namespaces.stream_management),
                        nsmap={None: namespaces.stream_management})
                ],
                [
                    "{{{}}}enabled".format(namespaces.stream_management),
                    "{{{}}}failed".format(namespaces.stream_management)
                ])

            if node.tag.endswith("}failed"):
                logger.error("sm negotiation failed")
                raise errors.StreamNegotiationFailure(
                    "Could not negotiate stream management")

        if node.get("resume", "").lower() in {"true", "1"}:
            ctx.set_session_id(sm_id)

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
                self.tx_context(
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
            raise errors.StreamNegotiationFailure(
                "Stream management counter has invalid value")

        self._stanza_broker.sm_resume(acked_ctr)

        return True

    # ###################### #
    # Connection maintenance #
    # ###################### #

    def _disconnect(self, exc=None):
        self._disconnecting = True
        self._stanza_broker.stop()
        self._xmlstream.close()

    def _handle_xmlstream_connection_lost(self, exc):
        if not self._disconnecting:
            self._stanza_broker.stop()
        self._fire_callback("connection_lost", exc)
        self._disconnect_event.set()

    @asyncio.coroutine
    def _handle_ping_timeout(self):
        logger.warning("ping timeout, disconnecting")
        self._mark_stream_dead()

    def _mark_stream_dead(self):
        self._handle_xmlstream_connection_lost(ConnectionError(
            "Stream died due to internal error or ping timeout")
        )

    # ############### #
    # Stanza handling #
    # ############### #

    @asyncio.coroutine
    def _default_iq_request_handler(self, iq):
        logger.warning("no handler for iq data_tag=%r, type=%r",
                       iq.data.tag if iq.data is not None else None,
                       iq.type_)
        raise errors.XMPPCancelError(
            error_tag="feature-not-implemented",
            text="No handler registered for this request pattern")

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

    def _handle_iq_request(self, iq):
        # handle this, or reply with error
        if iq.data is not None:
            tag = iq.data.tag
        else:
            tag = None

        try:
            coro = self._iq_request_coros[tag, iq.type_]
        except KeyError:
            coro = self._default_iq_request_handler

        self._start_iq_handler_task(iq, coro)

    def _handle_message(self, message):
        from_ = message.from_
        id_ = message.id_
        type_ = message.type_

        keys = [
            (str(from_), type_),
            (str(from_.bare), type_),
            (None, type_),
        ]
        if not self._dispatch_stanza(self._message_callbacks, keys, message):
            logger.warning("unhandled message stanza: %r", message)
            return

    def _handle_presence(self, presence):
        from_ = presence.from_
        id_ = presence.id_
        type_ = presence.type_

        keys = [
            (type_, )
        ]

        if not self._dispatch_stanza(self._presence_callbacks, keys, presence):
            logger.warning("unhandled presence stanza: %r", presence)
            return

    def _iq_handler_task_done(self, iq, task):
        is_error = True
        try:
            try:
                try:
                    response_data = task.result()
                    if not isinstance(response_data, stanza.Error):
                        is_error = False
                except errors.XMPPError as err:
                    # just re-raise to outer handler
                    raise
                except Exception as err:
                    logger.exception("IQ handler task raised non-XMPP"
                                     " exception. returning generic error")
                    raise errors.XMPPError(
                        "internal-server-error",
                        text=type(err).__name__
                    )
            except errors.XMPPError as err:
                response_data = stanza.Error()
                response_data.type_ = err.TYPE
                response_data.condition = err.error_tag
                response_data.text = err.text
                if err.application_defined_condition:
                    response_data.application_defined_condition = \
                        err.application_defined_condition
        except Exception as err:
            logger.exception("While constructing an appropriate error stanza "
                             "for an exception thrown by an IQ handler, the"
                             " following exception occured:")
            response_data = stanza.Error()
            response_data.type_ = "cancel"
            response_data.condition = "internal-server-error"
            response_data.text = "giving up on deeply nested errors"

        response = self.tx_context.make_reply(iq)
        if is_error:
            response.type_ = "error"
        if response_data is not None:
            response.append(response_data)
        self.enqueue_stanza(response)

    def _start_iq_handler_task(self, iq, coro):
        task = asyncio.async(coro(iq))
        task.add_done_callback(functools.partial(
            self._iq_handler_task_done,
            iq
        ))

    # ############### #
    # Stanza services #
    # ############### #

    def enqueue_stanza(self, stanza, **kwargs):
        """
        Enqueue a stanza for sending. For this, it is wrapped into a
        :class:`~.stanza.StanzaToken`. The keyword arguments are forwarded to
        the :class:`~.stanza.StanzaToken` constructor. The token is returned.

        .. note::

           The *_impl*-arguments of the constructor are overriden by the stanza
           broker, and attempting to set them will result in a
           :class:`TypeError`.

        .. seealso::

           See the documentation of
           :meth:`.stream_worker.StanzaBroker.make_stanza_token` and
           :meth:`~.stream_worker.StanzaBroker.enqueue_token` for details.

        """
        token = self._stanza_broker.make_stanza_token(stanza, **kwargs)
        self._stanza_broker.enqueue_token(token)

    def make_iq(self, **kwargs):
        """
        Create and return a new :class:`~.stanza.IQ` stanza. The attributes
        *to*, *from_* and *type_* are initialized with the value of the keyword
        respective argument, if set.
        """
        iq = self.tx_context.make_iq(**kwargs)
        return iq

    def make_presence(self, **kwargs):
        """
        Create and return a new :class:`~.stanza.Presence` stanza. The
        attributes *to*, *from_* and *type_* are initialized with the value of
        the keyword respective argument, if set.
        """
        presence = self.tx_context.make_presence(**kwargs)
        return presence

    def make_message(self, **kwargs):
        """
        Create and return a new :class:`~.stanza.Message` stanza. The attributes
        *to*, *from_* and *type_* are initialized with the value of the keyword
        respective argument, if set.
        """
        message = self.tx_context.make_message(**kwargs)
        return message

    def register_iq_request_coro(self, tag, type_, coro):
        """
        Register a coroutine which is started (asynchronously) whenever an IQ
        stanza with a data element of the given *tag* and the given IQ *type_*
        arrives.

        The coroutine is started with the stanza as the only argument. It must
        return one of the following (or raise):

        * an :class:`~.stanza.Error` element, which is sent as only child in the
          IQ ``"error"`` response.
        * another :class:`lxml.etree._Element`, which is sent as only child in
          the IQ ``"result"`` response.
        * :data:`None`, if an empty ``"result"`` response shall be sent.

        If the function raises an exception which is not an
        :class:`~.errors.XMPPError`, it is converted to a generic error, which
        is returned to the original sender.

        If the function raises a :class:`~.errors.XMPPError`, this is equivalent
        to returning the equivalent :class:`~.stanza.Error` element.

        Only one coroutine may be registered for a tag-type combination at any
        time. Attempting to register multiple coroutines for the same tag-type
        combination will result in a :class:`ValueError`.
        """

        if not isinstance(tag, str) or not tag:
            raise ValueError("Element tags must be non-empty strings")
        if type_ not in {"set", "get"}:
            raise ValueError('Coroutines can only be registered for "set" or '
                             '"get" IQ stanzas (got {!r})'.format(type_))

        try:
            existing = self._iq_request_coros[tag, type_]
        except KeyError:
            self._iq_request_coros[tag, type_] = coro
        else:
            raise ValueError("Another coroutine is already registered for "
                             "IQs with data tag {!r} and type={!r}".format(
                                 tag, type_))

    @asyncio.coroutine
    def _wait_for_reply_future(self, reply_future, timeout):
        disconnect_future = asyncio.async(
            self._request_disconnect.wait(),
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
        return (yield from self._wait_for_reply_future(
            token.response_future,
            timeout))

    @asyncio.coroutine
    def send_iq_and_wait(self, iq, timeout):
        """
        Send an IQ stanza and wait for a reply, for at most *timeout*
        seconds. Return the result stanza, if it arrives in time. Otherwise,
        :class:`TimeoutError` is raised.

        If the connection terminated by the user while waiting for the reply,
        :class:`ConnectionError` is raised.
        """
        future = asyncio.Future()

        token = self._stanza_broker.make_stanza_token(
            iq,
            response_future=future)

        yield from self._send_token_and_wait(token, timeout)

        return future.result()

    def unregister_iq_request_coro(self, tag, type_, coro):
        """
        Remove a coroutine which has previously registered for the given IQ data
        *tag* and IQ stanza *type_*.
        """

        existing = self._iq_request_coros[tag, type_]
        if existing != coro:
            raise ValueError("Coroutine does not match the registered "
                             "coroutine")
        del self._iq_request_coros[tag, type_]


    # other stuff

    @property
    def client_jid(self):
        return self._client_jid

    @asyncio.coroutine
    def connect(self, override_addr=None):
        """
        Try to connect to the XMPP server. At most
        :attr:`max_reconnect_attempts` are made, and authentication failures
        propagating outwards the :attr:`security_layer` are fatal immediately
        (as normally, the security layer takes care of repeating a password
        request if neccessary).

        If *override_addr* is given, it must be a pair of hostname and port
        number to connect to. In that case, DNS lookups are skipped (even for
        reconnects).
        """

        if override_addr:
            self._override_addr = override_addr

        return (yield from self._connect())

    @asyncio.coroutine
    def disconnect(self):
        """
        If connected, start to disconnect and wait until the connection has
        closed down completely.

        Otherwise, set a flag to abort any connection attempts in progress. Note
        that these may still return successfully if the flag is not checked in
        time. These connections are not terminated.
        """
        self._request_disconnect.set()
        if not self._xmlstream:
            return
        self._disconnect()
        yield from self._disconnect_event.wait()

    @property
    def ping_timeout(self):
        """
        A :class:`datetime.timedelta` which describes the interval after which
        the XML stream is considered dead, if no reply arrives from the server
        to a request it must respond to.

        .. seealso::

           This is used and enforced by the respective
           :class:`~.stream_worker.LivenessHandler` implementation in use. See
           the documentation there for more details.

        """
        return self._stanza_broker.ping_timeout

    @ping_timeout.setter
    def ping_timeout(self, value):
        self._stanza_broker.ping_timeout = value

    def register_callback(self, event_name, callback):
        """
        Register the given *callback* for the connection event *event_name*.

        The following events and signatures exist:

        .. function:: connecting()

           This event is called when the connection is about to be
           established. This is followed by either :func:`connection_made` or
           :func:`connection_failed`.

        .. function:: connection_made()

           This event fires when the connection has been fully established and
           stanzas can be sent. Useful to send initial presence.

        .. function:: connection_lost([exc=None])

           Whenever the connection is lost (after it has been established) this
           event is fired. If the connection was lost due to an error, *exc* is
           the exception which caused the connection to fail.

        .. function:: connection_failed(nattempt, exc, [fatal=False])

           If a connection attempt has failed, this event is fired. *nattempt*
           here is the number of the attempt which was made (starting at
           0). *exc* is the exception which caused the connection to fail.

           Depending on the error, *fatal* is either :data:`True` or
           :data:`False`. If it is true, the connection will not be reattempted
           and :meth:`stay_connected` will return.
        """
        self._callbacks[event_name].add(callback)

    @property
    def security_layer(self):
        return self._security_layer

    @asyncio.coroutine
    def stay_connected(self, override_addr=None):
        """
        Connect to the XMPP server and stay connected as long as possible. If
        the connection fails, a reconnect is attempted until the reconnect
        counter reaches :attr:`max_reconnect_attempts`.

        If the connection is closed cleanly, the function returns. If the
        connection fails and the maximum amount of reconnects fails too, a
        :class:`ConnectionError` is raised.

        If stream negotiation fails for any reason, that error is propagated.

        If *override_addr* is given, it must be a pair of hostname and port
        number to connect to. In that case, DNS lookups are skipped (even for
        reconnects).
        """
        self._request_disconnect.clear()

        if override_addr:
            self._override_addr = override_addr

        while True:
            connected = yield from self._connect()
            if not connected:
                # disconnect as requested by user
                return

            yield from self._disconnect_event.wait()

            if request_disconnect_event.is_set():
                return

    def unregister_callback(self, event_name, callback):
        """
        Un-register a *callback* previously registered for the event called
        *event_name*.

        This function never raises.
        """
        try:
            self._callbacks[event_name].discard(callback)
        except KeyError:
            pass
