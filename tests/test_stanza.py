import itertools
import unittest

import aioxmpp.xso as xso
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.errors as errors

from aioxmpp.utils import namespaces


TEST_FROM = structs.JID.fromstr("foo@example.test")
TEST_TO = structs.JID.fromstr("bar@example.test")


class TestPayload(xso.XSO):
    def __repr__(self):
        return "foobar"


class TestStanzaBase(unittest.TestCase):
    def test_declare_ns(self):
        self.assertDictEqual(
            stanza.StanzaBase.DECLARE_NS,
            {}
        )

    def test_from_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.from_,
            xso.Attr)
        self.assertEqual(
            (None, "from"),
            stanza.StanzaBase.from_.tag)
        self.assertIsInstance(
            stanza.StanzaBase.from_.type_,
            xso.JID)

    def test_to_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.to,
            xso.Attr)
        self.assertEqual(
            (None, "to"),
            stanza.StanzaBase.to.tag)
        self.assertIsInstance(
            stanza.StanzaBase.to.type_,
            xso.JID)

    def test_lang_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.lang,
            xso.LangAttr)

    def test_error_attr(self):
        self.assertIsInstance(
            stanza.StanzaBase.error,
            xso.Child)
        self.assertIs(stanza.StanzaBase.error.default, None)

    def test_autoset_id_generates_random_str_on_none(self):
        s = stanza.StanzaBase()
        s.autoset_id()
        id1 = s.id_
        self.assertTrue(s.id_)
        del s.id_
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


class TestBody(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.client, "body"),
            stanza.Body.TAG)

    def test_lang_attr(self):
        self.assertIsInstance(
            stanza.Body.lang,
            xso.LangAttr)

    def test_text_attr(self):
        self.assertIsInstance(
            stanza.Body.text,
            xso.Text)


class TestSubject(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.client, "subject"),
            stanza.Subject.TAG)

    def test_lang_attr(self):
        self.assertIsInstance(
            stanza.Subject.lang,
            xso.LangAttr)

    def test_text_attr(self):
        self.assertIsInstance(
            stanza.Subject.text,
            xso.Text)


class TestMessage(unittest.TestCase):
    def test_inheritance(self):
        self.assertTrue(issubclass(
            stanza.Message,
            stanza.StanzaBase))

    def test_unknown_child_policy(self):
        self.assertEqual(
            stanza.Message.UNKNOWN_CHILD_POLICY,
            xso.UnknownChildPolicy.DROP
        )

    def test_id_attr(self):
        self.assertIsInstance(
            stanza.Message.id_,
            xso.Attr)
        self.assertEqual(
            (None, "id"),
            stanza.Message.id_.tag)
        self.assertIs(stanza.Message.id_.default, None)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "message"),
            stanza.Message.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Message.type_,
            xso.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Message.type_.tag)
        self.assertIsInstance(
            stanza.Message.type_.validator,
            xso.RestrictToSet)
        self.assertSetEqual(
            {
                "chat",
                "error",
                "groupchat",
                "headline",
                "normal",
            },
            stanza.Message.type_.validator.values)
        self.assertEqual(
            stanza.Message.type_.default,
            "normal"
        )

    def test_ext_attr(self):
        self.assertIsInstance(
            stanza.Message.ext,
            xso.ChildMap)

    def test_body_attr(self):
        self.assertIsInstance(
            stanza.Message.body,
            xso.ChildList)
        self.assertSetEqual(
            {stanza.Body},
            set(stanza.Message.body._classes)
        )

    def test_subject_attr(self):
        self.assertIsInstance(
            stanza.Message.subject,
            xso.ChildList)
        self.assertSetEqual(
            {stanza.Subject},
            set(stanza.Message.subject._classes)
        )

    def test_thread_attr(self):
        self.assertIsInstance(
            stanza.Message.thread,
            xso.Child)
        self.assertSetEqual(
            {stanza.Thread},
            set(stanza.Message.thread._classes)
        )

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

    def test_reject_init_without_type(self):
        with self.assertRaisesRegexp(TypeError, "type_"):
            stanza.Message()

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

    def test_make_error(self):
        e = stanza.Error(
            condition=(namespaces.stanzas, "feature-not-implemented")
        )
        s = stanza.Message(from_=TEST_FROM,
                           to=TEST_TO,
                           id_="someid",
                           type_="groupchat")
        r = s.make_error(e)

        self.assertIsInstance(r, stanza.Message)

        self.assertEqual(
            r.type_,
            "error")
        self.assertEqual(
            TEST_FROM,
            r.to)
        self.assertEqual(
            TEST_TO,
            r.from_)
        self.assertEqual(
            s.id_,
            r.id_)

    def test_repr(self):
        s = stanza.Message(from_=TEST_FROM,
                           to=TEST_TO,
                           id_="someid",
                           type_="groupchat")
        self.assertEqual(
            "<message from='foo@example.test' to='bar@example.test'"
            " id='someid' type='groupchat'>",
            repr(s)
        )


