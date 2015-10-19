import asyncio
import contextlib
import functools
import ipaddress
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp.node as node
import aioxmpp.structs as structs
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza
import aioxmpp.rfc6120 as rfc6120
import aioxmpp.service as service

from aioxmpp.utils import namespaces

from aioxmpp import xmltestutils
from aioxmpp.testutils import (
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer
)


class Testconnect_to_xmpp_server(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.ssl_transport.STARTTLSTransport"),
            unittest.mock.patch("aioxmpp.protocol.XMLStream"),
            unittest.mock.patch("aioxmpp.network.group_and_order_srv_records"),
            unittest.mock.patch("aioxmpp.network.find_xmpp_host_addr")
        ]
        (self.STARTTLSTransport,
         self.XMLStream,
         self.group_and_order_srv_records,
         self.find_xmpp_host_addr) = (patch.start() for patch in self.patches)

        self.srv_records = [
            (2, 1, ("xmpp.backup.bar.example", 5222)),
            (0, 1, ("xmpp1.bar.example", 5223)),
            (0, 1, ("xmpp2.bar.example", 5224))
        ]

        self.find_xmpp_host_addr.return_value = self._coro_return(
            self.srv_records)

        self.group_and_order_srv_records.return_value = [
            ("xmpp1.bar.example", 5223),
            ("xmpp2.bar.example", 5224),
            ("xmpp.backup.bar.example", 5222),
        ]

        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")


    @asyncio.coroutine
    def _coro_return(self, value):
        return value

    @asyncio.coroutine
    def _create_startttls_connection(self,
                                     STARTTLSTransport,
                                     mock_recorder,
                                     fail_sequence,
                                     loop, xmlstream, **kwargs):
        mock_recorder(loop, xmlstream, **kwargs)
        try:
            exc = fail_sequence.pop(0)
        except IndexError:
            pass
        else:
            if exc:
                raise exc
        return STARTTLSTransport(), xmlstream

    def test_connection(self):
        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  [])):

            transport, protocol, features_future = run_coroutine(
                node.connect_to_xmpp_server(
                    self.test_jid
                ),
                loop=self.loop
            )

        self.find_xmpp_host_addr.assert_called_once_with(
            self.loop,
            self.test_jid.domain
        )

        self.group_and_order_srv_records.assert_called_once_with(
            self.srv_records
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp1.bar.example",
                    port=5223,
                    peer_hostname="xmpp1.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                )
            ],
            create_starttls_connection_mock.mock_calls
        )

        self.assertEqual(
            protocol,
            self.XMLStream(to=self.test_jid.domain,
                           features_future=features_future)
        )

    def test_use_next_host_on_failure(self):
        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  [OSError(), OSError()]
                )):

            transport, protocol, features_future = run_coroutine(
                node.connect_to_xmpp_server(
                    self.test_jid
                ),
                loop=self.loop
            )

        self.find_xmpp_host_addr.assert_called_once_with(
            self.loop,
            self.test_jid.domain
        )

        self.group_and_order_srv_records.assert_called_once_with(
            self.srv_records
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp1.bar.example",
                    port=5223,
                    peer_hostname="xmpp1.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                ),
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp2.bar.example",
                    port=5224,
                    peer_hostname="xmpp2.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                ),
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp.backup.bar.example",
                    port=5222,
                    peer_hostname="xmpp.backup.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                )
            ],
            create_starttls_connection_mock.mock_calls
        )

    def test_raise_if_all_hosts_fail(self):
        excs = [OSError() for i in range(3)]

        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  excs[:]
                )):

            with self.assertRaises(errors.MultiOSError) as ctx:
                transport, protocol, features_future = run_coroutine(
                    node.connect_to_xmpp_server(
                        self.test_jid
                    ),
                    loop=self.loop
                )

        self.assertSequenceEqual(
            excs,
            ctx.exception.exceptions
        )

        self.find_xmpp_host_addr.assert_called_once_with(
            self.loop,
            self.test_jid.domain
        )

        self.group_and_order_srv_records.assert_called_once_with(
            self.srv_records
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp1.bar.example",
                    port=5223,
                    peer_hostname="xmpp1.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                ),
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp2.bar.example",
                    port=5224,
                    peer_hostname="xmpp2.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                ),
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp.backup.bar.example",
                    port=5222,
                    peer_hostname="xmpp.backup.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                )
            ],
            create_starttls_connection_mock.mock_calls
        )

    def test_raise_if_no_hosts_discovered(self):
        self.srv_records.clear()
        self.group_and_order_srv_records.return_value = []

        with self.assertRaisesRegexp(OSError,
                                     "does not support XMPP"):
            transport, protocol, features_future = run_coroutine(
                node.connect_to_xmpp_server(
                    self.test_jid
                ),
                loop=self.loop
            )

    def test_re_raise_if_only_one_option(self):
        self.srv_records.clear()
        self.group_and_order_srv_records.return_value = [
            ("xmpp1.bar.example", 5222)
        ]

        exc = OSError()

        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  [exc]
                )):

            with self.assertRaises(OSError) as ctx:
                transport, protocol, features_future = run_coroutine(
                    node.connect_to_xmpp_server(
                        self.test_jid
                    ),
                    loop=self.loop
                )

        self.assertIs(
            exc,
            ctx.exception
        )

    def test_override_peer_with_success(self):
        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  [])):

            transport, protocol, features_future = run_coroutine(
                node.connect_to_xmpp_server(
                    self.test_jid,
                    override_peer=("foo.bar.example", 5234)
                ),
                loop=self.loop
            )

        self.assertFalse(self.find_xmpp_host_addr.mock_calls)
        self.assertFalse(self.group_and_order_srv_records.mock_calls)

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="foo.bar.example",
                    port=5234,
                    peer_hostname="foo.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                )
            ],
            create_starttls_connection_mock.mock_calls
        )

        self.assertEqual(
            protocol,
            self.XMLStream(to=self.test_jid.domain,
                           features_future=features_future)
        )

    def test_skip_to_next_on_failure(self):
        exc = ConnectionError()

        create_starttls_connection_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "aioxmpp.ssl_transport.create_starttls_connection",
                functools.partial(self._create_startttls_connection,
                                  self.STARTTLSTransport,
                                  create_starttls_connection_mock,
                                  [exc])):

            transport, protocol, features_future = run_coroutine(
                node.connect_to_xmpp_server(
                    self.test_jid,
                    override_peer=("foo.bar.example", 5234)
                ),
                loop=self.loop
            )

        self.find_xmpp_host_addr.assert_called_once_with(
            self.loop,
            self.test_jid.domain
        )

        self.group_and_order_srv_records.assert_called_once_with(
            self.srv_records
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="foo.bar.example",
                    port=5234,
                    peer_hostname="foo.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                ),
                unittest.mock.call(
                    self.loop,
                    unittest.mock.ANY,
                    host="xmpp1.bar.example",
                    port=5223,
                    peer_hostname="xmpp1.bar.example",
                    server_hostname=self.test_jid.domain,
                    use_starttls=True
                )
            ],
            create_starttls_connection_mock.mock_calls
        )

        self.assertEqual(
            protocol,
            self.XMLStream(to=self.test_jid.domain,
                           features_future=features_future)
        )

    def tearDown(self):
        for patch in self.patches:
            patch.stop()


