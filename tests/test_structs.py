import collections.abc
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
            structs.JID("\u0007", "example.com", "bar")
        with self.assertRaises(ValueError):
            structs.JID("foo", "\u070f", "bar")
        with self.assertRaises(ValueError):
            structs.JID("foo", "example.com", "\u0007")

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
            j.replace(localpart="\u0007")
        with self.assertRaises(ValueError):
            j.replace(domain="\u070f")
        with self.assertRaises(ValueError):
            j.replace(resource="\u0007")

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
            structs.JID(None, None, None)

    def test_replace_rejects_surplus_argument(self):
        j = structs.JID("foo", "example.test", "bar")
        with self.assertRaises(TypeError):
            j.replace(foobar="baz")

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
            j.bare())

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

    def test_init_normalizes_available(self):
        ps = structs.PresenceState(available="foo")
        self.assertIs(True, ps.available)

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

    def test_equality_deals_with_different_types(self):
        self.assertNotEqual(structs.PresenceState(), None)
        self.assertNotEqual(structs.PresenceState(), "foo")
        self.assertNotEqual(structs.PresenceState(), 123)

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

        ps = structs.PresenceState()
        ps.apply_to_stanza(stanza_obj)
        self.assertEqual(
            "unavailable",
            stanza_obj.type_
        )
        self.assertIsNone(
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


class TestLanguageTag(unittest.TestCase):
    def test_init_requires_kwargs(self):
        with self.assertRaisesRegexp(TypeError,
                                     "takes 1 positional argument"):
            structs.LanguageTag("foo")

    def test_init_requires_language(self):
        with self.assertRaisesRegexp(ValueError, "tag cannot be empty"):
            structs.LanguageTag()

    def test_fromstr_match_str(self):
        tag = structs.LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual(
            "de-latn-de-1999",
            tag.match_str
        )

    def test_fromstr_print_str(self):
        tag = structs.LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual(
            "de-Latn-DE-1999",
            tag.print_str
        )

    def test___str__(self):
        tag = structs.LanguageTag.fromstr("zh-Hans")
        self.assertEqual(
            "zh-Hans",
            str(tag)
        )
        tag = structs.LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual(
            "de-Latn-DE-1999",
            str(tag)
        )

    def test_compare_case_insensitively(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        tag2 = structs.LanguageTag.fromstr("de-de")
        tag3 = structs.LanguageTag.fromstr("fr")

        self.assertTrue(tag1 == tag2)
        self.assertFalse(tag1 != tag2)
        self.assertTrue(tag2 == tag1)
        self.assertFalse(tag2 != tag1)

        self.assertTrue(tag1 != tag3)
        self.assertFalse(tag1 == tag3)
        self.assertTrue(tag2 != tag3)
        self.assertFalse(tag2 == tag3)

        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)
        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)

    def test_order_case_insensitively(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        tag2 = structs.LanguageTag.fromstr("de-de")
        tag3 = structs.LanguageTag.fromstr("en-us")
        tag4 = structs.LanguageTag.fromstr("fr")

        self.assertLess(tag1, tag3)
        self.assertLess(tag1, tag4)
        self.assertLess(tag2, tag3)
        self.assertLess(tag2, tag4)
        self.assertLess(tag3, tag4)

        self.assertGreater(tag4, tag3)
        self.assertGreater(tag4, tag2)
        self.assertGreater(tag4, tag1)
        self.assertGreater(tag3, tag2)
        self.assertGreater(tag3, tag1)

        self.assertFalse(tag1 > tag2)
        self.assertFalse(tag2 > tag1)

        self.assertFalse(tag1 < tag2)
        self.assertFalse(tag2 < tag1)

    def test_hash_case_insensitively(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        tag2 = structs.LanguageTag.fromstr("de-de")

        self.assertEqual(hash(tag1), hash(tag2))

    def test_not_equal_to_None(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        self.assertNotEqual(tag1, None)

    def test__repr__(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        tag2 = structs.LanguageTag.fromstr("fr")

        self.assertEqual(
            "<aioxmpp.structs.LanguageTag.fromstr('de-DE')>",
            repr(tag1)
        )

        self.assertEqual(
            "<aioxmpp.structs.LanguageTag.fromstr('fr')>",
            repr(tag2)
        )

    def test_immutable(self):
        tag = structs.LanguageTag.fromstr("foo")
        with self.assertRaises(AttributeError):
            tag.foo = "bar"


class TestLanguageRange(unittest.TestCase):
    def test_init_requires_kwargs(self):
        with self.assertRaisesRegexp(TypeError,
                                     "takes 1 positional argument"):
            structs.LanguageRange("foo")

    def test_init_requires_language(self):
        with self.assertRaisesRegexp(ValueError, "range cannot be empty"):
            structs.LanguageRange()

    def test_fromstr_match_str(self):
        tag = structs.LanguageRange.fromstr("de-DE")
        self.assertEqual(
            "de-de",
            tag.match_str
        )

    def test_fromstr_print_str(self):
        tag = structs.LanguageRange.fromstr("de-Latn-DE-1999")
        self.assertEqual(
            "de-Latn-DE-1999",
            tag.print_str
        )

    def test___str__(self):
        tag = structs.LanguageRange.fromstr("zh-Hans")
        self.assertEqual(
            "zh-Hans",
            str(tag)
        )
        tag = structs.LanguageRange.fromstr("de-Latn-DE-1999")
        self.assertEqual(
            "de-Latn-DE-1999",
            str(tag)
        )

    def test_compare_case_insensitively(self):
        tag1 = structs.LanguageRange.fromstr("de-DE")
        tag2 = structs.LanguageRange.fromstr("de-de")
        tag3 = structs.LanguageRange.fromstr("fr")

        self.assertTrue(tag1 == tag2)
        self.assertFalse(tag1 != tag2)
        self.assertTrue(tag2 == tag1)
        self.assertFalse(tag2 != tag1)

        self.assertTrue(tag1 != tag3)
        self.assertFalse(tag1 == tag3)
        self.assertTrue(tag2 != tag3)
        self.assertFalse(tag2 == tag3)

        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)
        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)

    def test_hash_case_insensitively(self):
        tag1 = structs.LanguageRange.fromstr("de-DE")
        tag2 = structs.LanguageRange.fromstr("de-de")

        self.assertEqual(hash(tag1), hash(tag2))

    def test_not_equal_to_None(self):
        r1 = structs.LanguageRange.fromstr("de-DE")
        self.assertNotEqual(r1, None)

    def test_wildcard(self):
        r1 = structs.LanguageRange.fromstr("*")
        r2 = structs.LanguageRange.fromstr("*")
        self.assertIs(r1, r2)

    def test_strip_rightmost(self):
        r = structs.LanguageRange.fromstr("de-Latn-DE-x-foo")
        self.assertEqual(
            structs.LanguageRange.fromstr("de-Latn-DE"),
            r.strip_rightmost()
        )
        self.assertEqual(
            structs.LanguageRange.fromstr("de-Latn"),
            r.strip_rightmost().strip_rightmost()
        )
        self.assertEqual(
            structs.LanguageRange.fromstr("de"),
            r.strip_rightmost().strip_rightmost().strip_rightmost()
        )
        with self.assertRaises(ValueError):
            r.strip_rightmost().strip_rightmost()\
                .strip_rightmost().strip_rightmost()

    def test_immutable(self):
        r = structs.LanguageRange.fromstr("foo")
        with self.assertRaises(AttributeError):
            r.foo = "bar"


class Testbasic_filter_languages(unittest.TestCase):
    def setUp(self):
        self.languages = [
            structs.LanguageTag.fromstr("de-Latn-DE-1999"),
            structs.LanguageTag.fromstr("de-DE"),
            structs.LanguageTag.fromstr("de-Latn"),
            structs.LanguageTag.fromstr("fr-CH"),
            structs.LanguageTag.fromstr("it"),
        ]


    def test_filter(self):
        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[1],
                self.languages[2],
            ],
            list(structs.basic_filter_languages(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "de",
                ]))
            ))
        )

        self.assertSequenceEqual(
            [
                self.languages[1],
            ],
            list(structs.basic_filter_languages(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "de-DE",
                ]))
            ))
        )

        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[2],
            ],
            list(structs.basic_filter_languages(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "de-Latn",
                ]))
            ))
        )

    def test_filter_no_dupes_and_ordered(self):
        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[2],
                self.languages[1],
            ],
            list(structs.basic_filter_languages(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "de-Latn",
                    "de",
                ]))
            ))
        )

    def test_filter_wildcard(self):
        self.assertSequenceEqual(
            self.languages,
            list(structs.basic_filter_languages(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "fr",
                    "*",
                ]))
            ))
        )


