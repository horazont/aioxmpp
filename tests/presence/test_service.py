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
import itertools
import types
import unittest

import aioxmpp
import aioxmpp.presence.service as presence_service
import aioxmpp.service as service
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
    CoroutineMock,
    make_listener,
)


TEST_PEER_JID1 = structs.JID.fromstr("bar@b.example")
TEST_PEER_JID2 = structs.JID.fromstr("baz@c.example")


class TestPresenceClient(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            presence_service.PresenceClient,
            service.Service
        ))

    def setUp(self):
        self.cc = make_connected_client()
        self.presence_dispatcher = aioxmpp.dispatcher.SimplePresenceDispatcher(
            self.cc,
        )
        self.s = presence_service.PresenceClient(self.cc, dependencies={
            aioxmpp.dispatcher.SimplePresenceDispatcher:
                self.presence_dispatcher,
        })
        self.listener = make_listener(self.s)

    def test_handle_presence_decorated(self):
        self.assertTrue(
            aioxmpp.dispatcher.is_presence_handler(
                structs.PresenceType.AVAILABLE,
                None,
                presence_service.PresenceClient.handle_presence,
            ),
        )

        self.assertTrue(
            aioxmpp.dispatcher.is_presence_handler(
                structs.PresenceType.UNAVAILABLE,
                None,
                presence_service.PresenceClient.handle_presence,
            ),
        )

        self.assertTrue(
            aioxmpp.dispatcher.is_presence_handler(
                structs.PresenceType.ERROR,
                None,
                presence_service.PresenceClient.handle_presence,
            ),
        )

    def test_return_empty_resource_set_for_arbitrary_jid(self):
        self.assertDictEqual(
            {},
            self.s.get_peer_resources(TEST_PEER_JID1)
        )

    def test_track_available_resources(self):
        st1 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        self.assertDictEqual(
            {
                "foo": st1
            },
            self.s.get_peer_resources(TEST_PEER_JID1)
        )

        st2 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        self.assertDictEqual(
            {
                "foo": st1,
                "bar": st2,
            },
            self.s.get_peer_resources(TEST_PEER_JID1)
        )

        st = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertDictEqual(
            {
                "bar": st2
            },
            self.s.get_peer_resources(TEST_PEER_JID1)
        )

    def test_get_stanza_returns_None_for_arbitrary_jid(self):
        self.assertIsNone(self.s.get_stanza(
            TEST_PEER_JID1.replace(resource="foo")
        ))

    def test_get_stanza_returns_original_stanza_as_received(self):
        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

    def test_get_stanza_returns_error_stanza_for_bare_jid_as_received(self):
        st = stanza.Presence(type_=structs.PresenceType.ERROR,
                             from_=TEST_PEER_JID1)
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

        self.assertDictEqual(
            {},
            self.s.get_peer_resources(st.from_.bare())
        )

    def test_get_stanza_returns_error_stanza_for_full_jid_as_received_for_bare_jid(
            self):
        st = stanza.Presence(type_=structs.PresenceType.ERROR,
                             from_=TEST_PEER_JID1)
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_.replace(resource="foo")), st)

    def test_error_stanza_overrides_all_other_stanzas(self):
        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

        st = stanza.Presence(type_=structs.PresenceType.ERROR,
                             from_=TEST_PEER_JID1)
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_.replace(resource="foo")), st)

    def test_get_any_non_error_stanza_erases_error_stanza(self):
        st = stanza.Presence(type_=structs.PresenceType.ERROR,
                             from_=TEST_PEER_JID1)
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

        st = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertIsNone(self.s.get_stanza(st.from_.bare()))
        self.assertIsNone(self.s.get_stanza(st.from_))

        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertIs(self.s.get_stanza(st.from_), st)

    def test_get_most_available_stanza(self):
        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st)

        self.assertIs(
            self.s.get_most_available_stanza(TEST_PEER_JID1),
            st
        )

        staway = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                 show=structs.PresenceShow.AWAY,
                                 from_=TEST_PEER_JID1.replace(resource="baz"))
        self.s.handle_presence(staway)

        self.assertIs(
            self.s.get_most_available_stanza(TEST_PEER_JID1),
            st
        )

        stdnd = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                                show=structs.PresenceShow.DND,
                                from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(stdnd)

        self.assertEqual(
            len(self.s.get_peer_resources(TEST_PEER_JID1)),
            3
        )

        self.assertIs(
            self.s.get_most_available_stanza(TEST_PEER_JID1),
            stdnd
        )

    def test_get_most_available_stanza_returns_None_for_unavailable_JID(self):
        self.assertIsNone(self.s.get_most_available_stanza(TEST_PEER_JID1))

    def test_handle_presence_emits_available_signals(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_bare_available.connect(base.bare)
        self.s.on_available.connect(base.full)

        st1 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        st2 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.bare(st1),
                unittest.mock.call.full(st1.from_, st1),
                unittest.mock.call.full(st2.from_, st2),
            ]
        )

    def test_handle_presence_ignores_available_presence_from_None(self):
        st1 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=None)
        self.s.handle_presence(st1)

        self.assertSequenceEqual(self.listener.mock_calls, [])

    def test_handle_presence_ignores_available_presence_from_None(self):
        st1 = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                              from_=None)
        self.s.handle_presence(st1)

        self.assertSequenceEqual(self.listener.mock_calls, [])

    def test_handle_presence_ignores_available_presence_from_None(self):
        st1 = stanza.Presence(type_=structs.PresenceType.ERROR,
                              from_=None)
        self.s.handle_presence(st1)

        self.assertSequenceEqual(self.listener.mock_calls, [])

    def test_handle_presence_emits_available_signals_only_if_not_available(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_bare_available.connect(base.bare)
        self.s.on_available.connect(base.full)

        st1 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        st2 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        st3 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st3)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.bare(st1),
                unittest.mock.call.full(st1.from_, st1),
                unittest.mock.call.full(st2.from_, st2),
            ]
        )

    def test_handle_presence_does_not_emit_unavailable_if_already_unavailable(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_bare_unavailable.connect(base.bare)
        self.s.on_unavailable.connect(base.full)

        st2 = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        st1 = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        self.assertSequenceEqual(
            base.mock_calls,
            [
            ]
        )


    def test_handle_presence_emits_unavailable_signals(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_bare_unavailable.connect(base.bare)
        self.s.on_unavailable.connect(base.full)

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="foo"))
        )

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="bar"))
        )

        st2 = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        st1 = stanza.Presence(type_=structs.PresenceType.UNAVAILABLE,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.full(st2.from_, st2),
                unittest.mock.call.full(st1.from_, st1),
                unittest.mock.call.bare(st1),
            ]
        )

    def test_handle_presence_emits_changed_signals(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_changed.connect(base.full)

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="foo"))
        )

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="bar"))
        )

        st1 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              show=structs.PresenceShow.DND,
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        st2 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              show=structs.PresenceShow.DND,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        st3 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              show=structs.PresenceShow.CHAT,
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st3)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.full(st1.from_, st1),
                unittest.mock.call.full(st2.from_, st2),
                unittest.mock.call.full(st3.from_, st3),
            ]
        )

    def test_handle_presence_emits_unavailable_on_error(self):
        base = unittest.mock.Mock()
        base.bare.return_value = False
        base.full.return_value = False

        self.s.on_unavailable.connect(base.full)
        self.s.on_bare_unavailable.connect(base.bare)

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="foo"))
        )

        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            from_=TEST_PEER_JID1.replace(resource="bar"))
        )

        st = stanza.Presence(type_=structs.PresenceType.ERROR,
                             from_=TEST_PEER_JID1)
        self.s.handle_presence(st)

        self.assertIn(
            unittest.mock.call.full(st.from_.replace(resource="foo"), st),
            base.mock_calls
        )

        self.assertIn(
            unittest.mock.call.full(st.from_.replace(resource="bar"), st),
            base.mock_calls
        )

        self.assertIn(
            unittest.mock.call.bare(st),
            base.mock_calls
        )

    def tearDown(self):
        del self.s
        del self.cc


