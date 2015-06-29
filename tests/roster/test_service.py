import unittest

import aioxmpp.errors as errors
import aioxmpp.roster.service as roster_service
import aioxmpp.roster.xso as roster_xso
import aioxmpp.service as service
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs

from aioxmpp.utils import namespaces

from ..testutils import make_connected_client, run_coroutine


class TestItem(unittest.TestCase):
    def setUp(self):
        self.jid = structs.JID.fromstr("user@foo.example")

    def test_init(self):
        item = roster_service.Item(self.jid)
        self.assertEqual(self.jid, item.jid)
        self.assertEqual("none", item.subscription)
        self.assertFalse(item.approved)
        self.assertIsNone(item.ask)
        self.assertIsNone(item.name)

        item = roster_service.Item(
            self.jid,
            subscription="both",
            approved=True,
            ask="subscribe",
            name="foobar")
        self.assertEqual("both", item.subscription)
        self.assertTrue(item.approved)
        self.assertEqual("subscribe", item.ask)
        self.assertEqual("foobar", item.name)

    def test_update_from_xso_item(self):
        xso_item = roster_xso.Item(
            jid=self.jid,
            subscription="to",
            ask="subscribe",
            approved=False,
            name="test")

        item = roster_service.Item(self.jid)
        item.update_from_xso_item(xso_item)
        self.assertEqual(xso_item.jid, item.jid)
        self.assertEqual(xso_item.subscription, item.subscription)
        self.assertEqual(xso_item.ask, item.ask)
        self.assertEqual(xso_item.approved, item.approved)
        self.assertEqual(xso_item.name, item.name)

        xso_item = roster_xso.Item(
            jid=structs.JID.fromstr("user@bar.example"),
            subscription="from",
            ask=None,
            approved=True,
            name="other test")
        item.update_from_xso_item(xso_item)

        self.assertEqual(self.jid, item.jid)
        self.assertEqual(xso_item.subscription, item.subscription)
        self.assertEqual(xso_item.ask, item.ask)
        self.assertEqual(xso_item.approved, item.approved)
        self.assertEqual(xso_item.name, item.name)

    @unittest.mock.patch.object(roster_service.Item, "update_from_xso_item")
    def test_from_xso_item(self, update_from_xso_item):
        xso_item = roster_xso.Item(
            jid=structs.JID.fromstr("user@bar.example"),
            subscription="from",
            ask=None,
            approved=True)

        item = roster_service.Item.from_xso_item(xso_item)
        self.assertEqual(xso_item.jid, item.jid)
        self.assertSequenceEqual(
            [
                unittest.mock.call(xso_item)
            ],
            update_from_xso_item.mock_calls
        )

    def test_export_as_json(self):
        item = roster_service.Item(
            jid=self.jid,
            subscription="to",
            ask="subscribe",
            approved=False,
            name="test")

        self.assertDictEqual(
            {
                "subscription": "to",
                "ask": "subscribe",
                "name": "test",
            },
            item.export_as_json()
        )

        item = roster_service.Item(
            jid=self.jid,
            approved=True)

        self.assertDictEqual(
            {
                "subscription": "none",
                "approved": True
            },
            item.export_as_json()
        )

    def test_update_from_json(self):
        item = roster_service.Item(jid=self.jid)

        item.update_from_json({
            "subscription": "both"
        })
        self.assertEqual("both", item.subscription)

        item.update_from_json({
            "approved": True
        })
        self.assertTrue(item.approved)
        self.assertEqual("none", item.subscription)

        item.update_from_json({
            "ask": "subscribe"
        })
        self.assertEqual("subscribe", item.ask)
        self.assertFalse(item.approved)

        item.update_from_json({
            "name": "foobar baz"
        })
        self.assertEqual("foobar baz", item.name)
        self.assertIsNone(item.ask)


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = roster_service.Service(self.cc)

        self.user1 = structs.JID.fromstr("user@foo.example")
        self.user2 = structs.JID.fromstr("user@bar.example")

        response = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1),
                roster_xso.Item(
                    jid=self.user2,
                    name="some bar user",
                    subscription="both"
                )
            ],
            ver="foobar"
        )

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.cc.before_stream_established())

        self.cc.stream.send_iq_and_wait_for_reply.reset_mock()

    def test_is_Service(self):
        self.assertIsInstance(
            self.s,
            service.Service
        )

    def test_init(self):
        s = roster_service.Service(self.cc)
        self.assertDictEqual({}, s.items)
        self.assertEqual(None, s.version)

    def test_setup(self):
        self.assertSequenceEqual(
            [
                unittest.mock.call.stream.register_iq_request_coro(
                    "set",
                    roster_xso.Query,
                    self.s.handle_roster_push
                ),
                unittest.mock.call.stream.send_iq_and_wait_for_reply(
                    unittest.mock.ANY,
                    timeout=self.cc.negotiation_timeout.total_seconds()
                )
            ],
            self.cc.mock_calls
        )

    def test_shutdown(self):
        run_coroutine(self.s.shutdown())
        self.assertSequenceEqual(
            [
                unittest.mock.call.stream.register_iq_request_coro(
                    "set",
                    roster_xso.Query,
                    unittest.mock.ANY
                ),
                unittest.mock.call.stream.send_iq_and_wait_for_reply(
                    unittest.mock.ANY,
                    timeout=self.cc.negotiation_timeout.total_seconds()
                ),
                unittest.mock.call.stream.unregister_iq_request_coro(
                    "set",
                    roster_xso.Query
                ),
            ],
            self.cc.mock_calls
        )

    def test_request_initial_roster_before_stream_established(self):
        self.assertIn(self.user1, self.s.items)
        self.assertIn(self.user2, self.s.items)
        self.assertEqual("foobar", self.s.version)

        self.assertEqual("both", self.s.items[self.user2].subscription)
        self.assertEqual("some bar user", self.s.items[self.user2].name)

    def test_handle_roster_push_rejects_push_with_nonempty_from(self):
        iq = stanza.IQ()
        iq.from_ = structs.JID.fromstr("foo@bar.example")

        with self.assertRaises(errors.XMPPAuthError) as ctx:
            run_coroutine(self.s.handle_roster_push(iq))

        self.assertEqual(
            (namespaces.stanzas, "forbidden"),
            ctx.exception.condition
        )

    def test_handle_roster_push_extends_roster(self):
        user1 = structs.JID.fromstr("user2@foo.example")
        user2 = structs.JID.fromstr("user2@bar.example")

        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=user1),
                roster_xso.Item(
                    jid=user2,
                    name="some bar user",
                    subscription="both"
                )
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        self.assertIsNone(
            run_coroutine(self.s.handle_roster_push(iq))
        )

        self.assertIn(user1, self.s.items)
        self.assertIn(user2, self.s.items)
        self.assertEqual("foobar", self.s.version)

        self.assertEqual("both", self.s.items[user2].subscription)
        self.assertEqual("some bar user", self.s.items[user2].name)

    def test_handle_roster_push_removes_from_roster(self):
        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1,
                    subscription="remove"),
            ],
            ver="foobarbaz"
        )

        iq = stanza.IQ()
        iq.payload = request

        self.assertIsNone(
            run_coroutine(self.s.handle_roster_push(iq))
        )

        self.assertNotIn(self.user1, self.s.items)
        self.assertIn(self.user2, self.s.items)
        self.assertEqual("foobarbaz", self.s.version)

    def test_item_objects_do_not_change_during_push(self):
        old_item = self.s.items[self.user1]

        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1,
                    subscription="both"
                ),
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        self.assertIsNone(
            run_coroutine(self.s.handle_roster_push(iq))
        )

        self.assertIs(old_item, self.s.items[self.user1])
        self.assertEqual("both", old_item.subscription)

    def test_initial_roster_discards_information(self):
        response = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user2,
                    name="some bar user",
                    subscription="both"
                )
            ],
            ver="foobar"
        )

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.cc.before_stream_established())
        self.assertSequenceEqual(
            [
                unittest.mock.call.stream.register_iq_request_coro(
                    "set",
                    roster_xso.Query,
                    self.s.handle_roster_push
                ),
                unittest.mock.call.stream.send_iq_and_wait_for_reply(
                    unittest.mock.ANY,
                    timeout=self.cc.negotiation_timeout.total_seconds()
                ),
                unittest.mock.call.stream.send_iq_and_wait_for_reply(
                    unittest.mock.ANY,
                    timeout=self.cc.negotiation_timeout.total_seconds()
                )
            ],
            self.cc.mock_calls
        )

        self.assertNotIn(self.user1, self.s.items)

    def test_initial_roster_keeps_existing_entries_alive(self):
        old_item = self.s.items[self.user2]

        response = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user2,
                    name="new name",
                    subscription="both"
                )
            ],
            ver="foobar"
        )

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.cc.before_stream_established())

        self.assertIs(old_item, self.s.items[self.user2])
        self.assertEqual("new name", old_item.name)

    def test_on_entry_name_changed(self):
        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1,
                    name="foobarbaz",
                ),
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        cb = unittest.mock.Mock()
        with self.s.on_entry_name_changed.context_connect(cb):
            run_coroutine(self.s.handle_roster_push(iq))
            run_coroutine(self.s.handle_roster_push(iq))

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.s.items[self.user1]),
            ],
            cb.mock_calls
        )

    def test_on_entry_subscription_state_changed(self):
        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1,
                    subscription="both",
                    approved=True,
                    ask="subscribe"
                ),
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        cb = unittest.mock.Mock()
        with self.s.on_entry_subscription_state_changed.context_connect(cb):
            run_coroutine(self.s.handle_roster_push(iq))
            run_coroutine(self.s.handle_roster_push(iq))

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.s.items[self.user1]),
            ],
            cb.mock_calls
        )

    def test_on_entry_removed(self):
        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user1,
                    subscription="remove",
                ),
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        old_item = self.s.items[self.user1]

        cb = unittest.mock.Mock()
        with self.s.on_entry_removed.context_connect(cb):
            run_coroutine(self.s.handle_roster_push(iq))
            run_coroutine(self.s.handle_roster_push(iq))

        self.assertSequenceEqual(
            [
                unittest.mock.call(old_item),
            ],
            cb.mock_calls
        )

    def test_on_entry_added(self):
        new_jid = structs.JID.fromstr("fnord@foo.example")

        request = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=new_jid,
                    subscription="none",
                ),
            ],
            ver="foobar"
        )

        iq = stanza.IQ()
        iq.payload = request

        cb = unittest.mock.Mock()
        with self.s.on_entry_added.context_connect(cb):
            run_coroutine(self.s.handle_roster_push(iq))
            run_coroutine(self.s.handle_roster_push(iq))

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.s.items[new_jid]),
            ],
            cb.mock_calls
        )

    def test_on_entry_removed_called_from_initial_roster(self):
        response = roster_xso.Query(
            items=[
                roster_xso.Item(
                    jid=self.user2,
                    name="some bar user",
                    subscription="both"
                )
            ],
            ver="foobar"
        )

        old_item = self.s.items[self.user1]

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        cb = unittest.mock.Mock()
        with self.s.on_entry_removed.context_connect(cb):
            run_coroutine(self.cc.before_stream_established())

        self.assertSequenceEqual(
            [
                unittest.mock.call(old_item),
            ],
            cb.mock_calls
        )

    def test_export_as_json(self):
        self.assertDictEqual(
            {
                "items": {
                    str(self.user1): {
                        "subscription": "none",
                    },
                    str(self.user2): {
                        "subscription": "both",
                        "name": "some bar user",
                    },
                },
                "ver": "foobar",
            },
            self.s.export_as_json()
        )

    def test_import_from_json(self):
        jid1 = structs.JID.fromstr("fnord@foo.example")
        jid2 = structs.JID.fromstr("fnord@bar.example")

        data = {
            "items": {
                str(jid1): {
                    "name": "foo fnord",
                    "subscription": "both",
                },
                str(jid2): {
                    "name": "bar fnord",
                    "subscription": "to",
                }
            },
            "ver": "foobarbaz",
        }

        self.s.import_from_json(data)

        self.assertEqual("foobarbaz", self.s.version)

        self.assertNotIn(self.user1, self.s.items)
        self.assertNotIn(self.user2, self.s.items)

        self.assertIn(jid1, self.s.items)
        self.assertIn(jid2, self.s.items)

        self.assertEqual(self.s.items[jid1].name, "foo fnord")
        self.assertEqual(self.s.items[jid1].subscription, "both")

        self.assertEqual(self.s.items[jid2].name, "bar fnord")
        self.assertEqual(self.s.items[jid2].subscription, "to")
