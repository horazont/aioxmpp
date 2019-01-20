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
import contextlib
import random
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp
import aioxmpp.service

import aioxmpp.adhoc.service as adhoc_service
import aioxmpp.adhoc.xso as adhoc_xso
import aioxmpp.disco

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_PEER_JID = aioxmpp.JID.fromstr("foo@bar.baz/fnord")
TEST_LOCAL_JID = aioxmpp.JID.fromstr("bar@bar.baz/fnord")


class TestAdHocClient(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.disco_service = unittest.mock.Mock()
        self.disco_service.query_info = CoroutineMock()
        self.disco_service.query_info.side_effect = AssertionError()
        self.disco_service.query_items = CoroutineMock()
        self.disco_service.query_items.side_effect = AssertionError()
        self.c = adhoc_service.AdHocClient(
            self.cc,
            dependencies={
                aioxmpp.disco.DiscoClient: self.disco_service,
            }
        )

    def tearDown(self):
        del self.c, self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            adhoc_service.AdHocClient,
            aioxmpp.service.Service,
        ))

    def test_depends_on_disco(self):
        self.assertIn(
            aioxmpp.disco.DiscoClient,
            adhoc_service.AdHocClient.ORDER_AFTER,
        )

    def test_detect_support_using_disco(self):
        response = aioxmpp.disco.xso.InfoQuery(
            features={
                "http://jabber.org/protocol/commands",
            }
        )
        self.disco_service.query_info.side_effect = None
        self.disco_service.query_info.return_value = response

        self.assertTrue(
            run_coroutine(self.c.supports_commands(TEST_PEER_JID)),
        )

        self.disco_service.query_info.assert_called_with(
            TEST_PEER_JID,
        )

    def test_detect_absence_of_support_using_disco(self):
        response = aioxmpp.disco.xso.InfoQuery(
            features=set()
        )
        self.disco_service.query_info.side_effect = None
        self.disco_service.query_info.return_value = response

        self.assertFalse(
            run_coroutine(self.c.supports_commands(TEST_PEER_JID)),
        )

        self.disco_service.query_info.assert_called_with(
            TEST_PEER_JID,
        )

    def test_enumerate_commands_uses_disco(self):
        items = [
            aioxmpp.disco.xso.Item(
                TEST_PEER_JID,
                node="cmd{}".format(i),
            )
            for i in range(3)
        ]

        response = aioxmpp.disco.xso.ItemsQuery(
            items=list(items)
        )
        self.disco_service.query_items.side_effect = None
        self.disco_service.query_items.return_value = response

        result = run_coroutine(
            self.c.get_commands(TEST_PEER_JID),
        )

        self.disco_service.query_items.assert_called_with(
            TEST_PEER_JID,
            node="http://jabber.org/protocol/commands",
        )

        self.assertSequenceEqual(
            result,
            items,
        )

    def test_get_command_info_uses_disco(self):
        self.disco_service.query_info.side_effect = None
        self.disco_service.query_info.return_value = \
            unittest.mock.sentinel.result

        result = run_coroutine(
            self.c.get_command_info(TEST_PEER_JID,
                                    unittest.mock.sentinel.node),
        )

        self.disco_service.query_info.assert_called_with(
            TEST_PEER_JID,
            node=unittest.mock.sentinel.node,
        )

        self.assertEqual(
            result,
            unittest.mock.sentinel.result,
        )

    def test_execute(self):
        with unittest.mock.patch(
                "aioxmpp.adhoc.service.ClientSession") as ClientSession:
            ClientSession().start = CoroutineMock()
            ClientSession.reset_mock()
            result = run_coroutine(self.c.execute(
                unittest.mock.sentinel.peer,
                unittest.mock.sentinel.node,
            ))

        ClientSession.assert_called_once_with(
            self.cc.stream,
            unittest.mock.sentinel.peer,
            unittest.mock.sentinel.node,
        )

        ClientSession().start.assert_called_once_with()

        self.assertEqual(result, ClientSession())


