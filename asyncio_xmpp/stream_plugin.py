import asyncio

import logging

from .utils import *

logger = logging.getLogger(__name__)

class StreamFeaturePlugin:
    feature = None

class STARTTLS(StreamFeaturePlugin):
    feature = "{urn:ietf:params:xml:ns:xmpp-tls}starttls"

    def __init__(self, ssl_context_factory):
        super().__init__()
        self._ssl_context_factory = ssl_context_factory

    @asyncio.coroutine
    def start(self, protocol, feature_node):
        if not hasattr(protocol._transport, "starttls"):
            logger.warn("STARTTLS not supported by transport")
            if feature_node.find(
                    "{urn:ietf:params:xml:ns:xmpp-tls}required") is not None:
                raise Exception("STARTTLS required, but not supported by "
                                "transport")
            return False

        logger.debug("STARTTLS feature enabled")

        node, success = yield from protocol.send_and_wait_for(
            protocol.E("{urn:ietf:params:xml:ns:xmpp-tls}starttls"),
            ("{urn:ietf:params:xml:ns:xmpp-tls}proceed", True),
            ("{urn:ietf:params:xml:ns:xmpp-tls}failure", False)
        )

        if success:
            logger.debug("received <proceed />")
            try:
                protocol._transport.starttls(
                    self._ssl_context_factory(),
                    server_hostname=protocol._to)
            except Exception as err:
                logger.exception("starttls failed")
                pass
            else:
                return True

        raise ConnectionError("STARTTLS negotiation failed")


class SASL(StreamFeaturePlugin):
    feature = "{urn:ietf:params:xml:ns:xmpp-sasl}mechanisms"

    def __init__(self, primary_mechanism, *additional_mechanisms):
        super().__init__()
        self._mechanisms = [primary_mechanism]
        self._mechanisms.extend(additional_mechanisms)

    @asyncio.coroutine
    def start(self, protocol, feature_node):
        mechanisms = [
            node.text
            for node in feature_node.iter(
                    "{urn:ietf:params:xml:ns:xmpp-sasl}mechanism")
        ]

        yield from asyncio.sleep(1)
