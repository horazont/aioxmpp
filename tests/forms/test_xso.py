import unittest

import aioxmpp.forms.xso as forms_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_form_namespace(self):
        self.assertEqual(
            "jabber:x:data",
            namespaces.xep0004_data
        )


class TestValue(unittest.TestCase):
    def test_is_AbstractTextChild(self):
        self.assertTrue(issubclass(
            forms_xso.Value,
            xso.AbstractTextChild
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "value"),
            forms_xso.Value.TAG
        )


class TestOption(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            forms_xso.Option,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "option"),
            forms_xso.Option.TAG
        )

    def test_label_attr(self):
        self.assertIsInstance(
            forms_xso.Option.label,
            xso.Attr
        )
        self.assertEqual(
            (None, "label"),
            forms_xso.Option.label.tag
        )

    def test_value_attr(self):
        self.assertIsInstance(
            forms_xso.Option.value,
            xso.ChildText
        )
        self.assertEqual(
            (namespaces.xep0004_data, "value"),
            forms_xso.Option.value.tag
        )

    def test_reject_missing_value(self):
        opt = forms_xso.Option()
        with self.assertRaisesRegexp(ValueError,
                                     "option is missing a value"):
            opt.validate()


class TestField(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            forms_xso.Field,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "field"),
            forms_xso.Field.TAG
        )

    def test_required_attr(self):
        self.assertIsInstance(
            forms_xso.Field.required,
            xso.ChildTag
        )
        self.assertSetEqual(
            {
                (namespaces.xep0004_data, "required"),
                None,
            },
            forms_xso.Field.required.validator.values
        )

    def test_desc_attr(self):
        self.assertIsInstance(
            forms_xso.Field.desc,
            xso.ChildText
        )
        self.assertEqual(
            (namespaces.xep0004_data, "desc"),
            forms_xso.Field.desc.tag
        )

    def test_values_attr(self):
        self.assertIsInstance(
            forms_xso.Field.values,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Value
            },
            set(forms_xso.Field.values._classes)
        )

    def test_options_attr(self):
        self.assertIsInstance(
            forms_xso.Field.options,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Option
            },
            set(forms_xso.Field.options._classes)
        )

    def test_var_attr(self):
        self.assertIsInstance(
            forms_xso.Field.var,
            xso.Attr
        )
        self.assertEqual(
            (None, "var"),
            forms_xso.Field.var.tag
        )

    def test_type_attr(self):
        self.assertIsInstance(
            forms_xso.Field.type_,
            xso.Attr
        )
        self.assertEqual(
            (None, "type"),
            forms_xso.Field.type_.tag
        )
        self.assertIsInstance(
            forms_xso.Field.type_.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            {
                "boolean",
                "fixed",
                "hidden",
                "jid-multi",
                "jid-single",
                "list-multi",
                "list-single",
                "text-multi",
                "text-private",
                "text-single",
            },
            forms_xso.Field.type_.validator.values
        )
        self.assertEqual(
            "text-single",
            forms_xso.Field.type_.default
        )

    def test_label_attr(self):
        self.assertIsInstance(
            forms_xso.Field.label,
            xso.Attr
        )
        self.assertEqual(
            (None, "label"),
            forms_xso.Field.label.tag
        )

    def test_reject_missing_var_for_non_fixed_fields(self):
        types = set(forms_xso.Field.type_.validator.values)
        types.discard("fixed")

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            with self.assertRaisesRegexp(ValueError,
                                         "missing attribute var"):
                f.validate()

    def test_accept_missing_var_for_fixed_fields(self):
        f = forms_xso.Field()
        f.type_ = "fixed"
        f.validate()

        f.var = "foobar"
        f.validate()

    def test_reject_options_for_non_list_fields(self):
        types = set(forms_xso.Field.type_.validator.values)
        types.discard("list-single")
        types.discard("list-multi")

        option = forms_xso.Option()
        option.value = "foobar"

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.options.append(option)

            with self.assertRaisesRegexp(ValueError,
                                         "unexpected option on non-list field"):
                f.validate()

    def test_accept_options_for_list_fields(self):
        types = {"list-single", "list-multi"}

        option = forms_xso.Option()
        option.value = "foobar"

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.options.append(option)

            f.validate()

    def test_reject_multiple_values_for_non_multi_fields(self):
        types = set(forms_xso.Field.type_.validator.values)
        types.discard("text-multi")
        types.discard("list-multi")
        types.discard("jid-multi")

        value = forms_xso.Value()

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.values.append(value)
            f.values.append(value)

            with self.assertRaisesRegexp(ValueError,
                                         "too many values on non-multi field"):
                f.validate()

    def test_accept_multiple_values_on_multi_fields(self):
        types = {"list-multi", "text-multi", "jid-multi"}

        value = forms_xso.Value()

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.values.append(value)
            f.values.append(value)

            f.validate()

    def test_reject_duplicate_option_labels(self):
        f = forms_xso.Field()
        f.type_ = "list-multi"
        f.var = "foobar"

        o1 = forms_xso.Option()
        o1.label = "foo"
        o1.value = "bar"

        o2 = forms_xso.Option()
        o2.label = "foo"
        o2.value = "baz"

        f.options.extend([o1, o2])

        with self.assertRaisesRegexp(ValueError,
                                     "duplicate option label"):
            f.validate()

    def test_reject_duplicate_option_values(self):
        f = forms_xso.Field()
        f.type_ = "list-multi"
        f.var = "foobar"

        o1 = forms_xso.Option()
        o1.label = "foo"
        o1.value = "bar"

        o2 = forms_xso.Option()
        o2.label = "baz"
        o2.value = "bar"

        f.options.extend([o1, o2])

        with self.assertRaisesRegexp(ValueError,
                                     "duplicate option label"):
            f.validate()


