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

    def start(self, protocol, feature_node):
        if not hasattr(protocol._transport, "starttls"):
            logger.warn("STARTTLS not supported by transport")
            if feature_node.find("{urn:ietf:params:xml:ns:xmpp-tls}required"):
                raise Exception("STARTTLS required, but not supported by "
                                "transport")
            return False

        logger.debug("STARTTLS feature enabled")

        protocol.add_stream_level_node_callback(
            "{urn:ietf:params:xml:ns:xmpp-tls}proceed",
            self._proceed)

        protocol.add_stream_level_node_callback(
            "{urn:ietf:params:xml:ns:xmpp-tls}failure",
            self._failure)

        protocol.send_node(
            protocol.E("{urn:ietf:params:xml:ns:xmpp-tls}starttls")
        )

        return True

    def _proceed(self, protocol, node):
        logger.debug("received <proceed />")
        protocol._transport.starttls(
            self._ssl_context_factory(),
            server_hostname=protocol._to)

    def _failure(self, protocol, node):
        raise Exception("STARTTLS failed to initialize")
