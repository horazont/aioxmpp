import unittest

import pytz

from datetime import datetime

import asyncio_xmpp.stanza_types as stanza_types


class TestStringType(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.String()
        self.assertEqual(
            "foo",
            t.parse("foo"))

    def test_format(self):
        t = stanza_types.String()
        self.assertEqual(
            "foo",
            t.format("foo"))


class TestIntegerType(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.Integer()
        self.assertEqual(
            123,
            t.parse("123"))

    def test_parse_failure(self):
        t = stanza_types.Integer()
        with self.assertRaises(ValueError):
            t.parse("123f")

    def test_format(self):
        t = stanza_types.Integer()
        self.assertEqual(
            "123",
            t.format(123))


class TestFloatType(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.Float()
        self.assertEqual(
            123.3,
            t.parse("123.3"))

    def test_parse_failure(self):
        t = stanza_types.Float()
        with self.assertRaises(ValueError):
            t.parse("123.3f")

    def test_format(self):
        t = stanza_types.Float()
        self.assertEqual(
            "123.3",
            t.format(123.3))


class TestBoolType(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.Bool()
        self.assertTrue(t.parse("true"))
        self.assertTrue(t.parse("1"))
        self.assertTrue(t.parse("  true  "))
        self.assertTrue(t.parse(" 1 "))
        self.assertFalse(t.parse("false"))
        self.assertFalse(t.parse("0"))
        self.assertFalse(t.parse("  false "))
        self.assertFalse(t.parse(" 0 "))

    def test_parse_failure(self):
        t = stanza_types.Bool()
        with self.assertRaises(ValueError):
            t.parse("foobar")
        with self.assertRaises(ValueError):
            t.parse("truefoo")
        with self.assertRaises(ValueError):
            t.parse("0foo")

    def test_format(self):
        t = stanza_types.Bool()
        self.assertEqual(
            "true",
            t.format(True))
        self.assertEqual(
            "false",
            t.format(False))


class TestDateTimeType(unittest.TestCase):
    def test_parse_example(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc),
            t.parse("2014-01-26T19:40:10Z"))

    def test_parse_timezoned(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc),
            t.parse("2014-01-26T20:40:10+01:00"))

    def test_parse_local(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 20, 40, 10),
            t.parse("2014-01-26T20:40:10"))

    def test_parse_milliseconds(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 20, 40, 10, 123456),
            t.parse("2014-01-26T20:40:10.123456"))

    def test_parse_milliseconds_timezoned(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            datetime(2014, 1, 26, 19, 40, 10, 123456, tzinfo=pytz.utc),
            t.parse("2014-01-26T20:40:10.123456+01:00"))

    def test_parse_need_time(self):
        t = stanza_types.DateTime()
        with self.assertRaises(ValueError):
            t.parse("2014-01-26")

    def test_parse_need_date(self):
        t = stanza_types.DateTime()
        with self.assertRaises(ValueError):
            t.parse("20:40:10")

    def test_format_timezoned(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10Z",
            t.format(datetime(2014, 1, 26, 19, 40, 10, tzinfo=pytz.utc))
        )

    def test_format_timezoned_microseconds(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10.1234Z",
            t.format(datetime(2014, 1, 26, 19, 40, 10, 123400,
                              tzinfo=pytz.utc))
        )

    def test_format_naive(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10",
            t.format(datetime(2014, 1, 26, 19, 40, 10))
        )

    def test_format_naive_microseconds(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            "2014-01-26T19:40:10.1234",
            t.format(datetime(2014, 1, 26, 19, 40, 10, 123400))
        )

    def test_format_timezoned_nonutc(self):
        t = stanza_types.DateTime()
        self.assertEqual(
            "2014-01-26T19:47:10Z",
            t.format(datetime(2014, 1, 26, 20, 40, 10,
                              tzinfo=pytz.timezone("Europe/Berlin")))
        )


class TestBase64Binary(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.Base64Binary()
        self.assertEqual(
            b"fnord",
            t.parse("Zm5vcmQ=")
        )

    def test_format(self):
        t = stanza_types.Base64Binary()
        self.assertEqual(
            "Zm5vcmQ=",
            t.format(b"fnord")
        )

    def test_format_long(self):
        t = stanza_types.Base64Binary()
        self.assertEqual(
            "Zm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZG"
            "Zub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRmbm9yZGZub3JkZm5vcmRm"
            "bm9yZGZub3JkZm5vcmRmbm9yZA==",
            t.format(b"fnord"*20)
        )


class TestHexBinary(unittest.TestCase):
    def test_parse(self):
        t = stanza_types.HexBinary()
        self.assertEqual(
            b"fnord",
            t.parse("666e6f7264")
        )

    def test_format(self):
        t = stanza_types.HexBinary()
        self.assertEqual(
            "666e6f7264",
            t.format(b"fnord")
        )
