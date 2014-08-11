"""
XMPP client basement
####################
"""
import asyncio
import random
import ssl

from . import network, jid, protocol, stream_plugin, ssl_wrapper

def default_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    return ctx

class Client:
    def __init__(self, loop, client_jid):
        super().__init__()
        self._loop = loop
        self._client_jid = jid.JID.fromstr(client_jid)
        self._stream_plugins = [
            stream_plugin.STARTTLS(default_ssl_context),
            stream_plugin.SASL()
        ]

    def _xmlstream_factory(self):
        proto = protocol.XMLStream(
            to=self._client_jid.domainpart)
        proto.add_stream_level_node_callback(
            "{http://etherx.jabber.org/streams}features",
            lambda *args: asyncio.async(self._stream_features(*args))
        )
        return ssl_wrapper.STARTTLSableTransportProtocol(self._loop, proto)

    # stream event handlers

    @asyncio.coroutine
    def _stream_features(self, proto, node):
        for plugin in self._stream_plugins:
            plugin_node = node.find(plugin.feature)
            if plugin_node is None:
                continue
            abort = yield from plugin.start(proto, plugin_node)
            if abort:
                # stream is being reset
                return True
        # negotiation done
        return False

    @asyncio.coroutine
    def connect(self, override_addr=None):
        if override_addr:
            record_iterable = [ovrride_addr]
        else:
            host = self._client_jid.domainpart
            srv_records = yield from network.find_xmpp_host_addr(self._loop, host)
            record_iterable = network.group_and_order_srv_records(srv_records)

        for host, port in record_iterable:
            print(repr(host), repr(port))
            try:
                self._proto = yield from self._loop.create_connection(
                    self._xmlstream_factory,
                    host=host,
                    port=port)
                break
            except OSError as err:
                logger.warn(err)
        else:
            raise OSError("Failed to connect to {}".format(
                self._client_jid.domainpart))
