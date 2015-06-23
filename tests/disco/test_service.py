import unittest

import aioxmpp.service as service
import aioxmpp.disco.service as disco_service
import aioxmpp.disco.xso as disco_xso
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces

from ..testutils import (
    make_connected_client,
    run_coroutine,
)


class TestIdentity(unittest.TestCase):
    def setUp(self):
        self.id_ = disco_service.Identity()

    def test_default_name(self):
        self.assertIsNone(self.id_.default_name)
        self.id_.default_name = "foobar"

    def test_name_map_is_LanguageMap(self):
        self.assertIsInstance(
            self.id_.names,
            structs.LanguageMap
        )


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = disco_service.Service(self.cc)
        self.cc.reset_mock()

        self.request_iq = stanza.IQ(
            from_=structs.JID.fromstr("user@foo.example/res1"),
            to=structs.JID.fromstr("user@bar.example/res2"))
        self.request_iq.autoset_id()
        self.request_iq.payload = disco_xso.InfoQuery()

    def test_is_Service_subclass(self):
        self.assertTrue(issubclass(
            disco_service.Service,
            service.Service))

    def test_setup(self):
        cc = make_connected_client()
        s = disco_service.Service(cc)

        self.assertSequenceEqual(
            [
                unittest.mock.call.stream.register_iq_request_coro(
                    "get",
                    disco_xso.InfoQuery,
                    s.handle_request
                ),
            ],
            cc.mock_calls
        )

    def test_shutdown(self):
        run_coroutine(self.s.shutdown())
        self.assertSequenceEqual(
            [
                unittest.mock.call.stream.unregister_iq_request_coro(
                    "get",
                    disco_xso.InfoQuery
                )
            ],
            self.cc.mock_calls
        )

    def test_default_response(self):
        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {namespaces.xep0030_info},
            set(item.var for item in response.features)
        )

        self.assertSetEqual(
            {
                ("client", "bot",
                 "aioxmpp default identity",
                 structs.LanguageTag.fromstr("en")),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

        self.assertFalse(response.node)

    def test_nonexistant_node_response(self):
        self.request_iq.payload.node = "foobar"
        with self.assertRaises(errors.XMPPCancelError) as ctx:
            run_coroutine(self.s.handle_request(self.request_iq))

        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            ctx.exception.condition
        )

    def test_register_feature_produces_it_in_response(self):
        self.s.register_feature("uri:foo")
        self.s.register_feature("uri:bar")

        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {"uri:foo", "uri:bar", namespaces.xep0030_info},
            set(item.var for item in response.features)
        )

    def test_unregister_feature_removes_it_from_response(self):
        self.s.register_feature("uri:foo")
        self.s.register_feature("uri:bar")

        self.s.unregister_feature("uri:bar")

        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {"uri:foo", namespaces.xep0030_info},
            set(item.var for item in response.features)
        )

    def test_unregister_feature_raises_KeyError_if_feature_has_not_been_registered(self):
        with self.assertRaisesRegexp(KeyError, "uri:foo"):
            self.s.unregister_feature("uri:foo")

    def test_unregister_feature_disallows_unregistering_disco_info_feature(self):
        with self.assertRaises(KeyError):
            self.s.unregister_feature(namespaces.xep0030_info)

    def test_register_identity_produces_it_in_response_and_replaces_default(self):
        self.s.register_identity(
            "client", "pc"
        )
        self.s.register_identity(
            "hierarchy", "branch"
        )

        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
                ("hierarchy", "branch", None, None),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_unregister_identity_removes_it_from_response(self):
        self.s.register_identity(
            "client", "pc"
        )
        self.s.register_identity(
            "hierarchy", "branch"
        )

        self.s.unregister_identity("hierarchy", "branch")

        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_unregister_identity_raises_KeyError_if_not_registered(self):
        with self.assertRaisesRegexp(KeyError, r"\('client', 'pc'\)"):
            self.s.unregister_identity("client", "pc")

    def test_unregister_identity_disallows_unregistering_default_identity(self):
        with self.assertRaisesRegexp(KeyError, r"\('client', 'bot'\)"):
            self.s.unregister_identity("client", "bot")

    def test_register_identity_returns_Identity(self):
        identity = self.s.register_identity("client", "pc")
        identity.names[structs.LanguageTag.fromstr("de")] = "Testidentität"
        identity.names[structs.LanguageTag.fromstr("en")] = "test identity"

        response = run_coroutine(self.s.handle_request(self.request_iq))

        self.assertSetEqual(
            {
                ("client", "pc",
                 "test identity",
                 structs.LanguageTag.fromstr("en")),
                ("client", "pc",
                 "Testidentität",
                 structs.LanguageTag.fromstr("de")),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_register_identity_disallows_duplicates(self):
        self.s.register_identity("client", "pc")
        with self.assertRaisesRegexp(ValueError, "identity already claimed"):
            self.s.register_identity("client", "pc")

    def test_register_feature_disallows_duplicates(self):
        self.s.register_feature("uri:foo")
        with self.assertRaisesRegexp(ValueError, "feature already claimed"):
            self.s.register_feature("uri:foo")
        with self.assertRaisesRegexp(ValueError, "feature already claimed"):
            self.s.register_feature(namespaces.xep0030_info)

    def test_query_info(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(
            self.s.query_info(to)
        )

        self.assertIs(result, response)
        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        # call[1] are args
        request_iq, = call[1]

        self.assertEqual(
            to,
            request_iq.to
        )
        self.assertEqual(
            "get",
            request_iq.type_
        )
        self.assertIsInstance(request_iq.payload, disco_xso.InfoQuery)
        self.assertFalse(request_iq.payload.features)
        self.assertFalse(request_iq.payload.identities)
        self.assertIsNone(request_iq.payload.node)

    def test_query_info_with_node(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        with self.assertRaises(TypeError):
            self.s.query_info(to, "foobar")

        result = run_coroutine(
            self.s.query_info(to, node="foobar")
        )

        self.assertIs(result, response)
        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

        call, = self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        # call[1] are args
        request_iq, = call[1]

        self.assertEqual(
            to,
            request_iq.to
        )
        self.assertEqual(
            "get",
            request_iq.type_
        )
        self.assertIsInstance(request_iq.payload, disco_xso.InfoQuery)
        self.assertFalse(request_iq.payload.features)
        self.assertFalse(request_iq.payload.identities)
        self.assertEqual("foobar", request_iq.payload.node)

    def test_query_info_caches(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        with self.assertRaises(TypeError):
            self.s.query_info(to, "foobar")

        result1 = run_coroutine(
            self.s.query_info(to, node="foobar")
        )
        result2 = run_coroutine(
            self.s.query_info(to, node="foobar")
        )

        self.assertIs(result1, response)
        self.assertIs(result2, response)

        self.assertEqual(
            1,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

    def test_query_info_cache_override(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        response1 = disco_xso.InfoQuery()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response1

        with self.assertRaises(TypeError):
            self.s.query_info(to, "foobar")

        result1 = run_coroutine(
            self.s.query_info(to, node="foobar")
        )

        response2 = disco_xso.InfoQuery()
        self.cc.stream.send_iq_and_wait_for_reply.return_value = response2

        result2 = run_coroutine(
            self.s.query_info(to, node="foobar", require_fresh=True)
        )

        self.assertIs(result1, response1)
        self.assertIs(result2, response2)

        self.assertEqual(
            2,
            len(self.cc.stream.send_iq_and_wait_for_reply.mock_calls)
        )

    def test_query_info_timeout(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        result = run_coroutine(
            self.s.query_info(to, timeout=10)
        )

        self.assertIs(result, response)
        self.assertSequenceEqual(
            [
                unittest.mock.call(unittest.mock.ANY, timeout=10),
            ],
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        )
