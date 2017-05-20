########################################################################
# File name: test_dispatcher.py
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
import contextlib
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.service
import aioxmpp.stream

import aioxmpp.dispatcher as dispatcher

from aioxmpp.testutils import (
    make_connected_client,
)


TEST_JID = aioxmpp.JID.fromstr("foo@bar.example/baz")
TEST_LOCAL_JID = aioxmpp.JID.fromstr("foo@local.example")


class FooStanza:
    def __init__(self, from_, type_):
        self.from_ = from_
        self.type_ = type_


class FooDispatcher(dispatcher.SimpleStanzaDispatcher):
    @property
    def local_jid(self):
        return TEST_LOCAL_JID


class TestSimpleStanzaDispatcher(unittest.TestCase):
    def setUp(self):
        self.d = FooDispatcher()

        self.handlers = unittest.mock.Mock()

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            self.handlers.type_fulljid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            self.handlers.type_barejid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            self.handlers.type_barejid_wildcard,
            wildcard_resource=True,
        )

        self.d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            self.handlers.type_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID,
            self.handlers.wildcard_fulljid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID.bare(),
            self.handlers.wildcard_barejid_no_wildcard,
            wildcard_resource=False,
        )

        self.d.register_callback(
            None,
            TEST_JID.bare(),
            self.handlers.wildcard_barejid_wildcard,
            wildcard_resource=True,
        )

        self.d.register_callback(
            None,
            None,
            self.handlers.wildcard_wildcard,
            wildcard_resource=False,
        )

    def tearDown(self):
        del self.d

    def test_register_callback_rejects_dups(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                TEST_JID,
                unittest.mock.sentinel.cb2,
            )

    def test_register_callback_flattens_wildcard_resource_for_fulljid(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                TEST_JID,
                unittest.mock.sentinel.cb,
            )

    def test_register_callback_flattens_wildcard_resource_for_None(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                "only one listener allowed"):
            d.register_callback(
                unittest.mock.sentinel.type_,
                None,
                unittest.mock.sentinel.cb,
            )

    def test_register_callback_honors_wildcard_resource_for_bare(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=True,
        )

    def test_unregister_removes_callback(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            wildcard_resource=False,
        )

        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=False,
        )

    def test_unregister_flattens_wildcard_resource_for_fulljid(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False,
        )

        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=True,
        )

    def test_unregister_flattens_wildcard_resource_for_None(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            None,
            wildcard_resource=False,
        )

        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            None,
            unittest.mock.sentinel.cb,
        )

        d.unregister_callback(
            unittest.mock.sentinel.type_,
            None,
            wildcard_resource=True,
        )

    def test_unregister_raises_KeyError_if_unregistered(self):
        d = FooDispatcher()
        d.register_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            unittest.mock.sentinel.cb,
            wildcard_resource=True,
        )

        with self.assertRaises(KeyError):
            d.unregister_callback(
                unittest.mock.sentinel.type_,
                TEST_JID.bare(),
                wildcard_resource=False,
            )

    def test_dispatch_converts_None_to_local_jid(self):
        self.d.register_callback(
            unittest.mock.sentinel.footype,
            TEST_LOCAL_JID,
            self.handlers.local,
        )

        stanza = FooStanza(None, unittest.mock.sentinel.footype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.local(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid(self):
        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_fulljid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid_via_wildcard_to_bare(self):
        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_barejid_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_fulljid_via_wildcard_to_none(self):
        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID,
            wildcard_resource=False
        )

        self.d.unregister_callback(
            unittest.mock.sentinel.type_,
            TEST_JID.bare(),
            wildcard_resource=True,
        )

        self.d.unregister_callback(
            None,
            TEST_JID.bare(),
            wildcard_resource=True,
        )

        self.d.unregister_callback(
            None,
            TEST_JID,
            wildcard_resource=False,
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_full_wildcard(self):
        stanza = FooStanza(TEST_JID.replace(localpart="fnord"),
                           unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_type_barejid_no_wildcard(self):
        stanza = FooStanza(TEST_JID.bare(), unittest.mock.sentinel.type_)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.type_barejid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_mistype_fulljid(self):
        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_fulljid_no_wildcard(stanza),
            ]
        )

    def test_dispatch_to_most_specific_mistype_fulljid_wildcard(self):
        self.d.unregister_callback(
            None,
            TEST_JID,
            wildcard_resource=False,
        )

        stanza = FooStanza(TEST_JID, unittest.mock.sentinel.othertype)
        self.d._feed(stanza)
        self.assertCountEqual(
            self.handlers.mock_calls,
            [
                unittest.mock.call.wildcard_barejid_wildcard(stanza),
            ]
        )

    def test_does_not_connect_to_on_message_received(self):
        self.assertFalse(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_message_received",
                self.d._feed,
            )
        )

    def test_does_not_connect_to_on_presence_received(self):
        self.assertFalse(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_presence_received",
                self.d._feed,
            )
        )

    def test_handler_context_is_context_manager(self):
        cm = self.d.handler_context(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )

        self.assertTrue(hasattr(cm, "__enter__"))
        self.assertTrue(hasattr(cm, "__exit__"))

    def test_handler_context_enter_registers_callback(self):
        cm = self.d.handler_context(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )

        # we need to mock this too, but we don’t want to test __exit__ here
        with unittest.mock.patch.object(
                self.d,
                "unregister_callback") as unregister_callback:
            with unittest.mock.patch.object(
                    self.d,
                    "register_callback") as register_callback:
                cm.__enter__()

            register_callback.assert_called_once_with(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                unittest.mock.sentinel.cb,
                wildcard_resource=unittest.mock.sentinel.wildcard_resource,
            )

            unregister_callback.assert_not_called()

            cm.__exit__(None, None, None)

    def test_handler_context_exit_unregisters_callback(self):
        cm = self.d.handler_context(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.d,
                    "register_callback")
            )
            unregister_callback = stack.enter_context(
                unittest.mock.patch.object(
                    self.d,
                    "unregister_callback")
            )

            cm.__enter__()
            cm.__exit__(None, None, None)

        unregister_callback.assert_called_once_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )

    def test_handler_context_exit_unregisters_and_does_not_swallow(self):
        cm = self.d.handler_context(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.cb,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )

        class FooException(Exception):
            pass

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(
                    self.d,
                    "register_callback")
            )
            unregister_callback = stack.enter_context(
                unittest.mock.patch.object(
                    self.d,
                    "unregister_callback")
            )
            stack.enter_context(
                self.assertRaises(FooException)
            )
            stack.enter_context(cm)
            raise FooException()

        unregister_callback.assert_called_once_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            wildcard_resource=unittest.mock.sentinel.wildcard_resource,
        )


class TestSimpleMessageDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.d = dispatcher.SimpleMessageDispatcher(self.cc)

    def tearDown(self):
        del self.d
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            dispatcher.SimpleMessageDispatcher,
            aioxmpp.service.Service,
        ))

    def test_is_SimpleStanzaDispatcher(self):
        self.assertTrue(issubclass(
            dispatcher.SimpleMessageDispatcher,
            dispatcher.SimpleStanzaDispatcher,
        ))

    def test_local_jid_uses_local_jid_from_client(self):
        self.assertEqual(
            self.d.local_jid,
            self.cc.local_jid,
        )

    def test_connects_to_on_message_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_message_received",
                self.d._feed,
            )
        )


class TestSimplePresenceDispatcher(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.d = dispatcher.SimplePresenceDispatcher(self.cc)

    def tearDown(self):
        del self.d
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            dispatcher.SimplePresenceDispatcher,
            aioxmpp.service.Service,
        ))

    def test_is_SimpleStanzaDispatcher(self):
        self.assertTrue(issubclass(
            dispatcher.SimplePresenceDispatcher,
            dispatcher.SimpleStanzaDispatcher,
        ))

    def test_local_jid_uses_local_jid_from_client(self):
        self.assertEqual(
            self.d.local_jid,
            self.cc.local_jid,
        )

    def test_connects_to_on_presence_received(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.stream.StanzaStream,
                "on_presence_received",
                self.d._feed,
            )
        )