class TestStatus(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(
            (namespaces.client, "status"),
            stanza.Status.TAG)

    def test_lang_attr(self):
        self.assertIsInstance(
            stanza.Status.lang,
            xso.LangAttr)

    def test_text_attr(self):
        self.assertIsInstance(
            stanza.Status.text,
            xso.Text)


class TestPresence(unittest.TestCase):
    def test_inheritance(self):
        self.assertIsInstance(
            stanza.Presence(),
            stanza.StanzaBase)

    def test_id_attr(self):
        self.assertIsInstance(
            stanza.Presence.id_,
            xso.Attr)
        self.assertEqual(
            (None, "id"),
            stanza.Presence.id_.tag)
        self.assertIs(stanza.Presence.id_.default, None)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "presence"),
            stanza.Presence.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Presence.type_,
            xso.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Presence.type_.tag)
        self.assertIsInstance(
            stanza.Presence.type_.validator,
            xso.RestrictToSet)
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
        self.assertIs(stanza.Presence.type_.default, None)

    def test_show_attr(self):
        self.assertIsInstance(
            stanza.Presence.show,
            xso.ChildText)
        self.assertEqual(
            (namespaces.client, "show"),
            stanza.Presence.show.tag
        )
        self.assertEqual(
            xso.ValidateMode.ALWAYS,
            stanza.Presence.show.validate
        )
        self.assertIsInstance(
            stanza.Presence.show.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            {
                "dnd",
                "away",
                "xa",
                None,
                "chat",
            },
            stanza.Presence.show.validator.values
        )

    def test_status_attr(self):
        self.assertIsInstance(
            stanza.Presence.status,
            xso.ChildList)
        self.assertSetEqual(
            {stanza.Status},
            set(stanza.Presence.status._classes)
        )

    def test_priority_attr(self):
        self.assertIsInstance(
            stanza.Presence.priority,
            xso.ChildText)
        self.assertEqual(
            (namespaces.client, "priority"),
            stanza.Presence.priority.tag
        )
        self.assertIsInstance(
            stanza.Presence.priority.type_,
            xso.Integer
        )
        self.assertEqual(
            0,
            stanza.Presence.priority.default
        )

    def test_ext_attr(self):
        self.assertIsInstance(
            stanza.Presence.ext,
            xso.ChildMap)

    def test_error_attr(self):
        self.assertIsInstance(
            stanza.Presence.error,
            xso.Child)

    def test_init(self):
        s = stanza.Presence(
            from_=TEST_FROM,
            type_="probe",
            show="away")
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            "probe",
            s.type_)
        self.assertEqual(
            "away",
            s.show)

    def test_default(self):
        s = stanza.Presence()
        self.assertIsNone(s.type_)
        self.assertIsNone(s.show)

    def test_make_error(self):
        e = stanza.Error(
            condition=(namespaces.stanzas, "gone")
        )
        s = stanza.Presence(from_=TEST_FROM,
                            to=TEST_TO,
                            id_="someid",
                            type_="unavailable")
        r = s.make_error(e)

        self.assertIsInstance(r, stanza.Presence)

        self.assertEqual(
            r.type_,
            "error")
        self.assertEqual(
            TEST_FROM,
            r.to)
        self.assertEqual(
            TEST_TO,
            r.from_)
        self.assertEqual(
            s.id_,
            r.id_)

    def test_repr(self):
        s = stanza.Presence(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="probe")
        self.assertEqual(
            "<presence from='foo@example.test' to='bar@example.test'"
            " id='someid' type='probe'>",
            repr(s)
        )
        s = stanza.Presence(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_=None)
        self.assertEqual(
            "<presence from='foo@example.test' to='bar@example.test'"
            " id='someid' type=None>",
            repr(s)
        )

    def test_collector(self):
        self.assertIsInstance(
            stanza.Presence.unhandled_children,
            xso.Collector
        )


