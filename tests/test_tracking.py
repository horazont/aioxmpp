########################################################################
# File name: test_tracking.py
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
import itertools
import unittest
import unittest.mock

from datetime import timedelta

import aioxmpp.service
import aioxmpp.tracking as tracking

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    make_connected_client,
)


TEST_LOCAL = aioxmpp.JID.fromstr("romeo@montague.example/garden")
TEST_PEER = aioxmpp.JID.fromstr("juliet@capulet.example/chamber")


class TestMessageTracker(unittest.TestCase):
    def setUp(self):
        self.t = tracking.MessageTracker()
        self.listener = unittest.mock.Mock()
        for ev in ["on_closed", "on_state_changed"]:
            cb = getattr(self.listener, ev)
            cb.return_value = None
            getattr(self.t, ev).connect(cb)

    def tearDown(self):
        del self.t

    def test_init(self):
        self.assertIsNone(self.t.response)
        self.assertEqual(
            self.t.state,
            tracking.MessageState.IN_TRANSIT
        )
        self.assertIs(self.t.closed, False)

    def test_state_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.t.state = self.t.state

    def test_response_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.t.response = self.t.response

    def test_closed_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.t.closed = self.t.closed

    def test_close_sets_closed_to_true(self):
        self.t.close()
        self.assertIs(self.t.closed, True)

    def test_close_fires_event(self):
        self.t.close()
        self.listener.on_closed.assert_called_once_with()
        self.listener.on_state_changed.assert_not_called()

    def test_close_is_idempotent(self):
        self.t.close()
        self.listener.on_closed.assert_called_once_with()
        self.listener.on_state_changed.assert_not_called()
        self.t.close()
        self.listener.on_closed.assert_called_once_with()
        self.listener.on_state_changed.assert_not_called()

    def test__set_state_updates_state_and_response(self):
        self.t._set_state(
            tracking.MessageState.ERROR,
            unittest.mock.sentinel.response,
        )

        self.assertEqual(
            self.t.state,
            tracking.MessageState.ERROR,
        )
        self.assertEqual(
            self.t.response,
            unittest.mock.sentinel.response,
        )

    def test__set_state_fires_event(self):
        self.t._set_state(
            tracking.MessageState.DELIVERED_TO_RECIPIENT,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.assert_called_once_with(
            tracking.MessageState.DELIVERED_TO_RECIPIENT,
            unittest.mock.sentinel.response,
        )

    def test__set_state_rejects_transitions_from_aborted(self):
        self.t._set_state(
            tracking.MessageState.ABORTED,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.reset_mock()
        self.listener.on_state_changed.return_value = None

        for state in tracking.MessageState:
            with self.assertRaisesRegex(
                    ValueError,
                    "transition from .* to .*not allowed"):
                self.t._set_state(state)
            self.listener.on_state_changed.assert_not_called()
            self.assertEqual(
                self.t.state,
                tracking.MessageState.ABORTED,
            )
            self.assertEqual(
                self.t.response,
                unittest.mock.sentinel.response,
            )

    def test__set_state_rejects_transitions_from_error_to_in_transit(self):
        self.t._set_state(
            tracking.MessageState.ERROR,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.reset_mock()
        self.listener.on_state_changed.return_value = None

        with self.assertRaisesRegex(
                ValueError,
                "transition from .* to .*not allowed"):
            self.t._set_state(tracking.MessageState.IN_TRANSIT)

        self.listener.on_state_changed.assert_not_called()
        self.assertEqual(
            self.t.state,
            tracking.MessageState.ERROR,
        )
        self.assertEqual(
            self.t.response,
            unittest.mock.sentinel.response,
        )

    def test__set_state_rejects_transitions_from_error_to_aborted(self):
        self.t._set_state(
            tracking.MessageState.ERROR,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.reset_mock()
        self.listener.on_state_changed.return_value = None

        with self.assertRaisesRegex(
                ValueError,
                "transition from .* to .*not allowed"):
            self.t._set_state(tracking.MessageState.ABORTED)

        self.listener.on_state_changed.assert_not_called()
        self.assertEqual(
            self.t.state,
            tracking.MessageState.ERROR,
        )
        self.assertEqual(
            self.t.response,
            unittest.mock.sentinel.response,
        )

    def test__set_state_rejects_transitions_from_error_to_delivered_to_server(
            self):
        self.t._set_state(
            tracking.MessageState.ERROR,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.reset_mock()
        self.listener.on_state_changed.return_value = None

        with self.assertRaisesRegex(
                ValueError,
                "transition from .* to .*not allowed"):
            self.t._set_state(tracking.MessageState.DELIVERED_TO_SERVER)

        self.listener.on_state_changed.assert_not_called()
        self.assertEqual(
            self.t.state,
            tracking.MessageState.ERROR,
        )
        self.assertEqual(
            self.t.response,
            unittest.mock.sentinel.response,
        )

    def test__set_state_allows_transition_from_error_to_delivered_to_recipient(
            self):
        self.t._set_state(
            tracking.MessageState.ERROR,
            unittest.mock.sentinel.response,
        )
        self.listener.on_state_changed.reset_mock()
        self.listener.on_state_changed.return_value = None

        self.t._set_state(
            tracking.MessageState.DELIVERED_TO_RECIPIENT,
            unittest.mock.sentinel.response,
        )

        self.listener.on_state_changed.assert_called_once_with(
            tracking.MessageState.DELIVERED_TO_RECIPIENT,
            unittest.mock.sentinel.response,
        )

    def test__set_state_rejects_transitions_to_in_transit(self):
        for state in tracking.MessageState:
            t = tracking.MessageTracker()
            if state != t.state:
                t._set_state(state, unittest.mock.sentinel.response)
            on_state_changed = unittest.mock.Mock()
            t.on_state_changed.connect(on_state_changed)
            with self.assertRaisesRegex(
                    ValueError,
                    "transition from .* to .*not allowed"):
                t._set_state(tracking.MessageState.IN_TRANSIT)
            on_state_changed.assert_not_called()
            self.assertEqual(
                t.state,
                state,
            )
            if state != t.state:
                self.assertEqual(
                    t.response,
                    unittest.mock.sentinel.response,
                )

    def test__set_state_rejects_some_other_transitions(self):
        to_reject = [
            (
                tracking.MessageState.DELIVERED_TO_RECIPIENT,
                tracking.MessageState.DELIVERED_TO_SERVER,
            ),
            (
                tracking.MessageState.SEEN_BY_RECIPIENT,
                tracking.MessageState.DELIVERED_TO_SERVER,
            ),
            (
                tracking.MessageState.SEEN_BY_RECIPIENT,
                tracking.MessageState.DELIVERED_TO_RECIPIENT,
            ),
        ]

        for state1, state2 in itertools.product(
                tracking.MessageState,
                tracking.MessageState):
            if state1 == tracking.MessageState.ABORTED:
                # already tested elsewhere
                continue
            if state1 == tracking.MessageState.ERROR:
                # already tested elsewhere
                continue
            if state2 == tracking.MessageState.IN_TRANSIT:
                # already tested elsewhere
                continue
            t = tracking.MessageTracker()

            if state1 != t.state:
                t._set_state(state1, unittest.mock.sentinel.response)

            on_state_changed = unittest.mock.Mock()
            t.on_state_changed.connect(on_state_changed)

            if (state1, state2) in to_reject:
                with self.assertRaisesRegex(
                        ValueError,
                        "transition from .* to .*not allowed",
                        msg=(state1, state2)):
                    t._set_state(state2)
                on_state_changed.assert_not_called()
                self.assertEqual(
                    t.state,
                    state1,
                )
                if state1 != t.state:
                    self.assertEqual(
                        t.response,
                        unittest.mock.sentinel.response,
                    )

            else:
                t._set_state(
                    state2,
                    unittest.mock.sentinel.response2
                )
                self.assertEqual(
                    t.state,
                    state2,
                )
                self.assertEqual(
                    t.response,
                    unittest.mock.sentinel.response2,
                )

    def test__set_state_bails_out_early_if_closed(self):
        self.t._set_state(
            tracking.MessageState.DELIVERED_TO_SERVER,
            unittest.mock.sentinel.response,
        )

        self.t.close()

        for s in tracking.MessageState:
            with self.assertRaisesRegex(
                    RuntimeError,
                    "tracker is closed"):
                self.t._set_state(s)
            self.assertEqual(
                self.t.state,
                tracking.MessageState.DELIVERED_TO_SERVER,
            )
            self.assertEqual(
                self.t.response,
                unittest.mock.sentinel.response,
            )

    def test__set_timeout_with_number_calls_call_later(self):
        with contextlib.ExitStack() as stack:
            get_event_loop = stack.enter_context(unittest.mock.patch(
                "asyncio.get_event_loop",
            ))

            self.t.set_timeout(unittest.mock.sentinel.timeout)

        get_event_loop.assert_called_once_with()
        get_event_loop().call_later.assert_called_once_with(
            unittest.mock.sentinel.timeout,
            self.t.close,
        )

    def test__set_timeout_with_timedelta_calls_call_later(self):
        with contextlib.ExitStack() as stack:
            get_event_loop = stack.enter_context(unittest.mock.patch(
                "asyncio.get_event_loop",
            ))

            self.t.set_timeout(timedelta(days=1))

        get_event_loop.assert_called_once_with()
        get_event_loop().call_later.assert_called_once_with(
            timedelta(days=1).total_seconds(),
            self.t.close,
        )


class TestBasicTrackingService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = tracking.BasicTrackingService(self.cc)

    def tearDown(self):
        del self.s
        del self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            tracking.BasicTrackingService,
            aioxmpp.service.Service,
        ))

    def test_installs_message_filter(self):
        self.assertTrue(aioxmpp.service.is_inbound_message_filter(
            tracking.BasicTrackingService._inbound_message_filter,
        ))

    def test_inbound_message_filter_forwards_stanzas(self):
        for type_ in aioxmpp.MessageType:
            msg = aioxmpp.Message(
                type_=type_,
                from_=TEST_PEER,
                to=TEST_LOCAL,
            )
            self.assertIs(
                msg,
                self.s._inbound_message_filter(msg),
            )

    def test_inbound_message_filter_forwards_broken_stanzas(self):
        msg = object()
        self.assertIs(
            msg,
            self.s._inbound_message_filter(msg),
        )

    def test_attach_tracker_calls_autoset_id(self):
        msg = unittest.mock.Mock()
        self.s.attach_tracker(msg)
        msg.autoset_id.assert_called_once_with()

    def test_attach_tracker_with_subsequent_error_modifies_tracking(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))

        self.assertIsNone(self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.ERROR
        )
        self.assertIs(
            tracker.response,
            error,
        )

    def test_attach_tracker_with_subsequent_error_from_bare_modifies_tracking(
            self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))
        error.from_ = error.from_.bare()

        self.assertIsNone(self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.ERROR
        )
        self.assertIs(
            tracker.response,
            error,
        )

    def test_attach_tracker_with_subsequent_error_from_other_id_untracked(
            self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))
        error.id_ = "fnord"

        self.assertIs(self.s._inbound_message_filter(error), error)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT
        )
        self.assertIs(
            tracker.response,
            None,
        )

    def test_attach_tracker_sets_delivered_to_server_if_ok(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        token = unittest.mock.Mock()
        self.assertIs(
            self.s.attach_tracker(msg, tracker, token),
            tracker
        )

        token.future.add_done_callback.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (cb, ), _ = token.future.add_done_callback.mock_calls[0]

        cb(token.future)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.DELIVERED_TO_SERVER,
        )

    def test_attach_tracker_sets_aborted_if_aborted(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        token = unittest.mock.Mock()
        self.assertIs(
            self.s.attach_tracker(msg, tracker, token),
            tracker
        )

        token.future.add_done_callback.assert_called_once_with(
            unittest.mock.ANY,
        )
        token.future.result.side_effect = RuntimeError()

        _, (cb, ), _ = token.future.add_done_callback.mock_calls[0]

        cb(token.future)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.ABORTED,
        )

    def test_attach_tracker_sets_aborted_on_other_exception(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        token = unittest.mock.Mock()
        self.assertIs(
            self.s.attach_tracker(msg, tracker, token),
            tracker
        )

        class FooException(Exception):
            pass

        token.future.add_done_callback.assert_called_once_with(
            unittest.mock.ANY,
        )
        token.future.result.side_effect = FooException()

        _, (cb, ), _ = token.future.add_done_callback.mock_calls[0]

        cb(token.future)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.ABORTED,
        )

    def test_attach_tracker_handler_does_not_raise_exception_if_state_already_set(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        token = unittest.mock.Mock()
        self.assertIs(
            self.s.attach_tracker(msg, tracker, token),
            tracker
        )

        token.future.add_done_callback.assert_called_once_with(
            unittest.mock.ANY,
        )

        _, (cb, ), _ = token.future.add_done_callback.mock_calls[0]

        tracker._set_state(tracking.MessageState.DELIVERED_TO_RECIPIENT)

        cb(token.future)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.DELIVERED_TO_RECIPIENT,
        )

    def test_attach_tracker_ignores_cancelled_stanza_token(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        token = unittest.mock.Mock()
        self.assertIs(
            self.s.attach_tracker(msg, tracker, token),
            tracker
        )

        token.future.add_done_callback.assert_called_once_with(
            unittest.mock.ANY,
        )
        token.future.result.side_effect = asyncio.CancelledError()

        _, (cb, ), _ = token.future.add_done_callback.mock_calls[0]

        cb(token.future)

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT,
        )

    def test_attach_tracker_does_not_set_error_if_in_delivered_state(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        tracker._set_state(tracking.MessageState.DELIVERED_TO_RECIPIENT)

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))

        self.assertIsNone(self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.DELIVERED_TO_RECIPIENT
        )
        self.assertIs(
            tracker.response,
            None,
        )

    def test_attach_tracker_does_not_set_error_if_in_seen_state(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        tracker._set_state(tracking.MessageState.SEEN_BY_RECIPIENT)

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))

        self.assertIsNone(self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.SEEN_BY_RECIPIENT
        )
        self.assertIs(
            tracker.response,
            None,
        )

    def test_attach_tracker_with_subsequent_chat_is_not_tracked(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        reply = msg.make_reply()
        reply.id_ = msg.id_
        self.assertIs(
            reply,
            self.s._inbound_message_filter(reply)
        )

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT
        )

    def test_inbound_message_filter_ignores_closed_tracker(self):
        tracker = tracking.MessageTracker()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        self.assertIs(
            self.s.attach_tracker(msg, tracker),
            tracker
        )

        tracker.close()

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))

        self.assertIs(error, self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.IN_TRANSIT,
        )
        self.assertTrue(tracker.closed)

    def test_attach_tracker_autocreates_tracker_if_needed(self):
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT,
            from_=TEST_LOCAL,
            to=TEST_PEER,
        )
        tracker = self.s.attach_tracker(msg, None)
        self.assertIsInstance(tracker, tracking.MessageTracker)

        error = msg.make_error(aioxmpp.stanza.Error.from_exception(
            aioxmpp.XMPPCancelError(
                aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED
            )
        ))

        self.assertIsNone(self.s._inbound_message_filter(error))

        self.assertEqual(
            tracker.state,
            tracking.MessageState.ERROR
        )
        self.assertIs(
            tracker.response,
            error,
        )

    def test_send_tracked_attaches_and_returns_tracker(self):
        tracker = unittest.mock.sentinel.tracker
        msg = unittest.mock.sentinel.message

        with contextlib.ExitStack() as stack:
            attach_tracker = stack.enter_context(unittest.mock.patch.object(
                self.s,
                "attach_tracker",
            ))

            result = self.s.send_tracked(msg, tracker)

            self.cc.enqueue.assert_called_once_with(
                msg,
            )

            attach_tracker.assert_called_once_with(
                msg,
                tracker,
                self.cc.enqueue(),
            )

            self.assertEqual(
                result,
                self.cc.enqueue(),
            )