class TestCommandNode(unittest.TestCase):
    def test_is_static_node(self):
        self.assertTrue(issubclass(
            adhoc_service.CommandEntry,
            aioxmpp.disco.StaticNode,
        ))

    def test_defaults(self):
        stanza = unittest.mock.Mock()

        cn = adhoc_service.CommandEntry(
            "foo",
            unittest.mock.sentinel.handler,
            features={}
        )

        self.assertDictEqual(
            cn.name,
            {
                None: "foo",
            }
        )

        self.assertIsInstance(
            cn.name,
            aioxmpp.structs.LanguageMap,
        )

        self.assertEqual(
            cn.handler,
            unittest.mock.sentinel.handler
        )

        self.assertIn(
            ("automation", "command-node", None, "foo"),
            list(cn.iter_identities(stanza))
        )

        self.assertCountEqual(
            {
                namespaces.xep0030_info,
                namespaces.xep0050_commands,
            },
            cn.iter_features(unittest.mock.sentinel.stanza)
        )

        self.assertIsNone(
            cn.is_allowed
        )

        self.assertTrue(
            cn.is_allowed_for(unittest.mock.sentinel.jid)
        )

    def test_is_allowed_inhibits_identities_response(self):
        stanza = unittest.mock.Mock()
        is_allowed = unittest.mock.Mock()
        is_allowed.return_value = False

        cn = adhoc_service.CommandEntry(
            "foo",
            unittest.mock.sentinel.handler,
            features={},
            is_allowed=is_allowed
        )

        self.assertSequenceEqual([], list(cn.iter_identities(stanza)))
        is_allowed.assert_called_once_with(
            stanza.from_,
        )

        is_allowed.reset_mock()
        is_allowed.return_value = True

        self.assertIn(
            ("automation", "command-node", None, "foo"),
            list(cn.iter_identities(stanza))
        )

    def test_is_allowed_for_calls_is_allowed_if_defined(self):
        is_allowed = unittest.mock.Mock()

        cn = adhoc_service.CommandEntry(
            "foo",
            unittest.mock.sentinel.handler,
            is_allowed=is_allowed,
        )

        result = cn.is_allowed_for(
            unittest.mock.sentinel.a,
            unittest.mock.sentinel.b,
            x=unittest.mock.sentinel.x,
        )

        is_allowed.assert_called_once_with(
            unittest.mock.sentinel.a,
            unittest.mock.sentinel.b,
            x=unittest.mock.sentinel.x,
        )

        self.assertEqual(
            result,
            is_allowed(),
        )


