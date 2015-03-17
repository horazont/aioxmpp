import unittest

import aioxmpp.stanza_model as stanza_model
import aioxmpp.stanza_types as stanza_types
import aioxmpp.stanza as stanza
import aioxmpp.jid as jid
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces


TEST_FROM = jid.JID.fromstr("foo@example.test")
TEST_TO = jid.JID.fromstr("bar@example.test")


class TestStanzaBase(unittest.TestCase):
    def test_id_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.id_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "id"),
            stanza.StanzaBase.id_.tag)
        self.assertTrue(stanza.StanzaBase.id_.required)

    def test_from_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.from_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "from"),
            stanza.StanzaBase.from_.tag)
        self.assertIsInstance(
            stanza.StanzaBase.from_.type_,
            stanza_types.JID)

    def test_to_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.to,
            stanza_model.Attr)
        self.assertEqual(
            (None, "to"),
            stanza.StanzaBase.to.tag)
        self.assertIsInstance(
            stanza.StanzaBase.to.type_,
            stanza_types.JID)

    def test_autoset_id_generates_random_str_on_none(self):
        s = stanza.StanzaBase()
        self.assertIsNone(s.id_)
        s.autoset_id()
        id1 = s.id_
        self.assertTrue(s.id_)
        s.id_ = None
        s.autoset_id()
        self.assertTrue(s.id_)
        self.assertNotEqual(id1, s.id_)
        self.assertIsInstance(s.id_, str)

        # ensure that there are not too many A chars (i.e. zero bits)
        self.assertLess(sum(1 for c in id1 if c == "A"), 5)

    def test_autoset_id_does_not_override(self):
        s = stanza.StanzaBase()
        s.id_ = "foo"
        s.autoset_id()
        self.assertEqual("foo", s.id_)

    def test_make_reply(self):
        s = stanza.StanzaBase()
        s.from_ = TEST_FROM
        s.to = TEST_TO
        s.id_ = "id"

        r = s._make_reply()
        self.assertIsInstance(r, type(s))
        self.assertEqual(
            r.from_,
            s.to)
        self.assertEqual(
            r.to,
            s.from_)
        self.assertEqual(
            r.id_,
            s.id_)

    def test_init(self):
        id_ = "someid"

        s = stanza.StanzaBase(
            from_=TEST_FROM,
            to=TEST_TO,
            id_=id_)
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            TEST_TO,
            s.to)
        self.assertEqual(
            id_,
            s.id_)


class TestMessage(unittest.TestCase):
    def test_inheritance(self):
        self.assertIsInstance(
            stanza.Message(),
            stanza.StanzaBase)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "message"),
            stanza.Message.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Message.type_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Message.type_.tag)
        self.assertIsInstance(
            stanza.Message.type_.validator,
            stanza_types.RestrictToSet)
        self.assertSetEqual(
            {
                "chat",
                "error",
                "groupchat",
                "headline",
                "normal",
            },
            stanza.Message.type_.validator.values)
        self.assertTrue(
            stanza.Message.type_.required)

    def test_ext_attr(self):
        self.assertIsInstance(
            stanza.Message.ext,
            stanza_model.ChildMap)

    def test_init(self):
        s = stanza.Message(from_=TEST_FROM,
                           to=TEST_TO,
                           id_="someid",
                           type_="groupchat")
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            "groupchat",
            s.type_)

    def test_init_default(self):
        s = stanza.Message()
        self.assertEqual("chat", s.type_)

    def test_make_reply(self):
        s = stanza.Message(from_=TEST_FROM,
                           to=TEST_TO,
                           id_="someid",
                           type_="groupchat")
        r = s.make_reply()
        self.assertEqual(
            r.type_,
            s.type_)
        self.assertEqual(
            TEST_FROM,
            r.to)
        self.assertEqual(
            TEST_TO,
            r.from_)
        self.assertIsNone(r.id_)


class TestPresence(unittest.TestCase):
    def test_inheritance(self):
        self.assertIsInstance(
            stanza.Presence(),
            stanza.StanzaBase)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "presence"),
            stanza.Presence.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Presence.type_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Presence.type_.tag)
        self.assertIsInstance(
            stanza.Presence.type_.validator,
            stanza_types.RestrictToSet)
        self.assertSetEqual(
            {
                "error",
                "probe",
                "subscribe",
                "subscribed",
                "unavailable",
                "unsubscribe",
                "unsubscribed",
            },
            stanza.Presence.type_.validator.values)
        self.assertFalse(
            stanza.Presence.type_.required)

    def test_ext_attr(self):
        self.assertIsInstance(
            stanza.Presence.ext,
            stanza_model.ChildMap)

    def test_init(self):
        s = stanza.Presence(
            from_=TEST_FROM,
            type_="probe")
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            "probe",
            s.type_)

    def test_default(self):
        s = stanza.Presence()
        self.assertIsNone(s.type_)


class TestError(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "error"),
            stanza.Error.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Error.type_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Error.type_.tag)
        self.assertIsInstance(
            stanza.Error.type_.validator,
            stanza_types.RestrictToSet)
        self.assertSetEqual(
            {
                "auth",
                "cancel",
                "continue",
                "modify",
                "wait",
            },
            stanza.Error.type_.validator.values)
        self.assertTrue(
            stanza.Error.type_.required)

    def test_from_exception(self):
        exc = errors.XMPPWaitError(
            condition=(namespaces.stanzas, "item-not-found"),
            text="foobar"
        )
        obj = stanza.Error.from_exception(exc)
        self.assertEqual(
            "wait",
            obj.type_
        )
        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            obj.condition
        )
        self.assertEqual(
            "foobar",
            obj.text
        )


class TestIQ(unittest.TestCase):
    def test_inheritance(self):
        self.assertIsInstance(
            stanza.IQ(),
            stanza.StanzaBase)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "iq"),
            stanza.IQ.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.IQ.type_,
            stanza_model.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.IQ.type_.tag)
        self.assertIsInstance(
            stanza.IQ.type_.validator,
            stanza_types.RestrictToSet)
        self.assertSetEqual(
            {
                "get",
                "set",
                "error",
                "result",
            },
            stanza.IQ.type_.validator.values)
        self.assertTrue(
            stanza.IQ.type_.required)

    def test_error(self):
        self.assertIsInstance(
            stanza.IQ.error,
            stanza_model.Child)

    def test_payload(self):
        self.assertIsInstance(
            stanza.IQ.payload,
            stanza_model.Child)

    def test_init(self):
        s = stanza.IQ(from_=TEST_FROM, type_="result")
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            "result",
            s.type_)

    def test_make_reply(self):
        s = stanza.IQ(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="get")

        r1 = s.make_reply("error")
        self.assertEqual(
            s.from_,
            r1.to)
        self.assertEqual(
            s.to,
            r1.from_)
        self.assertEqual(
            s.id_,
            r1.id_)
        self.assertEqual(
            "error",
            r1.type_)

    def test_make_reply_enforces_request(self):
        s = stanza.IQ(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="error")
        with self.assertRaises(ValueError):
            s.make_reply("error")
        s.type_ = "result"
        with self.assertRaises(ValueError):
            s.make_reply("error")
