import asyncio
import base64
import unittest

import asyncio_xmpp.protocol as protocol
import asyncio_xmpp.hooks as hooks
import asyncio_xmpp.node as node
import asyncio_xmpp.stanza as stanza
import asyncio_xmpp.plugins.rfc6120 as rfc6120
import asyncio_xmpp.xml as xml
import asyncio_xmpp.security_layer as security_layer
import asyncio_xmpp.errors as errors

from asyncio_xmpp.utils import *

from .mocks import TestableClient, XMLStreamMock

class TestClient(unittest.TestCase):
    def setUp(self):
        self._loop = asyncio.get_event_loop()

    def _run_until_complete_and_catch_errors(self, future):
        return self._loop.run_until_complete(asyncio.wait_for(
            future,
            timeout=2
        ))

    def _make_stream(self):
        stream = XMLStreamMock(
            self,
            loop=self._loop)
        stream.Estream = stream.tx_context.default_ns_builder(
            namespaces.xmlstream)
        stream.Eerror = stream.tx_context.default_ns_builder(
            namespaces.streams)
        stream.Estarttls = stream.tx_context.default_ns_builder(
            namespaces.starttls)
        stream.Esasl = stream.tx_context.default_ns_builder(
            namespaces.sasl)
        return stream

    def _prepend_actions_up_to_binding(self, stream,
                                       probe_stanzas,
                                       custom_actions):
        bind_response = rfc6120.Bind()
        bind_response.jid = "test@example.com/foo"

        result = [
            (stream.E("{{{}}}starttls".format(namespaces.starttls)),
             [stream.E("{{{}}}proceed".format(namespaces.starttls))]),
            ("!starttls@example.com", None),
            ("!reset",
             [stream.E(
                 "{{{}}}features".format(namespaces.xmlstream),
                 stream.E(
                     "{{{}}}mechanisms".format(namespaces.sasl),
                     stream.E(
                         "{{{}}}mechanism".format(namespaces.sasl),
                         "PLAIN"
                     )
                 )
             )]),
            (stream.E(
                "{{{}}}auth".format(namespaces.sasl),
                base64.b64encode(b"\0test\0test").decode(),
                mechanism="PLAIN"),
             [stream.E("{{{}}}success".format(namespaces.sasl))]),
            ("!reset",
             [
                 stream.E(
                     "{{{}}}features".format(namespaces.xmlstream),
                     stream.E("{{{}}}bind".format(namespaces.bind))
                 )
             ]),
            (stream.E(
                "{{{}}}iq".format(namespaces.client),
                rfc6120.Bind(),
                type="set"),
             [
                 stream.E(
                     "{{{}}}iq".format(namespaces.client),
                     bind_response,
                     type="result")
             ]+probe_stanzas),
        ]
        result.extend(custom_actions)
        stream.define_actions(result)

    @asyncio.coroutine
    def _run_client(self, initial_node, stream,
                    client_jid="test@example.com",
                    password="test",
                    *args, **kwargs):
        connecting, done = asyncio.Event(), asyncio.Event()
        connection_err = None

        client = TestableClient(
            stream,
            client_jid,
            password,
            max_reconnect_attempts=1,
            initial_node=initial_node,
            loop=self._loop)

        try:
            yield from asyncio.wait_for(
                client.connect(),
                timeout=10)
            yield from asyncio.wait_for(
                stream.done_event.wait(),
                timeout=2)
        except TimeoutError:
            raise TimeoutError("Test timed out") from None

        yield from client.disconnect()

    def _simply_run_client(self, stream):
        @asyncio.coroutine
        def task():
            features = stream.E(
                "{{{}}}features".format(namespaces.xmlstream),
                stream.E(
                    "{{{}}}starttls".format(namespaces.starttls),
                    stream.E("{{{}}}required".format(namespaces.starttls))
                )
            )
            err = yield from self._run_client(
                features,
                stream
            )
            if err is not None:
                raise err

        self._run_until_complete_and_catch_errors(task())

    def test_require_starttls(self):
        stream = self._make_stream()
        stream.define_actions(
            [
                (
                    (
                        stream.Estream(
                            "error",
                            stream.Eerror("policy-violation"),
                            stream.Eerror(
                                "text",
                                "TLS failure: STARTTLS not supported by peer"),
                            stream.Eerror(
                                "{{{}}}tls-failure".format(
                                    namespaces.asyncio_xmpp)),
                        )
                    ),
                    ()
                ),
                ("!close", None)
            ]
        )

        @asyncio.coroutine
        def task():
            with self.assertRaises(errors.TLSFailure):
                err = yield from self._run_client(
                    stream.E("{{{}}}features".format(namespaces.xmlstream)),
                    stream
                )

        self._run_until_complete_and_catch_errors(task())

        stream.mock_finalize()

    def _test_sasl_unavailable(self, stream, mechanisms, message):
        initial_features = stream.Estream(
            "features",
            stream.Estarttls("starttls")
        )

        post_tls_features = stream.Estream("features")
        if mechanisms is not None:
            post_tls_features.append(mechanisms)

        stream.define_actions(
            [
                (stream.Estarttls("starttls"),
                 (stream.Estarttls("proceed"),)),
                ("!starttls@example.com", None),
                ("!reset", (post_tls_features,)),
                (stream.Estream(
                    "error",
                    stream.Eerror("policy-violation"),
                    stream.Eerror("text", message),
                    stream.Eerror("{{{}}}sasl-failure".format(
                        namespaces.asyncio_xmpp))),
                 ()),
                ("!close", None),
            ]
        )

        with self.assertRaises(errors.SASLUnavailable) as ctx:
            self._run_until_complete_and_catch_errors(
                self._run_client(initial_features, stream)
            )

        self.assertEqual(
            message,
            str(ctx.exception))

        stream.mock_finalize()

    def test_sasl_unavailable_not_advertised_at_all(self):
        stream = self._make_stream()
        self._test_sasl_unavailable(
            stream,
            None,
            "SASL failure: Remote side does not support SASL")

    def test_sasl_unavailable_no_common_mechanisms(self):
        stream = self._make_stream()
        self._test_sasl_unavailable(
            stream,
            stream.Esasl("mechanisms"),
            "SASL failure: No common mechanisms"
        )

    def test_negotiate_stream(self):
        stream = self._make_stream()

        self._prepend_actions_up_to_binding(
            stream,
            [],
            [("!close", None),]
        )

        self._simply_run_client(stream)

        stream.mock_finalize()

    def test_iq_error_response(self):
        stream = self._make_stream()

        probeiq = stream.E("{jabber:client}iq")
        probeiq.data = stream.E("{foo}data")
        probeiq.type_ = "set"
        probeiq.to = "test@example.com/foo"
        probeiq.from_ = "foo@example.com/bar"
        probeiq.autoset_id()

        err = stanza.Error()
        err.type_ = "cancel"
        err.condition = "feature-not-implemented"
        err.text =("No handler registered for this request "
                   "pattern")

        erriq = stream.tx_context.make_reply(probeiq, error=True)
        erriq.error = err

        self._prepend_actions_up_to_binding(
            stream,
            [
                probeiq
            ],
            [
                (erriq, []),
                ("!close", None),
            ]
        )

        self._simply_run_client(stream)

        stream.mock_finalize()

    def test_iq_silence_for_errornous_result(self):
        stream = self._make_stream()

        probeiq = stream.E("{jabber:client}iq")
        probeiq.type_ = "result"
        probeiq.data = stream.E("{foo}data")
        probeiq.to = "test@example.com/foo"
        probeiq.from_ = "foo@example.com/bar"
        probeiq.autoset_id()

        self._prepend_actions_up_to_binding(
            stream,
            [
                probeiq
            ],
            [
                ("!close", None),
            ]
        )

        self._simply_run_client(stream)

        stream.mock_finalize()