class TestAdHocServer(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_LOCAL_JID
        self.disco_service = unittest.mock.Mock()
        self.s = adhoc_service.AdHocServer(
            self.cc,
            dependencies={
                aioxmpp.disco.DiscoServer: self.disco_service,
            }
        )
        self.disco_service.reset_mock()

    def tearDown(self):
        del self.s
        del self.disco_service
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            adhoc_service.AdHocServer,
            aioxmpp.service.Service
        ))

    def test_is_disco_node(self):
        self.assertTrue(issubclass(
            adhoc_service.AdHocServer,
            aioxmpp.disco.Node
        ))

    def test_registers_iq_handler(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.SET,
                adhoc_xso.Command,
                adhoc_service.AdHocServer._handle_command,
            )
        )

    def test_registers_as_node(self):
        self.assertIsInstance(
            adhoc_service.AdHocServer.disco_node,
            aioxmpp.disco.mount_as_node,
        )
        self.assertEqual(
            adhoc_service.AdHocServer.disco_node.mountpoint,
            "http://jabber.org/protocol/commands"
        )

    def test_items_empty_by_default(self):
        stanza = unittest.mock.Mock()
        stanza.lang = None

        self.assertSequenceEqual(
            list(self.s.iter_items(stanza)),
            [],
        )

    def test_identity(self):
        self.assertSetEqual(
            {
                ("automation", "command-list", None, None)
            },
            set(self.s.iter_identities(unittest.mock.sentinel.stanza))
        )

    def test_register_stateless_command_makes_it_appear_in_listing(self):
        handler = unittest.mock.Mock()
        base = unittest.mock.Mock()
        base.CommandEntry().name.lookup.return_value = "some name"

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.adhoc.service.CommandEntry",
                    new=base.CommandEntry,
                ),
            )

            self.s.register_stateless_command(
                "node",
                unittest.mock.sentinel.name,
                handler,
            )

        self.assertCountEqual(
            [
                (self.cc.local_jid, "node", "some name"),
            ],
            [
                (item.jid, item.node, item.name)
                for item in self.s.iter_items(base.stanza)
            ]
        )

    def test_listing_respects_is_allowed(self):
        handler = unittest.mock.Mock()
        base = unittest.mock.Mock()
        base.CommandEntry().name.lookup.return_value = "some name"

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.adhoc.service.CommandEntry",
                    new=base.CommandEntry),
            )

            self.s.register_stateless_command(
                "node",
                unittest.mock.sentinel.name,
                handler,
            )

        base.CommandEntry().is_allowed_for.return_value = False

        items = [
            (item.jid, item.node, item.name)
            for item in self.s.iter_items(base.stanza)
        ]

        base.CommandEntry().is_allowed_for.assert_called_once_with(
            base.stanza.from_,
        )

        self.assertCountEqual(
            [
            ],
            items,
        )

    def test_listing_respects_request_language(self):
        handler = unittest.mock.Mock()
        base = unittest.mock.Mock()
        base.stanza.lang = "de"
        base.CommandEntry().name.lookup.return_value = "some name"

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.adhoc.service.CommandEntry",
                    new=base.CommandEntry),
            )

            self.s.register_stateless_command(
                "node",
                unittest.mock.sentinel.name,
                handler,
            )

        base.CommandEntry().is_allowed_for.return_value = True

        items = [
            (item.jid, item.node, item.name)
            for item in self.s.iter_items(base.stanza)
        ]

        base.CommandEntry().name.lookup.assert_called_once_with(
            [
                aioxmpp.structs.LanguageRange.fromstr("de"),
                aioxmpp.structs.LanguageRange.fromstr("en"),
            ]
        )

    def test_register_stateless_registers_command_at_disco_service(self):
        with contextlib.ExitStack() as stack:
            CommandEntry = stack.enter_context(unittest.mock.patch(
                "aioxmpp.adhoc.service.CommandEntry"
            ))

            self.s.register_stateless_command(
                unittest.mock.sentinel.node,
                unittest.mock.sentinel.name,
                unittest.mock.sentinel.handler,
                features=unittest.mock.sentinel.features,
                is_allowed=unittest.mock.sentinel.is_allowed,
            )

        CommandEntry.assert_called_once_with(
            unittest.mock.sentinel.name,
            unittest.mock.sentinel.handler,
            features=unittest.mock.sentinel.features,
            is_allowed=unittest.mock.sentinel.is_allowed,
        )

        self.disco_service.mount_node.assert_called_once_with(
            unittest.mock.sentinel.node,
            CommandEntry()
        )

        (_, (_, obj), _), = self.disco_service.mount_node.mock_calls

    def test__handle_command_raises_item_not_found_for_unknown_node(self):
        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_PEER_JID,
            to=TEST_LOCAL_JID,
            payload=adhoc_xso.Command(
                "node",
            )
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError) as ctx:
            run_coroutine(self.s._handle_command(req))

        self.assertEqual(
            ctx.exception.condition,
            aioxmpp.ErrorCondition.ITEM_NOT_FOUND,
        )

        self.assertRegex(
            ctx.exception.text,
            "no such command: 'node'"
        )

    def test__handle_command_raises_forbidden_for_disallowed_node(self):
        handler = CoroutineMock()
        handler.return_value = unittest.mock.sentinel.result
        is_allowed = unittest.mock.Mock()
        is_allowed.return_value = False

        self.s.register_stateless_command(
            "node",
            "Command name",
            handler,
            is_allowed=is_allowed,
        )

        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_PEER_JID,
            to=TEST_LOCAL_JID,
            payload=adhoc_xso.Command(
                "node",
            )
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError) as ctx:
            run_coroutine(self.s._handle_command(req))

        is_allowed.assert_called_once_with(req.from_)

        self.assertEqual(
            ctx.exception.condition,
            aioxmpp.ErrorCondition.FORBIDDEN,
        )

        handler.assert_not_called()

    def test__handle_command_dispatches_to_command(self):
        handler = CoroutineMock()
        handler.return_value = unittest.mock.sentinel.result

        self.s.register_stateless_command(
            "node",
            "Command name",
            handler,
        )

        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_PEER_JID,
            to=TEST_LOCAL_JID,
            payload=adhoc_xso.Command(
                "node",
            )
        )

        result = run_coroutine(self.s._handle_command(req))

        handler.assert_called_once_with(req)

        self.assertEqual(
            result,
            unittest.mock.sentinel.result,
        )