class Test_apply_message_handler(unittest.TestCase):
    def test_uses_SimpleMessageDispatcher(self):
        instance = unittest.mock.MagicMock()
        dependency = unittest.mock.Mock()
        instance.dependencies.__getitem__.return_value = dependency

        result = dispatcher._apply_message_handler(
            instance,
            unittest.mock.sentinel.stream,
            unittest.mock.sentinel.func,
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
        )

        instance.dependencies.__getitem__.assert_called_once_with(
            dispatcher.SimpleMessageDispatcher,
        )

        dependency.handler_context.assert_called_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.func,
        )

        self.assertEqual(
            result,
            dependency.handler_context(),
        )


class Test_apply_presence_handler(unittest.TestCase):
    def test_uses_SimplePresenceDispatcher(self):
        instance = unittest.mock.MagicMock()
        dependency = unittest.mock.Mock()
        instance.dependencies.__getitem__.return_value = dependency

        result = dispatcher._apply_presence_handler(
            instance,
            unittest.mock.sentinel.stream,
            unittest.mock.sentinel.func,
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
        )

        instance.dependencies.__getitem__.assert_called_once_with(
            dispatcher.SimplePresenceDispatcher,
        )

        dependency.handler_context.assert_called_with(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_,
            unittest.mock.sentinel.func,
        )

        self.assertEqual(
            result,
            dependency.handler_context(),
        )


class Testmessage_handler(unittest.TestCase):
    def setUp(self):
        self.decorator = dispatcher.message_handler(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_
        )

    def tearDown(self):
        del self.decorator

    def test_works_as_decorator(self):
        def cb():
            pass

        self.assertIs(
            cb,
            self.decorator(cb),
        )

    def test_adds_magic_attribute(self):
        def cb():
            pass

        self.decorator(cb)

        self.assertTrue(hasattr(cb, "_aioxmpp_service_handlers"))

    def test_adds__apply_message_handler_entry(self):
        def cb():
            pass

        self.decorator(cb)

        self.assertIn(
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_message_handler,
                 (unittest.mock.sentinel.type_,
                  unittest.mock.sentinel.from_)),
                is_unique=True,
                require_deps=(
                    dispatcher.SimpleMessageDispatcher,
                ),
            ),
            cb._aioxmpp_service_handlers
        )

    def test_stacks_with_other_effects(self):
        def cb():
            pass

        cb._aioxmpp_service_handlers = {"foo"}

        self.decorator(cb)

        self.assertIn(
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_message_handler,
                 (unittest.mock.sentinel.type_,
                  unittest.mock.sentinel.from_)),
                is_unique=True,
                require_deps=(
                    dispatcher.SimpleMessageDispatcher,
                ),
            ),
            cb._aioxmpp_service_handlers
        )

        self.assertIn(
            "foo",
            cb._aioxmpp_service_handlers,
        )

    def test_requires_non_coroutine(self):
        with unittest.mock.patch(
                "asyncio.iscoroutinefunction") as iscoroutinefunction:
            iscoroutinefunction.return_value = True

            with self.assertRaisesRegex(
                    TypeError,
                    "must not be a coroutine function"):
                self.decorator(unittest.mock.sentinel.cb)

        iscoroutinefunction.assert_called_with(
            unittest.mock.sentinel.cb,
        )

    def test_works_with_is_message_handler(self):
        def cb():
            pass

        self.assertFalse(
            dispatcher.is_message_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                cb,
            )
        )

        self.decorator(cb)

        self.assertTrue(
            dispatcher.is_message_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                cb,
            )
        )