class Testconnect_secured_xmlstream(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

        self.patches = [
            unittest.mock.patch("aioxmpp.protocol.XMLStream"),
        ]
        self.XMLStream, = (patch.start() for patch in self.patches)

        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")

    @asyncio.coroutine
    def _security_layer(self,
                        mock_recorder,
                        tls_transport,
                        new_features,
                        negotiation_timeout, jid, features, xmlstream):
        mock_recorder(negotiation_timeout, jid, features, xmlstream)
        return tls_transport, new_features

    @asyncio.coroutine
    def _connect_to_xmpp_server(self,
                                transport,
                                features,
                                xmlstream,
                                mock_recorder,
                                *args, **kwargs):
        mock_recorder(*args, **kwargs)
        fut = asyncio.Future()
        fut.set_result(features)
        xmlstream.transport = transport
        return transport, xmlstream, fut

    def test_call_sequence(self):
        connect_to_xmpp_server_recorder = unittest.mock.MagicMock()
        security_layer_recorder = unittest.mock.MagicMock()

        transport = object()
        override_peer = object()
        xmlstream = unittest.mock.MagicMock()

        final_features = stream_xsos.StreamFeatures()
        tls_transport = object()
        security_layer = functools.partial(
            self._security_layer,
            security_layer_recorder,
            tls_transport,
            final_features)

        features = stream_xsos.StreamFeatures()

        with unittest.mock.patch("aioxmpp.node.connect_to_xmpp_server",
                                 functools.partial(
                                     self._connect_to_xmpp_server,
                                     transport,
                                     features,
                                     xmlstream,
                                     connect_to_xmpp_server_recorder
                                 )):
            result = run_coroutine(
                node.connect_secured_xmlstream(
                    self.test_jid,
                    security_layer,
                    negotiation_timeout=10.0,
                    override_peer=override_peer,
                    loop=self.loop)
            )

        connect_to_xmpp_server_recorder.assert_called_once_with(
            self.test_jid,
            override_peer=override_peer,
            loop=self.loop
        )

        security_layer_recorder.assert_called_once_with(
            10.0,
            self.test_jid,
            features,
            xmlstream,
        )

        result_tls_transport, result_xmlstream, result_features = result

        self.assertIs(tls_transport, result_tls_transport)
        self.assertIs(xmlstream, result_xmlstream)
        self.assertIs(final_features, result_features)

    def test_connect_timeout(self):
        connect_to_xmpp_server_recorder = unittest.mock.MagicMock()
        security_layer_recorder = unittest.mock.MagicMock()

        transport = object()
        xmlstream = unittest.mock.MagicMock()

        final_features = stream_xsos.StreamFeatures()
        tls_transport = object()
        security_layer = functools.partial(
            self._security_layer,
            security_layer_recorder,
            tls_transport,
            final_features)

        features = stream_xsos.StreamFeatures()

        @asyncio.coroutine
        def sleeper(jid, override_peer, loop):
            yield from asyncio.sleep(10, loop=loop)

        with unittest.mock.patch("aioxmpp.node.connect_to_xmpp_server",
                                 sleeper):
            with self.assertRaisesRegexp(TimeoutError,
                                         "connection to .* timed out"):
                run_coroutine(
                    node.connect_secured_xmlstream(
                        self.test_jid,
                        security_layer,
                        negotiation_timeout=0.2,
                        loop=self.loop)
                )

    @unittest.mock.patch("aioxmpp.protocol.send_stream_error_and_close")
    def test_send_stream_error_on_sasl_unavailable_and_re_raise(
            self,
            send_stream_error_and_close
    ):
        connect_to_xmpp_server_recorder = unittest.mock.MagicMock()
        security_layer_recorder = unittest.mock.MagicMock()
        security_layer_recorder.side_effect = errors.SASLUnavailable(
            "invalid-mechanism")

        transport = object()
        xmlstream = unittest.mock.MagicMock()

        final_features = stream_xsos.StreamFeatures()
        tls_transport = object()
        security_layer = functools.partial(
            self._security_layer,
            security_layer_recorder,
            tls_transport,
            final_features)

        features = stream_xsos.StreamFeatures()

        with unittest.mock.patch("aioxmpp.node.connect_to_xmpp_server",
                                 functools.partial(
                                     self._connect_to_xmpp_server,
                                     transport,
                                     features,
                                     xmlstream,
                                     connect_to_xmpp_server_recorder
                                 )):
            with self.assertRaises(errors.SASLUnavailable):
                run_coroutine(
                    node.connect_secured_xmlstream(
                        self.test_jid,
                        security_layer,
                        negotiation_timeout=10.0,
                        loop=self.loop)
                )

        connect_to_xmpp_server_recorder.assert_called_once_with(
            self.test_jid,
            override_peer=None,
            loop=self.loop
        )

        security_layer_recorder.assert_called_once_with(
            10.0,
            self.test_jid,
            features,
            xmlstream,
        )

        send_stream_error_and_close.assert_called_once_with(
            xmlstream,
            condition=(namespaces.streams, "policy-violation"),
            text="SASL failure: invalid-mechanism")

    @unittest.mock.patch("aioxmpp.protocol.send_stream_error_and_close")
    def test_send_stream_error_on_tls_unavailable_and_re_raise(
            self,
            send_stream_error_and_close
    ):
        connect_to_xmpp_server_recorder = unittest.mock.MagicMock()
        security_layer_recorder = unittest.mock.MagicMock()
        security_layer_recorder.side_effect = errors.TLSUnavailable(
            "policy-violation")

        transport = object()
        xmlstream = unittest.mock.MagicMock()

        final_features = stream_xsos.StreamFeatures()
        tls_transport = object()
        security_layer = functools.partial(
            self._security_layer,
            security_layer_recorder,
            tls_transport,
            final_features)

        features = stream_xsos.StreamFeatures()

        with unittest.mock.patch("aioxmpp.node.connect_to_xmpp_server",
                                 functools.partial(
                                     self._connect_to_xmpp_server,
                                     transport,
                                     features,
                                     xmlstream,
                                     connect_to_xmpp_server_recorder
                                 )):
            with self.assertRaises(errors.TLSUnavailable):
                run_coroutine(
                    node.connect_secured_xmlstream(
                        self.test_jid,
                        security_layer,
                        negotiation_timeout=10.0,
                        loop=self.loop)
                )

        connect_to_xmpp_server_recorder.assert_called_once_with(
            self.test_jid,
            override_peer=None,
            loop=self.loop
        )

        security_layer_recorder.assert_called_once_with(
            10.0,
            self.test_jid,
            features,
            xmlstream,
        )

        send_stream_error_and_close.assert_called_once_with(
            xmlstream,
            condition=(namespaces.streams, "policy-violation"),
            text="TLS failure: policy-violation")

    @unittest.mock.patch("aioxmpp.protocol.send_stream_error_and_close")
    def test_send_stream_error_on_sasl_failure_and_re_raise(
            self,
            send_stream_error_and_close
    ):
        connect_to_xmpp_server_recorder = unittest.mock.MagicMock()
        security_layer_recorder = unittest.mock.MagicMock()
        exc = errors.SASLFailure(
            "malformed-request",
            text="Nonce does not match")
        security_layer_recorder.side_effect = exc

        transport = object()
        xmlstream = unittest.mock.MagicMock()

        final_features = stream_xsos.StreamFeatures()
        tls_transport = object()
        security_layer = functools.partial(
            self._security_layer,
            security_layer_recorder,
            tls_transport,
            final_features)

        features = stream_xsos.StreamFeatures()

        with unittest.mock.patch("aioxmpp.node.connect_to_xmpp_server",
                                 functools.partial(
                                     self._connect_to_xmpp_server,
                                     transport,
                                     features,
                                     xmlstream,
                                     connect_to_xmpp_server_recorder
                                 )):
            with self.assertRaises(errors.SASLFailure):
                run_coroutine(
                    node.connect_secured_xmlstream(
                        self.test_jid,
                        security_layer,
                        negotiation_timeout=10.0,
                        loop=self.loop)
                )

        connect_to_xmpp_server_recorder.assert_called_once_with(
            self.test_jid,
            override_peer=None,
            loop=self.loop
        )

        security_layer_recorder.assert_called_once_with(
            10.0,
            self.test_jid,
            features,
            xmlstream,
        )

        send_stream_error_and_close.assert_called_once_with(
            xmlstream,
            condition=(namespaces.streams, "undefined-condition"),
            text=str(exc))

    def tearDown(self):
        for patch in self.patches:
            patch.stop()


class TestAbstractClient(xmltestutils.XMLTestCase):
    @asyncio.coroutine
    def _connect_secured_xmlstream(self, *args, **kwargs):
        self.connect_secured_xmlstream_rec(*args, **kwargs)
        return None, self.xmlstream, self.features

    @staticmethod
    def _autoset_id(self):
        # self refers to a StanzaBase object!
        self.id_ = "autoset"

    @property
    def xmlstream(self):
        if self._xmlstream is None or self._xmlstream._exception:
            self._xmlstream = XMLStreamMock(self, loop=self.loop)
        return self._xmlstream

    def setUp(self):
        self.connect_secured_xmlstream_rec = unittest.mock.MagicMock()
        self.failure_rec = unittest.mock.MagicMock()
        self.failure_rec.return_value = None
        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None
        self.security_layer = object()

        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.node.connect_secured_xmlstream",
                                self._connect_secured_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id)
        ]
        self.connect_secured_xmlstream, _ = (patch.start()
                                             for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = stream_xsos.StreamFeatures()
        self.features[...] = rfc6120.BindFeature()

        self.client = node.AbstractClient(
            self.test_jid,
            self.security_layer,
            loop=self.loop)
        self.client.on_failure.connect(self.failure_rec)
        self.client.on_stream_destroyed.connect(self.destroyed_rec)
        self.client.on_stream_established.connect(self.established_rec)

        # some XMLStreamMock test case parts
        self.sm_negotiation_exchange = [
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=XMLStreamMock.Receive(
                    stream_xsos.SMEnabled(resume=True,
                                          id_="foobar")
                )
            )
        ]
        self.resource_binding = [
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid,
                        ),
                        type_="result",
                        id_="autoset"
                    )
                )
            )
        ]
        self.sm_request = [
            XMLStreamMock.Send(
                stream_xsos.SMRequest()
            )
        ]

    def test_defaults(self):
        self.assertEqual(
            self.client.negotiation_timeout,
            timedelta(seconds=60)
        )

    def test_setup(self):
        client = node.AbstractClient(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=timedelta(seconds=30)
        )
        self.assertEqual(client.local_jid, self.test_jid)
        self.assertEqual(
            client.negotiation_timeout,
            timedelta(seconds=30)
        )
        self.assertEqual(
            client.backoff_start,
            timedelta(seconds=1)
        )
        self.assertEqual(
            client.backoff_cap,
            timedelta(seconds=60)
        )
        self.assertEqual(
            client.backoff_factor,
            1.2
        )

        with self.assertRaises(AttributeError):
            client.local_jid = structs.JID.fromstr("bar@bar.example/baz")

    def test_start(self):
        self.assertFalse(self.client.established)
        run_coroutine(asyncio.sleep(0))
        self.connect_secured_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        self.connect_secured_xmlstream_rec.assert_called_once_with(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=None,
            loop=self.loop
        )

    def test_reject_start_twice(self):
        self.client.start()
        with self.assertRaisesRegexp(RuntimeError,
                                     "already running"):
            self.client.start()

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_stanza_stream_starts_and_stops_with_client(self):
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.stream.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.established)

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close()
        ]))
        self.assertFalse(self.client.stream.running)

    def test_stop(self):
        cb = unittest.mock.Mock()
        cb.return_value = False

        run_coroutine(asyncio.sleep(0))
        self.connect_secured_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.established)
        self.assertTrue(self.client.running)

        self.client.on_stopped.connect(cb)

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))

        self.client.stop()
        self.assertSequenceEqual([], cb.mock_calls)

        run_coroutine(self.xmlstream.run_test(
            [
                XMLStreamMock.Close(),
            ],
        ))

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.established)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            cb.mock_calls
        )

    def test_reconnect_on_failure(self):
        self.client.backoff_start = timedelta(seconds=0.008)
        self.client.negotiation_timeout = timedelta(seconds=0.01)
        self.client.start()

        iq = stanza.IQ()
        iq.autoset_id()
        @asyncio.coroutine
        def stimulus():
            self.client.stream.enqueue_stanza(iq)

        run_coroutine_with_peer(
            stimulus(),
            self.xmlstream.run_test(
                self.resource_binding+[
                    XMLStreamMock.Send(
                        iq,
                        response=[
                            XMLStreamMock.Fail(
                                exc=ConnectionError()
                            ),
                        ]
                    ),
                ]
            )
        )
        run_coroutine(
            self.xmlstream.run_test(
                self.resource_binding
            )
        )

        run_coroutine(asyncio.sleep(0.015))

        self.assertTrue(self.client.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    negotiation_timeout=0.01,
                    override_peer=None,
                    loop=self.loop)
            ]*2,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        # the client has not failed
        self.assertFalse(self.failure_rec.mock_calls)
        self.assertTrue(self.client.established)

    def test_fail_on_authentication_failure(self):
        exc = errors.AuthenticationFailure("not-authorized")
        self.connect_secured_xmlstream_rec.side_effect = exc
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(exc)
            ],
            self.failure_rec.mock_calls
        )

    def test_fail_on_stream_negotation_failure(self):
        exc = errors.StreamNegotiationFailure("undefined-condition")
        self.connect_secured_xmlstream_rec.side_effect = exc
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)
        self.assertSequenceEqual(
            [
                unittest.mock.call(exc)
            ],
            self.failure_rec.mock_calls
        )

    def test_exponential_backoff_on_os_error(self):
        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=None,
            loop=self.loop)

        exc = OSError()
        self.connect_secured_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.01))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.02))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.04))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.08))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_secured_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_negotiate_stream_management(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding+
            self.sm_negotiation_exchange
        ))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.stream.running)
        self.assertTrue(self.client.running)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_resume_stream_management(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        with contextlib.ExitStack() as stack:
            _resume_sm = stack.enter_context(
                unittest.mock.patch.object(self.client.stream, "_resume_sm"),
            )

            run_coroutine(self.xmlstream.run_test(self.resource_binding+[
                XMLStreamMock.Send(
                    stream_xsos.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            stream_xsos.SMEnabled(resume=True,
                                                  id_="foobar"),

                        ),
                        XMLStreamMock.Fail(
                            exc=ConnectionError()
                        ),
                    ]
                ),
            ]))

            # new xmlstream here after failure
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Send(
                    stream_xsos.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            stream_xsos.SMResumed(counter=0)
                        )
                    ]
                )
            ]))

            _resume_sm.assert_called_once_with(0)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_stop_stream_management_if_remote_stops_providing_support(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMEnabled(resume=True,
                                              id_="foobar"),

                    ),
                    XMLStreamMock.Fail(
                    exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure

        del self.features[stream_xsos.StreamManagementFeature]

        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        run_coroutine(asyncio.sleep(0))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ]*2,
            self.established_rec.mock_calls
        )
        self.destroyed_rec.assert_called_once_with()

    def test_reconnect_at_advised_location_for_resumable_stream(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMEnabled(
                            resume=True,
                            id_="foobar",
                            location=(ipaddress.IPv6Address("fe80::"), 5222)),

                    ),
                    XMLStreamMock.Fail(
                        exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stream_xsos.SMResume(counter=0, previd="foobar"),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMResumed(counter=0)
                    )
                ]
            )
        ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=None,
                    negotiation_timeout=60.0,
                    loop=self.loop),
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=("fe80::", 5222),
                    negotiation_timeout=60.0,
                    loop=self.loop),
            ],
            self.connect_secured_xmlstream_rec.mock_calls
        )

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_degrade_to_non_sm_if_sm_fails(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMFailed(),
                    ),
                ]
            ),
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.client.stream.sm_enabled)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_retry_sm_restart_if_sm_resumption_fails(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMEnabled(resume=True,
                                              id_="foobar"),

                    ),
                    XMLStreamMock.Fail(
                        exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stream_xsos.SMResume(counter=0, previd="foobar"),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMFailed()
                    )
                ]
            ),
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stream_xsos.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        stream_xsos.SMEnabled(resume=True,
                                              id_="foobar"),

                    ),
                ]
            ),
        ]))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.running)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),  # stream established #1
                unittest.mock.call(),  # resumption failed, so new stream
            ],
            self.established_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(),  # resumption failed
            ],
            self.destroyed_rec.mock_calls
        )

    def test_fail_on_resource_binding_error(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        error=stanza.Error(
                            condition=(namespaces.stanzas,
                                       "resource-constraint"),
                            text="too many resources",
                            type_="cancel"
                        ),
                        type_="error",
                        id_="autoset"
                    )
                )
            )
        ]))
        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertEqual(
            1,
            len(self.failure_rec.mock_calls)
        )

        error_call, = self.failure_rec.mock_calls

        self.assertIsInstance(
            error_call[1][0],
            errors.StreamNegotiationFailure
        )

        self.assertFalse(self.established_rec.mock_calls)
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_resource_binding(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid.replace(
                                resource="foobarbaz"),
                        ),
                        type_="result",
                        id_="autoset",
                    )
                )
            )
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertEqual(
            self.test_jid.replace(resource="foobarbaz"),
            self.client.local_jid
        )

        self.established_rec.assert_called_once_with()

    def test_stream_features_attribute(self):
        self.assertIsNone(self.client.stream_features)

        self.client.start()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid.replace(
                                resource="foobarbaz"),
                        ),
                        type_="result",
                        id_="autoset",
                    )
                )
            )
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertIs(
            self.features,
            self.client.stream_features
        )

    def test_signals_fire_correctly_on_fail_after_established_connection(self):
        self.client.start()

        run_coroutine(self.xmlstream.run_test([]))

        exc = errors.AuthenticationFailure("not-authorized")
        self.connect_secured_xmlstream_rec.side_effect = exc

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=[
                    XMLStreamMock.Receive(
                        stanza.IQ(
                            payload=rfc6120.Bind(
                                jid=self.test_jid,
                            ),
                            type_="result",
                            id_="autoset"
                        )
                    ),
                ]
            )
        ]))

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Fail(exc=ConnectionError())
        ))

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.destroyed_rec.assert_called_once_with()
        self.assertFalse(self.client.established)

    def test_signals_fire_correctly_on_fail_after_established_sm_connection(self):
        self.features[...] = stream_xsos.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding+
            self.sm_negotiation_exchange
        ))

        exc = errors.AuthenticationFailure("not-authorized")
        self.connect_secured_xmlstream_rec.side_effect = exc

        run_coroutine(self.xmlstream.run_test(
            [],
            stimulus=XMLStreamMock.Fail(exc=ConnectionError())
        ))

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.destroyed_rec.assert_called_once_with()

    def test_summon(self):
        svc_init = unittest.mock.Mock()

        class Svc1(service.Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        class Svc2(service.Service):
            SERVICE_BEFORE = [Svc1]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        class Svc3(service.Service):
            SERVICE_BEFORE = [Svc2]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        svc2 = self.client.summon(Svc2)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc3(self.client),
                unittest.mock.call.Svc2(self.client),
            ],
            svc_init.mock_calls
        )

        svc3 = self.client.summon(Svc3)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc3(self.client),
                unittest.mock.call.Svc2(self.client),
            ],
            svc_init.mock_calls
        )

        svc1 = self.client.summon(Svc1)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc3(self.client),
                unittest.mock.call.Svc2(self.client),
                unittest.mock.call.Svc1(self.client),
            ],
            svc_init.mock_calls
        )

    def test_call_before_stream_established(self):
        @asyncio.coroutine
        def coro():
            iq = stanza.IQ(
                type_="set",
            )
            yield from self.client.stream.send_iq_and_wait_for_reply(
                iq)

        self.client.before_stream_established.connect(coro)

        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.IQ(type_="set",
                          id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(type_="result",
                              id_="autoset")
                )
            ),
        ]))

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        if self.client.running:
            self.client.stop()
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Close()
            ]))
        run_coroutine(self.xmlstream.run_test([
        ]))


