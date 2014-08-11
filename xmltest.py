import asyncio
import logging

import asyncio_xmpp.node

logging.basicConfig(level=logging.DEBUG)

loop = asyncio.get_event_loop()
loop.set_debug(True)

@asyncio.coroutine
def foo():
    client = asyncio_xmpp.node.Client(
        loop,
        "test@hub.sotecware.net/foo"
    )
    yield from client.connect()
    while True:
        yield from asyncio.sleep(10)


loop.run_until_complete(foo())