class TestTitle(unittest.TestCase):
    def test_is_AbstractTextChild(self):
        self.assertTrue(issubclass(
            forms_xso.Title,
            xso.AbstractTextChild
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "title"),
            forms_xso.Title.TAG
        )


class TestInstructions(unittest.TestCase):
    def test_is_AbstractTextChild(self):
        self.assertTrue(issubclass(
            forms_xso.Instructions,
            xso.AbstractTextChild
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "instructions"),
            forms_xso.Instructions.TAG
        )


class TestAbstractItem(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            forms_xso.AbstractItem,
            xso.XSO
        ))

    def test_fields_attr(self):
        self.assertIsInstance(
            forms_xso.AbstractItem.fields,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Field,
            },
            set(forms_xso.AbstractItem.fields._classes)
        )

    def test_has_no_tag(self):
        self.assertFalse(hasattr(forms_xso.AbstractItem, "TAG"))


class TestItem(unittest.TestCase):
    def test_is_abstract_item(self):
        self.assertTrue(issubclass(
            forms_xso.Item,
            forms_xso.AbstractItem
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "item"),
            forms_xso.Item.TAG
        )


class TestReported(unittest.TestCase):
    def test_is_abstract_item(self):
        self.assertTrue(issubclass(
            forms_xso.Reported,
            forms_xso.AbstractItem
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "reported"),
            forms_xso.Reported.TAG
        )


class TestData(unittest.TestCase):
    def test_is_abstract_item(self):
        self.assertTrue(issubclass(
            forms_xso.Data,
            forms_xso.AbstractItem
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "x"),
            forms_xso.Data.TAG
        )

    def test_type_attr(self):
        self.assertIsInstance(
            forms_xso.Data.type_,
            xso.Attr
        )
        self.assertEqual(
            (None, "type"),
            forms_xso.Data.type_.tag
        )
        self.assertIsInstance(
            forms_xso.Data.type_.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            {
                "form",
                "submit",
                "cancel",
                "result",
            },
            forms_xso.Data.type_.validator.values
        )
        self.assertEqual(
            xso.ValidateMode.ALWAYS,
            forms_xso.Data.type_.validate
        )
        self.assertTrue(forms_xso.Data.type_.required)

    def test_title_attr(self):
        self.assertIsInstance(
            forms_xso.Data.title,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Title,
            },
            set(forms_xso.Data.title._classes)
        )

    def test_instructions_attr(self):
        self.assertIsInstance(
            forms_xso.Data.instructions,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Instructions,
            },
            set(forms_xso.Data.instructions._classes)
        )

    def test_items_attr(self):
        self.assertIsInstance(
            forms_xso.Data.items,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Item,
            },
            set(forms_xso.Data.items._classes)
        )

    def test_reported_attr(self):
        self.assertIsInstance(
            forms_xso.Data.reported,
            xso.Child
        )
        self.assertSetEqual(
            {
                forms_xso.Reported,
            },
            set(forms_xso.Data.reported._classes)
        )

    def test_validate_rejects_reported_or_items_if_type_is_not_result(self):
        types = ["form", "submit", "cancel"]

        rep = forms_xso.Reported()
        item = forms_xso.Item()

        for type_ in types:
            obj = forms_xso.Data()
            obj.type_ = type_
            obj.reported = rep
            with self.assertRaisesRegexp(ValueError, "report in non-result"):
                obj.validate()
            obj.reported = None
            obj.items.append(item)
            with self.assertRaisesRegexp(ValueError, "report in non-result"):
                obj.validate()
            obj.items.clear()

    def test_validate_rejects_fields_for_results(self):
        field = forms_xso.Field()
        field.type_ = "fixed"
        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.fields.append(field)

        with self.assertRaisesRegexp(ValueError, "field in report result"):
            obj.validate()

    def test_validate_reject_empty_reported(self):
        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.reported = forms_xso.Reported()

        with self.assertRaisesRegexp(ValueError, "empty report header"):
            obj.validate()

    def test_validate_reject_empty_items(self):
        f = forms_xso.Field()
        f.var = "foobar"

        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.reported = forms_xso.Reported()
        obj.reported.fields.append(f)

        obj.items.append(forms_xso.Item())

        with self.assertRaisesRegexp(ValueError,
                                     "field mismatch between row and header"):
            obj.validate()

    def test_validate_reject_mismatching_items(self):
        f = forms_xso.Field()
        f.var = "foobar"

        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.reported = forms_xso.Reported()
        obj.reported.fields.append(f)

        f2 = forms_xso.Field()
        f2.var = "fnord"

        item = forms_xso.Item()
        item.fields.append(f2)
        obj.items.append(item)

        with self.assertRaisesRegexp(ValueError,
                                     "field mismatch between row and header"):
            obj.validate()
