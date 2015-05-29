import unittest

import aioxmpp.errors as errors

from aioxmpp.utils import etree


class Testformat_error_text(unittest.TestCase):
    def test_only_condition(self):
        self.assertEqual(
            "{uri:foo}error",
            errors.format_error_text(
                condition=("uri:foo", "error")
            )
        )

    def test_with_text(self):
        self.assertEqual(
            "{uri:foo}error ('foobar')",
            errors.format_error_text(
                condition=("uri:foo", "error"),
                text="foobar",
            )
        )

    def test_with_application_defined(self):
        appcond = etree.Element("{uri:bar}value-error")
        self.assertEqual(
            "{uri:foo}error/{uri:bar}value-error",
            errors.format_error_text(
                condition=("uri:foo", "error"),
                application_defined_condition=appcond,
            )
        )

    def test_with_application_defined_and_text(self):
        appcond = etree.Element("{uri:bar}value-error")
        self.assertEqual(
            "{uri:foo}error/{uri:bar}value-error ('that’s not an integer')",
            errors.format_error_text(
                condition=("uri:foo", "error"),
                application_defined_condition=appcond,
                text="that’s not an integer"
            )
        )


class TestMultiOSError(unittest.TestCase):
    def test_message(self):
        exc = errors.MultiOSError("foo",
                                  [ValueError("bar"),
                                   ValueError("baz")])

        self.assertEqual(
            "foo: multiple errors: bar, baz",
            str(exc)
        )


    def test_flatten(self):
        base_excs1 = [OSError(), OSError()]
        base_excs2 = [OSError(), OSError()]
        exc3 = OSError()

        excs = [errors.MultiOSError("foo", base_excs1),
                errors.MultiOSError("foo", base_excs2),
                exc3]

        exc = errors.MultiOSError("bar", excs)

        self.assertSequenceEqual(
            base_excs1+base_excs2+[exc3],
            exc.exceptions
        )
