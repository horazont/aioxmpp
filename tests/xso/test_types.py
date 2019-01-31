########################################################################
# File name: test_types.py
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
import abc
import contextlib
import decimal
import fractions
import inspect
import ipaddress
import itertools
import unittest
import unittest.mock
import warnings

from enum import Enum, IntEnum

import pytz

from datetime import datetime, date, time

import aioxmpp.xso as xso
import aioxmpp.structs as structs


class Unknown(unittest.TestCase):
    def test_init(self):
        u = xso.Unknown(unittest.mock.sentinel.value)
        self.assertEqual(
            u.value,
            unittest.mock.sentinel.value,
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            xso.Unknown()

    def test_value_not_settable(self):
        u = xso.Unknown(unittest.mock.sentinel.value)
        with self.assertRaises(AttributeError):
            u.value = "foobar"

    def test_hash_equal_to_value_hash(self):
        values = [
            None,
            "foobar",
            object(),
            10,
            10.2,
        ]

        for value in values:
            u = xso.Unknown(value)
            self.assertEqual(hash(u), hash(value))

    def test_equality(self):
        values = [
            None,
            "foobar",
            object(),
            10,
            10.2,
        ]

        for v1, v2 in itertools.product(values, values):
            if v1 == v2:
                self.assertTrue(xso.Unknown(v1) == xso.Unknown(v2))
                self.assertFalse(xso.Unknown(v1) != xso.Unknown(v2))
            else:
                self.assertFalse(xso.Unknown(v1) == xso.Unknown(v2))
                self.assertTrue(xso.Unknown(v1) != xso.Unknown(v2))
                self.assertFalse(v1 == xso.Unknown(v2))
                self.assertFalse(xso.Unknown(v2) == v1)
                self.assertTrue(v1 != xso.Unknown(v2))
                self.assertTrue(xso.Unknown(v2) != v1)

    def test_repr(self):
        values = [
            None,
            "foobar",
            object(),
            10,
            10.2,
        ]

        for v in values:
            self.assertEqual(
                repr(xso.Unknown(v)),
                "<Unknown: {!r}>".format(v),
            )


class TestAbstractCDataType(unittest.TestCase):
    class DummyType(xso.AbstractCDataType):
        def parse(self, v):
            pass

    def test_is_abstract(self):
        self.assertIsInstance(
            xso.AbstractCDataType,
            abc.ABCMeta)
        with self.assertRaises(TypeError):
            xso.AbstractCDataType()

    def test_parse_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractCDataType.parse))

    def test_format_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractCDataType.format))
        self.assertEqual(
            "foo",
            self.DummyType().format("foo"))
        self.assertEqual(
            "23",
            self.DummyType().format(23))


class TestAbstractElementType(unittest.TestCase):
    class DummyType(xso.AbstractElementType):
        def unpack(self, obj):
            pass

        def pack(self, v):
            pass

        def get_xso_types(self):
            pass

    def test_is_abstract(self):
        self.assertIsInstance(
            xso.AbstractElementType,
            abc.ABCMeta)
        with self.assertRaises(TypeError):
            xso.AbstractElementType()

    def test_unpack_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractElementType.unpack))

    def test_coerce_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractElementType.coerce))
        self.assertEqual(
            self.DummyType().coerce(unittest.mock.sentinel.value),
            unittest.mock.sentinel.value
        )

    def test_get_xso_types(self):
        self.assertTrue(inspect.isfunction(
            xso.AbstractElementType.get_xso_types
        ))

    def test_pack_method(self):
        self.assertTrue(inspect.isfunction(xso.AbstractElementType.pack))