class TestDirectedPresenceHandle(unittest.TestCase):
    def setUp(self):
        self.svc = unittest.mock.Mock(spec=presence_service.PresenceServer)
        self.h = presence_service.DirectedPresenceHandle(
            self.svc,
            TEST_PEER_JID1,
        )

    def tearDown(self):
        del self.svc
        del self.h

    def test_init(self):
        self.assertEqual(self.h.address, TEST_PEER_JID1)
        self.assertIsNone(self.h.presence_filter)
        self.assertIs(self.h.muted, False)

    def test_address_cannot_be_assigned_directly(self):
        with self.assertRaises(AttributeError):
            self.h.address = self.h.address

    def test_muted_cannot_be_assigned_directly(self):
        with self.assertRaises(AttributeError):
            self.h.muted = self.h.muted

    def test_presence_filter_can_be_assigned_to(self):
        self.h.presence_filter = unittest.mock.sentinel.foo
        self.assertEqual(self.h.presence_filter,
                         unittest.mock.sentinel.foo)

    def test_set_muted_changes_muted(self):
        self.h.set_muted(True)

        self.assertTrue(self.h.muted)

        self.h.set_muted(False)

        self.assertFalse(self.h.muted)

    def test_set_muted_raises_if_unsubscribed(self):
        self.h.unsubscribe()

        with self.assertRaisesRegexp(
                RuntimeError,
                r"directed presence relationship is unsubscribed"):
            self.h.set_muted(True)

        with self.assertRaisesRegexp(
                RuntimeError,
                r"directed presence relationship is unsubscribed"):
            self.h.set_muted(False)

    def test_resend_presence_raises_if_unsubscribed(self):
        self.h.unsubscribe()

        with self.assertRaisesRegexp(
                RuntimeError,
                r"directed presence relationship is unsubscribed"):
            self.h.resend_presence()


