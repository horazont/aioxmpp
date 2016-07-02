import asyncio
import contextlib
import functools
import ipaddress
import itertools
import logging
import unittest
import unittest.mock

from datetime import timedelta

import dns.resolver

import aiosasl

import aioxmpp.node as node
import aioxmpp.structs as structs
import aioxmpp.nonza as nonza
import aioxmpp.errors as errors
import aioxmpp.stanza as stanza
import aioxmpp.rfc3921 as rfc3921
import aioxmpp.rfc6120 as rfc6120
import aioxmpp.service as service

from aioxmpp.utils import namespaces

from aioxmpp import xmltestutils
from aioxmpp.testutils import (
    run_coroutine,
    XMLStreamMock,
    run_coroutine_with_peer,
    CoroutineMock,
)


class Testdiscover_connectors(unittest.TestCase):
    def test_request_SRV_records(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        def tls_connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "tls{}".format(i))

        def srv_records():
            yield [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (unittest.mock.sentinel.host1, unittest.mock.sentinel.port1)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (unittest.mock.sentinel.host2, unittest.mock.sentinel.port2)),
            ]
            yield [
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4)),
            ]

        def grouped_results():
            yield 1
            yield 2

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            XMPPOverTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.XMPPOverTLSConnector")
            )
            XMPPOverTLSConnector.side_effect = tls_connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.side_effect = srv_records()

            group_and_order = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.group_and_order_srv_records")
            )
            group_and_order.return_value = grouped_results()

            result = run_coroutine(
                node.discover_connectors(
                    unittest.mock.sentinel.domain,
                    loop=loop,
                )
            )

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        group_and_order.assert_called_with(
            [
                (unittest.mock.sentinel.prio1,
                 unittest.mock.sentinel.weight1,
                 (unittest.mock.sentinel.host1, unittest.mock.sentinel.port1,
                  unittest.mock.sentinel.starttls0)),
                (unittest.mock.sentinel.prio2,
                 unittest.mock.sentinel.weight2,
                 (unittest.mock.sentinel.host2, unittest.mock.sentinel.port2,
                  unittest.mock.sentinel.starttls1)),
                (unittest.mock.sentinel.prio3,
                 unittest.mock.sentinel.weight3,
                 (unittest.mock.sentinel.host3, unittest.mock.sentinel.port3,
                  unittest.mock.sentinel.tls0)),
                (unittest.mock.sentinel.prio4,
                 unittest.mock.sentinel.weight4,
                 (unittest.mock.sentinel.host4, unittest.mock.sentinel.port4,
                  unittest.mock.sentinel.tls1)),
            ]
        )

        self.assertSequenceEqual(
            result,
            [1, 2],
        )

    def test_fallback_to_domain_name(self):
        loop = asyncio.get_event_loop()

        def connectors():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel,
                              "starttls{}".format(i))

        with contextlib.ExitStack() as stack:
            STARTTLSConnector = stack.enter_context(
                unittest.mock.patch("aioxmpp.connector.STARTTLSConnector")
            )
            STARTTLSConnector.side_effect = connectors()

            lookup_srv = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.lookup_srv",
                                    new=CoroutineMock()),
            )
            lookup_srv.return_value = None

            group_and_order = stack.enter_context(
                unittest.mock.patch("aioxmpp.network.group_and_order_srv_records")
            )

            result = run_coroutine(
                node.discover_connectors(
                    unittest.mock.sentinel.domain,
                    loop=loop,
                )
            )

        self.assertSequenceEqual(
            lookup_srv.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpp-client",
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.domain,
                    "xmpps-client",
                ),
            ]
        )

        self.assertFalse(group_and_order.mock_calls)

        self.assertSequenceEqual(
            result,
            [(unittest.mock.sentinel.domain,
              5222,
              unittest.mock.sentinel.starttls0)],
        )


