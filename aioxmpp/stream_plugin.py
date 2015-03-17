import asyncio

import logging

from .utils import *
from . import sasl

logger = logging.getLogger(__name__)

class StreamFeaturePlugin:
    feature = None

class STARTTLS(StreamFeaturePlugin):
    feature = "{urn:ietf:params:xml:ns:xmpp-tls}starttls"

    def __init__(self, ssl_context_factory):
        super().__init__()
        self._ssl_context_factory = ssl_context_factory

    @asyncio.coroutine
    def start(self, node, feature_node):
        if not hasattr(node.xmlstream._transport, "starttls"):
            logger.warn("STARTTLS not supported by transport")
            if feature_node.find(
                    "{urn:ietf:params:xml:ns:xmpp-tls}required") is not None:
                raise ConnectionError("STARTTLS required, but not supported by "
                                      "transport")
            return False

        logger.debug("STARTTLS feature enabled")

        node, success = yield from node.xmlstream.send_and_wait_for(
            [node.xmlstream.E("{urn:ietf:params:xml:ns:xmpp-tls}starttls")],
            [
                ("{urn:ietf:params:xml:ns:xmpp-tls}proceed", True),
                ("{urn:ietf:params:xml:ns:xmpp-tls}failure", False)
            ]
        )

        if success:
            logger.debug("received <proceed />")
            try:
                node.xmlstream._transport.starttls(
                    self._ssl_context_factory(),
                    server_hostname=node.xmlstream._to)
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
    def start(self, xmlstream, feature_node):
        mechanisms = frozenset(
            node.text
            for node in feature_node.iter(
                    "{urn:ietf:params:xml:ns:xmpp-sasl}mechanism")
        )

        for mechanism in self._mechanisms:
            token = mechanism.any_supported(mechanisms)
            state_machine = sasl.SASLStateMachine(node.xmlstream)
            if token is not None:
                result = yield from mechanism.authenticate(
                    state_machine,
                    token)
                if not result:
                    logger.info("authentication failed")
                else:
                    node.xmlstream.reset_stream()
                    return True


class Bind(StreamFeaturePlugin):
    feature = "{urn:ietf:params:xml:ns:xmpp-bind}bind"

    def __init__(self, preferred_resource=None):
        super().__init__()
        self._preferred_resource = preferred_resource

    @asyncio.coroutine
    def start(self, node, feature_node):
        bind = node.xmlstream.E(
            "{urn:ietf:params:xml:ns:xmpp-bind}bind"
        )

        if self._preferred_resource is not None:
            bind.append(
                node.xmlstream.E(
                    "{urn:ietf:params:xml:ns:xmpp-bind}jid",
                    node._client_jid.replace(resource=self._preferred_resource)
                )
            )
