import abc
import inspect
import unittest

import pytz

from datetime import datetime

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
            "2014-01-26T19:47:10Z",
            t.format(datetime(2014, 1, 26, 20, 40, 10,
                              tzinfo=pytz.timezone("Europe/Berlin")))
        )


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


class TestAbstractValidator(unittest.TestCase):
    def test_is_abstract(self):
        self.assertIsInstance(
            xso.AbstractValidator,
            abc.ABCMeta)
        with self.assertRaises(TypeError):
            xso.AbstractValidator()


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
