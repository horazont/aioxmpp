import asyncio

from . import stanza

class PubSubClient:
    def __init__(self, node, pubsub_service):
        self._node = node
        self._pubsub_service = pubsub_service

    @asyncio.coroutine
    def create_node(self, node_name, timeout):
        iq = self._node.make_iq(type="set", to=self._pubsub_service)
        pubsub = stanza.PubSub()
        iq.data = pubsub

        create = stanza.Create()
        create.node = node_name

        pubsub.append(create)

        future = asyncio.Future()

        self._node.enqueue_stanza(
            iq,
            response_future=future)

        result = yield from asyncio.wait_for(future, timeout)

        if result.error is not None:
            raise result.error.make_exception()

        return result
