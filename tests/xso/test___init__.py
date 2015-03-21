import unittest

import aioxmpp.xso as xso


class Testtag_to_str(unittest.TestCase):
    def test_unqualified(self):
        self.assertEqual(
            "foo",
            xso.tag_to_str((None, "foo"))
        )

    def test_with_namespace(self):
        self.assertEqual(
            "{uri:bar}foo",
            xso.tag_to_str(("uri:bar", "foo"))
        )


class Testnormalize_tag(unittest.TestCase):
    def test_unqualified(self):
        self.assertEqual(
            (None, "foo"),
            xso.normalize_tag("foo")
        )

    def test_with_namespace(self):
        self.assertEqual(
            ("uri:bar", "foo"),
            xso.normalize_tag(("uri:bar", "foo"))
        )

    def test_etree_format(self):
        self.assertEqual(
            ("uri:bar", "foo"),
            xso.normalize_tag("{uri:bar}foo")
        )

    def test_validate_etree_format(self):
        with self.assertRaises(ValueError):
            xso.normalize_tag("uri:bar}foo")

    def test_validate_tuple_format(self):
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo",))
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo", "bar", "baz"))
        with self.assertRaises(ValueError):
            xso.normalize_tag(("foo", None))
        with self.assertRaises(ValueError):
            xso.normalize_tag((None, None))
        with self.assertRaises(TypeError):
            xso.normalize_tag((1, 2))

    def test_reject_incorrect_types(self):
        with self.assertRaises(TypeError):
            xso.normalize_tag(1)
        with self.assertRaises(TypeError):
            xso.normalize_tag((1, 2))
