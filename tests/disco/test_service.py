########################################################################
# File name: test_service.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio
import contextlib
import unittest
import sys

import aioxmpp.service as service
import aioxmpp.disco.service as disco_service
import aioxmpp.disco.xso as disco_xso
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
)


TEST_JID = structs.JID.fromstr("foo@bar.example")


class TestNode(unittest.TestCase):
    def test_init(self):
        n = disco_service.Node()
        self.assertSequenceEqual(
            [],
            list(n.iter_identities(unittest.mock.sentinel.stanza))
        )
        self.assertSetEqual(
            {namespaces.xep0030_info},
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )
        self.assertSequenceEqual(
            [],
            list(n.iter_items(unittest.mock.sentinel.stanza))
        )

    def test_register_feature_adds_the_feature(self):
        n = disco_service.Node()
        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_feature("uri:foo")

        self.assertSetEqual(
            {
                "uri:foo",
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        cb.assert_called_with()

    def test_iter_features_works_without_argument(self):
        n = disco_service.Node()
        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_feature("uri:foo")

        self.assertSetEqual(
            {
                "uri:foo",
                namespaces.xep0030_info
            },
            set(n.iter_features())
        )

        cb.assert_called_with()

    def test_register_feature_prohibits_duplicate_registration(self):
        n = disco_service.Node()
        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_feature("uri:bar")
        cb.mock_calls.clear()

        with self.assertRaisesRegex(ValueError,
                                    "feature already claimed"):
            n.register_feature("uri:bar")

        self.assertSetEqual(
            {
                "uri:bar",
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        self.assertFalse(cb.mock_calls)

    def test_register_feature_prohibits_registration_of_xep0030_features(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        with self.assertRaisesRegex(ValueError,
                                    "feature already claimed"):
            n.register_feature(namespaces.xep0030_info)

        self.assertFalse(cb.mock_calls)

    def test_unregister_feature_removes_the_feature(self):
        n = disco_service.Node()
        n.register_feature("uri:foo")
        n.register_feature("uri:bar")

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        self.assertSetEqual(
            {
                "uri:foo",
                "uri:bar",
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        n.unregister_feature("uri:foo")

        cb.assert_called_with()
        cb.mock_calls.clear()

        self.assertSetEqual(
            {
                "uri:bar",
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        n.unregister_feature("uri:bar")

        self.assertSetEqual(
            {
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        cb.assert_called_with()
        cb.mock_calls.clear()

    def test_unregister_feature_prohibts_removal_of_nonexistant_feature(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        with self.assertRaises(KeyError):
            n.unregister_feature("uri:foo")

        self.assertFalse(cb.mock_calls)

    def test_unregister_feature_prohibts_removal_of_xep0030_features(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        with self.assertRaises(KeyError):
            n.unregister_feature(namespaces.xep0030_info)

        self.assertSetEqual(
            {
                namespaces.xep0030_info
            },
            set(n.iter_features(unittest.mock.sentinel.stanza))
        )

        self.assertFalse(cb.mock_calls)

    def test_register_identity_defines_identity(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_identity(
            "client", "pc"
        )

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
            },
            set(n.iter_identities(unittest.mock.sentinel.stanza))
        )

        cb.assert_called_with()

    def test_iter_identities_works_without_stanza(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_identity(
            "client", "pc"
        )

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
            },
            set(n.iter_identities())
        )

        cb.assert_called_with()

    def test_register_identity_prohibits_duplicate_registration(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_identity(
            "client", "pc"
        )

        cb.assert_called_with()
        cb.mock_calls.clear()

        with self.assertRaisesRegex(ValueError,
                                   "identity already claimed"):
            n.register_identity("client", "pc")

        self.assertFalse(cb.mock_calls)

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
            },
            set(n.iter_identities(unittest.mock.sentinel.stanza))
        )

    def test_register_identity_with_names(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_identity(
            "client", "pc",
            names={
                structs.LanguageTag.fromstr("en"): "test identity",
                structs.LanguageTag.fromstr("de"): "Testidentität",
            }
        )

        cb.assert_called_with()

        self.assertSetEqual(
            {
                ("client", "pc",
                 structs.LanguageTag.fromstr("en"), "test identity"),
                ("client", "pc",
                 structs.LanguageTag.fromstr("de"), "Testidentität"),
            },
            set(n.iter_identities(unittest.mock.sentinel.stanza))
        )

    def test_unregister_identity_prohibits_removal_of_last_identity(self):
        n = disco_service.Node()

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.register_identity(
            "client", "pc",
            names={
                structs.LanguageTag.fromstr("en"): "test identity",
                structs.LanguageTag.fromstr("de"): "Testidentität",
            }
        )

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        with self.assertRaisesRegex(ValueError,
                                    "cannot remove last identity"):
            n.unregister_identity(
                "client", "pc",
            )

        self.assertFalse(cb.mock_calls)

    def test_unregister_identity_prohibits_removal_of_undeclared_identity(
            self):
        n = disco_service.Node()

        n.register_identity(
            "client", "pc",
            names={
                structs.LanguageTag.fromstr("en"): "test identity",
                structs.LanguageTag.fromstr("de"): "Testidentität",
            }
        )

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        with self.assertRaises(KeyError):
            n.unregister_identity("foo", "bar")

        self.assertFalse(cb.mock_calls)

    def test_unregister_identity_removes_identity(self):
        n = disco_service.Node()

        n.register_identity(
            "client", "pc",
            names={
                structs.LanguageTag.fromstr("en"): "test identity",
                structs.LanguageTag.fromstr("de"): "Testidentität",
            }
        )

        n.register_identity(
            "foo", "bar"
        )

        self.assertSetEqual(
            {
                ("client", "pc",
                 structs.LanguageTag.fromstr("en"), "test identity"),
                ("client", "pc",
                 structs.LanguageTag.fromstr("de"), "Testidentität"),
                ("foo", "bar", None, None),
            },
            set(n.iter_identities(unittest.mock.sentinel.stanza))
        )

        cb = unittest.mock.Mock()
        n.on_info_changed.connect(cb)

        n.unregister_identity("foo", "bar")

        cb.assert_called_with()

        self.assertSetEqual(
            {
                ("client", "pc",
                 structs.LanguageTag.fromstr("en"), "test identity"),
                ("client", "pc",
                 structs.LanguageTag.fromstr("de"), "Testidentität"),
            },
            set(n.iter_identities(unittest.mock.sentinel.stanza))
        )

    def test_iter_items_works_without_argument(self):
        n = disco_service.Node()
        self.assertSequenceEqual(
            list(n.iter_items()),
            []
        )

    def test_as_info_xso(self):
        n = disco_service.Node()

        features = [
            "http://jabber.org/protocol/disco#info",
            unittest.mock.sentinel.f1,
            unittest.mock.sentinel.f2,
            unittest.mock.sentinel.f3,
        ]

        identities = [
            ("cat1", "t1",
             structs.LanguageTag.fromstr("lang-a"), "name11"),
            ("cat1", "t1",
             structs.LanguageTag.fromstr("lang-b"), "name12"),
            ("cat2", "t2", None, "name2"),
            ("cat3", "t3", None, None),
        ]

        with contextlib.ExitStack() as stack:
            iter_features = stack.enter_context(
                unittest.mock.patch.object(n, "iter_features")
            )
            iter_features.return_value = iter(features)

            iter_identities = stack.enter_context(
                unittest.mock.patch.object(n, "iter_identities")
            )
            iter_identities.return_value = iter(identities)

            iter_items = stack.enter_context(
                unittest.mock.patch.object(n, "iter_items")
            )

            result = n.as_info_xso()

        self.assertIsInstance(
            result,
            disco_xso.InfoQuery,
        )

        iter_items.assert_not_called()

        iter_features.assert_called_once_with(None)
        iter_identities.assert_called_once_with(None)

        self.assertSetEqual(
            result.features,
            set(features),
        )

        self.assertCountEqual(
            [
                (i.category, i.type_, i.lang, i.name)
                for i in result.identities
            ],
            identities,
        )

    def test_as_info_xso_with_stanza(self):
        n = disco_service.Node()

        features = [
            "http://jabber.org/protocol/disco#info",
            unittest.mock.sentinel.f1,
        ]

        identities = [
            ("cat1", "t1",
             structs.LanguageTag.fromstr("lang-a"), "name11"),
            ("cat1", "t1",
             structs.LanguageTag.fromstr("lang-b"), "name12"),
        ]

        with contextlib.ExitStack() as stack:
            iter_features = stack.enter_context(
                unittest.mock.patch.object(n, "iter_features")
            )
            iter_features.return_value = iter(features)

            iter_identities = stack.enter_context(
                unittest.mock.patch.object(n, "iter_identities")
            )
            iter_identities.return_value = iter(identities)

            iter_items = stack.enter_context(
                unittest.mock.patch.object(n, "iter_items")
            )

            result = n.as_info_xso(unittest.mock.sentinel.stanza)

        self.assertIsInstance(
            result,
            disco_xso.InfoQuery,
        )

        iter_items.assert_not_called()

        iter_features.assert_called_once_with(unittest.mock.sentinel.stanza)
        iter_identities.assert_called_once_with(unittest.mock.sentinel.stanza)

        self.assertSetEqual(
            result.features,
            set(features),
        )

        self.assertCountEqual(
            [
                (i.category, i.type_, i.lang, i.name)
                for i in result.identities
            ],
            identities,
        )


class TestStaticNode(unittest.TestCase):
    def setUp(self):
        self.n = disco_service.StaticNode()

    def test_is_Node(self):
        self.assertIsInstance(self.n, disco_service.Node)

    def test_add_items(self):
        item1 = disco_xso.Item(TEST_JID.replace(localpart="foo"))
        item2 = disco_xso.Item(TEST_JID.replace(localpart="bar"))
        self.n.items.append(item1)
        self.n.items.append(item2)

        self.assertSequenceEqual(
            [
                item1,
                item2
            ],
            list(self.n.iter_items(unittest.mock.sentinel.jid))
        )

    def test_iter_items_works_without_argument(self):
        self.assertSequenceEqual(
            list(self.n.iter_items()),
            []
        )

    def test_clone(self):
        other_node = unittest.mock.Mock([
            "iter_features",
            "iter_identities",
            "iter_items",
        ])

        features = [
            "http://jabber.org/protocol/disco#info",
            unittest.mock.sentinel.f1,
            unittest.mock.sentinel.f2,
            unittest.mock.sentinel.f3,
        ]

        identities = [
            (unittest.mock.sentinel.cat1, unittest.mock.sentinel.t1,
             unittest.mock.sentinel.lang11, unittest.mock.sentinel.name11),
            (unittest.mock.sentinel.cat1, unittest.mock.sentinel.t1,
             unittest.mock.sentinel.lang12, unittest.mock.sentinel.name12),
            (unittest.mock.sentinel.cat2, unittest.mock.sentinel.t2,
             None, unittest.mock.sentinel.name2),
            (unittest.mock.sentinel.cat3, unittest.mock.sentinel.t3,
             None, None),
        ]

        items = [
            unittest.mock.sentinel.item1,
            unittest.mock.sentinel.item2,
        ]

        other_node.iter_features.return_value = iter(features)
        other_node.iter_identities.return_value = iter(identities)
        other_node.iter_items.return_value = iter(items)

        n = disco_service.StaticNode.clone(other_node)

        self.assertIsInstance(n, disco_service.StaticNode)

        other_node.iter_features.assert_called_once_with()
        other_node.iter_identities.assert_called_once_with()
        other_node.iter_items.assert_called_once_with()

        self.assertCountEqual(
            features,
            list(n.iter_features()),
        )

        self.assertCountEqual(
            identities,
            list(n.iter_identities()),
        )

        self.assertCountEqual(
            items,
            list(n.iter_items()),
        )


class TestDiscoServer(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = disco_service.DiscoServer(self.cc)
        self.cc.reset_mock()

        self.request_iq = stanza.IQ(
            structs.IQType.GET,
            from_=structs.JID.fromstr("user@foo.example/res1"),
            to=structs.JID.fromstr("user@bar.example/res2"))
        self.request_iq.autoset_id()
        self.request_iq.payload = disco_xso.InfoQuery()

        self.request_items_iq = stanza.IQ(
            structs.IQType.GET,
            from_=structs.JID.fromstr("user@foo.example/res1"),
            to=structs.JID.fromstr("user@bar.example/res2"))
        self.request_items_iq.autoset_id()
        self.request_items_iq.payload = disco_xso.ItemsQuery()

    def test_is_Service_subclass(self):
        self.assertTrue(issubclass(
            disco_service.DiscoServer,
            service.Service))

    def test_setup(self):
        cc = make_connected_client()
        s = disco_service.DiscoServer(cc)

        self.assertCountEqual(
            [
                unittest.mock.call.stream.register_iq_request_handler(
                    structs.IQType.GET,
                    disco_xso.InfoQuery,
                    s.handle_info_request
                ),
                unittest.mock.call.stream.register_iq_request_handler(
                    structs.IQType.GET,
                    disco_xso.ItemsQuery,
                    s.handle_items_request
                )
            ],
            cc.mock_calls
        )

    def test_shutdown(self):
        run_coroutine(self.s.shutdown())
        self.assertCountEqual(
            [
                unittest.mock.call.stream.unregister_iq_request_handler(
                    structs.IQType.GET,
                    disco_xso.InfoQuery
                ),
                unittest.mock.call.stream.unregister_iq_request_handler(
                    structs.IQType.GET,
                    disco_xso.ItemsQuery
                ),
            ],
            self.cc.mock_calls
        )

    def test_handle_info_request_is_decorated(self):
        self.assertTrue(
            service.is_iq_handler(
                structs.IQType.GET,
                disco_xso.InfoQuery,
                disco_service.DiscoServer.handle_info_request,
            )
        )

    def test_handle_items_request_is_decorated(self):
        self.assertTrue(
            service.is_iq_handler(
                structs.IQType.GET,
                disco_xso.ItemsQuery,
                disco_service.DiscoServer.handle_items_request,
            )
        )

    def test_default_response(self):
        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {namespaces.xep0030_info},
            response.features,
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
        with self.assertRaises(errors.XMPPModifyError) as ctx:
            run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            ctx.exception.condition
        )

    def test_register_feature_produces_it_in_response(self):
        self.s.register_feature("uri:foo")
        self.s.register_feature("uri:bar")

        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {"uri:foo", "uri:bar", namespaces.xep0030_info},
            response.features,
        )

    def test_unregister_feature_removes_it_from_response(self):
        self.s.register_feature("uri:foo")
        self.s.register_feature("uri:bar")

        self.s.unregister_feature("uri:bar")

        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {"uri:foo", namespaces.xep0030_info},
            response.features
        )

    def test_unregister_feature_raises_KeyError_if_feature_has_not_been_registered(self):
        with self.assertRaisesRegex(KeyError, "uri:foo"):
            self.s.unregister_feature("uri:foo")

    def test_unregister_feature_disallows_unregistering_disco_info_feature(self):
        with self.assertRaises(KeyError):
            self.s.unregister_feature(namespaces.xep0030_info)

    def test_register_identity_produces_it_in_response(self):
        self.s.register_identity(
            "client", "pc"
        )
        self.s.register_identity(
            "hierarchy", "branch"
        )

        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
                ("hierarchy", "branch", None, None),
                ("client", "bot", "aioxmpp default identity",
                 structs.LanguageTag.fromstr("en")),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_unregister_identity_removes_it_from_response(self):
        self.s.register_identity(
            "client", "pc"
        )

        self.s.unregister_identity("client", "bot")

        self.s.register_identity(
            "hierarchy", "branch"
        )

        self.s.unregister_identity("hierarchy", "branch")

        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {
                ("client", "pc", None, None),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_unregister_identity_raises_KeyError_if_not_registered(self):
        with self.assertRaisesRegex(KeyError, r"\('client', 'pc'\)"):
            self.s.unregister_identity("client", "pc")

    def test_register_identity_with_names(self):
        self.s.register_identity(
            "client", "pc",
            names={
                structs.LanguageTag.fromstr("en"): "test identity",
                structs.LanguageTag.fromstr("de"): "Testidentität",
            }
        )

        self.s.unregister_identity("client", "bot")

        response = run_coroutine(self.s.handle_info_request(self.request_iq))

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
        with self.assertRaisesRegex(ValueError, "identity already claimed"):
            self.s.register_identity("client", "pc")

    def test_register_feature_disallows_duplicates(self):
        self.s.register_feature("uri:foo")
        with self.assertRaisesRegex(ValueError, "feature already claimed"):
            self.s.register_feature("uri:foo")
        with self.assertRaisesRegex(ValueError, "feature already claimed"):
            self.s.register_feature(namespaces.xep0030_info)

    def test_mount_node_produces_response(self):
        node = disco_service.StaticNode()
        node.register_identity("hierarchy", "leaf")

        self.s.mount_node("foo", node)

        self.request_iq.payload.node = "foo"
        response = run_coroutine(self.s.handle_info_request(self.request_iq))

        self.assertSetEqual(
            {
                ("hierarchy", "leaf", None, None),
            },
            set((item.category, item.type_,
                 item.name, item.lang) for item in response.identities)
        )

    def test_mount_node_without_identity_produces_item_not_found(self):
        node = disco_service.StaticNode()

        self.s.mount_node("foo", node)

        self.request_iq.payload.node = "foo"
        with self.assertRaises(errors.XMPPModifyError):
            run_coroutine(self.s.handle_info_request(self.request_iq))

    def test_unmount_node(self):
        node = disco_service.StaticNode()
        node.register_identity("hierarchy", "leaf")

        self.s.mount_node("foo", node)

        self.s.unmount_node("foo")

        self.request_iq.payload.node = "foo"
        with self.assertRaises(errors.XMPPModifyError):
            run_coroutine(self.s.handle_info_request(self.request_iq))

    def test_default_items_response(self):
        response = run_coroutine(
            self.s.handle_items_request(self.request_items_iq)
        )
        self.assertIsInstance(response, disco_xso.ItemsQuery)
        self.assertSequenceEqual(
            [],
            response.items
        )

    def test_items_query_returns_item_not_found_for_unknown_node(self):
        self.request_items_iq.payload.node = "foobar"
        with self.assertRaises(errors.XMPPModifyError):
            run_coroutine(
                self.s.handle_items_request(self.request_items_iq)
            )

    def test_items_query_returns_items_of_mounted_node(self):
        item1 = disco_xso.Item(TEST_JID.replace(localpart="foo"))
        item2 = disco_xso.Item(TEST_JID.replace(localpart="bar"))

        node = disco_service.StaticNode()
        node.register_identity("hierarchy", "leaf")
        node.items.append(item1)
        node.items.append(item2)

        self.s.mount_node("foo", node)

        self.request_items_iq.payload.node = "foo"
        response = run_coroutine(
            self.s.handle_items_request(self.request_items_iq)
        )

        self.assertSequenceEqual(
            [item1, item2],
            response.items
        )

    def test_items_query_forwards_stanza(self):
        node = unittest.mock.Mock()
        node.iter_items.return_value = iter([])

        self.s.mount_node("foo", node)

        self.request_items_iq.payload.node = "foo"
        run_coroutine(
            self.s.handle_items_request(self.request_items_iq)
        )

        node.iter_items.assert_called_once_with(
            self.request_items_iq
        )

    def test_info_query_forwards_stanza(self):
        node = unittest.mock.Mock()

        self.s.mount_node("foo", node)
        self.request_iq.payload.node = "foo"

        result = run_coroutine(
            self.s.handle_info_request(self.request_iq)
        )

        node.as_info_xso.assert_called_once_with(
            self.request_iq
        )

        self.assertEqual(result, node.as_info_xso())

    def test_info_query_sets_node(self):
        node = unittest.mock.Mock()

        self.s.mount_node("foo", node)
        self.request_iq.payload.node = "foo"

        result = run_coroutine(
            self.s.handle_info_request(self.request_iq)
        )

        node.as_info_xso.assert_called_once_with(
            self.request_iq
        )

        self.assertEqual(result.node, "foo")
        self.assertEqual(result, node.as_info_xso())


class TestDiscoClient(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = disco_service.DiscoClient(self.cc)
        self.cc.reset_mock()

        self.request_iq = stanza.IQ(
            structs.IQType.GET,
            from_=structs.JID.fromstr("user@foo.example/res1"),
            to=structs.JID.fromstr("user@bar.example/res2"))
        self.request_iq.autoset_id()
        self.request_iq.payload = disco_xso.InfoQuery()

        self.request_items_iq = stanza.IQ(
            structs.IQType.GET,
            from_=structs.JID.fromstr("user@foo.example/res1"),
            to=structs.JID.fromstr("user@bar.example/res2"))
        self.request_items_iq.autoset_id()
        self.request_items_iq.payload = disco_xso.ItemsQuery()

    def test_is_Service_subclass(self):
        self.assertTrue(issubclass(
            disco_service.DiscoClient,
            service.Service))

    def test_send_and_decode_info_query(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        node = "foobar"
        response = disco_xso.InfoQuery()

        self.cc.send.return_value = response

        result = run_coroutine(
            self.s.send_and_decode_info_query(to, node)
        )

        self.assertEqual(result, response)

        self.assertEqual(
            1,
            len(self.cc.send.mock_calls)
        )

        call, = self.cc.send.mock_calls
        # call[1] are args
        request_iq, = call[1]

        self.assertEqual(
            to,
            request_iq.to
        )
        self.assertEqual(
            structs.IQType.GET,
            request_iq.type_
        )
        self.assertIsInstance(request_iq.payload, disco_xso.InfoQuery)
        self.assertFalse(request_iq.payload.features)
        self.assertFalse(request_iq.payload.identities)
        self.assertIs(request_iq.payload.node, node)

    def test_uses_LRUDict(self):
        with contextlib.ExitStack() as stack:
            LRUDict = stack.enter_context(unittest.mock.patch(
                "aioxmpp.cache.LRUDict",
                new=unittest.mock.MagicMock()
            ))

            self.s = disco_service.DiscoClient(self.cc)

        self.assertCountEqual(
            LRUDict.mock_calls,
            [
                unittest.mock.call(),
                unittest.mock.call(),
            ]
        )

        LRUDict().__getitem__.side_effect = KeyError

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:

            run_coroutine(
                self.s.query_info(unittest.mock.sentinel.jid,
                                  node=unittest.mock.sentinel.node)
            )

        LRUDict().__setitem__.assert_called_once_with(
            (unittest.mock.sentinel.jid, unittest.mock.sentinel.node),
            unittest.mock.ANY,
        )
        LRUDict().__setitem__.reset_mock()

        run_coroutine(
            self.s.query_items(TEST_JID,
                               node="some node")
        )

        LRUDict().__setitem__.assert_called_once_with(
            (TEST_JID, "some node"),
            unittest.mock.ANY,
        )

    def test_info_cache_size(self):
        self.assertEqual(
            self.s.info_cache_size,
            10000,
        )

        self.assertEqual(
            self.s.info_cache_size,
            self.s._info_pending.maxsize,
        )

    def test_info_cache_size_is_settable(self):
        self.s.info_cache_size = 5

        self.assertEqual(
            self.s.info_cache_size,
            5,
        )

        self.assertEqual(
            self.s._info_pending.maxsize,
            self.s.info_cache_size,
        )

    def test_items_cache_size(self):
        self.assertEqual(
            self.s.items_cache_size,
            100,
        )

        self.assertEqual(
            self.s.items_cache_size,
            self.s._items_pending.maxsize,
        )

    def test_items_cache_size_is_settable(self):
        self.s.items_cache_size = 5

        self.assertEqual(
            self.s.items_cache_size,
            5,
        )

        self.assertEqual(
            self.s._items_pending.maxsize,
            self.s.items_cache_size,
        )

    def test_query_info(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            result = run_coroutine(
                self.s.query_info(to)
            )

        send_and_decode.assert_called_with(to, None)
        self.assertIs(response, result)

    def test_query_response_leads_to_signal_emission(self):
        handler = unittest.mock.Mock()
        handler.return_value = None

        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            self.s.on_info_result.connect(handler)

            run_coroutine(
                self.s.query_info(to)
            )

        handler.assert_called_with(to, None, response)

    def test_query_response_for_node_leads_to_signal_emission(self):
        handler = unittest.mock.Mock()
        handler.return_value = None

        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            self.s.on_info_result.connect(handler)

            run_coroutine(
                self.s.query_info(to, node="foo")
            )

        handler.assert_called_with(to, "foo", response)

    def test_query_info_with_node(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with self.assertRaises(TypeError):
            self.s.query_info(to, "foobar")

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            result = run_coroutine(
                self.s.query_info(to, node="foobar")
            )

        send_and_decode.assert_called_with(to, "foobar")
        self.assertIs(result, response)

    def test_query_info_caches(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

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
            len(send_and_decode.mock_calls)
        )

    def test_query_info_does_not_cache_if_no_cache_is_false(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            result1 = run_coroutine(
                self.s.query_info(to, node="foobar", no_cache=True)
            )
            result2 = run_coroutine(
                self.s.query_info(to, node="foobar")
            )

            self.assertIs(result1, response)
            self.assertIs(result2, response)

        self.assertEqual(
            2,
            len(send_and_decode.mock_calls)
        )

    def test_query_info_with_no_cache_uses_cached_result(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = {}

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.return_value = response

            result1 = run_coroutine(
                self.s.query_info(to, node="foobar")
            )
            result2 = run_coroutine(
                self.s.query_info(to, node="foobar", no_cache=True)
            )

            self.assertIs(result1, response)
            self.assertIs(result2, response)

        self.assertEqual(
            1,
            len(send_and_decode.mock_calls)
        )

    def test_query_info_reraises_and_aliases_exception(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        ncall = 0

        @asyncio.coroutine
        def mock(*args, **kwargs):
            nonlocal ncall
            ncall += 1
            if ncall == 1:
                raise errors.XMPPCancelError(
                    condition=(namespaces.stanzas, "feature-not-implemented"),
                )
            else:
                raise ConnectionError()

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=mock):

            task1 = asyncio.async(
                self.s.query_info(to, node="foobar")
            )
            task2 = asyncio.async(
                self.s.query_info(to, node="foobar")
            )

            with self.assertRaises(errors.XMPPCancelError):
                run_coroutine(task1)

            with self.assertRaises(errors.XMPPCancelError):
                run_coroutine(task2)

    def test_query_info_reraises_but_does_not_cache_exception(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            send_and_decode.side_effect = errors.XMPPCancelError(
                condition=(namespaces.stanzas, "feature-not-implemented"),
            )

            with self.assertRaises(errors.XMPPCancelError):
                run_coroutine(
                    self.s.query_info(to, node="foobar")
                )

            send_and_decode.side_effect = ConnectionError()

            with self.assertRaises(ConnectionError):
                run_coroutine(
                    self.s.query_info(to, node="foobar")
                )

    def test_query_info_cache_override(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            response1 = {}

            send_and_decode.return_value = response1

            result1 = run_coroutine(
                self.s.query_info(to, node="foobar")
            )

            response2 = {}
            send_and_decode.return_value = response2

            result2 = run_coroutine(
                self.s.query_info(to, node="foobar", require_fresh=True)
            )

        self.assertIs(result1, response1)
        self.assertIs(result2, response2)

        self.assertEqual(
            2,
            len(send_and_decode.mock_calls)
        )

    def test_query_info_cache_clears_on_disconnect(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            response1 = {}

            send_and_decode.return_value = response1

            result1 = run_coroutine(
                self.s.query_info(to, node="foobar")
            )

            self.cc.on_stream_destroyed()

            response2 = {}
            send_and_decode.return_value = response2

            result2 = run_coroutine(
                self.s.query_info(to, node="foobar")
            )

        self.assertIs(result1, response1)
        self.assertIs(result2, response2)

        self.assertEqual(
            2,
            len(send_and_decode.mock_calls)
        )

    def test_query_info_timeout(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            response = {}

            send_and_decode.delay = 1
            send_and_decode.return_value = response

            with self.assertRaises(TimeoutError):
                result = run_coroutine(
                    self.s.query_info(to, timeout=0.01)
                )

                self.assertSequenceEqual(
                    [
                        unittest.mock.call(to, None),
                    ],
                    send_and_decode.mock_calls
                )

    def test_query_info_deduplicate_requests(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            response = {}

            send_and_decode.return_value = response

            result = run_coroutine(
                asyncio.gather(
                    self.s.query_info(to, timeout=10),
                    self.s.query_info(to, timeout=10),
                )
            )

            self.assertIs(result[0], response)
            self.assertIs(result[1], response)

        self.assertSequenceEqual(
            [
                unittest.mock.call(to, None),
            ],
            send_and_decode.mock_calls
        )

    def test_query_info_transparent_deduplication_when_cancelled(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.InfoQuery()

        with unittest.mock.patch.object(
                self.s,
                "send_and_decode_info_query",
                new=CoroutineMock()) as send_and_decode:
            response = {}

            send_and_decode.return_value = response
            send_and_decode.delay = 0.1

            q1 = asyncio.async(self.s.query_info(to))
            q2 = asyncio.async(self.s.query_info(to))

            run_coroutine(asyncio.sleep(0.05))

            q1.cancel()

            result = run_coroutine(q2)

        self.assertIs(result, response)

        self.assertSequenceEqual(
            [
                unittest.mock.call(to, None),
                unittest.mock.call(to, None),
            ],
            send_and_decode.mock_calls
        )

    def test_query_items(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.return_value = response

        result = run_coroutine(
            self.s.query_items(to)
        )

        self.assertIs(result, response)
        self.assertEqual(
            1,
            len(self.cc.send.mock_calls)
        )

        call, = self.cc.send.mock_calls
        # call[1] are args
        request_iq, = call[1]

        self.assertEqual(
            to,
            request_iq.to
        )
        self.assertEqual(
            structs.IQType.GET,
            request_iq.type_
        )
        self.assertIsInstance(request_iq.payload, disco_xso.ItemsQuery)
        self.assertFalse(request_iq.payload.items)
        self.assertIsNone(request_iq.payload.node)

    def test_query_items_with_node(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.return_value = response

        with self.assertRaises(TypeError):
            self.s.query_items(to, "foobar")

        result = run_coroutine(
            self.s.query_items(to, node="foobar")
        )

        self.assertIs(result, response)
        self.assertEqual(
            1,
            len(self.cc.send.mock_calls)
        )

        call, = self.cc.send.mock_calls
        # call[1] are args
        request_iq, = call[1]

        self.assertEqual(
            to,
            request_iq.to
        )
        self.assertEqual(
            structs.IQType.GET,
            request_iq.type_
        )
        self.assertIsInstance(request_iq.payload, disco_xso.ItemsQuery)
        self.assertFalse(request_iq.payload.items)
        self.assertEqual("foobar", request_iq.payload.node)

    def test_query_items_caches(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.return_value = response

        with self.assertRaises(TypeError):
            self.s.query_items(to, "foobar")

        result1 = run_coroutine(
            self.s.query_items(to, node="foobar")
        )
        result2 = run_coroutine(
            self.s.query_items(to, node="foobar")
        )

        self.assertIs(result1, response)
        self.assertIs(result2, response)

        self.assertEqual(
            1,
            len(self.cc.send.mock_calls)
        )

    def test_query_items_reraises_and_aliases_exception(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        ncall = 0

        @asyncio.coroutine
        def mock(*args, **kwargs):
            nonlocal ncall
            ncall += 1
            if ncall == 1:
                raise errors.XMPPCancelError(
                    condition=(namespaces.stanzas, "feature-not-implemented"),
                )
            else:
                raise ConnectionError()

        with unittest.mock.patch.object(
                self.cc,
                "send",
                new=mock):

            task1 = asyncio.async(
                self.s.query_info(to, node="foobar")
            )
            task2 = asyncio.async(
                self.s.query_info(to, node="foobar")
            )

            with self.assertRaises(errors.XMPPCancelError):
                run_coroutine(task1)

            with self.assertRaises(errors.XMPPCancelError):
                run_coroutine(task2)

    def test_query_info_reraises_but_does_not_cache_exception(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        self.cc.send.side_effect = \
            errors.XMPPCancelError(
                condition=(namespaces.stanzas, "feature-not-implemented"),
            )

        with self.assertRaises(errors.XMPPCancelError):
            run_coroutine(
                self.s.query_items(to, node="foobar")
            )

        self.cc.send.side_effect = \
            ConnectionError()

        with self.assertRaises(ConnectionError):
            run_coroutine(
                self.s.query_items(to, node="foobar")
            )

    def test_query_items_cache_override(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        response1 = disco_xso.ItemsQuery()
        self.cc.send.return_value = response1

        with self.assertRaises(TypeError):
            self.s.query_items(to, "foobar")

        result1 = run_coroutine(
            self.s.query_items(to, node="foobar")
        )

        response2 = disco_xso.ItemsQuery()
        self.cc.send.return_value = response2

        result2 = run_coroutine(
            self.s.query_items(to, node="foobar", require_fresh=True)
        )

        self.assertIs(result1, response1)
        self.assertIs(result2, response2)

        self.assertEqual(
            2,
            len(self.cc.send.mock_calls)
        )

    def test_query_items_cache_clears_on_disconnect(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        response1 = disco_xso.ItemsQuery()
        self.cc.send.return_value = response1

        with self.assertRaises(TypeError):
            self.s.query_items(to, "foobar")

        result1 = run_coroutine(
            self.s.query_items(to, node="foobar")
        )

        self.cc.on_stream_destroyed()

        response2 = disco_xso.ItemsQuery()
        self.cc.send.return_value = response2

        result2 = run_coroutine(
            self.s.query_items(to, node="foobar")
        )

        self.assertIs(result1, response1)
        self.assertIs(result2, response2)

        self.assertEqual(
            2,
            len(self.cc.send.mock_calls)
        )

    def test_query_items_timeout(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.delay = 1
        self.cc.send.return_value = response

        with self.assertRaises(TimeoutError):
            result = run_coroutine(
                self.s.query_items(to, timeout=0.01)
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call(unittest.mock.ANY),
            ],
            self.cc.send.mock_calls
        )

    def test_query_items_deduplicate_requests(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.return_value = response

        result = run_coroutine(
            asyncio.gather(
                self.s.query_items(to, timeout=10),
                self.s.query_items(to, timeout=10),
            )
        )

        self.assertIs(result[0], response)
        self.assertIs(result[1], response)

        self.assertSequenceEqual(
            [
                unittest.mock.call(unittest.mock.ANY),
            ],
            self.cc.send.mock_calls
        )

    def test_query_items_transparent_deduplication_when_cancelled(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.cc.send.return_value = response
        self.cc.send.delay = 0.1

        q1 = asyncio.async(self.s.query_items(to))
        q2 = asyncio.async(self.s.query_items(to))

        run_coroutine(asyncio.sleep(0.05))

        q1.cancel()

        result = run_coroutine(q2)

        self.assertIs(result, response)

        self.assertSequenceEqual(
            [
                unittest.mock.call(unittest.mock.ANY),
                unittest.mock.call(unittest.mock.ANY),
            ],
            self.cc.send.mock_calls
        )

    def test_set_info_cache(self):
        to = structs.JID.fromstr("user@foo.example/res1")
        response = disco_xso.ItemsQuery()

        self.s.set_info_cache(
            to,
            None,
            response
        )

        other_response = disco_xso.InfoQuery()
        self.cc.send.return_value = \
            other_response

        result = run_coroutine(self.s.query_info(to, node=None))

        self.assertIs(result, response)
        self.assertFalse(self.cc.stream.mock_calls)

    def test_set_info_future(self):
        to = structs.JID.fromstr("user@foo.example/res1")

        fut = asyncio.Future()

        self.s.set_info_future(
            to,
            None,
            fut
        )

        request = asyncio.async(
            self.s.query_info(to)
        )

        run_coroutine(asyncio.sleep(0))
        self.assertFalse(request.done())

        result = object()
        fut.set_result(result)

        self.assertIs(run_coroutine(request), result)

    def test_set_info_future_stays_even_with_exception(self):
        exc = ConnectionError()
        to = structs.JID.fromstr("user@foo.example/res1")

        fut = asyncio.Future()

        self.s.set_info_future(
            to,
            None,
            fut
        )

        request = asyncio.async(
            self.s.query_info(to)
        )

        run_coroutine(asyncio.sleep(0))
        self.assertFalse(request.done())

        fut.set_exception(exc)

        with self.assertRaises(Exception) as ctx:
            run_coroutine(request)

        self.assertIs(ctx.exception, exc)


class Testmount_as_node(unittest.TestCase):
    def setUp(self):
        self.pn = disco_service.mount_as_node(
            unittest.mock.sentinel.mountpoint
        )
        self.instance = unittest.mock.Mock()
        self.disco_server = unittest.mock.Mock()
        self.instance.dependencies = {
            disco_service.DiscoServer: self.disco_server
        }

    def tearDown(self):
        del self.instance
        del self.disco_server
        del self.pn

    def test_value_type(self):
        self.assertIs(
            self.pn.value_type,
            type(None),
        )

    def test_mountpoint(self):
        self.assertEqual(
            self.pn.mountpoint,
            unittest.mock.sentinel.mountpoint,
        )

    def test_required_dependencies(self):
        self.assertSetEqual(
            set(self.pn.required_dependencies),
            {disco_service.DiscoServer},
        )

    def test_contextmanager(self):
        cm = self.pn.init_cm(self.instance)
        self.disco_server.mount_node.assert_not_called()
        cm.__enter__()
        self.disco_server.mount_node.assert_called_once_with(
            unittest.mock.sentinel.mountpoint,
            self.instance,
        )
        self.disco_server.unmount_node.assert_not_called()
        cm.__exit__(None, None, None)
        self.disco_server.unmount_node.assert_called_once_with(
            unittest.mock.sentinel.mountpoint,
        )

    def test_contextmanager_is_exception_safe(self):
        cm = self.pn.init_cm(self.instance)
        self.disco_server.mount_node.assert_not_called()
        cm.__enter__()
        self.disco_server.mount_node.assert_called_once_with(
            unittest.mock.sentinel.mountpoint,
            self.instance,
        )
        self.disco_server.unmount_node.assert_not_called()
        try:
            raise Exception()
        except:
            cm.__exit__(*sys.exc_info())
        self.disco_server.unmount_node.assert_called_once_with(
            unittest.mock.sentinel.mountpoint,
        )



class TestRegisteredFeature(unittest.TestCase):
    def setUp(self):
        self.s = unittest.mock.Mock()
        self.rf = disco_service.RegisteredFeature(
            self.s,
            unittest.mock.sentinel.feature,
        )

    def test_contextmanager(self):
        self.s.register_feature.assert_not_called()
        result = self.rf.__enter__()
        self.assertIs(result, self.rf)
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
        self.s.unregister_feature.assert_not_called()
        result = self.rf.__exit__(None, None, None)
        self.assertFalse(result)
        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_contextmanager_is_exception_safe(self):
        class FooException(Exception):
            pass

        self.s.register_feature.assert_not_called()
        with self.assertRaises(FooException):
            with self.rf:
                self.s.register_feature.assert_called_once_with(
                    unittest.mock.sentinel.feature,
                )
                self.s.unregister_feature.assert_not_called()

                raise FooException()

        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_feature(self):
        self.assertEqual(
            self.rf.feature,
            unittest.mock.sentinel.feature,
        )

    def test_feature_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.rf.feature = self.rf.feature

    def test_enabled(self):
        self.assertFalse(self.rf.enabled)

    def test_enabled_changes_with_cm_use(self):
        with self.rf:
            self.assertTrue(self.rf.enabled)
        self.assertFalse(self.rf.enabled)

    def test_setting_enabled_registers_feature(self):
        self.assertFalse(self.rf.enabled)
        self.s.register_feature.assert_not_called()
        self.rf.enabled = True
        self.assertTrue(self.rf.enabled)
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_setting_enabled_is_idempotent(self):
        self.assertFalse(self.rf.enabled)
        self.s.register_feature.assert_not_called()
        self.rf.enabled = True
        self.assertTrue(self.rf.enabled)
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

        self.rf.enabled = True
        self.assertTrue(self.rf.enabled)
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_clearing_enabled_unregisters_feature(self):
        self.assertFalse(self.rf.enabled)
        self.s.register_feature.assert_not_called()
        self.rf.enabled = True
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
        self.s.unregister_feature.assert_not_called()

        self.rf.enabled = False

        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_clearing_enabled_is_idempotent(self):
        self.assertFalse(self.rf.enabled)
        self.s.register_feature.assert_not_called()
        self.rf.enabled = True
        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
        self.s.unregister_feature.assert_not_called()

        self.rf.enabled = False
        self.assertFalse(self.rf.enabled)

        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

        self.rf.enabled = False

        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_clearing_enabled_while_in_cm_does_not_duplicate_unregister(self):
        with self.rf:
            self.rf.enabled = False

            self.s.unregister_feature.assert_called_once_with(
                unittest.mock.sentinel.feature,
            )

        self.s.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_setting_enabled_before_entering_cm_does_not_duplicate_register(self):  # NOQA
        self.rf.enabled = True

        self.s.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

        with self.rf:
            self.s.register_feature.assert_called_once_with(
                unittest.mock.sentinel.feature,
            )


class Testregister_feature(unittest.TestCase):
    def setUp(self):
        self.pn = disco_service.register_feature(
            unittest.mock.sentinel.feature
        )
        self.instance = unittest.mock.Mock()
        self.disco_server = unittest.mock.Mock()
        self.instance.dependencies = {
            disco_service.DiscoServer: self.disco_server
        }

    def tearDown(self):
        del self.instance
        del self.disco_server
        del self.pn

    def test_value_type(self):
        self.assertIs(
            self.pn.value_type,
            disco_service.RegisteredFeature,
        )

    def test_mountpoint(self):
        self.assertEqual(
            self.pn.feature,
            unittest.mock.sentinel.feature,
        )

    def test_required_dependencies(self):
        self.assertSetEqual(
            set(self.pn.required_dependencies),
            {disco_service.DiscoServer},
        )

    def test_init_cm_creates_RegisteredFeature(self):
        with contextlib.ExitStack() as stack:
            RegisteredFeature = stack.enter_context(
                unittest.mock.patch("aioxmpp.disco.service.RegisteredFeature")
            )

            result = self.pn.init_cm(self.instance)

        RegisteredFeature.assert_called_once_with(
            self.disco_server,
            unittest.mock.sentinel.feature,
        )

        self.assertEqual(result, RegisteredFeature())

    def test_contextmanager(self):
        cm = self.pn.init_cm(self.instance)
        self.disco_server.register_feature.assert_not_called()
        cm.__enter__()
        self.disco_server.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
        self.disco_server.unregister_feature.assert_not_called()
        cm.__exit__(None, None, None)
        self.disco_server.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )

    def test_contextmanager_is_exception_safe(self):
        cm = self.pn.init_cm(self.instance)
        self.disco_server.register_feature.assert_not_called()
        cm.__enter__()
        self.disco_server.register_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
        self.disco_server.unregister_feature.assert_not_called()
        try:
            raise Exception()
        except:
            cm.__exit__(*sys.exc_info())
        self.disco_server.unregister_feature.assert_called_once_with(
            unittest.mock.sentinel.feature,
        )