class Testconnect_xmlstream(unittest.TestCase):
    def setUp(self):
        self.discover_connectors = CoroutineMock()
        self.negotiate_sasl = CoroutineMock()
        self.send_stream_error = unittest.mock.Mock()

        self.patches = [
            unittest.mock.patch("aioxmpp.node.discover_connectors",
                                new=self.discover_connectors),
            unittest.mock.patch("aioxmpp.security_layer.negotiate_sasl",
                                new=self.negotiate_sasl),
            unittest.mock.patch("aioxmpp.protocol.send_stream_error_and_close",
                                new=self.send_stream_error),
        ]

        self.negotiate_sasl.return_value = \
            unittest.mock.sentinel.post_sasl_features

        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_uses_discover_connectors_and_tries_them_in_order(self):
        NCONNECTORS = 4

        logger = unittest.mock.Mock()
        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            loop=unittest.mock.sentinel.loop,
            logger=logger,
        ))

        jid.domain.encode.assert_called_with("idna")

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_negotiate_sasl_after_success(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            negotiation_timeout=unittest.mock.sentinel.timeout,
            loop=unittest.mock.sentinel.loop,
        ))

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.negotiate_sasl.assert_called_with(
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            base.metadata.sasl_providers,
            unittest.mock.sentinel.timeout,
            jid,
            unittest.mock.sentinel.features,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    unittest.mock.sentinel.timeout,
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_try_next_on_generic_SASL_problem(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.t1,
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.f1,
        )

        base.c3.connect.side_effect = None
        base.c3.connect.return_value = (
            unittest.mock.sentinel.t2,
            unittest.mock.sentinel.p2,
            unittest.mock.sentinel.f2,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        exc = errors.SASLUnavailable("fubar")

        def results():
            yield exc
            yield unittest.mock.sentinel.post_sasl_features

        self.negotiate_sasl.side_effect = results()

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            loop=unittest.mock.sentinel.loop,
        ))

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            self.negotiate_sasl.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.t1,
                    unittest.mock.sentinel.p1,
                    base.metadata.sasl_providers,
                    60.,
                    jid,
                    unittest.mock.sentinel.f1,
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.t2,
                    unittest.mock.sentinel.p2,
                    base.metadata.sasl_providers,
                    60.,
                    jid,
                    unittest.mock.sentinel.f2,
                ),
            ]
        )

        self.send_stream_error.assert_called_with(
            unittest.mock.sentinel.p1,
            condition=(namespaces.streams, "policy-violation"),
            text=str(exc)
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                )
                for i in range(NCONNECTORS)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.t2,
                unittest.mock.sentinel.p2,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_abort_on_authentication_failed(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.t1,
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.f1,
        )

        base.c3.connect.side_effect = None
        base.c3.connect.return_value = (
            unittest.mock.sentinel.t2,
            unittest.mock.sentinel.p2,
            unittest.mock.sentinel.f2,
        )

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        exc = aiosasl.AuthenticationFailure("fubar")

        def results():
            yield exc
            yield unittest.mock.sentinel.post_sasl_features

        self.negotiate_sasl.side_effect = results()

        with self.assertRaises(aiosasl.AuthenticationFailure) as exc_ctx:
            run_coroutine(node.connect_xmlstream(
                jid,
                base.metadata,
                loop=unittest.mock.sentinel.loop,
            ))

        self.assertEqual(exc_ctx.exception, exc)

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.send_stream_error.assert_called_with(
            unittest.mock.sentinel.p1,
            condition=(namespaces.streams, "undefined-condition"),
            text=str(exc)
        )

        self.assertSequenceEqual(
            self.negotiate_sasl.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.t1,
                    unittest.mock.sentinel.p1,
                    base.metadata.sasl_providers,
                    60.,
                    jid,
                    unittest.mock.sentinel.f1,
                ),
            ]
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                )
                for i in range(3)
            ]
        )

    def test_uses_override_peer_before_connectors(self):
        NCONNECTORS = 4

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            connect.side_effect = OSError()
            getattr(base, "c{}".format(i)).connect = connect

        base.c2.connect.side_effect = None
        base.c2.connect.return_value = (
            unittest.mock.sentinel.transport,
            unittest.mock.sentinel.protocol,
            unittest.mock.sentinel.features,
        )

        override_peer = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2)
        ]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(2, NCONNECTORS)
        ]

        result = run_coroutine(node.connect_xmlstream(
            jid,
            base.metadata,
            override_peer=override_peer,
            loop=unittest.mock.sentinel.loop,
        ))

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                )
                for i in range(3)
            ]
        )

        self.assertEqual(
            result,
            (
                unittest.mock.sentinel.transport,
                unittest.mock.sentinel.protocol,
                unittest.mock.sentinel.post_sasl_features,
            )
        )

    def test_aggregates_exceptions_and_raises_MultiOSError(self):
        NCONNECTORS = 3

        excs = [
            OSError(),
            errors.TLSUnavailable(
                (namespaces.streams, "policy-violation"),
            ),
            errors.TLSFailure(
                (namespaces.streams, "policy-violation"),
            ),
        ]

        base = unittest.mock.Mock()
        jid = unittest.mock.Mock()

        for i in range(NCONNECTORS):
            connect = CoroutineMock()
            getattr(base, "c{}".format(i)).connect = connect

        base.c0.connect.side_effect = excs[0]
        base.c1.connect.side_effect = excs[1]
        base.c2.connect.side_effect = excs[2]

        self.discover_connectors.return_value = [
            (getattr(unittest.mock.sentinel, "h{}".format(i)),
             getattr(unittest.mock.sentinel, "p{}".format(i)),
             getattr(base, "c{}".format(i)))
            for i in range(NCONNECTORS)
        ]

        with self.assertRaises(errors.MultiOSError) as exc_ctx:
            run_coroutine(node.connect_xmlstream(
                jid,
                base.metadata,
                loop=unittest.mock.sentinel.loop,
            ))

        self.discover_connectors.assert_called_with(
            jid.domain.encode(),
            loop=unittest.mock.sentinel.loop,
            logger=node.logger,
        )

        self.assertSequenceEqual(
            base.mock_calls,
            [
                getattr(unittest.mock.call, "c{}".format(i)).connect(
                    unittest.mock.sentinel.loop,
                    base.metadata,
                    jid.domain,
                    getattr(unittest.mock.sentinel, "h{}".format(i)),
                    getattr(unittest.mock.sentinel, "p{}".format(i)),
                    60.,
                )
                for i in range(3)
            ]
        )

        self.assertSequenceEqual(
            exc_ctx.exception.exceptions,
            excs,
        )

    def test_handle_no_options(self):
        base = unittest.mock.Mock()

        jid = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            discover_connectors = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.node.discover_connectors",
                    new=CoroutineMock(),
                )
            )
            discover_connectors.return_value = []

            with self.assertRaisesRegex(
                    ValueError,
                    "no options to connect to XMPP domain .+"):
                run_coroutine(node.connect_xmlstream(
                    jid,
                    base.metadata,
                ))


