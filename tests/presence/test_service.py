import unittest

import aioxmpp.presence.service as presence_service
import aioxmpp.service as service
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.xso as xso
import aioxmpp.xso.model

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
)


TEST_PEER_JID1 = structs.JID.fromstr("bar@b.example")
TEST_PEER_JID2 = structs.JID.fromstr("baz@c.example")


class TestService(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            presence_service.Service,
            service.Service
        ))

    def setUp(self):
        self.cc = make_connected_client()
        self.s = presence_service.Service(self.cc)

    def test_setup(self):
        self.assertSequenceEqual(
            self.cc.mock_calls,
            [
                unittest.mock.call.stream.register_presence_callback(
                    structs.PresenceType.AVAILABLE,
                    None,
                    self.s.handle_presence
                ),
                unittest.mock.call.stream.register_presence_callback(
                    structs.PresenceType.ERROR,
                    None,
                    self.s.handle_presence
                ),
                unittest.mock.call.stream.register_presence_callback(
                    structs.PresenceType.UNAVAILABLE,
                    None,
                    self.s.handle_presence
                ),
            ]
        )

    def test_shutdown(self):
        self.cc.mock_calls.clear()
        run_coroutine(self.s.shutdown())

        self.assertSequenceEqual(
            self.cc.mock_calls,
            [
                unittest.mock.call.stream.unregister_presence_callback(
                    structs.PresenceType.UNAVAILABLE,
                    None,
                ),
                unittest.mock.call.stream.unregister_presence_callback(
                    structs.PresenceType.ERROR,
                    None,
                ),
                unittest.mock.call.stream.unregister_presence_callback(
                    structs.PresenceType.AVAILABLE,
                    None,
                ),
            ]
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


        self.s.handle_presence(
            stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                            show="dnd",
                            from_=TEST_PEER_JID1.replace(resource="bar"))
        )

        self.assertIs(
            self.s.get_most_available_stanza(TEST_PEER_JID1),
            st
        )

        st = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                             show="chat",
                             from_=TEST_PEER_JID1.replace(resource="baz"))
        self.s.handle_presence(st)

        self.assertEqual(
            len(self.s.get_peer_resources(TEST_PEER_JID1)),
            3
        )

        self.assertIs(
            self.s.get_most_available_stanza(TEST_PEER_JID1),
            st
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
                              show="dnd",
                              from_=TEST_PEER_JID1.replace(resource="foo"))
        self.s.handle_presence(st1)

        st2 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              show="dnd",
                              from_=TEST_PEER_JID1.replace(resource="bar"))
        self.s.handle_presence(st2)

        st3 = stanza.Presence(type_=structs.PresenceType.AVAILABLE,
                              show="chat",
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