class TestPresenceServer(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.send = CoroutineMock()
        self.cc.send.return_value = None
        self.s = presence_service.PresenceServer(self.cc)

    def tearDown(self):
        del self.s
        del self.cc

    def test_no_presence_to_emit_by_default(self):
        self.assertEqual(self.s.state, aioxmpp.PresenceState(False))
        self.assertDictEqual(self.s.status, {})
        self.assertEqual(self.s.priority, 0)

        run_coroutine(self.cc.before_stream_established())

        self.cc.send.assert_not_called()

    def test_before_stream_established_handler_returns_true_for_unav(self):
        self.assertTrue(
            run_coroutine(self.s._before_stream_established())
        )

    def test_before_stream_established_handler_returns_true_for_avail(self):
        self.s.set_presence(aioxmpp.PresenceState(True))

        self.assertTrue(
            run_coroutine(self.s._before_stream_established())
        )

    def test_set_presence_rejects_non_PresenceState_state(self):
        with self.assertRaisesRegex(
                TypeError,
                r"invalid state: got <enum '.*PresenceType'>, "
                r"expected aioxmpp.PresenceState"):
            self.s.set_presence(aioxmpp.PresenceType.AVAILABLE)

    def test_set_presence_with_status_string(self):
        # not established
        self.cc.established = False

        self.s.set_presence(
            aioxmpp.PresenceState(True),
            status="foo"
        )

        self.assertEqual(
            self.s.state,
            aioxmpp.PresenceState(True)
        )

        self.assertDictEqual(
            self.s.status,
            {
                None: "foo",
            }
        )

    def test_set_presence_with_status_mapping(self):
        # not established
        self.cc.established = False

        m = {
            None: "foo",
            aioxmpp.structs.LanguageTag.fromstr("en-gb"): "bar",
        }

        self.s.set_presence(
            aioxmpp.PresenceState(True),
            status=m,
        )

        self.assertEqual(
            self.s.state,
            aioxmpp.PresenceState(True)
        )

        self.assertDictEqual(
            self.s.status,
            m,
        )

        self.assertIsNot(self.s.status, m)

        del m[None]

        self.assertIn(None, self.s.status)

    def test_set_presence_priority(self):
        self.cc.established = False

        self.s.set_presence(aioxmpp.PresenceState(False), priority=10)

        self.assertEqual(
            self.s.priority,
            10,
        )

    def test_set_presence_rejects_non_integer_priority(self):
        self.cc.established = False

        with self.assertRaisesRegex(
                TypeError,
                r"invalid priority: got <class 'str'>, expected integer"):
            self.s.set_presence(
                aioxmpp.PresenceState(True),
                status="foo",
                priority="10",
            )

        self.assertEqual(self.s.state, aioxmpp.PresenceState(False))
        self.assertDictEqual(self.s.status, {})

    def test_emit_configured_presence_when_stream_establishes(self):
        self.s.set_presence(aioxmpp.PresenceState(True))

        with unittest.mock.patch.object(self.s, "make_stanza") as make_stanza:
            make_stanza.return_value = unittest.mock.sentinel.presence
            run_coroutine(self.cc.before_stream_established())

        self.cc.send.assert_called_with(
            unittest.mock.sentinel.presence,
        )

    def test_set_presence_broadcasts_if_established(self):
        self.cc.established = True

        def check_state():
            self.assertEqual(self.cc.state, aioxmpp.PresenceState(True))
            self.assertEqual(self.cc.status, {None: "foo"})

        with unittest.mock.patch.object(self.s, "make_stanza") as make_stanza:
            make_stanza.return_value = unittest.mock.sentinel.presence

            result = self.s.set_presence(
                aioxmpp.PresenceState(True),
                status="foo",
            )

        self.cc.enqueue.assert_called_with(
            unittest.mock.sentinel.presence
        )

        self.assertEqual(
            result,
            self.cc.enqueue()
        )

    def test_make_stanza_converts_state_to_stanza(self):
        m = unittest.mock.Mock(spec=aioxmpp.PresenceState)
        self.s.set_presence(m)

        stanza = self.s.make_stanza()
        self.assertIsInstance(
            stanza,
            aioxmpp.Presence,
        )

        m.apply_to_stanza.assert_called_with(stanza)

    def test_make_stanza_converts_incorporates_status(self):
        self.s.set_presence(aioxmpp.PresenceState(True), status="foo")

        stanza = self.s.make_stanza()
        self.assertDictEqual(
            stanza.status,
            {None: "foo"}
        )

    def test_set_presence_state_emits_events(self):
        new_state = aioxmpp.PresenceState(True)
        new_status = {None: "foo"}
        new_priority = -2

        def check_values():
            self.assertEqual(
                self.s.state,
                new_state,
            )
            self.assertDictEqual(
                self.s.status,
                new_status,
            )
            self.assertEqual(
                self.s.priority,
                new_priority,
            )

        overall_cb = unittest.mock.Mock()
        overall_cb.side_effect = check_values
        state_cb = unittest.mock.Mock()
        state_cb.side_effect = check_values

        self.s.on_presence_changed.connect(overall_cb)
        self.s.on_presence_state_changed.connect(state_cb)

        self.s.set_presence(
            new_state,
            status=new_status,
            priority=new_priority,
        )

        overall_cb.assert_called_once_with()
        state_cb.assert_called_once_with()

    def test_set_presence_state_does_not_emit_state_event_if_state_unchanged(self):
        new_state = aioxmpp.PresenceState(False)
        new_status = {None: "foo"}
        new_priority = -2

        def check_values():
            self.assertEqual(
                self.s.state,
                new_state,
            )
            self.assertDictEqual(
                self.s.status,
                new_status,
            )
            self.assertEqual(
                self.s.priority,
                new_priority,
            )

        overall_cb = unittest.mock.Mock()
        overall_cb.side_effect = check_values
        state_cb = unittest.mock.Mock()
        state_cb.side_effect = check_values

        self.s.on_presence_changed.connect(overall_cb)
        self.s.on_presence_state_changed.connect(state_cb)

        self.s.set_presence(
            new_state,
            status=new_status,
            priority=new_priority,
        )

        overall_cb.assert_called_once_with()
        state_cb.assert_not_called()

    def test_set_presence_state_does_not_emit_events_if_unchanged(self):
        new_state = aioxmpp.PresenceState(False)
        new_status = {}
        new_priority = 0

        def check_values():
            self.assertEqual(
                self.s.state,
                new_state,
            )
            self.assertDictEqual(
                self.s.status,
                new_status,
            )
            self.assertEqual(
                self.s.priority,
                new_priority,
            )

        overall_cb = unittest.mock.Mock()
        overall_cb.side_effect = check_values
        state_cb = unittest.mock.Mock()
        state_cb.side_effect = check_values

        self.s.on_presence_changed.connect(overall_cb)
        self.s.on_presence_state_changed.connect(state_cb)

        self.s.set_presence(
            new_state,
            status=new_status,
            priority=new_priority,
        )

        overall_cb.assert_not_called()
        state_cb.assert_not_called()

    def test_set_presence_state_does_not_emit_stanza_if_unchanged(self):
        new_state = aioxmpp.PresenceState(False)
        new_status = {}
        new_priority = 0

        self.s.set_presence(
            new_state,
            status=new_status,
            priority=new_priority,
        )

        self.cc.enqueue.assert_not_called()

    def test_resend_presence_broadcasts_if_established(self):
        self.cc.established = True

        with unittest.mock.patch.object(self.s, "make_stanza") as make_stanza:
            make_stanza.return_value = unittest.mock.sentinel.presence

            result = self.s.resend_presence()

        self.cc.enqueue.assert_called_with(
            unittest.mock.sentinel.presence
        )

        self.assertEqual(
            result,
            self.cc.enqueue(),
        )

    def test_subscribe_peer_directed_creates_handle(self):
        h = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.assertIsInstance(h, presence_service.DirectedPresenceHandle)
        self.assertEqual(h.address, TEST_PEER_JID1)
        self.assertFalse(h.muted)
        self.assertIsNone(h.presence_filter)

    def test_subscribe_peer_directed_different_handles_for_different_peers(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID2
        )

        self.assertEqual(h1.address, TEST_PEER_JID1)
        self.assertEqual(h2.address, TEST_PEER_JID2)

    def test_subscribe_peer_directed_rejects_duplicate_peer(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for "
                r"the same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1
            )

    def test_subscribe_peer_directed_allows_multiple_sessions_for_distinct_resources(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="y")
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="x"))
        self.assertEqual(h2.address, TEST_PEER_JID1.replace(resource="y"))

    def test_subscribe_peer_directed_does_not_allow_resource_and_bare(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID2.replace(resource="y")
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="y")
            )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID2
            )

    def test_unsubscribing_DirectedPresenceHandle_frees_the_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        h1.unsubscribe()

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID1)
        self.assertEqual(h2.address, TEST_PEER_JID1)

    def test_unsubscribing_bare_DirectedPresenceHandle_frees_the_slot_for_full(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        h1.unsubscribe()

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID1)
        self.assertEqual(h2.address, TEST_PEER_JID1.replace(resource="x"))

    def test_unsubscribing_full_DirectedPresenceHandle_frees_the_slot_for_bare(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h1.unsubscribe()

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="x"))
        self.assertEqual(h2.address, TEST_PEER_JID1)

    def test_unsubscribing_single_full_DirectedPresenceHandle_does_not_free_the_slot_for_bare(self):  # NOQA
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="y")
        )

        h1.unsubscribe()

        with self.assertRaises(ValueError):
            h3 = self.s.subscribe_peer_directed(
                TEST_PEER_JID1
            )

        h2.unsubscribe()

        h3 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.assertIsNot(h1, h3)
        self.assertIsNot(h2, h3)
        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="x"))
        self.assertEqual(h2.address, TEST_PEER_JID1.replace(resource="y"))
        self.assertEqual(h3.address, TEST_PEER_JID1)

    def test_unsubscribe_is_idempotent(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h1.unsubscribe()

        h1.unsubscribe()

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

    def test_unsubscribe_is_idempotent_even_after_resubscription(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h1.unsubscribe()

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        h1.unsubscribe()

        with self.assertRaises(ValueError):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x")
            )

    def test_rebind_directed_presence_to_other_jid(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID2
        )

        self.assertEqual(h1.address, TEST_PEER_JID2)

    def test_rebind_directed_presence_to_other_jid_releases_old_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID2
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID2)
        self.assertEqual(h2.address, TEST_PEER_JID1)

    def test_rebind_directed_presence_to_other_jid_holds_new_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID2
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID2
            )

    def test_rebind_directed_presence_to_existing_jid_fails(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID2
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.rebind_directed_presence(
                h1,
                TEST_PEER_JID2
            )

    def test_rebind_directed_presence_noop(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1
        )

        self.assertEqual(h1.address, TEST_PEER_JID1)

    def test_rebind_directed_presence_bare_to_full(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="x")
        )

        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="x"))

    def test_rebind_directed_presence_bare_to_full_holds_new_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="x")
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x")
            )

    def test_rebind_directed_presence_bare_to_full_blocks_bare_alloc(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="x")
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1
            )

    def test_rebind_directed_presence_full_to_bare(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1
        )

        self.assertEqual(h1.address, TEST_PEER_JID1)

    def test_rebind_directed_presence_full_to_bare_holds_new_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1
            )

    def test_rebind_directed_presence_full_to_bare_blocks_full_alloc(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1
        )

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x")
            )

    def test_rebind_directed_presence_change_resource(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="y")
        )

        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="y"))

    def test_rebind_directed_presence_change_resource_releases_old_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="y")
        )

        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="y"))

        h2 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.assertIsNot(h1, h2)
        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="y"))
        self.assertEqual(h2.address, TEST_PEER_JID1.replace(resource="x"))

    def test_rebind_directed_presence_change_resource_holds_new_slot(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.s.rebind_directed_presence(
            h1,
            TEST_PEER_JID1.replace(resource="y")
        )

        self.assertEqual(h1.address, TEST_PEER_JID1.replace(resource="y"))

        with self.assertRaisesRegex(
                ValueError,
                r"cannot create multiple directed presence sessions for the "
                r"same peer"):
            self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="y")
            )

    def test_resend_presence_emits_stanza_for_directed_session(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x")
        )

        self.cc.enqueue.reset_mock()

        stanzas = []

        def stanza_generator():
            while True:
                st = aioxmpp.stanza.Presence()
                st.type_ = aioxmpp.structs.PresenceType.AVAILABLE
                stanzas.append(st)
                yield st

        def token_generator():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel, "token{}".format(i))

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s, "make_stanza",
                side_effect=stanza_generator(),
            ))

            self.cc.enqueue.side_effect = token_generator()

            result = self.s.resend_presence()

        self.cc.established = True

        (_, (p1, ), _), (_, (p2, ), _) = self.cc.enqueue.mock_calls

        self.assertIsNot(p1, p2)
        self.assertEqual(p1, stanzas[0])
        self.assertEqual(p2, stanzas[1])

        self.assertEqual(p2.to, TEST_PEER_JID1.replace(resource="x"))

        self.assertEqual(result, unittest.mock.sentinel.token0)

    def test_direct_presence_stanza_passes_through_filter(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
        )

        self.cc.enqueue.reset_mock()

        filter_func = unittest.mock.Mock()

        h1.presence_filter = filter_func

        stanzas = []

        def stanza_generator():
            while True:
                st = aioxmpp.stanza.Presence()
                st.type_ = aioxmpp.structs.PresenceType.AVAILABLE
                stanzas.append(st)
                yield st

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s, "make_stanza",
                side_effect=stanza_generator(),
            ))

            self.s.resend_presence()

        self.cc.established = True

        _, (_, (p2, ), _) = self.cc.enqueue.mock_calls

        filter_func.assert_called_once_with(stanzas[1])
        self.assertEqual(p2, filter_func())

    def test_emission_of_directed_presence_is_skipped_if_filter_returns_None(
            self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
        )

        self.cc.enqueue.reset_mock()

        filter_func = unittest.mock.Mock()
        filter_func.return_value = None

        h1.presence_filter = filter_func

        stanzas = []

        def stanza_generator():
            while True:
                st = aioxmpp.stanza.Presence()
                st.type_ = aioxmpp.structs.PresenceType.AVAILABLE
                stanzas.append(st)
                yield st

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s, "make_stanza",
                side_effect=stanza_generator(),
            ))

            self.s.resend_presence()

        self.cc.established = True

        self.assertEqual(len(self.cc.enqueue.mock_calls), 1)

        filter_func.assert_called_once_with(stanzas[1])

    def test_emission_of_directed_presence_is_skipped_for_muted(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
            muted=True
        )

        self.cc.enqueue.reset_mock()

        filter_func = unittest.mock.Mock()
        h1.presence_filter = filter_func

        stanzas = []

        def stanza_generator():
            while True:
                st = aioxmpp.stanza.Presence()
                st.type_ = aioxmpp.structs.PresenceType.AVAILABLE
                stanzas.append(st)
                yield st

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s, "make_stanza",
                side_effect=stanza_generator(),
            ))

            self.s.resend_presence()

        self.cc.established = True

        self.assertEqual(len(self.cc.enqueue.mock_calls), 1)

        filter_func.assert_not_called()

    def test_creating_unmuted_directed_presence_relation_emits_presence(self):
        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1 = self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x"),
            )

        self.assertFalse(h1.muted)

        make_stanza.assert_called_once_with()

        (_, (p, ), _), = self.cc.enqueue.mock_calls

        self.assertIs(p, st)
        self.assertEqual(p.to, TEST_PEER_JID1.replace(resource="x"))

    def test_creating_muted_directed_presence_relation_does_not_emit_presence(self):  # NOQA
        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1 = self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x"),
                muted=True,
            )

        self.assertTrue(h1.muted)

        make_stanza.assert_not_called()
        self.cc.enqueue.assert_not_called()

    def test_unmuting_relation_emits_presence_by_default(self):
        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
            muted=True,
        )

        self.assertTrue(h1.muted)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1.set_muted(False)

        make_stanza.assert_called_once_with()

        (_, (p, ), _), = self.cc.enqueue.mock_calls

        self.assertIs(p, st)
        self.assertEqual(p.to, TEST_PEER_JID1.replace(resource="x"))

    def test_unmuting_relation_twice_does_not_reemit_presence(self):
        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1 = self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x"),
                muted=True,
            )

        self.assertTrue(h1.muted)

        h1.set_muted(False)

        self.cc.enqueue.reset_mock()

        h1.set_muted(False)

        self.cc.enqueue.assert_not_called()

    def test_muted_relationship_does_not_emit_presence_when_resending(self):
        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1 = self.s.subscribe_peer_directed(
                TEST_PEER_JID1.replace(resource="x"),
                muted=True,
            )

        self.assertTrue(h1.muted)

        make_stanza.assert_not_called()
        self.cc.enqueue.assert_not_called()

    def test_resend_presence_on_muted_handle_emits_presence(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
            muted=True,
        )

        self.cc.enqueue.assert_not_called()

        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1.resend_presence()

        self.cc.enqueue.assert_called_once_with(st)
        self.assertEqual(st.to, h1.address)

    def test_resend_presence_on_unmuted_handle_emits_presence(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
        )

        self.cc.enqueue.reset_mock()

        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1.resend_presence()

        self.cc.enqueue.assert_called_once_with(st)
        self.assertEqual(st.to, h1.address)

    def test_resend_presence_calls_filter(self):
        h1 = self.s.subscribe_peer_directed(
            TEST_PEER_JID1.replace(resource="x"),
            muted=True
        )

        self.cc.enqueue.assert_not_called()

        filter_func = unittest.mock.Mock()
        h1.presence_filter = filter_func

        st = unittest.mock.Mock(spec=aioxmpp.stanza.Presence)

        with unittest.mock.patch.object(self.s, "make_stanza",
                                        return_value=st) as make_stanza:
            h1.resend_presence()

        filter_func.assert_called_once_with(st)
        self.cc.enqueue.assert_called_once_with(filter_func())
        self.assertEqual(st.to, h1.address)