class TestStringType(unittest.TestCase):
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.String(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Integer(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Float(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Bool(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.DateTime(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Date(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Time(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.Base64Binary(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.HexBinary(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.JID(),
            xso.AbstractCDataType)

    def test_parse(self):
        t = xso.JID()
        self.assertEqual(
            structs.JID("foo", "example.test", "bar"),
            t.parse("foo@example.test/bar")
        )

    def test_parse_uses_nonstrict_by_default(self):
        with unittest.mock.patch("aioxmpp.structs.JID") as JID:
            t = xso.JID()
            result = t.parse(unittest.mock.sentinel.jidstr)

        JID.fromstr.assert_called_with(
            unittest.mock.sentinel.jidstr,
            strict=False
        )

        self.assertEqual(result, JID.fromstr())

    def test_parse_can_be_set_to_strict(self):
        with unittest.mock.patch("aioxmpp.structs.JID") as JID:
            t = xso.JID(strict=True)
            result = t.parse(unittest.mock.sentinel.jidstr)

        JID.fromstr.assert_called_with(
            unittest.mock.sentinel.jidstr,
            strict=True
        )

        self.assertEqual(result, JID.fromstr())

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.ConnectionLocation(),
            xso.AbstractCDataType)

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
    def test_is_cdata_type(self):
        self.assertIsInstance(
            xso.LanguageTag(),
            xso.AbstractCDataType)

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


class TestJSON(unittest.TestCase):
    def test_is_cdata_type(self):
        self.assertTrue(issubclass(
            xso.JSON,
            xso.AbstractCDataType,
        ))

    def test_parse_loads_as_json_via_instance(self):
        j = xso.JSON()

        with contextlib.ExitStack() as stack:
            loads = stack.enter_context(unittest.mock.patch(
                "json.loads",
                return_value=unittest.mock.sentinel.parsed,
            ))

            result = j.parse(
                unittest.mock.sentinel.cdata,
            )

        loads.assert_called_once_with(unittest.mock.sentinel.cdata)

        self.assertEqual(result, unittest.mock.sentinel.parsed)

    def test_format_dumps_as_json_via_instance(self):
        j = xso.JSON()

        with contextlib.ExitStack() as stack:
            dumps = stack.enter_context(unittest.mock.patch(
                "json.dumps",
                return_value=unittest.mock.sentinel.serialised,
            ))

            result = j.format(
                unittest.mock.sentinel.data,
            )

        dumps.assert_called_once_with(unittest.mock.sentinel.data)

        self.assertEqual(result, unittest.mock.sentinel.serialised)

    def test_coerce_passes_everything_via_instance(self):
        value = object()

        self.assertIs(
            xso.JSON().coerce(value),
            value,
        )


class TestTextChildMap(unittest.TestCase):
    def test_is_element_type(self):
        self.assertTrue(issubclass(
            xso.TextChildMap,
            xso.AbstractElementType
        ))

    def setUp(self):
        self.type_ = xso.TextChildMap(xso.AbstractTextChild)

    def tearDown(self):
        del self.type_

    def test_get_xso_types(self):
        self.assertCountEqual(
            self.type_.get_xso_types(),
            [xso.AbstractTextChild]
        )

    def test_unpack(self):
        text, lang = "foo", structs.LanguageTag.fromstr("en-gb")
        item = xso.AbstractTextChild(text, lang)
        self.assertEqual(
            (lang, text),
            self.type_.unpack(item)
        )

    def test_pack(self):
        text, lang = "foo", structs.LanguageTag.fromstr("en-gb")
        item = self.type_.pack((lang, text))

        self.assertEqual(item.text, text)
        self.assertEqual(item.lang, lang)


class TestEnumCDataType(unittest.TestCase):
    class SomeEnum(Enum):
        X = 1
        Y = 2
        Z = 3

    class SomeIntEnum(IntEnum):
        X = 1
        Y = 2
        Z = 3

    def test_is_cdata_type(self):
        self.assertTrue(issubclass(
            xso.EnumCDataType,
            xso.AbstractCDataType,
        ))

    def test_init_default(self):
        with self.assertRaises(TypeError):
            xso.EnumCDataType()

    def test_init_with_enum(self):
        e = xso.EnumCDataType(self.SomeEnum)
        self.assertIs(
            e.enum_class,
            self.SomeEnum
        )
        self.assertIsInstance(
            e.nested_type,
            xso.String,
        )

    def test_init_with_custom_nested_type(self):
        e = xso.EnumCDataType(
            self.SomeEnum,
            nested_type=unittest.mock.sentinel.nested_type
        )
        self.assertIs(
            e.enum_class,
            self.SomeEnum
        )
        self.assertIs(
            e.nested_type,
            unittest.mock.sentinel.nested_type,
        )

    def test_parse_uses_enum_and_nested_type(self):
        enum_class = unittest.mock.Mock()
        nested_type = unittest.mock.Mock()
        e = xso.EnumCDataType(enum_class, nested_type)

        result = e.parse(unittest.mock.sentinel.value)

        nested_type.parse.assert_called_with(
            unittest.mock.sentinel.value,
        )

        enum_class.assert_called_with(
            nested_type.parse(),
        )

        self.assertEqual(
            result,
            enum_class(),
        )

    def test_parse_works_with_actual_enum(self):
        e = xso.EnumCDataType(self.SomeEnum, xso.Integer())
        for enum_value in self.SomeEnum:
            self.assertEqual(
                e.parse(str(enum_value.value)),
                enum_value,
            )

    def test_format_uses_enum_value_and_nested_type(self):
        enum_class = unittest.mock.Mock()
        enum_value = unittest.mock.Mock()
        nested_type = unittest.mock.Mock()
        e = xso.EnumCDataType(enum_class, nested_type)

        result = e.format(enum_value)

        nested_type.format.assert_called_with(
            enum_value.value,
        )

        self.assertEqual(
            result,
            nested_type.format(),
        )

    def test_format_works_with_actual_enums(self):
        e = xso.EnumCDataType(self.SomeEnum, xso.Integer())
        for enum_value in self.SomeEnum:
            self.assertEqual(
                e.format(enum_value),
                str(enum_value.value),
            )

    def test_get_formatted_type_not_implemented(self):
        self.assertFalse(
            hasattr(xso.EnumCDataType, "get_formatted_type")
        )

    def test_get_xso_types_not_implemented(self):
        self.assertFalse(
            hasattr(xso.EnumCDataType, "get_xso_types")
        )

    def test_pass_Enum_values_through_coerce(self):
        e = xso.EnumCDataType(self.SomeEnum)
        for enum_value in self.SomeEnum:
            self.assertIs(enum_value, e.coerce(enum_value))

    def test_reject_non_Enum_values_on_coerce(self):
        wrong = [
            1,
            "10",
            10.2,
            object()
        ]

        e = xso.EnumCDataType(self.SomeEnum)

        for thing in wrong:
            with self.assertRaises(TypeError):
                e.coerce(thing)

    def test_try_to_coerce_if_allow_coerce_is_set(self):
        enum_class = unittest.mock.Mock()
        enum_class.return_value = unittest.mock.sentinel.wrapped
        nested_t = xso.Integer()
        t = xso.EnumCDataType(
            enum_class,
            nested_t,
            allow_coerce=True,
        )

        with contextlib.ExitStack() as stack:
            w = stack.enter_context(warnings.catch_warnings())
            coerce = stack.enter_context(
                unittest.mock.patch.object(nested_t, "coerce")
            )

            coerce.return_value = unittest.mock.sentinel.coerced
            result = t.coerce(unittest.mock.sentinel.value)

        enum_class.assert_called_with(
            unittest.mock.sentinel.coerced,
        )

        self.assertEqual(
            result,
            unittest.mock.sentinel.wrapped,
        )

        self.assertFalse(w)

    def test_value_error_propagates(self):
        exc = ValueError()

        enum_class = unittest.mock.Mock()
        enum_class.side_effect = exc
        e = xso.EnumCDataType(enum_class, xso.Integer(), allow_coerce=True)

        with self.assertRaises(ValueError) as ctx:
            e.coerce(1234)

        self.assertIs(ctx.exception, exc)

    def test_deprecate_coerce(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
            allow_coerce=True,
            deprecate_coerce=True,
        )

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(1)

        warn.assert_called_with(
            "assignment of non-enum values to this descriptor is deprecated",
            DeprecationWarning,
            stacklevel=4
        )

        self.assertEqual(
            result,
            enum_class(1),
        )

    def test_deprecate_coerce_custom_stacklevel(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
            allow_coerce=True,
            deprecate_coerce=unittest.mock.sentinel.stacklevel,
        )

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(1)

        warn.assert_called_with(
            "assignment of non-enum values to this descriptor is deprecated",
            DeprecationWarning,
            stacklevel=unittest.mock.sentinel.stacklevel
        )

        self.assertEqual(
            result,
            enum_class(1),
        )

    def test_deprecate_coerce_does_not_emit_warning_for_enum_value(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
            allow_coerce=True,
            deprecate_coerce=True,
        )

        value = enum_class.X

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(value)

        self.assertFalse(warn.mock_calls)

        self.assertIs(
            value,
            result,
        )

    def test_accept_unknown_by_default(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
        )

        value = e.coerce(xso.Unknown(10))
        self.assertIsInstance(value, xso.Unknown)
        self.assertEqual(xso.Unknown(10), value)

    def test_accept_unknown_can_be_turned_off(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
            accept_unknown=False,
        )

        with self.assertRaisesRegex(
                TypeError,
                r"not a valid .* value: <Unknown: 10>"):
            e.coerce(xso.Unknown(10))

    def test_allow_unknown_by_default(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
        )

        value = e.parse("10")
        self.assertIsInstance(value, xso.Unknown)
        self.assertEqual(xso.Unknown(10), value)

    def test_allow_unknown_can_be_turned_off(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
            allow_unknown=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                r"10 is not a valid SomeEnum"):
            e.parse(10)

    def test_format_works_with_unknown(self):
        enum_class = self.SomeEnum
        e = xso.EnumCDataType(
            enum_class,
            xso.Integer(),
        )

        self.assertEqual(
            e.format(xso.Unknown(10)),
            "10",
        )

    def test_reject_pass_unknown_without_allow_unknown(self):
        enum_class = self.SomeEnum

        with self.assertRaisesRegex(
                ValueError,
                r"pass_unknown requires allow_unknown and accept_unknown"):
            xso.EnumCDataType(
                enum_class,
                xso.Integer(),
                allow_unknown=False,
                pass_unknown=True,
            )

    def test_reject_pass_unknown_without_accept_unknown(self):
        enum_class = self.SomeEnum

        with self.assertRaisesRegex(
                ValueError,
                r"pass_unknown requires allow_unknown and accept_unknown"):
            xso.EnumCDataType(
                enum_class,
                xso.Integer(),
                allow_unknown=False,
                pass_unknown=True,
            )

    def test_coerce_passes_non_members_with_pass_unknown(self):
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            xso.Integer(),
            pass_unknown=True,
        )

        v = t.coerce(10)
        self.assertFalse(isinstance(v, IntEnum))

    def test_coerce_passes_value_to_nested_type_coerce_with_pass_unknown(self):
        nested_t = xso.Integer()
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            nested_t,
            pass_unknown=True,
        )

        with unittest.mock.patch.object(nested_t, "coerce") as coerce:
            coerce.return_value = unittest.mock.sentinel.coerced

            v = t.coerce(unittest.mock.sentinel.value)

        self.assertEqual(v, unittest.mock.sentinel.coerced)

    def test_coerce_converts_to_enum_members_if_allow_coerce_is_set(self):
        nested_t = xso.Integer()
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            nested_t,
            allow_coerce=True,
            pass_unknown=True,
        )

        with unittest.mock.patch.object(nested_t, "coerce") as coerce:
            coerce.return_value = 2

            v = t.coerce(unittest.mock.sentinel.value)

        self.assertEqual(v, 2)
        self.assertIsInstance(v, self.SomeIntEnum)

    def test_coerce_does_not_convert_to_enum_members_if_allow_coerce_unset(self):  # NOQA
        nested_t = xso.Integer()
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            nested_t,
            allow_coerce=False,
            pass_unknown=True,
        )

        with unittest.mock.patch.object(nested_t, "coerce") as coerce:
            coerce.return_value = 2

            v = t.coerce(unittest.mock.sentinel.value)

        self.assertEqual(v, 2)
        self.assertFalse(isinstance(v, self.SomeIntEnum))

    def test_coerce_passes_non_members_with_pass_unknown_and_allow_coerce(self):
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            xso.Integer(),
            allow_coerce=True,
            pass_unknown=True,
        )

        v = t.coerce(10)
        self.assertFalse(isinstance(v, IntEnum))

    def test_parse_passes_unwrapped_value_if_pass_unknown(self):
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            xso.Integer(),
            pass_unknown=True,
        )

        v = t.parse("10")
        self.assertEqual(v, 10)
        self.assertFalse(isinstance(v, xso.Unknown))

    def test_format_works_with_unwrapped_unknowns_if_pass_unknown(self):
        t = xso.EnumCDataType(
            self.SomeIntEnum,
            xso.Integer(),
            pass_unknown=True,
        )

        v = t.format(10)
        self.assertEqual(v, "10")


class TestEnumElementType(unittest.TestCase):
    class SomeEnum(Enum):
        X = 1
        Y = 2
        Z = 3

    class FancyType(xso.AbstractElementType):
        def get_xso_types(self):
            raise NotImplementedError

        def pack(self, obj):
            return obj

        def unpack(self, obj):
            return obj

    def test_is_element_type(self):
        self.assertTrue(issubclass(
            xso.EnumElementType,
            xso.AbstractElementType,
        ))

    def test_init_default(self):
        with self.assertRaises(TypeError):
            xso.EnumElementType()

    def test_init_with_enum(self):
        with self.assertRaises(TypeError):
            xso.EnumElementType(self.SomeEnum)

    def test_init_with_custom_nested_type(self):
        e = xso.EnumElementType(
            self.SomeEnum,
            nested_type=unittest.mock.sentinel.nested_type
        )
        self.assertIs(
            e.enum_class,
            self.SomeEnum
        )
        self.assertIs(
            e.nested_type,
            unittest.mock.sentinel.nested_type,
        )

    def test_unpack_uses_enum_and_nested_type(self):
        enum_class = unittest.mock.Mock()
        nested_type = unittest.mock.Mock()
        e = xso.EnumElementType(enum_class, nested_type)

        result = e.unpack(unittest.mock.sentinel.value)

        nested_type.unpack.assert_called_with(
            unittest.mock.sentinel.value,
        )

        enum_class.assert_called_with(
            nested_type.unpack(),
        )

        self.assertEqual(
            result,
            enum_class(),
        )

    def test_unpack_works_with_actual_enum(self):
        e = xso.EnumElementType(self.SomeEnum, self.FancyType())
        for enum_value in self.SomeEnum:
            self.assertEqual(
                e.unpack(enum_value.value),
                enum_value,
            )

    def test_pack_uses_enum_value_and_nested_type(self):
        enum_class = unittest.mock.Mock()
        enum_value = unittest.mock.Mock()
        nested_type = unittest.mock.Mock()
        e = xso.EnumElementType(enum_class, nested_type)

        result = e.pack(enum_value)

        nested_type.pack.assert_called_with(
            enum_value.value,
        )

        self.assertEqual(
            result,
            nested_type.pack(),
        )

    def test_pack_works_with_actual_enums(self):
        e = xso.EnumElementType(self.SomeEnum, self.FancyType())
        for enum_value in self.SomeEnum:
            self.assertEqual(
                e.pack(enum_value),
                enum_value.value,
            )

    def test_get_xso_types_delegates_to_nested_type(self):
        nested_type = unittest.mock.Mock()
        e = xso.EnumElementType(
            unittest.mock.sentinel.enum_class,
            nested_type,
        )

        result = e.get_xso_types()
        nested_type.get_xso_types.assert_called_with()
        self.assertEqual(
            result,
            nested_type.get_xso_types(),
        )

    def test_pass_Enum_values_through_coerce(self):
        e = xso.EnumElementType(self.SomeEnum, self.FancyType())
        for enum_value in self.SomeEnum:
            self.assertIs(enum_value, e.coerce(enum_value))

    def test_reject_non_Enum_values_on_coerce(self):
        wrong = [
            1,
            "10",
            10.2,
            object()
        ]

        e = xso.EnumElementType(self.SomeEnum, self.FancyType())

        for thing in wrong:
            with self.assertRaises(TypeError):
                e.coerce(thing)

    def test_try_to_coerce_if_allow_coerce_is_set(self):
        enum_class = unittest.mock.Mock()
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
            allow_coerce=True,
        )

        with warnings.catch_warnings() as w:
            result = e.coerce(unittest.mock.sentinel.value)

        enum_class.assert_called_with(
            unittest.mock.sentinel.value,
        )

        self.assertEqual(
            result,
            enum_class(),
        )

        self.assertFalse(w)

    def test_value_error_propagates(self):
        exc = ValueError()

        enum_class = unittest.mock.Mock()
        enum_class.side_effect = exc
        e = xso.EnumElementType(enum_class, self.FancyType(),
                                allow_coerce=True)

        with self.assertRaises(ValueError) as ctx:
            e.coerce(unittest.mock.sentinel.value)

        self.assertIs(ctx.exception, exc)

    def test_deprecate_coerce(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
            allow_coerce=True,
            deprecate_coerce=True,
        )

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(1)

        warn.assert_called_with(
            "assignment of non-enum values to this descriptor is deprecated",
            DeprecationWarning,
            stacklevel=4
        )

        self.assertEqual(
            result,
            enum_class(1),
        )

    def test_deprecate_coerce_custom_stacklevel(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
            allow_coerce=True,
            deprecate_coerce=unittest.mock.sentinel.stacklevel,
        )

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(1)

        warn.assert_called_with(
            "assignment of non-enum values to this descriptor is deprecated",
            DeprecationWarning,
            stacklevel=unittest.mock.sentinel.stacklevel
        )

        self.assertEqual(
            result,
            enum_class(1),
        )

    def test_deprecate_coerce_does_not_emit_warning_for_enum_value(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
            allow_coerce=True,
            deprecate_coerce=True,
        )

        value = enum_class.X

        with contextlib.ExitStack() as stack:
            warn = stack.enter_context(
                unittest.mock.patch(
                    "warnings.warn",
                )
            )

            result = e.coerce(value)

        self.assertFalse(warn.mock_calls)

        self.assertIs(
            value,
            result,
        )

    def test_accept_unknown_by_default(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            xso.Integer(),
        )

        value = e.coerce(xso.Unknown(10))
        self.assertIsInstance(value, xso.Unknown)
        self.assertEqual(xso.Unknown(10), value)

    def test_accept_unknown_can_be_turned_off(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            xso.Integer(),
            accept_unknown=False,
        )

        with self.assertRaisesRegex(
                TypeError,
                r"not a valid .* value: <Unknown: 10>"):
            e.coerce(xso.Unknown(10))

    def test_allow_unknown_by_default(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
        )

        value = e.unpack(10)
        self.assertIsInstance(value, xso.Unknown)
        self.assertEqual(xso.Unknown(10), value)

    def test_allow_unknown_can_be_turned_off(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
            allow_unknown=False,
        )

        with self.assertRaisesRegex(
                ValueError,
                r"10 is not a valid SomeEnum"):
            e.unpack(10)

    def test_format_works_with_unknown(self):
        enum_class = self.SomeEnum
        e = xso.EnumElementType(
            enum_class,
            self.FancyType(),
        )

        self.assertEqual(
            e.pack(xso.Unknown(10)),
            10,
        )


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


