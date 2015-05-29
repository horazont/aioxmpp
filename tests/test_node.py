import asyncio
import functools
import unittest
import unittest.mock

import aioxmpp.node as node
import aioxmpp.structs as structs
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.errors as errors

from . import xmltestutils
from .testutils import run_coroutine


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
                    loop=self.loop)
            )

        connect_to_xmpp_server_recorder.assert_called_once_with(
            self.test_jid,
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
        def sleeper(jid, loop):
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


    def tearDown(self):
        for patch in self.patches:
            patch.stop()