class Testlookup_language(unittest.TestCase):
    def setUp(self):
        self.languages = [
            structs.LanguageTag.fromstr("de-Latn-DE-1999"),
            structs.LanguageTag.fromstr("fr-CH"),
            structs.LanguageTag.fromstr("it"),
        ]

    def test_match_direct(self):
        self.assertEqual(
            structs.LanguageTag.fromstr("fr-CH"),
            structs.lookup_language(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "en",
                    "fr-ch",
                    "de-de"
                ]))
            )
        )

        self.assertEqual(
            structs.LanguageTag.fromstr("it"),
            structs.lookup_language(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "it",
                ]))
            )
        )

    def test_decay(self):
        self.assertEqual(
            structs.LanguageTag.fromstr("de-Latn-DE-1999"),
            structs.lookup_language(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "de-de",
                    "en-GB",
                    "en"
                ]))
            )
        )

        self.assertEqual(
            structs.LanguageTag.fromstr("fr-CH"),
            structs.lookup_language(
                self.languages,
                list(map(structs.LanguageRange.fromstr, [
                    "fr-FR",
                    "de-DE",
                    "fr",
                ]))
            )
        )

    def test_decay_skips_extension_prefixes_properly(self):
        self.assertEqual(
            structs.LanguageTag.fromstr("de-DE"),
            structs.lookup_language(
                list(map(structs.LanguageTag.fromstr, [
                    "de-DE",
                    "de-x",
                ])),
                list(map(structs.LanguageRange.fromstr, [
                    "de-x-foobar",
                ]))
            )
        )