class TestNumericRange(unittest.TestCase):
    def test_is_abstract_validator(self):
        self.assertTrue(issubclass(
            xso.NumericRange,
            xso.AbstractValidator
        ))

    def test_validate_ok(self):
        v = xso.NumericRange(min_=10, max_=20)
        for i in range(10, 21):
            self.assertTrue(
                v.validate(i),
            )

    def test_validate_detailed_out_of_bounds(self):
        v = xso.NumericRange(min_=10, max_=20)
        for i in range(0, 10):
            self.assertFalse(
                v.validate(i),
            )

    def test_validate_detailed_too_small(self):
        v = xso.NumericRange(min_=10)
        for i in range(0, 10):
            self.assertFalse(
                v.validate(i),
            )

    def test_validate_detailed_too_large(self):
        v = xso.NumericRange(max_=-1)
        for i in range(0, 10):
            self.assertFalse(
                v.validate(i),
            )


class TestEnumType(unittest.TestCase):
    def test_instanciates_EnumCDataType_by_default_and_passes_kwargs(self):
        with contextlib.ExitStack() as stack:
            EnumCDataType = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.types.EnumCDataType")
            )

            result = xso.EnumType(
                unittest.mock.sentinel.enum_class,
                foo=unittest.mock.sentinel.foo,
                bar=unittest.mock.sentinel.bar,
            )

        EnumCDataType.assert_called_once_with(
            unittest.mock.sentinel.enum_class,
            foo=unittest.mock.sentinel.foo,
            bar=unittest.mock.sentinel.bar,
        )

        self.assertEqual(result, EnumCDataType())

    def test_instanciates_EnumCDataType_for_AbstractCDataType(self):
        m = unittest.mock.Mock(
            spec=xso.AbstractCDataType
        )

        with contextlib.ExitStack() as stack:
            EnumCDataType = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.types.EnumCDataType")
            )

            result = xso.EnumType(
                unittest.mock.sentinel.enum_class,
                m,
                foo=unittest.mock.sentinel.foo,
                bar=unittest.mock.sentinel.bar,
            )

        EnumCDataType.assert_called_once_with(
            unittest.mock.sentinel.enum_class,
            m,
            foo=unittest.mock.sentinel.foo,
            bar=unittest.mock.sentinel.bar,
        )

        self.assertEqual(result, EnumCDataType())

    def test_instanciates_EnumCDataType_for_AbstractElementType(self):
        m = unittest.mock.Mock(
            spec=xso.AbstractElementType
        )

        with contextlib.ExitStack() as stack:
            EnumElementType = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.types.EnumElementType")
            )

            result = xso.EnumType(
                unittest.mock.sentinel.enum_class,
                m,
                foo=unittest.mock.sentinel.foo,
                bar=unittest.mock.sentinel.bar,
            )

        EnumElementType.assert_called_once_with(
            unittest.mock.sentinel.enum_class,
            m,
            foo=unittest.mock.sentinel.foo,
            bar=unittest.mock.sentinel.bar,
        )

        self.assertEqual(result, EnumElementType())
