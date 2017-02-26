########################################################################
# File name: test_structs.py
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
import collections.abc
import enum
import unittest
import warnings

import aioxmpp
import aioxmpp.structs as structs
import aioxmpp.stanza as stanza


class DisableCompat:
    def __enter__(self):
        if aioxmpp.version_info < (1, 0, 0):
            structs._USE_COMPAT_ENUM = False

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if aioxmpp.version_info < (1, 0, 0):
            structs._USE_COMPAT_ENUM = True


class TestCompatibilityMixin(unittest.TestCase):
    class SomeEnum(structs.CompatibilityMixin, enum.Enum):
        X = "foo"
        Y = "bar"
        Z = None

    def test_compares_normally_without_warnings(self):
        E = self.SomeEnum

        with warnings.catch_warnings(record=True) as w:
            self.assertEqual(E.X, E.X)
            self.assertNotEqual(E.X, E.Y)
            self.assertNotEqual(E.X, E.Z)

            self.assertNotEqual(E.Y, E.X)
            self.assertEqual(E.Y, E.Y)
            self.assertNotEqual(E.Y, E.Z)

            self.assertNotEqual(E.Z, E.X)
            self.assertNotEqual(E.Z, E.Y)
            self.assertEqual(E.Z, E.Z)

        self.assertFalse(w)

    def test_hashes_to_values(self):
        for member in self.SomeEnum:
            self.assertEqual(
                hash(member),
                hash(member.value)
            )

    def _test_eq_with_warning(self, v1, v2):
        with self.assertWarnsRegex(
                DeprecationWarning,
                "as of aioxmpp 1.0, enums will not compare equal to their "
                "values") as ctx:
            self.assertTrue(v1 == v2)

        self.assertIn(
            "test_structs.py",
            ctx.filename,
        )

        with self.assertWarnsRegex(
                DeprecationWarning,
                "as of aioxmpp 1.0, enums will not compare equal to their "
                "values") as ctx:
            self.assertFalse(v1 != v2)

        self.assertIn(
            "test_structs.py",
            ctx.filename,
        )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_compares_equal_to_values_with_DeprecationWarning(self):
        for member in self.SomeEnum:
            self._test_eq_with_warning(member, member.value)
            self._test_eq_with_warning(member.value, member)

    @unittest.skipUnless(aioxmpp.version_info >= (1, 0, 0),
                         "does not apply to this version of aioxmpp")
    def test_compares_not_equal_to_values_by_default(self):
        for member in self.SomeEnum:
            self.assertTrue(member != member.value)
            self.assertTrue(member.value != member)
            self.assertFalse(member == member.value)
            self.assertFalse(member.value == member)

    def test_compares_not_equal_to_values_with_compat_disabled(self):
        with DisableCompat():
            for member in self.SomeEnum:
                self.assertTrue(member != member.value)
                self.assertTrue(member.value != member)
                self.assertFalse(member == member.value)
                self.assertFalse(member.value == member)


class TestErrorType(unittest.TestCase):
    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                structs.ErrorType,
                structs.CompatibilityMixin,
            )
        )


class TestMessageType(unittest.TestCase):
    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                structs.MessageType,
                structs.CompatibilityMixin,
            )
        )

    def test_values(self):
        self.assertSetEqual(
            {v.value for v in structs.MessageType},
            {
                "chat",
                "normal",
                "headline",
                "groupchat",
                "error",
            }
        )

    def test_is_response(self):
        for member in structs.MessageType:
            self.assertEqual(
                member == structs.MessageType.ERROR,
                member.is_response,
            )

    def test_is_error(self):
        for member in structs.MessageType:
            self.assertEqual(
                member == structs.MessageType.ERROR,
                member.is_error,
            )

    def test_is_request(self):
        for member in structs.MessageType:
            self.assertFalse(member.is_request)


