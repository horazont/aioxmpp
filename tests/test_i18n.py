import contextlib
import unittest
import unittest.mock

from datetime import datetime, timedelta, date, time

import babel
import babel.dates
import babel.numbers
import pytz
import tzlocal

import aioxmpp.i18n as i18n


class TestLocalizingFormatter(unittest.TestCase):
    def setUp(self):
        self.default_locale = babel.default_locale()
        self.foreign_locale = babel.Locale("it")
        if self.foreign_locale == self.default_locale:
            self.foreign_locale = babel.Locale("de")

        self.local_timezone = tzlocal.get_localzone()
        self.foreign_timezone = pytz.timezone("US/Eastern")
        if self.foreign_timezone == self.local_timezone:
            self.foreign_timezone = pytz.timezone("Europe/Berlin")

    def test_init_default(self):
        formatter = i18n.LocalizingFormatter()
        self.assertEqual(formatter.locale, babel.default_locale())
        self.assertEqual(formatter.tzinfo, self.local_timezone)

    def test_init_with_explicit_locale(self):
        formatter = i18n.LocalizingFormatter(self.foreign_locale)
        self.assertEqual(formatter.locale, self.foreign_locale)

    def test_init_with_explicit_timezone(self):
        formatter = i18n.LocalizingFormatter(self.foreign_locale, self.foreign_timezone)
        self.assertEqual(formatter.tzinfo, self.foreign_timezone)

    def test_convert_field_datetime_locale(self):
        formatter = i18n.LocalizingFormatter()

        loc = object()

        tzinfo = unittest.mock.Mock()
        dt = datetime.now(tz=pytz.utc)
        with contextlib.ExitStack() as stack:
            format_datetime = stack.enter_context(
                unittest.mock.patch("babel.dates.format_datetime")
            )
            s = formatter.convert_field(dt, "s",
                                        locale=loc,
                                        tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(tzinfo.normalize(dt), locale=loc),
            ],
            format_datetime.mock_calls
        )

        self.assertEqual(
            format_datetime(),
            s
        )

    def test_convert_field_datetime_default_locale(self):
        formatter = i18n.LocalizingFormatter()

        dt = datetime.now(tz=pytz.utc)
        with unittest.mock.patch("babel.dates.format_datetime") \
                 as format_datetime:
            s = formatter.convert_field(dt, "s")

        self.assertSequenceEqual(
            [
                unittest.mock.call(dt, locale=formatter.locale),
            ],
            format_datetime.mock_calls
        )

        self.assertEqual(
            format_datetime(),
            s
        )

    def test_convert_field_datetime_repr(self):
        formatter = i18n.LocalizingFormatter()

        loc = object()

        dt = datetime.now(tz=pytz.utc)
        with unittest.mock.patch("babel.dates.format_datetime") \
                 as format_datetime:
            r = formatter.convert_field(dt, "r", locale=loc)

        self.assertEqual(
            repr(dt),
            r
        )
        self.assertSequenceEqual(
            [],
            format_datetime.mock_calls
        )

    def test_convert_field_timedelta_locale(self):
        formatter = i18n.LocalizingFormatter()

        loc = object()

        td = timedelta(seconds=123)
        with unittest.mock.patch("babel.dates.format_timedelta") \
                 as format_timedelta:
            s = formatter.convert_field(td, "s", locale=loc)

        self.assertSequenceEqual(
            [
                unittest.mock.call(td, locale=loc),
            ],
            format_timedelta.mock_calls
        )

        self.assertEqual(
            format_timedelta(),
            s
        )

    def test_convert_field_timedelta_default_locale(self):
        formatter = i18n.LocalizingFormatter()

        td = timedelta(seconds=123)
        with unittest.mock.patch("babel.dates.format_timedelta") \
                 as format_timedelta:
            s = formatter.convert_field(td, "s")

        self.assertSequenceEqual(
            [
                unittest.mock.call(td, locale=formatter.locale),
            ],
            format_timedelta.mock_calls
        )

        self.assertEqual(
            format_timedelta(),
            s
        )

    def test_convert_field_timedelta_repr(self):
        formatter = i18n.LocalizingFormatter()

        td = timedelta(seconds=123)
        with unittest.mock.patch("babel.dates.format_timedelta") \
                 as format_timedelta:
            r = formatter.convert_field(td, "r")

        self.assertSequenceEqual(
            [],
            format_timedelta.mock_calls
        )

        self.assertEqual(
            repr(td),
            r
        )

    def test_convert_field_date_locale(self):
        formatter = i18n.LocalizingFormatter()

        loc = object()

        d = date.today()
        with unittest.mock.patch("babel.dates.format_date") \
                 as format_date:
            s = formatter.convert_field(d, "s", locale=loc)

        self.assertSequenceEqual(
            [
                unittest.mock.call(d, locale=loc),
            ],
            format_date.mock_calls
        )

        self.assertEqual(
            format_date(),
            s
        )

    def test_convert_field_date_default_locale(self):
        formatter = i18n.LocalizingFormatter()

        d = date.today()
        with unittest.mock.patch("babel.dates.format_date") \
                 as format_date:
            s = formatter.convert_field(d, "s")

        self.assertSequenceEqual(
            [
                unittest.mock.call(d, locale=formatter.locale),
            ],
            format_date.mock_calls
        )

        self.assertEqual(
            format_date(),
            s
        )

    def test_convert_field_date_repr(self):
        formatter = i18n.LocalizingFormatter()

        d = date.today()
        with unittest.mock.patch("babel.dates.format_date") \
                 as format_date:
            r = formatter.convert_field(d, "r")

        self.assertSequenceEqual(
            [],
            format_date.mock_calls
        )

        self.assertEqual(
            repr(d),
            r
        )

    def test_convert_field_time_locale(self):
        formatter = i18n.LocalizingFormatter()

        loc = object()

        t = datetime.now(tz=pytz.utc).time()
        with unittest.mock.patch("babel.dates.format_time") \
                 as format_time:
            s = formatter.convert_field(t, "s", locale=loc)

        self.assertSequenceEqual(
            [
                unittest.mock.call(t, locale=loc),
            ],
            format_time.mock_calls
        )

        self.assertEqual(
            format_time(),
            s
        )

    def test_convert_field_time_default_locale(self):
        formatter = i18n.LocalizingFormatter()

        t = datetime.now(tz=pytz.utc).timetz()
        with unittest.mock.patch("babel.dates.format_time") \
                 as format_time:
            s = formatter.convert_field(t, "s")

        self.assertSequenceEqual(
            [
                unittest.mock.call(t, locale=formatter.locale),
            ],
            format_time.mock_calls
        )

        self.assertEqual(
            format_time(),
            s
        )

    def test_convert_field_time_repr(self):
        formatter = i18n.LocalizingFormatter()

        t = datetime.now(tz=pytz.utc).timetz()
        with unittest.mock.patch("babel.dates.format_time") \
                 as format_time:
            r = formatter.convert_field(t, "r")

        self.assertSequenceEqual(
            [],
            format_time.mock_calls
        )

        self.assertEqual(
            repr(t),
            r
        )

    def test_convert_other_types(self):
        formatter = i18n.LocalizingFormatter()

        values = [
            123,
            1.2,
            "foobar",
            b"barbaz",
        ]

        for value in values:
            self.assertEqual(
                str(value),
                formatter.convert_field(value, "s")
            )

        for value in values:
            self.assertEqual(
                repr(value),
                formatter.convert_field(value, "r")
            )

    def test_format_field_datetime_forwards_to_babel(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        dt = datetime.now(tz=pytz.utc)
        loc = object()

        with contextlib.ExitStack() as stack:
            format_datetime = stack.enter_context(
                unittest.mock.patch("babel.dates.format_datetime")
            )
            s = formatter.format_field(dt, "full barbaz",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(tzinfo.normalize(dt),
                                   locale=loc,
                                   format="full barbaz")
            ],
            format_datetime.mock_calls
        )
        self.assertEqual(
            format_datetime(),
            s
        )

    def test_format_field_datetime_defaults_to_babels_default(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        dt = datetime.now(tz=pytz.utc)
        loc = object()

        with contextlib.ExitStack() as stack:
            format_datetime = stack.enter_context(
                unittest.mock.patch("babel.dates.format_datetime")
            )
            s = formatter.format_field(dt, "",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(tzinfo.normalize(dt),
                                   locale=loc)
            ],
            format_datetime.mock_calls
        )
        self.assertEqual(
            format_datetime(),
            s
        )

    def test_format_field_datetime_forwards_to_babel_with_defaults(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        dt = datetime.now(tz=pytz.utc)

        with contextlib.ExitStack() as stack:
            format_datetime = stack.enter_context(
                unittest.mock.patch("babel.dates.format_datetime")
            )
            s = formatter.format_field(dt, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(formatter.tzinfo.normalize(dt),
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_datetime.mock_calls
        )
        self.assertEqual(
            format_datetime(),
            s
        )

    def test_format_field_datetime_forwards_to_babel_without_tzinfo(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        dt = datetime.utcnow()

        self.assertIsNone(dt.tzinfo)

        with contextlib.ExitStack() as stack:
            format_datetime = stack.enter_context(
                unittest.mock.patch("babel.dates.format_datetime")
            )
            s = formatter.format_field(dt, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(dt,
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_datetime.mock_calls
        )
        self.assertEqual(
            format_datetime(),
            s
        )

    def test_format_field_timedelta_forwards_to_babel(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        td = timedelta(seconds=120)
        loc = object()

        with contextlib.ExitStack() as stack:
            format_timedelta = stack.enter_context(
                unittest.mock.patch("babel.dates.format_timedelta")
            )
            s = formatter.format_field(td, "full barbaz",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(td,
                                   locale=loc,
                                   format="full barbaz")
            ],
            format_timedelta.mock_calls
        )
        self.assertEqual(
            format_timedelta(),
            s
        )

    def test_format_field_timedelta_defaults_to_babels_default(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        td = timedelta(seconds=120)
        loc = object()

        with contextlib.ExitStack() as stack:
            format_timedelta = stack.enter_context(
                unittest.mock.patch("babel.dates.format_timedelta")
            )
            s = formatter.format_field(td, "",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(td,
                                   locale=loc)
            ],
            format_timedelta.mock_calls
        )
        self.assertEqual(
            format_timedelta(),
            s
        )

    def test_format_field_timedelta_forwards_to_babel_with_defaults(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        td = timedelta(seconds=120)

        with contextlib.ExitStack() as stack:
            format_timedelta = stack.enter_context(
                unittest.mock.patch("babel.dates.format_timedelta")
            )
            s = formatter.format_field(td, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(td,
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_timedelta.mock_calls
        )
        self.assertEqual(
            format_timedelta(),
            s
        )

    def test_format_field_date_forwards_to_babel(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        d = datetime.now(tz=pytz.utc).date()
        loc = object()

        with contextlib.ExitStack() as stack:
            format_date = stack.enter_context(
                unittest.mock.patch("babel.dates.format_date")
            )
            s = formatter.format_field(d, "full barbaz",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(d,
                                   locale=loc,
                                   format="full barbaz")
            ],
            format_date.mock_calls
        )
        self.assertEqual(
            format_date(),
            s
        )

    def test_format_field_date_defaults_to_babels_default(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        d = datetime.now(tz=pytz.utc).date()
        loc = object()

        with contextlib.ExitStack() as stack:
            format_date = stack.enter_context(
                unittest.mock.patch("babel.dates.format_date")
            )
            s = formatter.format_field(d, "",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(d,
                                   locale=loc)
            ],
            format_date.mock_calls
        )
        self.assertEqual(
            format_date(),
            s
        )

    def test_format_field_date_forwards_to_babel_with_defaults(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        d = datetime.now(tz=pytz.utc).date()

        with contextlib.ExitStack() as stack:
            format_date = stack.enter_context(
                unittest.mock.patch("babel.dates.format_date")
            )
            s = formatter.format_field(d, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(d,
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_date.mock_calls
        )
        self.assertEqual(
            format_date(),
            s
        )

    def test_format_field_time_forwards_to_babel(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        t = datetime.now(tz=pytz.utc).timetz()
        loc = object()

        with contextlib.ExitStack() as stack:
            format_time = stack.enter_context(
                unittest.mock.patch("babel.dates.format_time")
            )
            s = formatter.format_field(t, "full barbaz",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(t,
                                   locale=loc,
                                   format="full barbaz")
            ],
            format_time.mock_calls
        )
        self.assertEqual(
            format_time(),
            s
        )

    def test_format_field_time_defaults_to_babels_default(self):
        formatter = i18n.LocalizingFormatter()

        tzinfo = unittest.mock.Mock()
        t = datetime.now(tz=pytz.utc).timetz()
        loc = object()

        with contextlib.ExitStack() as stack:
            format_time = stack.enter_context(
                unittest.mock.patch("babel.dates.format_time")
            )
            s = formatter.format_field(t, "",
                                       locale=loc,
                                       tzinfo=tzinfo)

        self.assertSequenceEqual(
            [
                unittest.mock.call(t,
                                   locale=loc)
            ],
            format_time.mock_calls
        )
        self.assertEqual(
            format_time(),
            s
        )

    def test_format_field_time_forwards_to_babel_with_defaults(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        t = datetime.now(tz=pytz.utc).timetz()

        with contextlib.ExitStack() as stack:
            format_time = stack.enter_context(
                unittest.mock.patch("babel.dates.format_time")
            )
            s = formatter.format_field(t, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(t,
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_time.mock_calls
        )
        self.assertEqual(
            format_time(),
            s
        )

    def test_format_field_time_forwards_to_babel_without_tzinfo(self):
        formatter = i18n.LocalizingFormatter()

        formatter.tzinfo = unittest.mock.Mock()
        t = datetime.now(tz=pytz.utc).time()

        with contextlib.ExitStack() as stack:
            format_time = stack.enter_context(
                unittest.mock.patch("babel.dates.format_time")
            )
            s = formatter.format_field(t, "full barbaz")

        self.assertSequenceEqual(
            [
                unittest.mock.call(t,
                                   locale=formatter.locale,
                                   format="full barbaz")
            ],
            format_time.mock_calls
        )
        self.assertEqual(
            format_time(),
            s
        )

    def test_format_field_number_uses_format_number_on_empty_format(self):
        formatter = i18n.LocalizingFormatter()

        v = 123
        loc = object()

        with contextlib.ExitStack() as stack:
            format_number = stack.enter_context(
                unittest.mock.patch("babel.numbers.format_number")
            )

            s = formatter.format_field(v, "n", locale=loc)

        self.assertSequenceEqual(
            [
                unittest.mock.call(v, locale=loc),
            ],
            format_number.mock_calls
        )
        self.assertEqual(
            format_number(),
            s
        )

    def test_format_field_number_forwards_to_babel_format_decimal(self):
        formatter = i18n.LocalizingFormatter()

        v = 123
        loc = object()

        with contextlib.ExitStack() as stack:
            format_decimal = stack.enter_context(
                unittest.mock.patch("babel.numbers.format_decimal")
            )

            s = formatter.format_field(v, "##.###n", locale=loc)

        self.assertSequenceEqual(
            [
                unittest.mock.call(v, format="##.###", locale=loc),
            ],
            format_decimal.mock_calls
        )
        self.assertEqual(
            format_decimal(),
            s
        )

    def test_format_works_normally(self):
        formatter = i18n.LocalizingFormatter()

        testsets = [
            ("abc {} def {:10d} ghi {:.2f}", ("foo", 12, 34.5), {}),
        ]

        for fmt, args, kwargs in testsets:
            self.assertEqual(
                fmt.format(*args, **kwargs),
                formatter.format(fmt, *args, **kwargs),
            )


class TestLocalizableString(unittest.TestCase):
    def test_init(self):
        s = "foobar baz"
        ls = i18n.LocalizableString(s)
        self.assertNotEqual(ls, s)

        self.assertEqual(ls.singular, s)
        self.assertIsNone(ls.plural)
        self.assertIsNone(ls.number_index)

    def test_init_plural(self):
        sing = "{1:d} thing"
        plural = "{1:d} things"
        ls = i18n.LocalizableString(sing, plural, 1)

        self.assertEqual(
            sing,
            ls.singular,
        )
        self.assertEqual(
            plural,
            ls.plural
        )
        self.assertEqual(
            "1",
            ls.number_index
        )

    def test_init_plural_number_index_defaults_to_zero(self):
        sing = "{:d} thing"
        plural = "{:d} things"
        ls = i18n.LocalizableString(sing, plural)

        self.assertEqual(
            sing,
            ls.singular,
        )
        self.assertEqual(
            plural,
            ls.plural
        )
        self.assertEqual(
            "0",
            ls.number_index
        )

    def test_init_rejects_number_index_without_plural_string(self):
        with self.assertRaisesRegexp(ValueError, "plural is required"):
            i18n.LocalizableString("abc", number_index=12)

    def test_compares_to_other_localizable_strings(self):
        s1 = "foobar baz"
        s2 = "fnord"

        ls1 = i18n.LocalizableString(s1)
        ls2 = i18n.LocalizableString(s1)
        ls3 = i18n.LocalizableString(s2)

        self.assertTrue(ls1 == ls2)
        self.assertTrue(ls2 == ls1)
        self.assertFalse(ls1 != ls2)
        self.assertFalse(ls2 != ls1)

        self.assertTrue(ls1 != ls3)
        self.assertTrue(ls3 != ls1)
        self.assertFalse(ls1 == ls3)
        self.assertFalse(ls3 == ls1)

        self.assertTrue(ls2 != ls3)
        self.assertTrue(ls3 != ls2)
        self.assertFalse(ls2 == ls3)
        self.assertFalse(ls3 == ls2)

    def test_compares_to_other_localizable_strings_with_plural(self):
        s1 = "foobar baz"
        s2 = "fnord"

        ls1 = i18n.LocalizableString(s1, "plural")
        ls2 = i18n.LocalizableString(s1)
        ls3 = i18n.LocalizableString(s2, "plural")

        self.assertTrue(ls1 != ls2)
        self.assertTrue(ls2 != ls1)
        self.assertFalse(ls1 == ls2)
        self.assertFalse(ls2 == ls1)

        self.assertTrue(ls1 != ls3)
        self.assertTrue(ls3 != ls1)
        self.assertFalse(ls1 == ls3)
        self.assertFalse(ls3 == ls1)

        self.assertTrue(ls2 != ls3)
        self.assertTrue(ls3 != ls2)
        self.assertFalse(ls2 == ls3)
        self.assertFalse(ls3 == ls2)

    def test_compares_to_other_localizable_strings_with_plural_index(self):
        s1 = "foobar baz"
        s2 = "fnord"

        ls1 = i18n.LocalizableString(s1, "plural")
        ls2 = i18n.LocalizableString(s1, "plural", 1)
        ls3 = i18n.LocalizableString(s2, "plural")

        self.assertTrue(ls1 != ls2)
        self.assertTrue(ls2 != ls1)
        self.assertFalse(ls1 == ls2)
        self.assertFalse(ls2 == ls1)

        self.assertTrue(ls1 != ls3)
        self.assertTrue(ls3 != ls1)
        self.assertFalse(ls1 == ls3)
        self.assertFalse(ls3 == ls1)

        self.assertTrue(ls2 != ls3)
        self.assertTrue(ls3 != ls2)
        self.assertFalse(ls2 == ls3)
        self.assertFalse(ls3 == ls2)

    def test_compares_to_other_localizable_strings_with_plural_eq(self):
        s1 = "foobar baz"
        s2 = "fnord"

        ls1 = i18n.LocalizableString(s1, "plural")
        ls2 = i18n.LocalizableString(s1, "plural")
        ls3 = i18n.LocalizableString(s2, "plural")

        self.assertTrue(ls1 == ls2)
        self.assertTrue(ls2 == ls1)
        self.assertFalse(ls1 != ls2)
        self.assertFalse(ls2 != ls1)

        self.assertTrue(ls1 != ls3)
        self.assertTrue(ls3 != ls1)
        self.assertFalse(ls1 == ls3)
        self.assertFalse(ls3 == ls1)

        self.assertTrue(ls2 != ls3)
        self.assertTrue(ls3 != ls2)
        self.assertFalse(ls2 == ls3)
        self.assertFalse(ls3 == ls2)

    def test_localize(self):
        formatter = i18n.LocalizingFormatter()
        translator = unittest.mock.Mock()
        s = "abc {a} def {} ghi {foo}"
        ls = i18n.LocalizableString(s)

        with unittest.mock.patch.object(formatter, "vformat") as vformat:
            result = ls.localize(
                formatter,
                translator,
                "foobar",
                a=123,
                foo=34.5
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call.gettext(s)
            ],
            translator.mock_calls
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    translator.gettext(),
                    ("foobar",),
                    {
                        "a": 123,
                        "foo": 34.5,
                    },
                )
            ],
            vformat.mock_calls
        )

    def test_localize_plural(self):
        formatter = i18n.LocalizingFormatter()
        translator = unittest.mock.Mock()
        s1 = "{a} thing"
        sn = "{a} things"
        ls = i18n.LocalizableString(s1, sn, "a")

        with contextlib.ExitStack() as stack:
            vformat = stack.enter_context(
                unittest.mock.patch.object(formatter, "vformat")
            )
            get_field = stack.enter_context(
                unittest.mock.patch.object(formatter, "get_field")
            )
            get_field.return_value = 123, "a"

            result = ls.localize(
                formatter,
                translator,
                "foobar",
                a=123,
                foo=34.5
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call("a", ("foobar",), {"a": 123, "foo": 34.5}),
            ],
            get_field.mock_calls
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call.ngettext(s1, sn, 123)
            ],
            translator.mock_calls
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    translator.ngettext(),
                    ("foobar",),
                    {
                        "a": 123,
                        "foo": 34.5,
                    },
                )
            ],
            vformat.mock_calls
        )

    def test_str_singular(self):
        ls = i18n.LocalizableString("foobar")
        self.assertEqual(
            "foobar",
            str(ls),
        )

    def test_str_plural(self):
        ls = i18n.LocalizableString("foobar", "baz")
        self.assertEqual(
            "foobar",
            str(ls),
        )

    def test_repr_singular(self):
        ls = i18n.LocalizableString("foobar")
        self.assertEqual(
            "_({!r})".format("foobar"),
            repr(ls),
        )

    def test_repr_plural(self):
        ls = i18n.LocalizableString("foobar", "baz", "a")
        self.assertEqual(
            "ngettext({!r}, {!r}, {!r})".format("foobar", "baz", "a"),
            repr(ls),
        )

    def test_immutable(self):
        ls = i18n.LocalizableString("foo", "bar", "baz")
        with self.assertRaises(AttributeError):
            ls.singular = "fnord"
        with self.assertRaises(AttributeError):
            ls.plural = "fnord"
        with self.assertRaises(AttributeError):
            ls.number_index = "fnord"
        with self.assertRaises(AttributeError):
            ls.foobar = "fnord"

    def test_hashable(self):
        s1 = i18n.LocalizableString("foo")
        s2 = i18n.LocalizableString("foo")

        self.assertEqual(hash(s1), hash(s2))


class Test_(unittest.TestCase):
    def test_creates_string(self):
        with unittest.mock.patch(
                "aioxmpp.i18n.LocalizableString"
        ) as LocalizableString:
            s = i18n._("s")

        self.assertSequenceEqual(
            [
                unittest.mock.call("s"),
            ],
            LocalizableString.mock_calls
        )
        self.assertEqual(
            LocalizableString(),
            s
        )


class Testngettext(unittest.TestCase):
    def test_creates_string(self):
        with unittest.mock.patch(
                "aioxmpp.i18n.LocalizableString"
        ) as LocalizableString:
            s = i18n.ngettext("one", "many", "abc")

        self.assertSequenceEqual(
            [
                unittest.mock.call("one", "many", "abc"),
            ],
            LocalizableString.mock_calls
        )
        self.assertEqual(
            LocalizableString(),
            s
        )
