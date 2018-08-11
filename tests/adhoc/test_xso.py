########################################################################
# File name: test_xso.py
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

import aioxmpp
import aioxmpp.adhoc.xso as adhoc_xso
import aioxmpp.forms.xso as forms_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_commands_namespace(self):
        self.assertEqual(
            namespaces.xep0050_commands,
            "http://jabber.org/protocol/commands"
        )


class TestNote(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            adhoc_xso.Note,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            adhoc_xso.Note.TAG,
            (namespaces.xep0050_commands, "note"),
        )

    def test_body_attr(self):
        self.assertIsInstance(
            adhoc_xso.Note.body,
            xso.Text,
        )
        self.assertIsNone(
            adhoc_xso.Note.body.default,
        )

    def test_type__attr(self):
        self.assertIsInstance(
            adhoc_xso.Note.type_,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Note.type_.tag,
            (None, "type"),
        )
        self.assertIsInstance(
            adhoc_xso.Note.type_.type_,
            xso.EnumCDataType,
        )
        self.assertEqual(
            adhoc_xso.Note.type_.type_.enum_class,
            adhoc_xso.NoteType,
        )
        self.assertEqual(
            adhoc_xso.Note.type_.default,
            adhoc_xso.NoteType.INFO,
        )

    def test_init(self):
        n = adhoc_xso.Note(
            adhoc_xso.NoteType.INFO,
            "foo",
        )

        self.assertEqual(n.type_, adhoc_xso.NoteType.INFO)
        self.assertEqual(n.body, "foo")


