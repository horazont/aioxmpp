import asyncio
import logging

from datetime import timedelta

import asyncio_xmpp.node

logging.basicConfig(level=logging.DEBUG)

loop = asyncio.get_event_loop()
loop.set_debug(True)

@asyncio.coroutine
def foo():
    @asyncio.coroutine
    def password_provider(jid, nattempt):
        return "VE02AJ/fHZp0kyJ/+arNr5TF"

    client = asyncio_xmpp.node.Client(
        "test@hub.sotecware.net/foo",
        password_provider,
        loop=loop,
        # override_addr=("localhost", 12345),
        reconnect_interval_start=timedelta(seconds=1)
    )

    yield from client._worker_task


loop.run_until_complete(foo())
