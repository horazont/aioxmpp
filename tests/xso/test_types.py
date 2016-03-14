import abc
import decimal
import fractions
import inspect
import ipaddress
import unittest
import unittest.mock

import pytz

from datetime import datetime, date, time

import aioxmpp.xso as xso
import aioxmpp.structs as structs


class TestAbstractType(unittest.TestCase):
    class DummyType(xso.AbstractType):
        def parse(self, v):
            pass

    def test_is_abstract(self):
        self.assertIsInstance(
            xso.AbstractType,
            abc.ABCMeta)
        with self.assertRaises(TypeError):
            xso.AbstractType()

    def test_parse_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractType.parse))

    def test_get_formatted_type(self):
        self.assertIs(xso.AbstractType.get_formatted_type(object()), str)

    def test_format_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractType.format))
        self.assertEqual(
            "foo",
            self.DummyType().format("foo"))
        self.assertEqual(
            "23",
            self.DummyType().format(23))


class TestStringType(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.String(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.String()
        self.assertEqual(
            "foo",
            t.parse("foo"))

    def test_format(self):
        t = xso.String()
        self.assertEqual(
            "foo",
            t.format("foo"))

    def test_coerce_passes_string(self):
        t = xso.String()
        s = "foobar"
        self.assertIs(s, t.coerce(s))

    def test_coerce_rejects_non_strings(self):
        t = xso.String()

        values = [
            1.2,
            decimal.Decimal("1"),
            fractions.Fraction(1, 1),
            [],
            (),
            1.
        ]

        for value in values:
            with self.assertRaisesRegex(TypeError, "must be a str"):
                t.coerce(value)

    def test_coerce_stringprep(self):
        prepfunc = unittest.mock.Mock()
        t = xso.String(prepfunc=prepfunc)

        result = t.coerce("foobar")

        self.assertSequenceEqual(
            [
                unittest.mock.call("foobar"),
            ],
            prepfunc.mock_calls
        )

        self.assertEqual(
            prepfunc(),
            result,
        )

    def test_parse_stringprep(self):
        prepfunc = unittest.mock.Mock()
        t = xso.String(prepfunc=prepfunc)

        result = t.parse("foobar")

        self.assertSequenceEqual(
            [
                unittest.mock.call("foobar"),
            ],
            prepfunc.mock_calls
        )

        self.assertEqual(
            prepfunc(),
            result,
        )


class TestIntegerType(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Integer(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.Integer()
        self.assertEqual(
            123,
            t.parse("123"))

    def test_parse_failure(self):
        t = xso.Integer()
        with self.assertRaises(ValueError):
            t.parse("123f")

    def test_format(self):
        t = xso.Integer()
        self.assertEqual(
            "123",
            t.format(123))

    def test_coerce_passes_integral_numbers(self):
        t = xso.Integer()

        values = [-2, 0, 1, 2, 3, 4, 100]

        for value in values:
            self.assertIs(value, t.coerce(value))

        import random
        value = random.randint(1, 1e10)
        self.assertIs(value, t.coerce(value))
        value = -value
        self.assertIs(value, t.coerce(value))

    def test_coerce_requires_integral_number(self):
        t = xso.Integer()

        values = [
            1.2,
            "1",
            decimal.Decimal("1"),
            fractions.Fraction(1, 1),
            "foo",
            [],
            (),
            1.
        ]

        for value in values:
            with self.assertRaisesRegex(
                    TypeError,
                    "must be integral number"):
                t.coerce(value)


class TestFloatType(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Float(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.Float()
        self.assertEqual(
            123.3,
            t.parse("123.3"))

    def test_parse_failure(self):
        t = xso.Float()
        with self.assertRaises(ValueError):
            t.parse("123.3f")

    def test_format(self):
        t = xso.Float()
        self.assertEqual(
            "123.3",
            t.format(123.3))

    def test_coerce_passes_real_numbers(self):
        t = xso.Float()

        values = [
            # decimal.Decimal("1.23"),
            fractions.Fraction(1, 9),
            1.234,
            20,
            -1,
            -3.4,
        ]

        for value in values:
            self.assertEqual(
                float(value),
                t.coerce(value)
            )

    def test_coerce_passes_decimal(self):
        t = xso.Float()

        values = [
            decimal.Decimal("1.23"),
        ]

        for value in values:
            self.assertEqual(
                float(value),
                t.coerce(value)
            )

    def test_coerce_requires_float_number(self):
        t = xso.Float()

        values = [
            "foo",
            [],
            ()
        ]

        for value in values:
            with self.assertRaisesRegex(
                    TypeError,
                    "must be real number"):
                t.coerce(value)


class TestBoolType(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Bool(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.Bool()
        self.assertTrue(t.parse("true"))
        self.assertTrue(t.parse("1"))
        self.assertTrue(t.parse("  true  "))
        self.assertTrue(t.parse(" 1 "))
        self.assertFalse(t.parse("false"))
        self.assertFalse(t.parse("0"))
        self.assertFalse(t.parse("  false "))
        self.assertFalse(t.parse(" 0 "))

    def test_parse_failure(self):
        t = xso.Bool()
        with self.assertRaises(ValueError):
            t.parse("foobar")
        with self.assertRaises(ValueError):
            t.parse("truefoo")
        with self.assertRaises(ValueError):
            t.parse("0foo")

    def test_format(self):
        t = xso.Bool()
        self.assertEqual(
            "true",
            t.format(True))
        self.assertEqual(
            "false",
            t.format(False))

    def test_coerce_anything(self):
        t = xso.Bool()
        mock = unittest.mock.MagicMock()

        result = mock.__bool__()
        mock.reset_mock()

        self.assertEqual(
            result,
            t.coerce(mock))

        mock.__bool__.assert_called_once_with()


class TestDateTimeType(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.DateTime(),
            xso.AbstractType)

    def test_parse_example(self):
        t = xso.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc),
            t.parse("2014-01-26T19:40:10Z"))

    def test_parse_timezoned(self):
        t = xso.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc),
            t.parse("2014-01-26T20:40:10+01:00"))

    def test_parse_local(self):
        t = xso.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 20, 40, 10),
            t.parse("2014-01-26T20:40:10"))

    def test_parse_milliseconds(self):
        t = xso.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 20, 40, 10, 123456),
            t.parse("2014-01-26T20:40:10.123456"))

    def test_parse_milliseconds_timezoned(self):
        t = xso.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, 123456, tzinfo=pytz.utc),
            t.parse("2014-01-26T20:40:10.123456+01:00"))

    def test_parse_need_time(self):
        t = xso.DateTime()
        with self.assertRaises(ValueError):
            t.parse("2014-01-26")

    def test_parse_need_date(self):
        t = xso.DateTime()
        with self.assertRaises(ValueError):
            t.parse("20:40:10")

    def test_format_timezoned(self):
        t = xso.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10Z",
            t.format(datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc))
        )

    def test_format_timezoned_microseconds(self):
        t = xso.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10.1234Z",
            t.format(datetime(2014, 1, 26, 19, 40, 10, 123400,
                              tzinfo=pytz.utc))
        )

    def test_format_naive(self):
        t = xso.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10",
            t.format(datetime(2014, 1, 26, 19, 40, 10))
        )

    def test_format_naive_microseconds(self):
        t = xso.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10.1234",
            t.format(datetime(2014, 1, 26, 19, 40, 10, 123400))
        )

    def test_format_timezoned_nonutc(self):
        t = xso.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10Z",
            t.format(pytz.timezone("Europe/Berlin").localize(
                datetime(2014, 1, 26, 20, 40, 10)
            ))
        )

    def test_parse_xep0082_examples(self):
        t = xso.DateTime()
        self.assertEqual(
            t.parse("1969-07-21T02:56:15Z"),
            datetime(1969, 7, 21, 2, 56, 15, tzinfo=pytz.utc)
        )
        self.assertEqual(
            t.parse("1969-07-20T21:56:15-05:00"),
            datetime(1969, 7, 21, 2, 56, 15, tzinfo=pytz.utc)
        )

    def test_parse_legacy_format(self):
        t = xso.DateTime()
        self.assertEqual(
            t.parse("19690721T02:56:15"),
            datetime(1969, 7, 21, 2, 56, 15, tzinfo=pytz.utc)
        )

    def test_emit_legacy_format_with_switch(self):
        t = xso.DateTime(legacy=True)
        self.assertEqual(
            "19690721T02:56:15",
            t.format(datetime(1969, 7, 21, 2, 56, 15, tzinfo=pytz.utc))
        )
        self.assertEqual(
            "20140126T19:40:10",
            t.format(pytz.timezone("Europe/Berlin").localize(
                datetime(2014, 1, 26, 20, 40, 10)
            ))
        )

    def test_require_datetime(self):
        t = xso.DateTime()

        values = [
            1,
            "foo",
            "2014-01-26T19:47:10Z",
            12.3,
        ]

        for value in values:
            with self.assertRaisesRegex(
                    TypeError,
                    "must be a datetime object"):
                t.coerce(value)

    def test_pass_datetime(self):
        t = xso.DateTime()

        dt = datetime.utcnow()
        self.assertIs(
            dt,
            t.coerce(dt)
        )


