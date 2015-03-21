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
