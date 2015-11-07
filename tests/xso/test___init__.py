import unittest

import aioxmpp.structs as structs
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


class TestAbstractTextChild(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            xso.AbstractTextChild,
            xso.XSO
        ))

    def test_has_no_tag(self):
        self.assertFalse(hasattr(xso.AbstractTextChild, "TAG"))

    def test_lang_attr(self):
        self.assertIsInstance(
            xso.AbstractTextChild.lang,
            xso.LangAttr
        )

    def test_text_attr(self):
        self.assertIsInstance(
            xso.AbstractTextChild.text,
            xso.Text
        )

    def test_init_default(self):
        atc = xso.AbstractTextChild()
        self.assertIsNone(atc.lang)
        self.assertFalse(atc.text)

    def test_init_args(self):
        atc = xso.AbstractTextChild(
            "foo",
            lang=structs.LanguageTag.fromstr("de-DE"))
        self.assertEqual(atc.text, "foo")
        self.assertEqual(atc.lang, structs.LanguageTag.fromstr("de-DE"))

    def test_equality(self):
        atc1 = xso.AbstractTextChild()
        atc2 = xso.AbstractTextChild()

        self.assertTrue(atc1 == atc2)
        self.assertFalse(atc1 != atc2)

        atc1.text = "foo"

        self.assertFalse(atc1 == atc2)
        self.assertTrue(atc1 != atc2)

        atc2.text = "foo"
        atc2.lang = structs.LanguageTag.fromstr("de-DE")

        self.assertFalse(atc1 == atc2)
        self.assertTrue(atc1 != atc2)

        atc1.lang = atc2.lang

        self.assertTrue(atc1 == atc2)
        self.assertFalse(atc1 != atc2)

    def test_equality_handles_incorrect_peer_type_gracefully(self):
        atc = xso.AbstractTextChild()
        self.assertFalse(atc is None)
        self.assertFalse(atc == "foo")


class TestNO_DEFAULT(unittest.TestCase):
    def test_unequal_to_things(self):
        NO_DEFAULT = xso.NO_DEFAULT
        self.assertFalse(NO_DEFAULT is None)
        self.assertFalse(NO_DEFAULT is True)
        self.assertFalse(NO_DEFAULT is False)
        self.assertFalse(NO_DEFAULT == "")
        self.assertFalse(NO_DEFAULT == "foo")
        self.assertFalse(NO_DEFAULT == 0)
        self.assertFalse(NO_DEFAULT == 123)
        self.assertFalse(NO_DEFAULT == 0.)
        self.assertFalse(NO_DEFAULT == float("nan"))

    def test_equal_to_itself(self):
        self.assertTrue(xso.NO_DEFAULT == xso.NO_DEFAULT)
        self.assertFalse(xso.NO_DEFAULT != xso.NO_DEFAULT)

    def test___bool__raises(self):
        with self.assertRaises(TypeError):
            bool(xso.NO_DEFAULT)

    def test___index__raises(self):
        with self.assertRaises(TypeError):
            int(xso.NO_DEFAULT)

    def test___float__raises(self):
        with self.assertRaises(TypeError):
            float(xso.NO_DEFAULT)

    def test___lt__raises(self):
        with self.assertRaises(TypeError):
            xso.NO_DEFAULT < xso.NO_DEFAULT

    def test___gt__raises(self):
        with self.assertRaises(TypeError):
            xso.NO_DEFAULT > xso.NO_DEFAULT