class Testpresence_handler(unittest.TestCase):
    def setUp(self):
        self.decorator = dispatcher.presence_handler(
            unittest.mock.sentinel.type_,
            unittest.mock.sentinel.from_
        )

    def tearDown(self):
        del self.decorator

    def test_works_as_decorator(self):
        def cb():
            pass

        self.assertIs(
            cb,
            self.decorator(cb),
        )

    def test_adds_magic_attribute(self):
        def cb():
            pass

        self.decorator(cb)

        self.assertTrue(hasattr(cb, "_aioxmpp_service_handlers"))

    def test_adds__apply_presence_handler_entry(self):
        def cb():
            pass

        self.decorator(cb)

        self.assertIn(
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_presence_handler,
                 (unittest.mock.sentinel.type_,
                  unittest.mock.sentinel.from_)),
                is_unique=True,
                require_deps=(
                    dispatcher.SimplePresenceDispatcher,
                ),
            ),
            cb._aioxmpp_service_handlers
        )

    def test_stacks_with_other_effects(self):
        def cb():
            pass

        cb._aioxmpp_service_handlers = {"foo"}

        self.decorator(cb)

        self.assertIn(
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_presence_handler,
                 (unittest.mock.sentinel.type_,
                  unittest.mock.sentinel.from_)),
                is_unique=True,
                require_deps=(
                    dispatcher.SimplePresenceDispatcher,
                ),
            ),
            cb._aioxmpp_service_handlers
        )

        self.assertIn(
            "foo",
            cb._aioxmpp_service_handlers,
        )

    def test_requires_non_coroutine(self):
        with unittest.mock.patch(
                "asyncio.iscoroutinefunction") as iscoroutinefunction:
            iscoroutinefunction.return_value = True

            with self.assertRaisesRegex(
                    TypeError,
                    "must not be a coroutine function"):
                self.decorator(unittest.mock.sentinel.cb)

        iscoroutinefunction.assert_called_with(
            unittest.mock.sentinel.cb,
        )

    def test_works_with_is_presence_handler(self):
        def cb():
            pass

        self.assertFalse(
            dispatcher.is_presence_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                cb,
            )
        )

        self.decorator(cb)

        self.assertTrue(
            dispatcher.is_presence_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                cb,
            )
        )


class Testis_message_handler(unittest.TestCase):
    def test_return_false_if_magic_attr_is_missing(self):
        self.assertFalse(
            dispatcher.is_message_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                object()
            )
        )

    def test_return_true_if_token_in_magic_attr(self):
        m = unittest.mock.Mock()
        m._aioxmpp_service_handlers = [
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_message_handler,
                    (unittest.mock.sentinel.type_,
                     unittest.mock.sentinel.from_)),
                require_deps=(
                    dispatcher.SimpleMessageDispatcher,
                )
            ),
        ]

        self.assertTrue(
            dispatcher.is_message_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                m
            )
        )

    def test_return_false_if_token_not_in_magic_attr(self):
        m = unittest.mock.Mock()
        m._aioxmpp_service_handlers = [
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_message_handler,
                 (unittest.mock.sentinel.type2,
                     unittest.mock.sentinel.from2)),
                require_deps=(
                    dispatcher.SimpleMessageDispatcher,
                )
            )
        ]

        self.assertFalse(
            dispatcher.is_message_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                m
            )
        )


class Testis_presence_handler(unittest.TestCase):
    def test_return_false_if_magic_attr_is_missing(self):
        self.assertFalse(
            dispatcher.is_presence_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                object()
            )
        )

    def test_return_true_if_token_in_magic_attr(self):
        m = unittest.mock.Mock()
        m._aioxmpp_service_handlers = [
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_presence_handler,
                 (unittest.mock.sentinel.type_,
                  unittest.mock.sentinel.from_)),
                require_deps=(
                    dispatcher.SimplePresenceDispatcher,
                )
            )
        ]

        self.assertTrue(
            dispatcher.is_presence_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                m
            )
        )

    def test_return_false_if_token_not_in_magic_attr(self):
        m = unittest.mock.Mock()
        m._aioxmpp_service_handlers = [
            aioxmpp.service.HandlerSpec(
                (dispatcher._apply_presence_handler,
                 (unittest.mock.sentinel.type2,
                  unittest.mock.sentinel.from2)),
                require_deps=(
                    dispatcher.SimplePresenceDispatcher,
                )
            )
        ]

        self.assertFalse(
            dispatcher.is_presence_handler(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.from_,
                m
            )
        )
