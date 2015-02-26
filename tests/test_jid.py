import unittest

import asyncio_xmpp.jid as jid

class TestJID(unittest.TestCase):
    def test_init_full(self):
        j = jid.JID("foo", "example.com", "bar")
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
            j = jid.JID("\u0007", "example.com", "bar")
        with self.assertRaises(ValueError):
            j = jid.JID("foo", "\u070f", "bar")
        with self.assertRaises(ValueError):
            j = jid.JID("foo", "example.com", "\u0007")

        self.assertEqual(
            "ssa",
            jid.JID("ßA", "example.test", "").localpart)

        self.assertEqual(
            "ix.test",
            jid.JID("", "IX.test", "").domain)

        self.assertEqual(
            "IX",
            jid.JID("", "example.test", "\u2168").resource)

    def test_replace(self):
        j = jid.JID("foo", "example.com", "bar")
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
        j = jid.JID("foo", "example.com", "bar")
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
        j1 = jid.JID("foo", "bar", "baz")
        j2 = jid.JID("foo", "bar", "baz")
        self.assertEqual(
            hash(j1),
            hash(j2))

    def test_eq(self):
        j1 = jid.JID("foo", "bar", "baz")
        j2 = jid.JID("foo", "bar", "baz")
        self.assertEqual(j1, j2)

    def test_ne(self):
        j1 = jid.JID("foo", "bar", "baz")
        j2 = jid.JID("fooo", "bar", "baz")
        self.assertNotEqual(j1, j2)

    def test_str_full_jid(self):
        j = jid.JID("foo", "example.test", "bar")
        self.assertEqual(
            "foo@example.test/bar",
            str(j))

    def test_str_bare_jid(self):
        j = jid.JID("foo", "example.test", None)
        self.assertEqual(
            "foo@example.test",
            str(j))

    def test_str_domain_jid(self):
        j = jid.JID(None, "example.test", None)
        self.assertEqual(
            "example.test",
            str(j))

    def test_init_bare_jid(self):
        j = jid.JID("foo", "example.test", None)
        self.assertIsNone(j.resource)
        self.assertEqual(
            "foo",
            j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_init_domain_jid(self):
        j = jid.JID(None, "example.test", None)
        self.assertIsNone(j.resource)
        self.assertIsNone(j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_replace_domain_jid(self):
        j = jid.JID("foo", "example.test", "bar")
        self.assertEqual(
            jid.JID(None, "example.test", None),
            j.replace(localpart=None, resource=None)
        )

    def test_replace_require_domainpart(self):
        j = jid.JID("foo", "example.test", "bar")
        with self.assertRaises(ValueError):
            j.replace(domain=None)

    def test_require_domainpart(self):
        with self.assertRaises(ValueError):
            j = jid.JID(None, None, None)

    def test_alias_empty_to_none(self):
        j = jid.JID("", "example.test", "")
        self.assertIsNone(j.resource)
        self.assertIsNone(j.localpart)
        self.assertEqual(
            "example.test",
            j.domain)

    def test_immutable(self):
        j = jid.JID(None, "example.test", None)
        with self.assertRaises(AttributeError):
            j.foo = "bar"

    def test_bare(self):
        j = jid.JID("foo", "example.test", "bar")
        self.assertEqual(
            jid.JID("foo", "example.test", None),
            j.bare)

    def test_is_bare(self):
        self.assertFalse(jid.JID("foo", "example.test", "bar").is_bare)
        self.assertTrue(jid.JID("foo", "example.test", None).is_bare)
        self.assertTrue(jid.JID(None, "example.test", None).is_bare)

    def test_is_domain(self):
        self.assertFalse(jid.JID("foo", "example.test", "bar").is_domain)
        self.assertFalse(jid.JID("foo", "example.test", None).is_domain)
        self.assertTrue(jid.JID(None, "example.test", None).is_domain)

    def test_fromstr_full(self):
        self.assertEqual(
            jid.JID("foo", "example.test", "bar"),
            jid.JID.fromstr("foo@example.test/bar")
        )
        self.assertEqual(
            jid.JID("ßA", "IX.test", "\u2168"),
            jid.JID.fromstr("ssa@ix.test/IX")
        )
        self.assertEqual(
            jid.JID("ßA", "IX.test", "bar@baz/fnord"),
            jid.JID.fromstr("ssa@ix.test/bar@baz/fnord")
        )

    def test_fromstr_bare(self):
        self.assertEqual(
            jid.JID("foo", "example.test", None),
            jid.JID.fromstr("foo@example.test")
        )
        self.assertEqual(
            jid.JID("ßA", "IX.test", None),
            jid.JID.fromstr("ssa@ix.test")
        )

    def test_fromstr_domain(self):
        self.assertEqual(
            jid.JID(None, "example.test", None),
            jid.JID.fromstr("example.test")
        )
        self.assertEqual(
            jid.JID(None, "IX.test", None),
            jid.JID.fromstr("ix.test")
        )
