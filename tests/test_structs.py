import unittest

import aioxmpp.structs as structs


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