class TestLanguageMap(unittest.TestCase):
    def test_implements_mapping(self):
        mapping = structs.LanguageMap()
        self.assertIsInstance(
            mapping,
            collections.abc.MutableMapping
        )

    def test_mapping_interface(self):
        key1 = structs.LanguageTag.fromstr("de-DE")
        key2 = structs.LanguageTag.fromstr("en-US")
        key3 = structs.LanguageTag.fromstr("en")

        mapping = structs.LanguageMap()

        self.assertFalse(mapping)
        self.assertEqual(0, len(mapping))

        mapping[key1] = 10

        self.assertIn(key1, mapping)
        self.assertEqual(
            10,
            mapping[key1]
        )

        self.assertSetEqual(
            {key1},
            set(mapping)
        )

        mapping[key2] = 20

        self.assertIn(key2, mapping)
        self.assertEqual(
            20,
            mapping[key2]
        )

        self.assertSetEqual(
            {key1, key2},
            set(mapping)
        )

        key2_prime = structs.LanguageTag.fromstr("en-us")

        self.assertIn(key2_prime, mapping)
        self.assertEqual(
            20,
            mapping[key2_prime]
        )

        self.assertNotIn(key3, mapping)

        del mapping[key1]

        self.assertNotIn(key1, mapping)

        mapping.clear()

        self.assertNotIn(key2, mapping)

    def test_lookup(self):
        key1 = structs.LanguageTag.fromstr("de-DE")
        key2 = structs.LanguageTag.fromstr("en-US")
        key3 = structs.LanguageTag.fromstr("en")

        mapping = structs.LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertEqual(
            30,
            mapping.lookup([structs.LanguageRange.fromstr("en-GB")])
        )

    def test_values(self):
        key1 = structs.LanguageTag.fromstr("de-DE")
        key2 = structs.LanguageTag.fromstr("en-US")
        key3 = structs.LanguageTag.fromstr("en")

        mapping = structs.LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual(
            {10, 20, 30},
            set(mapping.values())
        )

    def test_keys(self):
        key1 = structs.LanguageTag.fromstr("de-DE")
        key2 = structs.LanguageTag.fromstr("en-US")
        key3 = structs.LanguageTag.fromstr("en")

        mapping = structs.LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual(
            {key1, key2, key3},
            set(mapping.keys())
        )

    def test_items(self):
        key1 = structs.LanguageTag.fromstr("de-DE")
        key2 = structs.LanguageTag.fromstr("en-US")
        key3 = structs.LanguageTag.fromstr("en")

        mapping = structs.LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual(
            {
                (key1, 10),
                (key2, 20),
                (key3, 30),
            },
            set(mapping.items())
        )

    def test_equality(self):
        mapping1 = structs.LanguageMap()
        mapping1[structs.LanguageTag.fromstr("de-de")] = 10
        mapping1[structs.LanguageTag.fromstr("en-US")] = 20

        mapping2 = structs.LanguageMap()
        mapping2[structs.LanguageTag.fromstr("de-DE")] = 10
        mapping2[structs.LanguageTag.fromstr("en-US")] = 20

        mapping3 = structs.LanguageMap()
        mapping3[structs.LanguageTag.fromstr("de-DE")] = 10
        mapping3[structs.LanguageTag.fromstr("en-GB")] = 20

        self.assertEqual(
            mapping1,
            mapping2
        )
        self.assertFalse(mapping1 != mapping2)

        self.assertNotEqual(
            mapping1,
            mapping3
        )
        self.assertFalse(mapping1 == mapping3)

        self.assertNotEqual(
            mapping2,
            mapping3
        )
        self.assertFalse(mapping2 == mapping3)

    def test_setdefault(self):
        l = []
        mapping = structs.LanguageMap()
        result = mapping.setdefault(structs.LanguageTag.fromstr("de-de"), l)

        self.assertIs(result, l)

        result = mapping.setdefault(structs.LanguageTag.fromstr("de-de"), [])

        self.assertIs(result, l)

    def test_lookup_returns_None_key_if_nothing_matches(self):
        mapping = structs.LanguageMap()
        mapping[None] = "foobar"
        mapping[structs.LanguageTag.fromstr("de")] = "Test"
        mapping[structs.LanguageTag.fromstr("en")] = "test"

        self.assertEqual(
            "foobar",
            mapping.lookup([structs.LanguageRange.fromstr("it")])
        )
