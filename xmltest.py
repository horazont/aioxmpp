import asyncio
import logging
import ssl
import sys

import asyncio_xmpp.protocol
import asyncio_xmpp.ssl_wrapper
import asyncio_xmpp.stream_plugin

def ssl_context_factory():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    return ctx

logging.basicConfig(level=logging.DEBUG)

loop = asyncio.get_event_loop()
loop.set_debug(True)

protocol = asyncio_xmpp.protocol.XMLStream(
    to="sotecware.net",
    stream_plugins=[
        asyncio_xmpp.stream_plugin.STARTTLS(ssl_context_factory)
    ])
transport = asyncio_xmpp.ssl_wrapper.STARTTLSableTransportProtocol(
    loop, protocol)

loop.run_until_complete(
    loop.create_connection(
        lambda: transport,
        host="xmpp.sotecware.net",
        port=5222))

loop.run_forever()
