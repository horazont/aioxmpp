"""
:mod:`~aioxmpp.node` --- XMPP network nodes (clients, mostly)
#############################################################

This module contains functions to connect to an XMPP server, as well as
maintaining the stream. In addition, a client class which completely manages a
stream based on a presence setting is provided.

Connecting streams
==================

.. autofunction:: connect_secured_xmlstream

.. autofunction:: connect_to_xmpp_server

"""

import asyncio

from . import network, ssl_transport, protocol, errors


@asyncio.coroutine
def connect_to_xmpp_server(jid, loop=None):
    """
    Connect to an XMPP server which serves the domain of the given *jid*.

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

    addresses = yield from network.find_xmpp_host_addr(
        loop,
        jid.domain)

    features_future = asyncio.Future()

    xmlstream = protocol.XMLStream(
        to=jid.domain,
        features_future=features_future)

    exceptions = []

    for host, port in network.group_and_order_srv_records(addresses):
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

    Return a triple consisting of the *transport*, the
    :class:`~aioxmpp.protocol.XMLStream` and the current
    :class:`~aioxmpp.stream_xsos.StreamFeatures` node. The *transport* returned
    in the triple is the one returned by the security layer and is :data:`None`
    if no starttls has been negotiated.

    If the connection fails or the domain does not support XMPP,
    :class:`OSError` is raised. That OSError may in fact be a
    :class:`~aioxmpp.errors.MultiOSError`, which gives more information on the
    different errors which occured.

    If SASL or TLS negotiation fails, the corresponding exception type from
    :mod:`aioxmpp.errors` is raised. Most notably, authentication failures
    caused by invalid credentials or a user abort are raised as
    :class:`~aioxmpp.errors.AuthenticationFailure`.
    """

    transport, xmlstream, features_future = yield from connect_to_xmpp_server(
        jid,
        loop=loop)

    features = yield from features_future

    new_transport, features = yield from security_layer(
        negotiation_timeout,
        jid,
        features,
        xmlstream)

    return new_transport, xmlstream, features