class TestClientSession(unittest.TestCase):
    def setUp(self):
        self.stream = unittest.mock.Mock()
        self.send_iq_and_wait_for_reply = CoroutineMock()
        self.send_iq_and_wait_for_reply.return_value = None
        self.stream.send_iq_and_wait_for_reply = \
            self.send_iq_and_wait_for_reply

        self.peer_jid = TEST_PEER_JID
        self.command_name = "foocmd"
        self.session = adhoc_service.ClientSession(
            self.stream,
            self.peer_jid,
            self.command_name,
        )

    def tearDown(self):
        del self.stream
        del self.send_iq_and_wait_for_reply
        del self.session

    def test_init(self):
        self.assertIsNone(
            self.session.status,
        )

        self.assertIsNone(
            self.session.first_payload,
        )

        self.assertIsNone(
            self.session.response,
        )

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

    def test_start(self):
        response = unittest.mock.Mock()

        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        result = run_coroutine(self.session.start())

        self.assertEqual(
            len(self.send_iq_and_wait_for_reply.mock_calls),
            1,
        )

        _, (iq,), _ = self.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(
            iq,
            aioxmpp.IQ,
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.IQType.SET,
        )
        self.assertEqual(
            iq.to,
            self.peer_jid,
        )
        self.assertIsInstance(
            iq.payload,
            adhoc_xso.Command,
        )

        cmd = iq.payload
        self.assertEqual(
            cmd.action,
            adhoc_xso.ActionType.EXECUTE,
        )
        self.assertEqual(
            cmd.node,
            self.command_name,
        )
        self.assertIsNone(cmd.actions)
        self.assertIsNone(cmd.first_payload)
        self.assertSequenceEqual(cmd.notes, [])
        self.assertIsNone(cmd.status)
        self.assertIsNone(cmd.sessionid)

        self.assertEqual(
            result,
            response.first_payload
        )

        self.assertEqual(
            self.session.first_payload,
            response.first_payload
        )

        self.assertEqual(
            self.session.response,
            response
        )

        self.assertEqual(
            self.session.status,
            response.status,
        )

        self.assertEqual(
            self.session.allowed_actions,
            response.actions.allowed_actions,
        )

        self.assertEqual(
            self.session.sessionid,
            response.sessionid,
        )

        # trick
        response.actions = None

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

    def test_aenter_starts(self):
        with unittest.mock.patch.object(self.session, "start") as start:
            result = run_coroutine(self.session.__aenter__())
            start.assert_called_once_with()
        self.assertEqual(result, self.session)

    def test_aenter_after_start_is_harmless(self):
        response = unittest.mock.Mock()

        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        run_coroutine(self.session.start())
        result = run_coroutine(self.session.__aenter__())
        self.assertEqual(result, self.session)

    def test_aexit_closes(self):
        with unittest.mock.patch.object(self.session, "close") as close:
            result = run_coroutine(self.session.__aexit__(
                unittest.mock.sentinel.type_,
                unittest.mock.sentinel.value,
                unittest.mock.sentinel.tb,
            ))
        close.assert_called_once_with()
        self.assertFalse(result)

    def test_reject_start_after_start(self):
        response = unittest.mock.Mock()

        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        run_coroutine(self.session.start())

        self.send_iq_and_wait_for_reply.mock_calls.clear()

        with self.assertRaisesRegex(
                RuntimeError,
                r"command execution already started"):
            run_coroutine(self.session.start())

        self.assertSequenceEqual(
            self.send_iq_and_wait_for_reply.mock_calls,
            []
        )

    def test_reject_proceed_before_start(self):
        with self.assertRaisesRegex(
                RuntimeError,
                r"command execution not started yet"):
            run_coroutine(self.session.proceed())

    def test_proceed_uses_execute_and_previous_payload_by_default(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.sessionid = "foobar"
        initial_response.actions = None
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        response = unittest.mock.Mock()
        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        result = run_coroutine(self.session.proceed())

        _, (iq,), _ = self.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(
            iq,
            aioxmpp.IQ,
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.IQType.SET,
        )
        self.assertEqual(
            iq.to,
            self.peer_jid,
        )
        self.assertIsInstance(
            iq.payload,
            adhoc_xso.Command,
        )

        cmd = iq.payload
        self.assertEqual(
            cmd.action,
            adhoc_xso.ActionType.EXECUTE,
        )
        self.assertEqual(
            cmd.node,
            self.command_name,
        )
        self.assertIsNone(cmd.actions)
        self.assertSequenceEqual(
            cmd.payload,
            initial_response.payload,
        )
        self.assertSequenceEqual(cmd.notes, [])
        self.assertIsNone(cmd.status)
        self.assertEqual(
            cmd.sessionid,
            "foobar",
        )

        self.assertEqual(
            result,
            response.first_payload
        )

        self.assertEqual(
            self.session.first_payload,
            response.first_payload
        )

        self.assertEqual(
            self.session.response,
            response
        )

        self.assertEqual(
            self.session.status,
            response.status,
        )

        self.assertEqual(
            self.session.allowed_actions,
            response.actions.allowed_actions,
        )

    def test_proceed_rejects_disallowed_action(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions.allowed_actions = set()
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        with self.assertRaisesRegex(
                ValueError,
                r"action .*NEXT not allowed in this stage"):
            run_coroutine(self.session.proceed(
                action=adhoc_xso.ActionType.NEXT
            ))

        self.assertSequenceEqual(
            self.send_iq_and_wait_for_reply.mock_calls,
            []
        )

    def test_proceed_with_custom_action(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions.allowed_actions = {
            adhoc_xso.ActionType.NEXT,
        }
        initial_response.sessionid = "baz"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        response = unittest.mock.Mock()
        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        run_coroutine(self.session.proceed(
            action=adhoc_xso.ActionType.NEXT,
        ))

        _, (iq,), _ = self.send_iq_and_wait_for_reply.mock_calls[0]
        cmd = iq.payload
        self.assertEqual(
            cmd.action,
            adhoc_xso.ActionType.NEXT,
        )

    def test_proceed_with_custom_payload(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "fnord"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        response = unittest.mock.Mock()
        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        Command = adhoc_xso.Command
        with unittest.mock.patch(
                "aioxmpp.adhoc.xso.Command") as Command_patched:
            Command_patched.side_effect = Command

            run_coroutine(self.session.proceed(
                payload=unittest.mock.sentinel.payload,
            ))

        Command_patched.assert_called_with(
            self.command_name,
            action=adhoc_xso.ActionType.EXECUTE,
            payload=unittest.mock.sentinel.payload,
            sessionid=initial_response.sessionid,
        )

        _, (iq,), _ = self.send_iq_and_wait_for_reply.mock_calls[0]
        cmd = iq.payload
        self.assertSequenceEqual(
            cmd.payload,
            [unittest.mock.sentinel.payload],
        )

    def test_proceed_calls_close_and_reraises_on_BadSessionID(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "fnord"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        exc = aioxmpp.errors.XMPPModifyError(
            aioxmpp.ErrorCondition.BAD_REQUEST,
            text="Bad Session",
            application_defined_condition=adhoc_xso.BadSessionID(),
        )
        self.send_iq_and_wait_for_reply.side_effect = exc

        with unittest.mock.patch.object(
                self.session,
                "close",
                new=CoroutineMock()) as close_:
            with self.assertRaisesRegex(
                    adhoc_service.SessionError,
                    r"Bad Session"):
                run_coroutine(self.session.proceed())

        close_.assert_called_once_with()

    def test_proceed_calls_close_and_reraises_on_SessionExpired(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "fnord"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        exc = aioxmpp.errors.XMPPCancelError(
            aioxmpp.ErrorCondition.NOT_ALLOWED,
            text="Session Expired",
            application_defined_condition=adhoc_xso.SessionExpired(),
        )
        self.send_iq_and_wait_for_reply.side_effect = exc

        with unittest.mock.patch.object(
                self.session,
                "close",
                new=CoroutineMock()) as close_:
            with self.assertRaisesRegex(
                    adhoc_service.SessionError,
                    r"Session Expired"):
                run_coroutine(self.session.proceed())

        close_.assert_called_once_with()

    def test_proceed_closes_on_other_cancel_exceptions(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "fnord"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        exc = aioxmpp.errors.XMPPCancelError(
            aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED,
        )
        self.send_iq_and_wait_for_reply.side_effect = exc

        with unittest.mock.patch.object(
                self.session,
                "close",
                new=CoroutineMock()) as close_:
            with self.assertRaises(aioxmpp.errors.XMPPCancelError):
                run_coroutine(self.session.proceed())

        close_.assert_called_once_with()

    def test_proceed_reraises_other_modify_exceptions_without_closing(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "fnord"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        exc = aioxmpp.errors.XMPPModifyError(
            aioxmpp.ErrorCondition.BAD_REQUEST,
        )
        self.send_iq_and_wait_for_reply.side_effect = exc

        with unittest.mock.patch.object(
                self.session,
                "close",
                new=CoroutineMock()) as close_:
            with self.assertRaises(aioxmpp.errors.XMPPModifyError):
                run_coroutine(self.session.proceed())

        self.assertFalse(close_.mock_calls)

    def test_allow_close_before_start(self):
        run_coroutine(self.session.close())

        self.assertIsNone(
            self.session.status,
        )

        self.assertIsNone(
            self.session.first_payload,
        )

        self.assertIsNone(
            self.session.response,
        )

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

    def test_close_after_start_sends_cancel_if_not_completed(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "funk"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        response = unittest.mock.Mock()
        self.send_iq_and_wait_for_reply.return_value = response
        self.send_iq_and_wait_for_reply.side_effect = None

        run_coroutine(self.session.close())

        _, (iq,), _ = self.send_iq_and_wait_for_reply.mock_calls[0]

        self.assertIsInstance(
            iq,
            aioxmpp.IQ,
        )
        self.assertEqual(
            iq.type_,
            aioxmpp.IQType.SET,
        )
        self.assertEqual(
            iq.to,
            self.peer_jid,
        )
        self.assertIsInstance(
            iq.payload,
            adhoc_xso.Command,
        )

        cmd = iq.payload
        self.assertEqual(
            cmd.action,
            adhoc_xso.ActionType.CANCEL,
        )
        self.assertEqual(
            cmd.node,
            self.command_name,
        )
        self.assertIsNone(cmd.actions)
        self.assertSequenceEqual(
            cmd.payload,
            [],
        )
        self.assertSequenceEqual(cmd.notes, [])
        self.assertIsNone(cmd.status)
        self.assertEqual(
            cmd.sessionid,
            initial_response.sessionid,
        )

        self.assertIsNone(
            self.session.status,
        )

        self.assertIsNone(
            self.session.first_payload,
        )

        self.assertIsNone(
            self.session.response,
        )

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

    def test_close_ignores_stanza_errors_in_reply(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "funk"
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        exc = aioxmpp.errors.StanzaError()
        self.send_iq_and_wait_for_reply.side_effect = exc

        run_coroutine(self.session.close())

        self.assertIsNone(
            self.session.status,
        )

        self.assertIsNone(
            self.session.first_payload,
        )

        self.assertIsNone(
            self.session.response,
        )

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

    def test_close_does_not_send_cancel_if_completed(self):
        initial_response = unittest.mock.Mock()
        initial_response.payload = [
            unittest.mock.sentinel.payload1,
            unittest.mock.sentinel.payload2,
        ]
        initial_response.actions = None
        initial_response.sessionid = "funk"
        initial_response.status = adhoc_xso.CommandStatus.COMPLETED
        self.send_iq_and_wait_for_reply.return_value = initial_response
        self.send_iq_and_wait_for_reply.side_effect = None
        run_coroutine(self.session.start())
        self.send_iq_and_wait_for_reply.mock_calls.clear()

        run_coroutine(self.session.close())

        self.assertFalse(self.send_iq_and_wait_for_reply.mock_calls)

        self.assertIsNone(
            self.session.status,
        )

        self.assertIsNone(
            self.session.first_payload,
        )

        self.assertIsNone(
            self.session.response,
        )

        self.assertSetEqual(
            self.session.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )


# class TestServerSession(unittest.TestCase):
#     def setUp(self):
#         self.cc = make_connected_client()
#         self.s = self.cc.stream
#         self.sessionid = "testsessionid"
#         self.ss = adhoc_service.ServerSession(
#             self.s,
#             sessionid=self.sessionid
#         )

#     def tearDown(self):
#         del self.ss
#         del self.sessionid
#         del self.s
#         del self.cc

#     def test_init_uses_system_entropy(self):
#         self.assertIsInstance(
#             adhoc_service._rng,
#             random.SystemRandom,
#         )

#         with unittest.mock.patch("aioxmpp.adhoc.service._rng") as rng:
#             rng.getrandbits.return_value = 1234

#             self.ss = adhoc_service.ServerSession(
#                 self.s,
#                 TEST_PEER_JID,
#             )

#         rng.getrandbits.assert_called_once_with(64)

#         self.assertEqual(
#             self.ss.sessionid,
#             "0gQAAAAAAAA"
#         )

#     def test_init(self):
#         self.assertEqual(self.ss.sessionid, self.sessionid)
#         self.assertEqual(self.ss.timeout, timedelta(seconds=60))

#     def test_reply_raises_if_handle_has_not_been_called(self):
#         with self.assertRaises(RuntimeError):
#             pass