class TestError(unittest.TestCase):
    def test_declare_ns(self):
        self.assertDictEqual(
            stanza.Error.DECLARE_NS,
            {}
        )

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "error"),
            stanza.Error.TAG)

    def test_unknown_child_policy(self):
        self.assertIs(
            stanza.Error.UNKNOWN_CHILD_POLICY,
            xso.UnknownChildPolicy.DROP
        )

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.Error.type_,
            xso.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.Error.type_.tag)
        self.assertIsInstance(
            stanza.Error.type_.validator,
            xso.RestrictToSet)
        self.assertSetEqual(
            {
                "auth",
                "cancel",
                "continue",
                "modify",
                "wait",
            },
            stanza.Error.type_.validator.values)

    def test_application_condition_attr(self):
        self.assertIsInstance(
            stanza.Error.application_condition,
            xso.Child)
        self.assertFalse(stanza.Error.application_condition.required)

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

    def test_to_exception(self):
        types = {
            "modify": errors.XMPPModifyError,
            "cancel": errors.XMPPCancelError,
            "auth": errors.XMPPAuthError,
            "wait": errors.XMPPWaitError,
            "continue": errors.XMPPContinueError,
        }
        conditions = [
            (namespaces.stanzas, "bad-request"),
            (namespaces.stanzas, "undefined-condition"),
        ]
        texts = [
            "foo",
            "bar",
            None,
        ]

        for (type_name, cls), condition, text in itertools.product(
                types.items(),
                conditions,
                texts):
            obj = stanza.Error(
                type_=type_name,
                condition=condition,
                text=text)
            exc = obj.to_exception()
            self.assertIsInstance(
                exc,
                cls
            )
            self.assertEqual(
                condition,
                exc.condition
            )
            self.assertEqual(
                text,
                exc.text
            )

    def test_repr(self):
        obj = stanza.Error()
        self.assertEqual(
            "<undefined-condition type='cancel'>",
            repr(obj)
        )
        obj = stanza.Error(
            type_="modify",
            condition=(namespaces.stanzas,
                       "bad-request"),
            text="foobar"
        )
        self.assertEqual(
            "<bad-request type='modify' text='foobar'>",
            repr(obj)
        )


class TestIQ(unittest.TestCase):
    def test_inheritance(self):
        self.assertTrue(issubclass(
            stanza.IQ,
            stanza.StanzaBase))

    def test_id_attr(self):
        self.assertIsInstance(
            stanza.IQ.id_,
            xso.Attr)
        self.assertEqual(
            (None, "id"),
            stanza.IQ.id_.tag)

    def test_tag(self):
        self.assertEqual(
            ("jabber:client", "iq"),
            stanza.IQ.TAG)

    def test_type_attr(self):
        self.assertIsInstance(
            stanza.IQ.type_,
            xso.Attr)
        self.assertEqual(
            (None, "type"),
            stanza.IQ.type_.tag)
        self.assertIsInstance(
            stanza.IQ.type_.validator,
            xso.RestrictToSet)
        self.assertSetEqual(
            {
                "get",
                "set",
                "error",
                "result",
            },
            stanza.IQ.type_.validator.values)

    def test_error(self):
        self.assertIsInstance(
            stanza.IQ.error,
            xso.Child)

    def test_payload(self):
        self.assertIsInstance(
            stanza.IQ.payload,
            xso.Child)
        self.assertIsNone(stanza.IQ.payload.default)

    def test_reject_init_without_type(self):
        with self.assertRaisesRegexp(TypeError, "type_"):
            stanza.IQ()

    def test_init(self):
        payload = object()

        s = stanza.IQ(
            from_=TEST_FROM,
            type_="result",
            payload=payload)
        self.assertEqual(
            TEST_FROM,
            s.from_)
        self.assertEqual(
            "result",
            s.type_)
        self.assertIs(
            payload,
            s.payload)

    def test_init_error(self):
        error = object()

        s = stanza.IQ(
            from_=TEST_FROM,
            type_="error",
            error=error)
        self.assertEqual(
            "error",
            s.type_)
        self.assertIs(
            error,
            s.error)

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

    def test_make_error(self):
        e = stanza.Error(
            condition=(namespaces.stanzas, "bad-request")
        )
        s = stanza.IQ(from_=TEST_FROM,
                      to=TEST_TO,
                      id_="someid",
                      type_="get")
        r = s.make_error(e)

        self.assertIsInstance(r, stanza.IQ)

        self.assertEqual(
            r.type_,
            "error")
        self.assertEqual(
            TEST_FROM,
            r.to)
        self.assertEqual(
            TEST_TO,
            r.from_)
        self.assertEqual(
            s.id_,
            r.id_)

    def test_repr(self):
        s = stanza.IQ(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="error")
        s.error = stanza.Error()
        self.assertEqual(
            "<iq from='foo@example.test' to='bar@example.test'"
            " id='someid' type='error'"
            " error=<undefined-condition type='cancel'>>",
            repr(s)
        )

        s = stanza.IQ(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="result")
        s.payload = TestPayload()
        self.assertEqual(
            "<iq from='foo@example.test' to='bar@example.test'"
            " id='someid' type='result'"
            " data=foobar>",
            repr(s)
        )

        s = stanza.IQ(
            from_=TEST_FROM,
            to=TEST_TO,
            id_="someid",
            type_="result")
        self.assertEqual(
            "<iq from='foo@example.test' to='bar@example.test'"
            " id='someid' type='result'>",
            repr(s)
        )

    def test_validate_requires_id(self):
        iq = stanza.IQ("get")
        with self.assertRaisesRegexp(
                ValueError,
                "IQ requires ID"):
            iq.validate()

    def test_as_payload_class(self):
        @stanza.IQ.as_payload_class
        class Foo(xso.XSO):
            TAG = ("uri:foo", "test_as_payload_class")

        self.assertIn(Foo.TAG, stanza.IQ.CHILD_MAP)
        self.assertIs(stanza.IQ.CHILD_MAP[Foo.TAG], stanza.IQ.payload)
