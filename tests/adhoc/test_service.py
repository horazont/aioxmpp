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
import unittest
import unittest.mock

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
        self.assertLess(
            aioxmpp.disco.DiscoClient,
            adhoc_service.AdHocClient,
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
            (namespaces.stanzas, "bad-request"),
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
            (namespaces.stanzas, "not-allowed"),
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
            (namespaces.stanzas, "feature-not-implemented"),
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
            (namespaces.stanzas, "bad-request"),
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
