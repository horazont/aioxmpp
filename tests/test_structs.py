import unittest

import aioxmpp.structs as structs
import aioxmpp.stanza as stanza


class TestJID(unittest.TestCase):
    def test_init_full(self):
        j = structs.JID("foo", "example.com", "bar")
        self.assertEqual(
            "foo",
            j.localpart)
        self.assertEqual(
            "example.com",
            j.domain)
        self.assertEqual(
            "bar",
            j.resource)

    def test_init_enforces_stringprep(self):
        with self.assertRaises(ValueError):
            j = structs.JID("\u0007", "example.com", "bar")
        with self.assertRaises(ValueError):
            j = structs.JID("foo", "\u070f", "bar")
        with self.assertRaises(ValueError):
            j = structs.JID("foo", "example.com", "\u0007")

        self.assertEqual(
            "ssa",
            structs.JID("ßA", "example.test", "").localpart)

        self.assertEqual(
            "ix.test",
            structs.JID("", "IX.test", "").domain)

        self.assertEqual(
            "IX",
            structs.JID("", "example.test", "\u2168").resource)

    def test_replace(self):
        j = structs.JID("foo", "example.com", "bar")
        j2 = j.replace(localpart="fnord",
                       domain="example.invalid",
                       resource="baz")
        self.assertEqual(
            "fnord",
            j2.localpart)
        self.assertEqual(
            "example.invalid",
            j2.domain)
        self.assertEqual(
            "baz",
            j2.resource)

    def test_replace_enforces_stringprep(self):
        j = structs.JID("foo", "example.com", "bar")
        with self.assertRaises(ValueError):
            j2 = j.replace(localpart="\u0007")
        with self.assertRaises(ValueError):
            j2 = j.replace(domain="\u070f")
        with self.assertRaises(ValueError):
            j2 = j.replace(resource="\u0007")

        self.assertEqual(
            "ssa",
            j.replace(localpart="ßA").localpart)
        self.assertEqual(
            "ix.test",
            j.replace(domain="IX.test").domain)
        self.assertEqual(
            "IX",
            j.replace(resource="\u2168").resource)

    def test_hashable(self):
        j1 = structs.JID("foo", "bar", "baz")
        j2 = structs.JID("foo", "bar", "baz")
        self.assertEqual(
            hash(j1),
            hash(j2))

    def test_eq(self):
        j1 = structs.JID("foo", "bar", "baz")
        j2 = structs.JID("foo", "bar", "baz")
        self.assertEqual(j1, j2)

    def test_ne(self):
        j1 = structs.JID("foo", "bar", "baz")
        j2 = structs.JID("fooo", "bar", "baz")
        self.assertNotEqual(j1, j2)

    def test_str_full_jid(self):
        j = structs.JID("foo", "example.test", "bar")
        self.assertEqual(
            "foo@example.test/bar",
            str(j))

    def test_str_bare_jid(self):
        j = structs.JID("foo", "example.test", None)
        self.assertEqual(
            "foo@example.test",
            str(j))

    def test_str_domain_jid(self):
        j = structs.JID(None, "example.test", None)
        self.assertEqual(
            "example.test",
            str(j))

    def test_init_bare_jid(self):
        j = structs.JID("foo", "example.test", None)
        self.assertIsNone(j.resource)
        self.assertEqual(
            "foo",
            j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_init_domain_jid(self):
        j = structs.JID(None, "example.test", None)
        self.assertIsNone(j.resource)
        self.assertIsNone(j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_replace_domain_jid(self):
        j = structs.JID("foo", "example.test", "bar")
        self.assertEqual(
            structs.JID(None, "example.test", None),
            j.replace(localpart=None, resource=None)
        )

    def test_replace_require_domainpart(self):
        j = structs.JID("foo", "example.test", "bar")
        with self.assertRaises(ValueError):
            j.replace(domain=None)

    def test_require_domainpart(self):
        with self.assertRaises(ValueError):
            j = structs.JID(None, None, None)

    def test_alias_empty_to_none(self):
        j = structs.JID("", "example.test", "")
        self.assertIsNone(j.resource)
        self.assertIsNone(j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_immutable(self):
        j = structs.JID(None, "example.test", None)
        with self.assertRaises(AttributeError):
            j.foo = "bar"

    def test_bare(self):
        j = structs.JID("foo", "example.test", "bar")
        self.assertEqual(
            structs.JID("foo", "example.test", None),
            j.bare)

    def test_is_bare(self):
        self.assertFalse(structs.JID("foo", "example.test", "bar").is_bare)
        self.assertTrue(structs.JID("foo", "example.test", None).is_bare)
        self.assertTrue(structs.JID(None, "example.test", None).is_bare)

    def test_is_domain(self):
        self.assertFalse(structs.JID("foo", "example.test", "bar").is_domain)
        self.assertFalse(structs.JID("foo", "example.test", None).is_domain)
        self.assertTrue(structs.JID(None, "example.test", None).is_domain)

    def test_fromstr_full(self):
        self.assertEqual(
            structs.JID("foo", "example.test", "bar"),
            structs.JID.fromstr("foo@example.test/bar")
        )
        self.assertEqual(
            structs.JID("ßA", "IX.test", "\u2168"),
            structs.JID.fromstr("ssa@ix.test/IX")
        )
        self.assertEqual(
            structs.JID("ßA", "IX.test", "bar@baz/fnord"),
            structs.JID.fromstr("ssa@ix.test/bar@baz/fnord")
        )

    def test_fromstr_bare(self):
        self.assertEqual(
            structs.JID("foo", "example.test", None),
            structs.JID.fromstr("foo@example.test")
        )
        self.assertEqual(
            structs.JID("ßA", "IX.test", None),
            structs.JID.fromstr("ssa@ix.test")
        )

    def test_fromstr_domain(self):
        self.assertEqual(
            structs.JID(None, "example.test", None),
            structs.JID.fromstr("example.test")
        )
        self.assertEqual(
            structs.JID(None, "IX.test", None),
            structs.JID.fromstr("ix.test")
        )


class TestPresenceState(unittest.TestCase):
    def test_immutable(self):
        ps = structs.PresenceState()
        with self.assertRaises(AttributeError):
            ps.foo = "bar"
        with self.assertRaises(AttributeError):
            ps.available = True
        with self.assertRaises(AttributeError):
            ps.show = "baz"

    def test_init_defaults(self):
        ps = structs.PresenceState()
        self.assertFalse(ps.available)
        self.assertIsNone(ps.show)

    def test_init_available(self):
        ps = structs.PresenceState(available=True)
        self.assertTrue(ps.available)

    def test_init_available_with_show(self):
        ps = structs.PresenceState(available=True, show="dnd")
        self.assertTrue(ps.available)
        self.assertEqual("dnd", ps.show)

    def test_init_available_validate_show(self):
        with self.assertRaises(ValueError):
            ps = structs.PresenceState(available=True, show="foobar")
        for value in ["dnd", "xa", "away", None, "chat"]:
            ps = structs.PresenceState(available=True, show=value)
            self.assertEqual(value, ps.show)

    def test_init_unavailable_forbids_show(self):
        with self.assertRaises(ValueError):
            structs.PresenceState(available=False, show="dnd")

    def test_ordering(self):
        values = [
            structs.PresenceState(),
            structs.PresenceState(available=True, show="dnd"),
            structs.PresenceState(available=True, show="xa"),
            structs.PresenceState(available=True, show="away"),
            structs.PresenceState(available=True),
            structs.PresenceState(available=True, show="chat"),
        ]

        for i in range(1, len(values)-1):
            for v1, v2 in zip(values[:-i], values[i:]):
                self.assertLess(v1, v2)
                self.assertLessEqual(v1, v2)
                self.assertNotEqual(v1, v2)
                self.assertGreater(v2, v1)
                self.assertGreaterEqual(v2, v1)

    def test_equality(self):
        self.assertEqual(
            structs.PresenceState(),
            structs.PresenceState()
        )
        self.assertEqual(
            structs.PresenceState(available=True),
            structs.PresenceState(available=True)
        )
        self.assertEqual(
            structs.PresenceState(available=True, show="dnd"),
            structs.PresenceState(available=True, show="dnd")
        )
        self.assertFalse(
            structs.PresenceState(available=True, show="dnd") !=
            structs.PresenceState(available=True, show="dnd")
        )

    def test_repr(self):
        self.assertEqual(
            "<PresenceState>",
            repr(structs.PresenceState())
        )
        self.assertEqual(
            "<PresenceState available>",
            repr(structs.PresenceState(available=True))
        )
        self.assertEqual(
            "<PresenceState available show='dnd'>",
            repr(structs.PresenceState(available=True, show="dnd"))
        )

    def test_apply_to_stanza(self):
        stanza_obj = stanza.Presence(type_="probe")
        self.assertEqual(
            "probe",
            stanza_obj.type_
        )
        self.assertIsNone(stanza_obj.show)

        ps = structs.PresenceState(available=True, show="dnd")
        ps.apply_to_stanza(stanza_obj)
        self.assertEqual(
            None,
            stanza_obj.type_
        )
        self.assertEqual(
            "dnd",
            stanza_obj.show
        )

    def test_from_stanza(self):
        stanza_obj = stanza.Presence(type_=None)
        stanza_obj.show = "xa"
        self.assertEqual(
            structs.PresenceState(available=True, show="xa"),
            structs.PresenceState.from_stanza(stanza_obj)
        )

        stanza_obj = stanza.Presence(type_="unavailable")
        self.assertEqual(
            structs.PresenceState(available=False),
            structs.PresenceState.from_stanza(stanza_obj)
        )

    def test_from_stanza_reject_incorrect_types(self):
        stanza_obj = stanza.Presence(type_="probe")
        with self.assertRaises(ValueError):
            structs.PresenceState.from_stanza(stanza_obj)

    def test_from_stanza_nonstrict_by_default(self):
        stanza_obj = stanza.Presence(type_="unavailable")
        stanza_obj.show = "dnd"
        self.assertEqual(
            structs.PresenceState(available=False),
            structs.PresenceState.from_stanza(stanza_obj)
        )

    def test_from_stanza_strict_by_default(self):
        stanza_obj = stanza.Presence(type_="unavailable")
        stanza_obj.show = "dnd"
        with self.assertRaises(ValueError):
            structs.PresenceState.from_stanza(stanza_obj, strict=True)