class TestAbstractClient(xmltestutils.XMLTestCase):
    @asyncio.coroutine
    def _connect_xmlstream(self, *args, **kwargs):
        self.connect_xmlstream_rec(*args, **kwargs)
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
        self.connect_xmlstream_rec = unittest.mock.MagicMock()
        self.failure_rec = unittest.mock.MagicMock()
        self.failure_rec.return_value = None
        self.established_rec = unittest.mock.MagicMock()
        self.established_rec.return_value = None
        self.destroyed_rec = unittest.mock.MagicMock()
        self.destroyed_rec.return_value = None
        self.security_layer = object()

        self.loop = asyncio.get_event_loop()
        self.patches = [
            unittest.mock.patch("aioxmpp.node.connect_xmlstream",
                                self._connect_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id)
        ]
        self.connect_xmlstream, _ = (patch.start()
                                     for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = nonza.StreamFeatures()
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
                nonza.SMEnable(resume=True),
                response=XMLStreamMock.Receive(
                    nonza.SMEnabled(resume=True,
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
                nonza.SMRequest()
            )
        ]

    def test_defaults(self):
        self.assertEqual(
            self.client.negotiation_timeout,
            timedelta(seconds=60)
        )
        self.assertEqual(
            self.client.local_jid.bare(),
            self.client.stream.local_jid
        )

    def test_setup(self):
        def peer_iterator():
            yield unittest.mock.sentinel.p1
            yield unittest.mock.sentinel.p2

        client = node.AbstractClient(
            self.test_jid,
            self.security_layer,
            override_peer=peer_iterator(),
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
        self.assertEqual(
            client.override_peer,
            [unittest.mock.sentinel.p1, unittest.mock.sentinel.p2],
        )

        self.assertEqual(client.on_stopped.logger,
                         client.logger.getChild("on_stopped"))
        self.assertEqual(client.on_failure.logger,
                         client.logger.getChild("on_failure"))
        self.assertEqual(client.on_stream_established.logger,
                         client.logger.getChild("on_stream_established"))
        self.assertEqual(client.on_stream_destroyed.logger,
                         client.logger.getChild("on_stream_destroyed"))

        with self.assertRaises(AttributeError):
            client.local_jid = structs.JID.fromstr("bar@bar.example/baz")

    def test_start(self):
        self.assertFalse(self.client.established)
        run_coroutine(asyncio.sleep(0))
        self.connect_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        self.connect_xmlstream_rec.assert_called_once_with(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop
        )

    def test_start_with_override_peer(self):
        self.assertFalse(self.client.established)
        self.client.override_peer = [
            unittest.mock.sentinel.p1,
            unittest.mock.sentinel.p2,
        ]
        run_coroutine(asyncio.sleep(0))
        self.connect_xmlstream_rec.assert_not_called()
        self.assertFalse(self.client.running)
        self.client.start()
        self.assertTrue(self.client.running)
        run_coroutine(self.xmlstream.run_test(self.resource_binding))
        self.connect_xmlstream_rec.assert_called_once_with(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=self.client.override_peer,
            loop=self.loop
        )

    def test_reject_start_twice(self):
        self.client.start()
        with self.assertRaisesRegex(RuntimeError,
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
        self.connect_xmlstream_rec.assert_not_called()
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

        iq = stanza.IQ("get")
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
                    override_peer=[],
                    loop=self.loop)
            ]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        # the client has not failed
        self.assertFalse(self.failure_rec.mock_calls)
        self.assertTrue(self.client.established)

    def test_fail_on_authentication_failure(self):
        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc
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
        self.connect_xmlstream_rec.side_effect = exc
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
            override_peer=[],
            loop=self.loop)

        exc = OSError()
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.01))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.02))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.04))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.08))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_exponential_backoff_on_no_nameservers(self):
        call = unittest.mock.call(
            self.test_jid,
            self.security_layer,
            negotiation_timeout=60.0,
            override_peer=[],
            loop=self.loop)

        exc = dns.resolver.NoNameservers()
        self.connect_xmlstream_rec.side_effect = exc
        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.stream.running)

        self.assertSequenceEqual(
            [call],
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.01))

        self.assertSequenceEqual(
            [call]*2,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.02))

        self.assertSequenceEqual(
            [call]*3,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.04))

        self.assertSequenceEqual(
            [call]*4,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.08))

        self.assertSequenceEqual(
            [call]*5,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*6,
            self.connect_xmlstream_rec.mock_calls
        )

        run_coroutine(asyncio.sleep(0.1))

        self.assertSequenceEqual(
            [call]*7,
            self.connect_xmlstream_rec.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.failure_rec.mock_calls
        )

        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_fail_on_value_error_while_live(self):

        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))
        run_coroutine(asyncio.sleep(0))

        exc = ValueError()
        self.client._stream_failure(exc)
        run_coroutine(asyncio.sleep(0))
        self.failure_rec.assert_called_with(exc)

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

    def test_fail_on_conflict_stream_error_while_live(self):
        self.client.backoff_start = timedelta(seconds=0.01)
        self.client.backoff_factor = 2
        self.client.backoff_cap = timedelta(seconds=0.1)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding
        ))
        run_coroutine(asyncio.sleep(0))

        exc = errors.StreamError(
            condition=(namespaces.streams, "conflict")
        )
        # stream would have been terminated normally, so we stop it manually
        # here
        self.client.stream._xmlstream_failed(exc)
        run_coroutine(asyncio.sleep(0))
        self.failure_rec.assert_called_with(exc)

        self.assertFalse(self.client.running)
        self.assertFalse(self.client.stream.running)

        # the XML stream is closed by the StanzaStream
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Close(),
        ]))

    def test_negotiate_stream_management(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding +
            self.sm_negotiation_exchange
        ))

        self.assertTrue(self.client.stream.sm_enabled)
        self.assertTrue(self.client.stream.running)
        self.assertTrue(self.client.running)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_negotiate_legacy_session(self):
        self.features[...] = rfc3921.SessionFeature()

        iqreq = stanza.IQ(type_="set")
        iqreq.payload = rfc3921.Session()
        iqreq.id_ = "autoset"

        iqresp = stanza.IQ(type_="result")
        iqresp.id_ = "autoset"

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding+
            [
                XMLStreamMock.Send(
                    iqreq,
                )
            ],
        ))

        self.assertFalse(self.client.established)

        run_coroutine(self.xmlstream.run_test(
            [
            ],
            stimulus=[
                XMLStreamMock.Receive(iqresp)
            ]
        ))

        run_coroutine(asyncio.sleep(0))

    def test_negotiate_legacy_session_after_stream_management(self):
        self.features[...] = rfc3921.SessionFeature()
        self.features[...] = nonza.StreamManagementFeature()

        iqreq = stanza.IQ(type_="set")
        iqreq.payload = rfc3921.Session()
        iqreq.id_ = "autoset"

        iqresp = stanza.IQ(type_="result")
        iqresp.id_ = "autoset"

        self.client.start()
        run_coroutine(self.xmlstream.run_test(
            self.resource_binding+
            self.sm_negotiation_exchange+
            [
                XMLStreamMock.Send(
                    iqreq,
                    response=[
                        XMLStreamMock.Receive(iqresp),
                    ]
                ),
                XMLStreamMock.Send(
                    nonza.SMRequest(),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMAcknowledgement(counter=1)
                        ),
                    ]
                )
            ],
        ))

        run_coroutine(asyncio.sleep(0))

        self.assertTrue(self.client.established)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=1)
            ),
            XMLStreamMock.Close()
        ]))

    def test_resume_stream_management(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        with contextlib.ExitStack() as stack:
            _resume_sm = stack.enter_context(
                unittest.mock.patch.object(self.client.stream, "_resume_sm"),
            )

            run_coroutine(self.xmlstream.run_test(self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(resume=True,
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
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

            _resume_sm.assert_called_once_with(0)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_stop_stream_management_if_remote_stops_providing_support(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
                                              id_="foobar"),

                    ),
                    XMLStreamMock.Fail(
                    exc=ConnectionError()
                    ),
                ]
            ),
        ]))
        # new xmlstream after failure

        del self.features[nonza.StreamManagementFeature]

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
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        with unittest.mock.patch("aioxmpp.connector.STARTTLSConnector") as C:
            C.return_value = unittest.mock.sentinel.connector
            run_coroutine(self.xmlstream.run_test([
            ]+self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(
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
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[],
                    negotiation_timeout=60.0,
                    loop=self.loop),
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        ("fe80::", 5222, unittest.mock.sentinel.connector)
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop),
            ],
            self.connect_xmlstream_rec.mock_calls
        )

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_sm_location_takes_precedence_over_override_peer(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()
        self.client.override_peer = [
            unittest.mock.sentinel.p1
        ]

        with unittest.mock.patch("aioxmpp.connector.STARTTLSConnector") as C:
            C.return_value = unittest.mock.sentinel.connector
            run_coroutine(self.xmlstream.run_test([
            ]+self.resource_binding+[
                XMLStreamMock.Send(
                    nonza.SMEnable(resume=True),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMEnabled(
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
                    nonza.SMResume(counter=0, previd="foobar"),
                    response=[
                        XMLStreamMock.Receive(
                            nonza.SMResumed(counter=0, previd="foobar")
                        )
                    ]
                )
            ]))

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        unittest.mock.sentinel.p1,
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop),
                unittest.mock.call(
                    self.test_jid,
                    self.security_layer,
                    override_peer=[
                        ("fe80::", 5222, unittest.mock.sentinel.connector),
                        unittest.mock.sentinel.p1,
                    ],
                    negotiation_timeout=60.0,
                    loop=self.loop),
            ],
            self.connect_xmlstream_rec.mock_calls
        )

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

    def test_degrade_to_non_sm_if_sm_fails(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMFailed(),
                    ),
                ]
            ),
        ]))

        run_coroutine(asyncio.sleep(0))

        self.assertFalse(self.client.stream.sm_enabled)

        self.established_rec.assert_called_once_with()
        self.assertFalse(self.destroyed_rec.mock_calls)

    def test_retry_sm_restart_if_sm_resumption_fails(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test([
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
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
                nonza.SMResume(counter=0, previd="foobar"),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMFailed()
                    )
                ]
            ),
        ]+self.resource_binding+[
            XMLStreamMock.Send(
                nonza.SMEnable(resume=True),
                response=[
                    XMLStreamMock.Receive(
                        nonza.SMEnabled(resume=True,
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

        self.client.stop()
        run_coroutine(self.xmlstream.run_test([
            XMLStreamMock.Send(
                nonza.SMAcknowledgement(counter=0)
            ),
            XMLStreamMock.Close()
        ]))

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
            ),
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

        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc

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
            [
            ],
            stimulus=XMLStreamMock.Fail(exc=ConnectionError())
        ))

        run_coroutine(asyncio.sleep(0))

        self.established_rec.assert_called_once_with()
        self.destroyed_rec.assert_called_once_with()
        self.assertFalse(self.client.established)

        # stop the client to avoid tearDown to wait for a close which isn’t
        # gonna happen
        self.client.stop()
        run_coroutine(asyncio.sleep(0))

    def test_signals_fire_correctly_on_fail_after_established_sm_connection(self):
        self.features[...] = nonza.StreamManagementFeature()

        self.client.backoff_start = timedelta(seconds=0)
        self.client.start()

        run_coroutine(self.xmlstream.run_test(
            self.resource_binding+
            self.sm_negotiation_exchange
        ))

        exc = aiosasl.AuthenticationFailure("not-authorized")
        self.connect_xmlstream_rec.side_effect = exc

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
            ORDER_BEFORE = [Svc1]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        class Svc3(service.Service):
            ORDER_BEFORE = [Svc2]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                getattr(svc_init, type(self).__name__)(*args, **kwargs)

        self.client.summon(Svc2)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc3(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.AbstractClient"
                    )
                ),
                unittest.mock.call.Svc2(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.AbstractClient"
                    )
                ),
            ],
            svc_init.mock_calls
        )

        svc_init.mock_calls.clear()

        self.client.summon(Svc3)

        self.assertSequenceEqual(
            [
            ],
            svc_init.mock_calls
        )

        svc_init.mock_calls.clear()

        self.client.summon(Svc1)

        self.assertSequenceEqual(
            [
                unittest.mock.call.Svc1(
                    self.client,
                    logger_base=logging.getLogger(
                        "aioxmpp.node.AbstractClient"
                    )
                ),
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
    def _connect_xmlstream(self, *args, **kwargs):
        self.connect_xmlstream_rec(*args, **kwargs)
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
        self.connect_xmlstream_rec = unittest.mock.MagicMock()
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
            unittest.mock.patch("aioxmpp.node.connect_xmlstream",
                                self._connect_xmlstream),
            unittest.mock.patch("aioxmpp.stanza.StanzaBase.autoset_id",
                                self._autoset_id),
        ]
        self.connect_xmlstream, _ = (patch.start()
                                     for patch in self.patches)
        self._xmlstream = XMLStreamMock(self, loop=self.loop)
        self.test_jid = structs.JID.fromstr("foo@bar.example/baz")
        self.features = nonza.StreamFeatures()
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

    def test_do_not_send_presence_if_unavailable(self):
        self.client.presence = structs.PresenceState(
            available=False
        )

        self.client.start()
        run_coroutine(asyncio.sleep(0))
        self.assertTrue(self.client.running)
        self.assertFalse(self.client.established)

        run_coroutine(
            self.xmlstream.run_test(self.resource_binding)
        )

        run_coroutine(asyncio.sleep(0.1))

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
        status_texts = {
            None: "generic",
            structs.LanguageTag.fromstr("de"): "de"
        }

        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status.update(status_texts)

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "stream",
                new=base.stream
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))

            self.client.set_presence(
                structs.PresenceState(
                    available=True,
                    show="chat"),
                status=status_texts
            )

            self.client.on_stream_established()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.stream.enqueue_stanza(unittest.mock.ANY)
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_with_single_string(self):
        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status[None] = "foobar"

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "stream",
                new=base.stream
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))

            self.client.set_presence(
                structs.PresenceState(
                    available=True,
                    show="chat"),
                status="foobar"
            )

            self.client.on_stream_established()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.stream.enqueue_stanza(unittest.mock.ANY)
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_set_presence_is_robust_against_modification_of_the_argument(self):
        status_texts = {
            None: "generic",
            structs.LanguageTag.fromstr("de"): "de",
        }

        expected = stanza.Presence(type_=None,
                                   show="chat",
                                   id_="autoset")
        expected.status.update(status_texts)

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "stream",
                new=base.stream
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.client,
                "start",
                new=base.start
            ))

            self.client.set_presence(
                structs.PresenceState(
                    available=True,
                    show="chat"),
                status=status_texts
            )

            del status_texts[None]

            self.client.on_stream_established()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.start(),
                unittest.mock.call.stream.enqueue_stanza(unittest.mock.ANY)
            ]
        )

        _, (sent,), _ = base.mock_calls[-1]

        self.assertDictEqual(
            sent.status,
            expected.status
        )
        self.assertEqual(sent.type_, expected.type_)
        self.assertEqual(sent.show, expected.show)

        self.presence_sent_rec.assert_called_once_with()

    def test_connected(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected()

        UseConnected.assert_called_with(self.client)

        self.assertEqual(result, UseConnected())

    def test_connected_kwargs(self):
        with unittest.mock.patch("aioxmpp.node.UseConnected") as UseConnected:
            result = self.client.connected(foo="bar", fnord=10)

        UseConnected.assert_called_with(
            self.client,
            foo="bar",
            fnord=10,
        )

        self.assertEqual(result, UseConnected())

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


class TestUseConnected(unittest.TestCase):
    def setUp(self):
        self.client = unittest.mock.Mock()
        self.client.presence = structs.PresenceState(False)
        self.client.established = False
        self.cm = node.UseConnected(self.client)

    def tearDown(self):
        del self.client

    def test_init(self):
        self.assertIsNone(self.cm.timeout)

        cm = node.UseConnected(
            self.client,
            timeout=timedelta(seconds=0.1),
            presence=structs.PresenceState(True, "away")
        )

        self.assertEqual(cm.timeout, timedelta(seconds=0.1))
        self.assertEqual(cm.presence, structs.PresenceState(True, "away"))

    def test_aenter_sets_presence(self):
        self.assertEqual(self.client.presence, structs.PresenceState(False))

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.assertEqual(self.client.presence, structs.PresenceState(True))

        task.cancel()

    def test_aenter_starts_client_directly_if_presence_is_unavailable(self):
        self.client.running = False

        self.cm.presence = structs.PresenceState(False)

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.client.start.assert_called_with()

        task.cancel()

    def test_aenter_starts_client_after_setting_presence(self):
        self.client.presence = unittest.mock.sentinel.foo

        self.client.running = False

        presence_at_start = None

        def check(*args, **kwargs):
            nonlocal presence_at_start
            presence_at_start = self.client.presence

        self.cm.presence = structs.PresenceState(False)

        self.client.start.side_effect = check

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.client.start.assert_called_with()

        self.assertEqual(
            presence_at_start,
            structs.PresenceState(False),
        )

        task.cancel()

    def test_aenter_sets_custom_presence(self):
        pres = structs.PresenceState(True, "away")
        self.cm.presence = pres

        self.assertEqual(self.client.presence, structs.PresenceState(False))

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.assertIs(self.client.presence, pres)

        task.cancel()

    def test_aenter_succeeds_and_returns_StanzaStream_on_presence_sent(self):
        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.assertFalse(task.done())

        self.client.on_presence_sent.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_presence_sent.AUTO_FUTURE,
        )

        _, (fut, _), _ = self.client.on_presence_sent.connect.mock_calls[0]

        fut.set_result(None)

        self.assertEqual(
            run_coroutine(task),
            self.client.stream
        )

    def test_aenter_re_raises_exception_from_on_failure(self):
        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.assertFalse(task.done())

        self.client.on_failure.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_failure.AUTO_FUTURE,
        )

        _, (fut, _), _ = self.client.on_failure.connect.mock_calls[0]

        class FooException(Exception):
            pass

        fut.set_exception(FooException())

        with self.assertRaises(FooException):
            run_coroutine(task)

    def test_aenter_does_not_wait_if_established(self):
        self.client.established = True

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        self.assertTrue(task.done())

        self.assertEqual(
            run_coroutine(task),
            self.client.stream
        )

    def test_aenter_times_out(self):
        self.cm.timeout = timedelta(seconds=0)

        with self.assertRaises(TimeoutError):
            run_coroutine(self.cm.__aenter__())

    def test_aenter_cancels_futures_stops_stream_and_resets_presence_on_timeout(self):
        self.cm.timeout = timedelta(seconds=0.1)

        task = asyncio.async(self.cm.__aenter__())
        run_coroutine(asyncio.sleep(0.01))

        _, (fut1, _), _ = self.client.on_presence_sent.connect.mock_calls[0]
        _, (fut2, _), _ = self.client.on_failure.connect.mock_calls[0]

        self.assertEqual(fut1, fut2)

        with self.assertRaises(TimeoutError):
            run_coroutine(task)

        self.assertTrue(fut1.cancelled())
        self.assertTrue(fut2.cancelled())

        self.client.stop.assert_called_with()
        self.assertEqual(self.client.presence, structs.PresenceState(False))

    def test_aexit_sets_presence_to_unavailable(self):
        self.client.established = True
        self.client.presence = structs.PresenceState(True)

        task = asyncio.async(self.cm.__aexit__(None, None, None))
        run_coroutine(asyncio.sleep(0.01))

        self.assertEqual(self.client.presence, structs.PresenceState(False))

        task.cancel()

    def test_aexit_waits_for_stopped_or_failed(self):
        self.client.established = True
        self.client.presence = structs.PresenceState(True)

        task = asyncio.async(self.cm.__aexit__(None, None, None))
        run_coroutine(asyncio.sleep(0.01))

        self.client.on_stopped.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_stopped.AUTO_FUTURE,
        )

        self.client.on_failure.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_failure.AUTO_FUTURE,
        )

        _, (fut1, _), _ = self.client.on_stopped.connect.mock_calls[0]
        _, (fut2, _), _ = self.client.on_failure.connect.mock_calls[0]

        self.assertEqual(fut1, fut2)

        fut1.set_result(None)

        self.assertFalse(run_coroutine(task))

    def test_aexit_re_raises_failure(self):
        self.client.established = True
        self.client.presence = structs.PresenceState(True)

        task = asyncio.async(self.cm.__aexit__(None, None, None))
        run_coroutine(asyncio.sleep(0.01))

        self.client.on_stopped.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_stopped.AUTO_FUTURE,
        )

        self.client.on_failure.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_failure.AUTO_FUTURE,
        )

        _, (fut1, _), _ = self.client.on_stopped.connect.mock_calls[0]
        _, (fut2, _), _ = self.client.on_failure.connect.mock_calls[0]

        class FooException(Exception):
            pass

        fut1.set_exception(FooException())

        with self.assertRaises(FooException):
            run_coroutine(task)

    def test_aexit_swallows_failure_in_exception_context(self):
        self.client.established = True
        self.client.presence = structs.PresenceState(True)

        task = asyncio.async(self.cm.__aexit__(
            unittest.mock.sentinel.exc_type,
            unittest.mock.sentinel.exc_value,
            unittest.mock.sentinel.exc_traceback,
        ))
        run_coroutine(asyncio.sleep(0.01))

        self.client.on_stopped.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_stopped.AUTO_FUTURE,
        )

        self.client.on_failure.connect.assert_called_with(
            unittest.mock.ANY,
            self.client.on_failure.AUTO_FUTURE,
        )

        _, (fut1, _), _ = self.client.on_stopped.connect.mock_calls[0]
        _, (fut2, _), _ = self.client.on_failure.connect.mock_calls[0]

        class FooException(Exception):
            pass

        fut1.set_exception(FooException())

        self.assertFalse(run_coroutine(task))

    def test_aexit_does_not_wait_if_not_established(self):
        self.client.established = False
        self.client.presence = structs.PresenceState(True)

        self.assertFalse(run_coroutine(self.cm.__aexit__(None, None, None)))

        self.assertEqual(self.client.presence, structs.PresenceState(False))