class TestActions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            adhoc_xso.Actions,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            adhoc_xso.Actions.TAG,
            (namespaces.xep0050_commands, "actions"),
        )

    def test_next_is_allowed_attr(self):
        self.assertIsInstance(
            adhoc_xso.Actions.next_is_allowed,
            xso.ChildFlag,
        )
        self.assertEqual(
            adhoc_xso.Actions.next_is_allowed.tag,
            (namespaces.xep0050_commands, "next"),
        )

    def test_prev_is_allowed_attr(self):
        self.assertIsInstance(
            adhoc_xso.Actions.prev_is_allowed,
            xso.ChildFlag,
        )
        self.assertEqual(
            adhoc_xso.Actions.prev_is_allowed.tag,
            (namespaces.xep0050_commands, "prev"),
        )

    def test_complete_is_allowed_attr(self):
        self.assertIsInstance(
            adhoc_xso.Actions.complete_is_allowed,
            xso.ChildFlag,
        )
        self.assertEqual(
            adhoc_xso.Actions.complete_is_allowed.tag,
            (namespaces.xep0050_commands, "complete"),
        )

    def test_execute_attr(self):
        self.assertIsInstance(
            adhoc_xso.Actions.execute,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Actions.execute.tag,
            (None, "execute"),
        )
        self.assertIsInstance(
            adhoc_xso.Actions.execute.type_,
            xso.EnumCDataType,
        )
        self.assertEqual(
            adhoc_xso.Actions.execute.type_.enum_class,
            adhoc_xso.ActionType,
        )
        self.assertIsInstance(
            adhoc_xso.Actions.execute.validator,
            xso.RestrictToSet,
        )
        self.assertSetEqual(
            adhoc_xso.Actions.execute.validator.values,
            {
                adhoc_xso.ActionType.NEXT,
                adhoc_xso.ActionType.PREV,
                adhoc_xso.ActionType.COMPLETE,
            }
        )
        self.assertEqual(
            adhoc_xso.Actions.execute.default,
            None,
        )

    def test_allowed_actions(self):
        actions = adhoc_xso.Actions()
        self.assertSetEqual(
            actions.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL}
        )

        actions.prev_is_allowed = True
        self.assertSetEqual(
            actions.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL,
             adhoc_xso.ActionType.PREV},
        )
        actions.prev_is_allowed = False

        actions.next_is_allowed = True
        self.assertSetEqual(
            actions.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL,
             adhoc_xso.ActionType.NEXT},
        )
        actions.next_is_allowed = False

        actions.complete_is_allowed = True
        self.assertSetEqual(
            actions.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL,
             adhoc_xso.ActionType.COMPLETE},
        )

        actions.next_is_allowed = True
        actions.prev_is_allowed = True
        self.assertSetEqual(
            actions.allowed_actions,
            {adhoc_xso.ActionType.EXECUTE,
             adhoc_xso.ActionType.CANCEL,
             adhoc_xso.ActionType.NEXT,
             adhoc_xso.ActionType.PREV,
             adhoc_xso.ActionType.COMPLETE},
        )

        self.assertIsInstance(
            actions.allowed_actions,
            frozenset
        )

    def test_set_allowed_actions_rejects_if_EXECUTE_is_missing(self):
        actions = adhoc_xso.Actions()
        with self.assertRaisesRegex(
                ValueError,
                r"EXECUTE must always be allowed"):
            actions.allowed_actions = {
                adhoc_xso.ActionType.CANCEL
            }

    def test_set_allowed_actions_rejects_if_CANCEL_is_missing(self):
        actions = adhoc_xso.Actions()
        with self.assertRaisesRegex(
                ValueError,
                r"CANCEL must always be allowed"):
            actions.allowed_actions = {
                adhoc_xso.ActionType.EXECUTE,
            }

    def test_set_allowed_actions(self):
        actions = adhoc_xso.Actions()
        actions.prev_is_allowed = True
        actions.next_is_allowed = True
        actions.complete_is_allowed = True

        actions.allowed_actions = {
            adhoc_xso.ActionType.EXECUTE,
            adhoc_xso.ActionType.CANCEL,
        }

        self.assertFalse(actions.prev_is_allowed)
        self.assertFalse(actions.next_is_allowed)
        self.assertFalse(actions.complete_is_allowed)

        actions.allowed_actions = {
            adhoc_xso.ActionType.EXECUTE,
            adhoc_xso.ActionType.CANCEL,
            adhoc_xso.ActionType.NEXT,
        }

        self.assertFalse(actions.prev_is_allowed)
        self.assertTrue(actions.next_is_allowed)
        self.assertFalse(actions.complete_is_allowed)

        actions.allowed_actions = {
            adhoc_xso.ActionType.EXECUTE,
            adhoc_xso.ActionType.CANCEL,
            adhoc_xso.ActionType.PREV,
        }

        self.assertTrue(actions.prev_is_allowed)
        self.assertFalse(actions.next_is_allowed)
        self.assertFalse(actions.complete_is_allowed)

        actions.allowed_actions = {
            adhoc_xso.ActionType.EXECUTE,
            adhoc_xso.ActionType.CANCEL,
            adhoc_xso.ActionType.COMPLETE,
        }

        self.assertFalse(actions.prev_is_allowed)
        self.assertFalse(actions.next_is_allowed)
        self.assertTrue(actions.complete_is_allowed)

        actions.allowed_actions = {
            adhoc_xso.ActionType.EXECUTE,
            adhoc_xso.ActionType.CANCEL,
            adhoc_xso.ActionType.NEXT,
            adhoc_xso.ActionType.PREV,
            adhoc_xso.ActionType.COMPLETE,
        }

        self.assertTrue(actions.prev_is_allowed)
        self.assertTrue(actions.next_is_allowed)
        self.assertTrue(actions.complete_is_allowed)