class TestPresenceType(unittest.TestCase):
    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                structs.PresenceType,
                structs.CompatibilityMixin,
            )
        )

    def test_values(self):
        self.assertSetEqual(
            {v.value for v in structs.PresenceType},
            {
                "error",
                "probe",
                "subscribe",
                "subscribed",
                "unsubscribe",
                "unsubscribed",
                "unavailable",
                None,
            }
        )

    def test_is_response(self):
        for member in structs.PresenceType:
            self.assertEqual(
                member == structs.PresenceType.ERROR,
                member.is_response,
            )

    def test_is_error(self):
        for member in structs.PresenceType:
            self.assertEqual(
                member == structs.PresenceType.ERROR,
                member.is_error,
            )

    def test_is_request(self):
        for member in structs.PresenceType:
            self.assertFalse(member.is_request)

    def test_is_presence_state(self):
        positive = [
            structs.PresenceType.AVAILABLE,
            structs.PresenceType.UNAVAILABLE,
        ]

        for member in structs.PresenceType:
            self.assertEqual(
                member in positive,
                member.is_presence_state,
            )


class TestIQType(unittest.TestCase):
    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                structs.IQType,
                structs.CompatibilityMixin,
            )
        )

    def test_values(self):
        self.assertSetEqual(
            {member.value for member in structs.IQType},
            {
                "get",
                "set",
                "result",
                "error",
            }
        )

    def test_is_error(self):
        for member in structs.IQType:
            self.assertEqual(
                member == structs.IQType.ERROR,
                member.is_error
            )

    def test_is_request(self):
        positive = [
            structs.IQType.GET,
            structs.IQType.SET,
        ]

        for member in structs.IQType:
            self.assertEqual(
                member in positive,
                member.is_request,
            )

    def test_is_response(self):
        positive = [
            structs.IQType.ERROR,
            structs.IQType.RESULT,
        ]

        for member in structs.IQType:
            self.assertEqual(
                member in positive,
                member.is_response,
            )


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
            structs.JID("ßA", "example.test", None).localpart)

        self.assertEqual(
            "ix.test",
            structs.JID(None, "IX.test", None).domain)

        self.assertEqual(
            "IX",
            structs.JID(None, "example.test", "\u2168").resource)

    def test_init_with_default_strict_errors_on_unassigned(self):
        with self.assertRaises(ValueError):
            structs.JID("\U0001f601", "example.com", "bar")
        with self.assertRaises(ValueError):
            structs.JID("foo", "\U0001f601example.com", "bar")
        with self.assertRaises(ValueError):
            structs.JID("foo", "example.com", "\U0001f601")

    def test_init_without_strict_does_not_error_on_unassigned(self):
        structs.JID("\U0001f601", "example.com", "bar", strict=False)
        structs.JID("foo", "\U0001f601example.com", "bar", strict=False)
        structs.JID("foo", "example.com", "\U0001f601", strict=False)

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

    def test_replace_ignores_problems_on_existing_parts(self):
        j = structs.JID(
            "\U0001f601foo", "\U0001f601example.test", "\U0001f601bar",
            strict=False,
        )

        j2 = j.replace()
        self.assertEqual(j, j2)

    def test_replace_checks_replaced_strings(self):
        j = structs.JID(
            "\U0001f601foo", "\U0001f601example.test", "\U0001f601bar",
            strict=False,
        )

        with self.assertRaises(ValueError):
            j.replace(
                domain=j.domain
            )

    def test_replace_nonstrict_allows_unassigned_codepoints(self):
        j = structs.JID(
            "\U0001f601foo", "\U0001f601example.test", "\U0001f601bar",
            strict=False,
        )

        j2 = j.replace(
            domain=j.domain,
            strict=False,
        )

        self.assertEqual(j, j2)

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

    def test_fromstr_domain_nonstrict(self):
        self.assertEqual(
            structs.JID("\U0001f601", "\U0001f601example.test", "\U0001f601",
                        strict=False),
            structs.JID.fromstr("\U0001f601@\U0001f601example.test/\U0001f601",
                                strict=False)
        )

    def test_reject_empty_localpart(self):
        with self.assertRaises(ValueError):
            structs.JID("", "bar.baz", None)
        with self.assertRaises(ValueError):
            structs.JID.fromstr("@bar.baz")

    def test_reject_empty_domainpart(self):
        with self.assertRaises(ValueError):
            structs.JID("foo", "", None)
        with self.assertRaises(ValueError):
            structs.JID.fromstr("foo@")

    def test_reject_empty_resource(self):
        with self.assertRaises(ValueError):
            structs.JID("foo", "bar.baz", "")
        with self.assertRaises(ValueError):
            structs.JID.fromstr("foo@bar.baz/")

    def test_reject_long_localpart(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID("x"*1024, "foo", None)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID("ü"*512, "foo", None)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID.fromstr("ü"*512 + "@foo")

    def test_reject_long_domainpart(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID(None, "x"*1024, None)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID(None, "ü"*512, None)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID.fromstr("ü"*512)

    def test_reject_long_resource(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID(None, "foo", "x"*1024)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID(None, "foo", "ü"*512)
        with self.assertRaisesRegex(ValueError, "too long"):
            structs.JID.fromstr("foo/" + "ü"*512)


class TestPresenceShow(unittest.TestCase):
    def test_aliases(self):
        self.assertIs(
            structs.PresenceShow.XA,
            structs.PresenceShow.EXTENDED_AWAY
        )

        self.assertIs(
            structs.PresenceShow.PLAIN,
            structs.PresenceShow.NONE
        )

        self.assertIs(
            structs.PresenceShow.CHAT,
            structs.PresenceShow.FREE_FOR_CHAT
        )

        self.assertIs(
            structs.PresenceShow.DND,
            structs.PresenceShow.DO_NOT_DISTURB
        )

    def test_ordering_simple(self):
        values = [
            structs.PresenceShow.AWAY,
            structs.PresenceShow.CHAT,
            structs.PresenceShow.PLAIN,
            structs.PresenceShow.DND,
            structs.PresenceShow.XA,
        ]
        values.sort()

        self.assertSequenceEqual(
            [
                structs.PresenceShow.XA,
                structs.PresenceShow.AWAY,
                structs.PresenceShow.PLAIN,
                structs.PresenceShow.CHAT,
                structs.PresenceShow.DND,
            ],
            values,
        )

    def test_proper_error_message_on_invalid_ordering_operand(self):
        with self.assertRaises(TypeError):
            structs.PresenceShow.AWAY < 1

    def test_value(self):
        values = [
            "xa",
            "away",
            None,
            "chat",
            "dnd"
        ]

        for v in values:
            m = structs.PresenceShow(v)
            self.assertEqual(m.value, v)

    def test_ordering(self):
        values = [
            structs.PresenceShow("xa"),
            structs.PresenceShow("away"),
            structs.PresenceShow(None),
            structs.PresenceShow("chat"),
            structs.PresenceShow("dnd"),
        ]

        for i in range(1, len(values)-1):
            for v1, v2 in zip(values[:-i], values[i:]):
                self.assertLess(v1, v2)
                self.assertLessEqual(v1, v2)
                self.assertNotEqual(v1, v2)
                self.assertGreater(v2, v1)
                self.assertGreaterEqual(v2, v1)

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                structs.PresenceShow,
                structs.CompatibilityMixin,
            )
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
        self.assertEqual(ps.show, structs.PresenceShow.NONE)

    def test_init_compat(self):
        with self.assertWarnsRegex(
                DeprecationWarning,
                "as of aioxmpp 1.0, the show argument must use "
                "PresenceShow instead of str") as ctx:
            ps = structs.PresenceState(True, "dnd")
        self.assertIn(
            "test_structs.py",
            ctx.filename,
        )
        self.assertTrue(ps.available)
        self.assertEqual(ps.show, structs.PresenceShow.DND)

    def test_init_available(self):
        ps = structs.PresenceState(available=True)
        self.assertTrue(ps.available)

    def test_init_normalizes_available(self):
        ps = structs.PresenceState(available="foo")
        self.assertIs(True, ps.available)

    def test_init_available_with_show(self):
        ps = structs.PresenceState(available=True,
                                   show=structs.PresenceShow.DND)
        self.assertTrue(ps.available)
        self.assertIs(structs.PresenceShow.DND, ps.show)

    def test_init_available_validate_show(self):
        with self.assertRaises(ValueError):
            ps = structs.PresenceState(available=True, show="foobar")
        for value in ["dnd", "xa", "away", None, "chat"]:
            value = structs.PresenceShow(value)
            ps = structs.PresenceState(
                available=True,
                show=value)
            self.assertEqual(value, ps.show)

    def test_init_unavailable_forbids_show(self):
        with self.assertRaises(ValueError):
            structs.PresenceState(available=False,
                                  show=structs.PresenceShow.DND)

    def test_ordering(self):
        values = [
            structs.PresenceState(),
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.XA),
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.AWAY),
            structs.PresenceState(available=True),
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.CHAT),
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.DND),
        ]

        for i in range(1, len(values)-1):
            for v1, v2 in zip(values[:-i], values[i:]):
                self.assertLess(v1, v2)
                self.assertLessEqual(v1, v2)
                self.assertNotEqual(v1, v2)
                self.assertGreater(v2, v1)
                self.assertGreaterEqual(v2, v1)

    def test_proper_exception_on_invalid_ordering_operand(self):
        with self.assertRaises(TypeError):
            structs.PresenceState() < 1

        with self.assertRaises(TypeError):
            structs.PresenceState() > 1

        with self.assertRaises(TypeError):
            structs.PresenceState() >= 1

        with self.assertRaises(TypeError):
            structs.PresenceState() <= 1

        self.assertFalse(structs.PresenceState() == 0)
        self.assertTrue(structs.PresenceState() != 0)

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
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.DND),
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.DND),
        )
        self.assertFalse(
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.DND) !=
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.DND)
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
            "<PresenceState available show=<PresenceShow.DND: 'dnd'>>",
            repr(structs.PresenceState(available=True,
                                       show=structs.PresenceShow.DND))
        )

    def test_apply_to_stanza(self):
        stanza_obj = stanza.Presence(type_=structs.PresenceType.PROBE)
        self.assertEqual(stanza_obj.show, structs.PresenceShow.NONE)

        ps = structs.PresenceState(available=True,
                                   show=structs.PresenceShow.DND)
        ps.apply_to_stanza(stanza_obj)
        self.assertEqual(
            structs.PresenceType.AVAILABLE,
            stanza_obj.type_
        )
        self.assertEqual(
            structs.PresenceShow.DND,
            stanza_obj.show
        )

        ps = structs.PresenceState()
        ps.apply_to_stanza(stanza_obj)
        self.assertEqual(
            structs.PresenceType.UNAVAILABLE,
            stanza_obj.type_
        )
        self.assertEqual(
            stanza_obj.show,
            structs.PresenceShow.NONE,
        )

    def test_from_stanza(self):
        stanza_obj = stanza.Presence(
            type_=structs.PresenceType.AVAILABLE
        )
        stanza_obj.show = structs.PresenceShow.XA
        self.assertEqual(
            structs.PresenceState(available=True,
                                  show=structs.PresenceShow.XA),
            structs.PresenceState.from_stanza(stanza_obj)
        )

        stanza_obj = stanza.Presence(
            type_=structs.PresenceType.UNAVAILABLE,
        )
        self.assertEqual(
            structs.PresenceState(available=False),
            structs.PresenceState.from_stanza(stanza_obj)
        )

    def test_from_stanza_reject_incorrect_types(self):
        stanza_obj = stanza.Presence(
            type_=structs.PresenceType.PROBE
        )
        with self.assertRaises(ValueError):
            structs.PresenceState.from_stanza(stanza_obj)

    def test_from_stanza_nonstrict_by_default(self):
        stanza_obj = stanza.Presence(
            type_=structs.PresenceType.UNAVAILABLE
        )
        stanza_obj.show = structs.PresenceShow.AWAY
        self.assertEqual(
            structs.PresenceState(available=False),
            structs.PresenceState.from_stanza(stanza_obj)
        )

    def test_from_stanza_strict_by_default(self):
        stanza_obj = stanza.Presence(
            type_=structs.PresenceType.UNAVAILABLE,
        )
        stanza_obj.show = structs.PresenceShow.DND
        with self.assertRaises(ValueError):
            structs.PresenceState.from_stanza(stanza_obj, strict=True)


class TestLanguageTag(unittest.TestCase):
    def test_init_requires_kwargs(self):
        with self.assertRaisesRegex(TypeError,
                                     "takes 1 positional argument"):
            structs.LanguageTag("foo")

    def test_init_requires_language(self):
        with self.assertRaisesRegex(ValueError, "tag cannot be empty"):
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

    def test_dont_compare_with_None(self):
        tag1 = structs.LanguageTag.fromstr("de-DE")
        with self.assertRaises(TypeError):
            tag1 > None
        with self.assertRaises(TypeError):
            tag1 < None
        with self.assertRaises(TypeError):
            tag1 >= None
        with self.assertRaises(TypeError):
            tag1 <= None

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
        with self.assertRaisesRegex(TypeError,
                                     "takes 1 positional argument"):
            structs.LanguageRange("foo")

    def test_init_requires_language(self):
        with self.assertRaisesRegex(ValueError, "range cannot be empty"):
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