class TestPresenceManagedClient(xmltestutils.XMLTestCase):
    @asyncio.coroutine
    def _connect_secured_xmlstream(self, *args, **kwargs):
        self.connect_secured_xmlstream_rec(*args, **kwargs)
        return None, self.xmlstream, self.features

    @staticmethod
    def _autoset_id(self):
        # self refers to a StanzaBase object!
        self.id_ = "autoset"

    @property
    def xmlstream(self):
        if self._xmlstream is None or self._xmlstream._exception:
            self._xmlstream = XMLStreamMock(self, loop=self.loop)
        return self._xmlstream

    def setUp(self):
        self.connect_secured_xmlstream_rec = unittest.mock.MagicMock()
        self.failure_rec = unittest.mock.MagicMock()
        self.failure_rec.return_value = None
        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None
        self.presence_sent_rec = unittest.mock.MagicMock()
        self.presence_sent_rec.return_value = None
        self.security_layer = object()

        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.node.connect_secured_xmlstream",
                                self._connect_secured_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id),
        ]
        self.connect_secured_xmlstream, _ = (patch.start()
                                             for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = stream_xsos.StreamFeatures()
        self.features[...] = rfc6120.BindFeature()

        self.client = node.PresenceManagedClient(
            self.test_jid,
            self.security_layer,
            loop=self.loop)
        self.client.on_failure.connect(self.failure_rec)
        self.client.on_stream_destroyed.connect(self.destroyed_rec)
        self.client.on_stream_established.connect(self.established_rec)
        self.client.on_presence_sent.connect(self.presence_sent_rec)

        self.resource_binding = [
            XMLStreamMock.Send(
                stanza.IQ(
                    payload=rfc6120.Bind(
                        resource=self.test_jid.resource),
                    type_="set",
                    id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.IQ(
                        payload=rfc6120.Bind(
                            jid=self.test_jid,
                        ),
                        type_="result",
                        id_="autoset"
                    )
                )
            )
        ]

    def test_setup(self):
        self.assertEqual(
            structs.PresenceState(),
            self.client.presence
        )

    def test_change_presence_to_available(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show="chat")

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="chat",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="chat",
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_change_presence_while_available(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show="chat")

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="chat",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="chat",
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

        self.client.presence = structs.PresenceState(
            available=True,
            show="away")

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="away",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="away",
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_change_presence_to_unavailable(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show="chat")

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="chat",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="chat",
                                    id_="autoset")
                )
            )
        ]))

        self.client.presence = structs.PresenceState()

        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close(),
        ]))

        self.assertFalse(self.client.running)

        self.presence_sent_rec.assert_called_once_with()

    def test_do_not_send_presence_twice_if_changed_while_establishing(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show="chat")
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.established)

        self.client.presence = structs.PresenceState(
            available=True,
            show="dnd")

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="dnd",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="dnd",
                                    id_="autoset")
                )
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_re_establish_on_presence_rewrite_if_disconnected(self):
        self.client.presence = structs.PresenceState(
            available=True,
            show="chat")

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="chat",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="chat",
                                    id_="autoset")
                )
            ),
        ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ],
            self.presence_sent_rec.mock_calls
        )
        self.presence_sent_rec.reset_mock()

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close()
        ]))

        self.client.presence = self.client.presence

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                stanza.Presence(type_=None,
                                show="chat",
                                id_="autoset"),
                response=XMLStreamMock.Receive(
                    stanza.Presence(type_=None,
                                    show="chat",
                                    id_="autoset")
                )
            ),
        ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call()
            ],
            self.presence_sent_rec.mock_calls
        )
        self.presence_sent_rec.reset_mock()

    def test_set_presence_with_texts(self):
        status_texts = [
            stanza.Status("de", structs.LanguageTag.fromstr("de")),
            stanza.Status("generic"),
        ]

        self.client.set_presence(
            structs.PresenceState(
                available=True,
                show="chat"),
            status=status_texts
        )

        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status.extend(status_texts)

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                expected
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_with_single_string(self):
        self.client.set_presence(
            structs.PresenceState(
                available=True,
                show="chat"),
            status="foobar"
        )

        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status.append(
            stanza.Status("foobar")
        )

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                expected
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_is_robust_against_modification_of_the_argument(self):
        status_texts = [
            stanza.Status("de", structs.LanguageTag.fromstr("de")),
            stanza.Status("generic"),
        ]

        self.client.set_presence(
            structs.PresenceState(
                available=True,
                show="chat"),
            status=status_texts
        )

        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status.extend(status_texts)

        del status_texts[0]

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                expected
            )
        ]))

        self.presence_sent_rec.assert_called_once_with()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        if self.client.running:
            self.client.stop()
            run_coroutine(self.xmlstream.run_test([
                XMLStreamMock.Close()
            ]))
        run_coroutine(self.xmlstream.run_test([
        ]))