class TestCommand(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            adhoc_xso.Command,
            xso.XSO,
        ))

    def test_is_iq_payload(self):
        self.assertIn(
            adhoc_xso.Command.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )

    def test_tag(self):
        self.assertEqual(
            adhoc_xso.Command.TAG,
            (namespaces.xep0050_commands, "command"),
        )

    def test_actions_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.actions,
            xso.Child,
        )
        self.assertCountEqual(
            adhoc_xso.Command.actions._classes,
            [
                adhoc_xso.Actions,
            ]
        )

    def test_notes_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.notes,
            xso.ChildList,
        )
        self.assertCountEqual(
            adhoc_xso.Command.notes._classes,
            [
                adhoc_xso.Note,
            ]
        )

    def test_action_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.action,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Command.action.tag,
            (None, "action"),
        )
        self.assertIsInstance(
            adhoc_xso.Command.action.type_,
            xso.EnumCDataType,
        )
        self.assertEqual(
            adhoc_xso.Command.action.type_.enum_class,
            adhoc_xso.ActionType,
        )
        self.assertEqual(
            adhoc_xso.Command.action.default,
            adhoc_xso.ActionType.EXECUTE,
        )

    def test_status_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.status,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Command.status.tag,
            (None, "status"),
        )
        self.assertIsInstance(
            adhoc_xso.Command.status.type_,
            xso.EnumCDataType,
        )
        self.assertEqual(
            adhoc_xso.Command.status.type_.enum_class,
            adhoc_xso.CommandStatus,
        )
        self.assertIsNone(
            adhoc_xso.Command.status.default,
        )

    def test_sessionid_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.sessionid,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Command.sessionid.tag,
            (None, "sessionid"),
        )
        self.assertIsNone(
            adhoc_xso.Command.sessionid.default,
        )

    def test_node_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.node,
            xso.Attr,
        )
        self.assertEqual(
            adhoc_xso.Command.node.tag,
            (None, "node"),
        )
        self.assertEqual(
            adhoc_xso.Command.node.default,
            xso.NO_DEFAULT,
        )

    def test_payload_attr(self):
        self.assertIsInstance(
            adhoc_xso.Command.payload,
            xso.ChildList,
        )
        self.assertIn(
            forms_xso.Data,
            adhoc_xso.Command.payload._classes,
        )

    def test_init_default(self):
        with self.assertRaisesRegex(
                TypeError,
                r"required positional argument: 'node'"):
            adhoc_xso.Command()

    def test_init(self):
        cmd = adhoc_xso.Command(node="foo")
        self.assertEqual(cmd.node, "foo")
        self.assertEqual(cmd.action, adhoc_xso.ActionType.EXECUTE)
        self.assertIsNone(cmd.status)
        self.assertIsNone(cmd.sessionid)
        self.assertSequenceEqual(cmd.payload, [])
        self.assertSequenceEqual(cmd.notes, [])
        self.assertIsNone(cmd.actions)
        self.assertIsNone(cmd.first_payload)

    def test_init_full(self):
        cmd = adhoc_xso.Command(
            node="foo",
            action=adhoc_xso.ActionType.COMPLETE,
            status=adhoc_xso.CommandStatus.EXECUTING,
            sessionid="foobar",
            payload=[
                unittest.mock.sentinel.payload1,
                unittest.mock.sentinel.payload2,
            ],
            notes=[
                unittest.mock.sentinel.note1,
                unittest.mock.sentinel.note2,
            ],
            actions=unittest.mock.sentinel.actions,
        )
        self.assertEqual(cmd.node, "foo")
        self.assertEqual(cmd.action, adhoc_xso.ActionType.COMPLETE)
        self.assertEqual(cmd.status, adhoc_xso.CommandStatus.EXECUTING)
        self.assertEqual(cmd.sessionid, "foobar")
        self.assertSequenceEqual(
            cmd.payload,
            [
                unittest.mock.sentinel.payload1,
                unittest.mock.sentinel.payload2,
            ]
        )
        self.assertSequenceEqual(
            cmd.notes,
            [
                unittest.mock.sentinel.note1,
                unittest.mock.sentinel.note2,
            ]
        )
        self.assertEqual(cmd.actions, unittest.mock.sentinel.actions)
        self.assertEqual(cmd.first_payload, unittest.mock.sentinel.payload1)

    def test_init_single_payload(self):
        cmd = adhoc_xso.Command(
            "foo",
            payload=unittest.mock.sentinel.payload1,
        )

        self.assertSequenceEqual(
            cmd.payload,
            [
                unittest.mock.sentinel.payload1,
            ]
        )

        self.assertEqual(cmd.first_payload, unittest.mock.sentinel.payload1)


class TestSimpleErrors(unittest.TestCase):
    ERROR_CLASSES = [
        ("MalformedAction", "malformed-action"),
        ("BadAction", "bad-action"),
        ("BadLocale", "bad-locale"),
        ("BadPayload", "bad-payload"),
        ("BadSessionID", "bad-sessionid"),
        ("SessionExpired", "session-expired"),
    ]

    def _run_tests(self, func):
        for clsname, *args in self.ERROR_CLASSES:
            cls = getattr(adhoc_xso, clsname)
            func(cls, args)

    def _test_is_xso(self, cls, args):
        self.assertTrue(issubclass(
            cls,
            xso.XSO
        ))

    def test_is_xso(self):
        self._run_tests(self._test_is_xso)

    def _test_tag(self, cls, args):
        self.assertEqual(
            ("http://jabber.org/protocol/commands", args[0]),
            cls.TAG
        )

    def test_tag(self):
        self._run_tests(self._test_tag)

    def _test_is_application_error(self, cls, args):
        self.assertIn(
            cls,
            aioxmpp.stanza.Error.application_condition._classes
        )

    def test_is_application_error(self):
        self._run_tests(self._test_is_application_error)