class TestDate(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Date(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.Date()
        self.assertEqual(
            t.parse("1776-07-04"),
            date(1776, 7, 4),
        )

    def test_format(self):
        t = xso.Date()
        self.assertEqual(
            t.format(date(1776, 7, 4)),
            "1776-07-04",
        )

    def test_coerce_rejects_datetime(self):
        t = xso.Date()
        with self.assertRaisesRegex(
                TypeError,
                "must be a date object"):
            t.coerce(datetime.utcnow())

    def test_coerce_rejects_time(self):
        t = xso.Date()
        with self.assertRaisesRegex(
                TypeError,
                "must be a date object"):
            t.coerce(datetime.utcnow().time())

    def test_coerce_accepts_date(self):
        t = xso.Date()
        v = datetime.utcnow().date()
        self.assertEqual(t.coerce(v), v)


class TestTime(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Time(),
            xso.AbstractType)

    def test_parse_example(self):
        t = xso.Time()
        self.assertEqual(
            time(19, 40, 10, tzinfo=pytz.utc),
            t.parse("19:40:10Z"))

    def test_parse_timezoned(self):
        t = xso.Time()
        self.assertEqual(
            time(19, 40, 10, tzinfo=pytz.utc),
            t.parse("20:40:10+01:00"))

    def test_parse_local(self):
        t = xso.Time()
        self.assertEqual(
            time(20, 40, 10),
            t.parse("20:40:10"))

    def test_parse_milliseconds(self):
        t = xso.Time()
        self.assertEqual(
            time(20, 40, 10, 123456),
            t.parse("20:40:10.123456"))

    def test_parse_milliseconds_timezoned(self):
        t = xso.Time()
        self.assertEqual(
            time(19, 40, 10, 123456, tzinfo=pytz.utc),
            t.parse("20:40:10.123456+01:00"))

    def test_format_timezoned(self):
        t = xso.Time()
        self.assertEqual(
            "19:40:10Z",
            t.format(time(19, 40, 10, tzinfo=pytz.utc))
        )

    def test_format_timezoned_microseconds(self):
        t = xso.Time()
        self.assertEqual(
            "19:40:10.1234Z",
            t.format(time(19, 40, 10, 123400,
                          tzinfo=pytz.utc))
        )

    def test_format_naive(self):
        t = xso.Time()
        self.assertEqual(
            "19:40:10",
            t.format(time(19, 40, 10))
        )

    def test_format_naive_microseconds(self):
        t = xso.Time()
        self.assertEqual(
            "19:40:10.1234",
            t.format(time(19, 40, 10, 123400))
        )

    def test_coerce_rejects_non_utc_timezone(self):
        t = xso.Time()
        with self.assertRaisesRegex(
                ValueError,
                "time must have UTC timezone or none at all"):
            t.coerce(pytz.timezone("Europe/Berlin").localize(
                datetime(2014, 1, 26, 20, 40, 10)
            ).timetz())

    def test_coerce_accepts_naive_timezone(self):
        t = xso.Time()
        v = time(20, 40, 10)
        result = t.coerce(v)
        self.assertEqual(v, result)

    def test_coerce_accepts_utc_timezone(self):
        t = xso.Time()
        v = time(20, 40, 10, tzinfo=pytz.utc)
        result = t.coerce(v)
        self.assertEqual(v, result)

    def test_coerce_rejects_datetime(self):
        t = xso.Time()
        with self.assertRaisesRegex(
                TypeError,
                "must be a time object"):
            t.coerce(datetime.utcnow())

    def test_coerce_rejects_date(self):
        t = xso.Time()
        with self.assertRaisesRegex(
                TypeError,
                "must be a time object"):
            t.coerce(datetime.utcnow().date())


class TestBase64Binary(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.Base64Binary(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.Base64Binary()
        self.assertEqual(
            b"fnord",
            t.parse("Zm5vcmQ=")
        )

    def test_parse_empty(self):
        t = xso.Base64Binary()
        self.assertEqual(
            b"",
            t.parse("")
        )
        self.assertEqual(
            b"",
            t.parse("=")
        )

    def test_format(self):
        t = xso.Base64Binary()
        self.assertEqual(
            "Zm5vcmQ=",
            t.format(b"fnord")
        )

    def test_format_empty_default(self):
        t = xso.Base64Binary()
        self.assertEqual(
            "",
            t.format(b"")
        )

    def test_format_empty_with_empty_as_equal_flag(self):
        t = xso.Base64Binary(empty_as_equal=True)
        self.assertEqual(
            "=",
            t.format(b"")
        )

    def test_format_long(self):
        t = xso.Base64Binary()
        self.assertEqual(
            "Zm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZG"
            "Zub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRm"
            "bm9yZGZub3JkZm5vcmRmbm9yZA==",
            t.format(b"fnord"*20)
        )

    def test_coerce_rejects_int(self):
        t = xso.Base64Binary()
        with self.assertRaisesRegex(TypeError,
                                    "must be convertible to bytes"):
            t.coerce(12)

    def test_coerce_accepts_bytes_bytearray_array(self):
        t = xso.Base64Binary()

        import array
        array_value = array.array("h")
        array_value.append(1234)
        array_value.append(5678)
        array_value.append(910)

        values = [
            b"foobar",
            bytearray(b"baz"),
        ]

        for value in values:
            result = t.coerce(value)
            self.assertEqual(
                bytes(value),
                result
            )
            self.assertIsInstance(
                result,
                bytes
            )

    def test_coerce_passes_bytes(self):
        t = xso.Base64Binary()

        value = b"foo"

        self.assertIs(
            value,
            t.coerce(value)
        )


class TestHexBinary(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.HexBinary(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.HexBinary()
        self.assertEqual(
            b"fnord",
            t.parse("666e6f7264")
        )

    def test_format(self):
        t = xso.HexBinary()
        self.assertEqual(
            "666e6f7264",
            t.format(b"fnord")
        )

    def test_coerce_rejects_int(self):
        t = xso.HexBinary()
        with self.assertRaisesRegex(TypeError,
                                    "must be convertible to bytes"):
            t.coerce(12)

    def test_coerce_accepts_bytes_bytearray_array(self):
        t = xso.HexBinary()

        import array
        array_value = array.array("h")
        array_value.append(1234)
        array_value.append(5678)
        array_value.append(910)

        values = [
            b"foobar",
            bytearray(b"baz"),
        ]

        for value in values:
            result = t.coerce(value)
            self.assertEqual(
                bytes(value),
                result
            )
            self.assertIsInstance(
                result,
                bytes
            )

    def test_coerce_passes_bytes(self):
        t = xso.HexBinary()

        value = b"foo"

        self.assertIs(
            value,
            t.coerce(value)
        )


class TestJID(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.JID(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.JID()
        self.assertEqual(
            structs.JID("foo", "example.test", "bar"),
            t.parse("foo@example.test/bar")
        )

    def test_format(self):
        t = xso.JID()
        self.assertEqual(
            "ssa@ix.test/IX",
            t.format(structs.JID("ßA", "IX.test", "\u2168"))
        )

    def test_coerce_rejects_non_jids(self):
        t = xso.JID()
        types = [str, int, float, object]
        for type_ in types:
            with self.assertRaisesRegex(TypeError,
                                        "not a JID"):
                t.coerce(type_())

    def test_coerce_rejects_str_jids(self):
        t = xso.JID()
        with self.assertRaisesRegex(
                TypeError,
                "<class 'str'> object 'foo@bar' is not a JID"):
            t.coerce("foo@bar")

    def test_coerce_passes_jid(self):
        t = xso.JID()

        values = [
            structs.JID.fromstr("foo@bar.example"),
            structs.JID.fromstr("bar.example"),
            structs.JID.fromstr("foo@bar.example/baz"),
        ]

        for value in values:
            self.assertIs(
                value,
                t.coerce(value)
            )


class TestConnectionLocation(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.ConnectionLocation(),
            xso.AbstractType)

    def test_parse_ipv6(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            (ipaddress.IPv6Address("fe80::"), 5222),
            t.parse("[fe80::]:5222")
        )

    def test_reject_non_integer_port_number(self):
        t = xso.ConnectionLocation()
        with self.assertRaises(ValueError):
            t.parse("[fe80::]:23.4")

    def test_reject_out_of_range_port_number(self):
        t = xso.ConnectionLocation()
        with self.assertRaises(ValueError):
            t.parse("[fe80::]:1000000")

    def test_reject_missing_colon(self):
        t = xso.ConnectionLocation()
        with self.assertRaises(ValueError):
            t.parse("foo.bar")

    def test_parse_ipv4(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            (ipaddress.IPv4Address("10.0.0.1"), 5223),
            t.parse("10.0.0.1:5223")
        )

    def test_parse_hostname(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            ("foo.bar.example", 5234),
            t.parse("foo.bar.example:5234")
        )

    def test_format_ipv6(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            "[fe80::]:5222",
            t.format((ipaddress.IPv6Address("fe80::"), 5222))
        )

    def test_format_ipv4(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            "10.0.0.1:1234",
            t.format((ipaddress.IPv4Address("10.0.0.1"), 1234))
        )

    def test_format_hostname(self):
        t = xso.ConnectionLocation()
        self.assertEqual(
            "foo.bar.baz:5234",
            t.format(("foo.bar.baz", 5234))
        )

    def test_coerce_rejects_non_2tuples(self):
        t = xso.ConnectionLocation()

        values = [
            ["foo", 1234],
            {"foo", 1234},
            ("foo", 1234, "bar")
        ]

        for value in values:
            with self.assertRaisesRegex(TypeError,
                                        "2-tuple required"):
                t.coerce(value)

    def test_coerce_parses_ip_addresses(self):
        t = xso.ConnectionLocation()

        value_pairs = [
            (("10.0.0.1", 1234), (ipaddress.IPv4Address("10.0.0.1"), 1234)),
            (("fe80::", 1234), (ipaddress.IPv6Address("fe80::"), 1234)),
            (("10.0.foobar", 1234), ("10.0.foobar", 1234)),
        ]

        for given, expected in value_pairs:
            self.assertEqual(
                expected,
                t.coerce(given)
            )

    def test_coerce_restricts_port_numbers(self):
        t = xso.ConnectionLocation()

        err_values = [
            ("foobar", -1),
            ("foobar", 65536),
        ]

        for err_value in err_values:
            with self.assertRaisesRegex(ValueError, "out of range"):
                t.coerce(err_value)

        ok_values = [
            ("foobar", 0),
            ("foobar", 65535),
        ]

        for ok_value in ok_values:
            self.assertEqual(
                ok_value,
                t.coerce(ok_value)
            )

    def test_coerce_requires_integral_number(self):
        t = xso.ConnectionLocation()

        values = [
            ("foobar", 1.2),
            ("foobar", "1"),
            ("foobar", decimal.Decimal("1")),
            ("foobar", fractions.Fraction(1, 1)),
        ]

        for value in values:
            with self.assertRaisesRegex(
                    TypeError,
                    "port number must be integral number"):
                t.coerce(value)


class TestLanguageTag(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertIsInstance(
            xso.LanguageTag(),
            xso.AbstractType)

    def test_parse(self):
        t = xso.LanguageTag()
        self.assertEqual(
            structs.LanguageTag.fromstr("de-Latn-DE-1999"),
            t.parse("de-Latn-DE-1999")
        )

    def test_format(self):
        t = xso.LanguageTag()
        self.assertEqual(
            "de-Latn-DE-1999",
            t.format(structs.LanguageTag.fromstr("de-Latn-DE-1999"))
        )

    def test_coerce_passes_language_tags(self):
        t = xso.LanguageTag()
        tag = structs.LanguageTag.fromstr("foo")
        self.assertIs(
            tag,
            t.coerce(tag)
        )

    def test_coerce_rejects_non_language_tags(self):
        t = xso.LanguageTag()

        values = [
            1.2,
            decimal.Decimal("1"),
            fractions.Fraction(1, 1),
            [],
            (),
            1.,
            "foo",
        ]

        for value in values:
            with self.assertRaisesRegex(
                    TypeError,
                    "is not a LanguageTag"):
                t.coerce(value)


class TestTextChildMap(unittest.TestCase):
    def test_is_abstract_type(self):
        self.assertTrue(issubclass(
            xso.TextChildMap,
            xso.AbstractType
        ))

    def setUp(self):
        self.type_ = xso.TextChildMap(xso.AbstractTextChild)

    def test_get_formatted_type(self):
        self.assertIs(self.type_.get_formatted_type(),
                      xso.AbstractTextChild)

    def test_parse(self):
        text, lang = "foo", structs.LanguageTag.fromstr("en-gb")
        item = xso.AbstractTextChild(text, lang)
        self.assertEqual(
            (lang, text),
            self.type_.parse(item)
        )

    def test_format(self):
        text, lang = "foo", structs.LanguageTag.fromstr("en-gb")
        item = self.type_.format((lang, text))

        self.assertEqual(item.text, text)
        self.assertEqual(item.lang, lang)

    def tearDown(self):
        del self.type_



class TestAbstractValidator(unittest.TestCase):
    def test_is_abstract(self):
        self.assertIsInstance(
            xso.AbstractValidator,
            abc.ABCMeta)
        with self.assertRaises(TypeError):
            xso.AbstractValidator()

    def test_validate_calls_validate_detailed(self):
        class FakeSubclass(xso.AbstractValidator):
            def validate_detailed(self, value):
                pass

        instance = FakeSubclass()
        obj = object()
        with unittest.mock.patch.object(instance, "validate_detailed") \
                 as validate_detailed:
            instance.validate(obj)

        self.assertSequenceEqual(
            [
                unittest.mock.call(obj),
                unittest.mock.call().__bool__(),
            ],
            validate_detailed.mock_calls
        )

    def test_validate_calls_validate_detailed_and_inverts_result(self):
        class FakeSubclass(xso.AbstractValidator):
            def validate_detailed(self, value):
                return []

        instance = FakeSubclass()
        obj = object()
        self.assertTrue(instance.validate(obj))


class TestRestrictToSet(unittest.TestCase):
    def test_is_abstract_validator(self):
        self.assertIsInstance(
            xso.RestrictToSet([]),
            xso.AbstractValidator)

    def test_validate(self):
        t = xso.RestrictToSet({"foo", "bar"})
        self.assertTrue(t.validate("foo"))
        self.assertTrue(t.validate("bar"))
        self.assertFalse(t.validate("baz"))


class TestNmtoken(unittest.TestCase):
    def test_is_abstract_validator(self):
        self.assertIsInstance(
            xso.RestrictToSet([]),
            xso.AbstractValidator)

    def _test_samples(self, t, samples, group):
        for sample in samples:
            self.assertTrue(
                t.validate(sample),
                "\\u{:04x} is supposed to be in {}".format(ord(sample), group)
            )

    def test_validate(self):
        t = xso.Nmtoken()
        # ok, testing this sucks hard. we’ll do some hand-waiving tests
        # guarding against the most important characters which must not occur.

        self.assertTrue(t.validate("foobar"))
        self.assertTrue(t.validate("foo:bar"))
        self.assertTrue(t.validate("foo-bar"))
        self.assertTrue(t.validate("foo.bar"))
        self.assertTrue(t.validate("foo_bar"))
        self.assertTrue(t.validate("."))
        self.assertTrue(t.validate(":"))
        self.assertTrue(t.validate("_"))
        self.assertTrue(t.validate("."))

        self.assertFalse(t.validate("\uf901"))
        self.assertFalse(t.validate("\ufffd"))
        self.assertFalse(t.validate("\u20dd"))
        self.assertFalse(t.validate(">"))
        self.assertFalse(t.validate("<"))
        self.assertFalse(t.validate("&"))

    def test_validate_base_char(self):
        self._test_samples(
            xso.Nmtoken(),
            "\u0041"
            "\u0061"
            "\u00c0"
            "\u00d8"
            "\u00F8"
            "\u0100"
            "\u0134"
            "\u0141"
            "\u014A"
            "\u0180"
            "\u01CD"
            "\u01F4"
            "\u01FA"
            "\u0250"
            "\u02BB"
            "\u0386"
            "\u0388"
            "\u038C"
            "\u038E"
            "\u03A3"
            "\u03D0"
            "\u03DA"
            "\u03DC"
            "\u03DE"
            "\u03E0"
            "\u03E2"
            "\u0401"
            "\u040E"
            "\u0451"
            "\u045E"
            "\u0490"
            "\u04C7"
            "\u04CB"
            "\u04D0"
            "\u04EE"
            "\u04F8"
            "\u0531"
            "\u0559"
            "\u0561"
            "\u05D0"
            "\u05F0"
            "\u0621"
            "\u0641"
            "\u0671"
            "\u06BA"
            "\u06C0"
            "\u06D0"
            "\u06D5"
            "\u06E5"
            "\u0905"
            "\u093D"
            "\u0958"
            "\u0985"
            "\u098F"
            "\u0993"
            "\u09AA"
            "\u09B2"
            "\u09B6"
            "\u09DC"
            "\u09DF"
            "\u09F0"
            "\u0A05"
            "\u0A0F"
            "\u0A13"
            "\u0A2A"
            "\u0A32"
            "\u0A35"
            "\u0A38"
            "\u0A59"
            "\u0A5E"
            "\u0A72"
            "\u0A85"
            "\u0A8D"
            "\u0A8F"
            "\u0A93"
            "\u0AAA"
            "\u0AB2"
            "\u0AB5"
            "\u0ABD"
            "\u0AE0"
            "\u0B05"
            "\u0B0F"
            "\u0B13"
            "\u0B2A"
            "\u0B32"
            "\u0B36"
            "\u0B3D"
            "\u0B5C"
            "\u0B5F"
            "\u0B85"
            "\u0B8E"
            "\u0B92"
            "\u0B99"
            "\u0B9C"
            "\u0B9E"
            "\u0BA3"
            "\u0BA8"
            "\u0BAE"
            "\u0BB7"
            "\u0C05"
            "\u0C0E"
            "\u0C12"
            "\u0C2A"
            "\u0C35"
            "\u0C60"
            "\u0C85"
            "\u0C8E"
            "\u0C92"
            "\u0CAA"
            "\u0CB5"
            "\u0CDE"
            "\u0CE0"
            "\u0D05"
            "\u0D0E"
            "\u0D12"
            "\u0D2A"
            "\u0D60"
            "\u0E01"
            "\u0E30"
            "\u0E32"
            "\u0E40"
            "\u0E81"
            "\u0E84"
            "\u0E87"
            "\u0E8A"
            "\u0E8D"
            "\u0E94"
            "\u0E99"
            "\u0EA1"
            "\u0EA5"
            "\u0EA7"
            "\u0EAA"
            "\u0EAD"
            "\u0EB0"
            "\u0EB2"
            "\u0EBD"
            "\u0EC0"
            "\u0F40"
            "\u0F49"
            "\u10A0"
            "\u10D0"
            "\u1100"
            "\u1102"
            "\u1105"
            "\u1109"
            "\u110B"
            "\u110E"
            "\u113C"
            "\u113E"
            "\u1140"
            "\u114C"
            "\u114E"
            "\u1150"
            "\u1154"
            "\u1159"
            "\u115F"
            "\u1163"
            "\u1165"
            "\u1167"
            "\u1169"
            "\u116D"
            "\u1172"
            "\u1175"
            "\u119E"
            "\u11A8"
            "\u11AB"
            "\u11AE"
            "\u11B7"
            "\u11BA"
            "\u11BC"
            "\u11EB"
            "\u11F0"
            "\u11F9"
            "\u1E00"
            "\u1EA0"
            "\u1F00"
            "\u1F18"
            "\u1F20"
            "\u1F48"
            "\u1F50"
            "\u1F59"
            "\u1F5B"
            "\u1F5D"
            "\u1F5F"
            "\u1F80"
            "\u1FB6"
            "\u1FBE"
            "\u1FC2"
            "\u1FC6"
            "\u1FD0"
            "\u1FD6"
            "\u1FE0"
            "\u1FF2"
            "\u1FF6"
            "\u2126"
            "\u212A"
            "\u212E"  # deliberately excluded
            "\u2180"
            "\u3041"
            "\u30A1"
            "\u3105"
            "\uAC00",
            "BaseChar"
        )

    def test_validate_ideographic(self):
        self._test_samples(
            xso.Nmtoken(),
            "\u4E00"
            "\u3007"
            "\u3021",
            "Ideographic"
        )

    def test_validate_combining(self):
        self._test_samples(
            xso.Nmtoken(),
            "\u0300"
            "\u0360"
            "\u0483"
            "\u0591"
            "\u05A3"
            "\u05BB"
            "\u05BF"
            "\u05C1"
            "\u05C4"
            "\u064B"
            "\u0670"
            "\u06D6"
            "\u06DD"
            "\u06E0"
            "\u06E7"
            "\u06EA"
            "\u0901"
            "\u093C"
            "\u093E"
            "\u094D"
            "\u0951"
            "\u0962"
            "\u0981"
            "\u09BC"
            "\u09BE"
            "\u09BF"
            "\u09C0"
            "\u09C7"
            "\u09CB"
            "\u09D7"
            "\u09E2"
            "\u0A02"
            "\u0A3C"
            "\u0A3E"
            "\u0A3F"
            "\u0A40"
            "\u0A47"
            "\u0A4B"
            "\u0A70"
            "\u0A81"
            "\u0ABC"
            "\u0ABE"
            "\u0AC7"
            "\u0ACB"
            "\u0B01"
            "\u0B3C"
            "\u0B3E"
            "\u0B47"
            "\u0B4B"
            "\u0B56"
            "\u0B82"
            "\u0BBE"
            "\u0BC6"
            "\u0BCA"
            "\u0BD7"
            "\u0C01"
            "\u0C3E"
            "\u0C46"
            "\u0C4A"
            "\u0C55"
            "\u0C82"
            "\u0CBE"
            "\u0CC6"
            "\u0CCA"
            "\u0CD5"
            "\u0D02"
            "\u0D3E"
            "\u0D46"
            "\u0D4A"
            "\u0D57"
            "\u0E31"
            "\u0E34"
            "\u0E47"
            "\u0EB1"
            "\u0EB4"
            "\u0EBB"
            "\u0EC8"
            "\u0F18"
            "\u0F35"
            "\u0F37"
            "\u0F39"
            "\u0F3E"
            "\u0F3F"
            "\u0F71"
            "\u0F86"
            "\u0F90"
            "\u0F97"
            "\u0F99"
            "\u0FB1"
            "\u0FB9"
            "\u20D0"
            "\u20E1"
            "\u302A"
            "\u3099"
            "\u309A",
            "CombiningChar"
        )

    def test_validate_digit(self):
        self._test_samples(
            xso.Nmtoken(),
            "\u0030"
            "\u0660"
            "\u06F0"
            "\u0966"
            "\u09E6"
            "\u0A66"
            "\u0AE6"
            "\u0B66"
            "\u0BE7"
            "\u0C66"
            "\u0CE6"
            "\u0D66"
            "\u0E50"
            "\u0ED0"
            "\u0F20",
            "Digit"
        )

    def test_validate_extender(self):
        self._test_samples(
            xso.Nmtoken(),
            "\u00B7"
            "\u02D0"
            "\u02D1"
            "\u0387"
            "\u0640"
            "\u0E46"
            "\u0EC6"
            "\u3005"
            "\u3031"
            "\u309D"
            "\u30FC",
            "Extender"
        )


class TestIsInstance(unittest.TestCase):
    def test_is_abstract_validator(self):
        self.assertTrue(issubclass(
            xso.IsInstance,
            xso.AbstractValidator
        ))

    def test_validate(self):
        v = xso.IsInstance((str, bytes))
        self.assertTrue(
            v.validate("abc")
        )
        self.assertTrue(
            v.validate(b"abc")
        )
        self.assertFalse(
            v.validate(1)
        )

    def test_list_of_classes_is_shared(self):
        classes = []
        v = xso.IsInstance(classes)

        self.assertFalse(
            v.validate("str")
        )

        classes.append(str)

        self.assertTrue(
            v.validate("str")
        )
