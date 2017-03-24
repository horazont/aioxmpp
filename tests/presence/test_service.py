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


class TestPresenceServer(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.stream.send = CoroutineMock()
        self.cc.stream.send.return_value = None
        self.s = presence_service.PresenceServer(self.cc)

    def tearDown(self):
        del self.s
        del self.cc

    def test_no_presence_to_emit_by_default(self):
        self.assertEqual(self.s.state, aioxmpp.PresenceState(False))
        self.assertDictEqual(self.s.status, {})
        self.assertEqual(self.s.priority, 0)

        run_coroutine(self.cc.before_stream_established())

        self.cc.stream.send.assert_not_called()

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

        self.cc.stream.send.assert_called_with(
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

        self.cc.stream.enqueue.assert_called_with(
            unittest.mock.sentinel.presence
        )

        self.assertEqual(
            result,
            self.cc.stream.enqueue()
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

        self.cc.stream.enqueue.assert_not_called()

    def test_resend_presence_broadcasts_if_established(self):
        self.cc.established = True

        with unittest.mock.patch.object(self.s, "make_stanza") as make_stanza:
            make_stanza.return_value = unittest.mock.sentinel.presence

            result = self.s.resend_presence()

        self.cc.stream.enqueue.assert_called_with(
            unittest.mock.sentinel.presence
        )

        self.assertEqual(
            result,
            self.cc.stream.enqueue(),
        )
