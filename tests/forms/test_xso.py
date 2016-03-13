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
    def test_is_xso(self):
        self.assertTrue(issubclass(
            forms_xso.Value,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "value"),
            forms_xso.Value.TAG
        )

    def test_value(self):
        self.assertIsInstance(
            forms_xso.Value.value,
            xso.Text
        )
        self.assertEqual(
            forms_xso.Value.value.default,
            ""
        )


class TestValueElement(unittest.TestCase):
    def test_is_type(self):
        self.assertTrue(issubclass(
            forms_xso.ValueElement,
            xso.AbstractType
        ))

    def test_get_formatted_type(self):
        t = forms_xso.ValueElement()
        self.assertIs(t.get_formatted_type(), forms_xso.Value)

    def test_parse(self):
        t = forms_xso.ValueElement()
        v = forms_xso.Value()
        v.value = "foobar"
        self.assertEqual(
            v.value,
            t.parse(v)
        )

    def test_format(self):
        t = forms_xso.ValueElement()
        v = t.format("foo")
        self.assertIsInstance(
            v,
            forms_xso.Value
        )
        self.assertEqual(v.value, "foo")


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
        with self.assertRaisesRegex(ValueError,
                                    "option is missing a value"):
            opt.validate()


class TestOptionElement(unittest.TestCase):
    def test_is_type(self):
        self.assertTrue(issubclass(
            forms_xso.OptionElement,
            xso.AbstractType
        ))

    def test_get_formatted_type(self):
        t = forms_xso.OptionElement()
        self.assertIs(t.get_formatted_type(), forms_xso.Option)

    def test_parse(self):
        t = forms_xso.OptionElement()
        o = forms_xso.Option()
        o.label = "fnord"
        o.value = "foobar"
        self.assertEqual(
            ("foobar", "fnord"),
            t.parse(o)
        )

    def test_format(self):
        t = forms_xso.OptionElement()
        o = t.format(("foo", "bar"))
        self.assertIsInstance(
            o,
            forms_xso.Option
        )
        self.assertEqual(o.value, "foo")
        self.assertEqual(o.label, "bar")


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
            xso.ChildValueList
        )
        self.assertSetEqual(
            {
                forms_xso.Value
            },
            set(forms_xso.Field.values._classes)
        )
        self.assertIsInstance(
            forms_xso.Field.values.type_,
            forms_xso.ValueElement
        )

    def test_options_attr(self):
        self.assertIsInstance(
            forms_xso.Field.options,
            xso.ChildValueMap
        )
        self.assertIsInstance(
            forms_xso.Field.options.type_,
            forms_xso.OptionElement
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
            forms_xso.Field.type_.default,
            "text-single"
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
            with self.assertRaisesRegex(ValueError,
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

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.options["foo"] = "bar"

            with self.assertRaisesRegex(ValueError,
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
            f.options["foo"] = "bar"

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

            with self.assertRaisesRegex(ValueError,
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

    def test_reject_duplicate_option_values(self):
        f = forms_xso.Field()
        f.type_ = "list-multi"
        f.var = "foobar"
        f.options["foo"] = "bar"
        f.options["baz"] = "bar"

        with self.assertRaisesRegex(ValueError,
                                    "duplicate option value"):
            f.validate()

    def test_init(self):
        f = forms_xso.Field()
        self.assertEqual(f.type_, "text-single")
        self.assertSequenceEqual(f.values, [])
        self.assertDictEqual(f.options, {})
        self.assertIsNone(f.required)
        self.assertIsNone(f.desc)
        self.assertIsNone(f.var)
        self.assertIsNone(f.label)

    def test_init_args(self):
        options = {
            "1": "Foo 1",
            "2": "Foo 2",
            "3": "Foo 3",
        }

        values = ["1", "2"]

        f = forms_xso.Field(
            type_="list-multi",
            options=options,
            values=values,
            desc="description",
            required=True,
            label="fnord"
        )

        self.assertEqual(f.type_, "list-multi")

        self.assertDictEqual(f.options, options)
        self.assertIsNot(f.options, options)

        self.assertSequenceEqual(f.values, values)
        self.assertIsNot(f.values, values)

        self.assertEqual(f.desc, "description")

        self.assertEqual(
            f.required,
            (namespaces.xep0004_data, "required")
        )

        self.assertEqual(f.label, "fnord")


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

    def test_fields_attr(self):
        self.assertIsInstance(
            forms_xso.Data.fields,
            xso.ChildList
        )
        self.assertSetEqual(
            {
                forms_xso.Field,
            },
            set(forms_xso.Data.fields._classes)
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
            with self.assertRaisesRegex(ValueError, "report in non-result"):
                obj.validate()
            obj.reported = None
            obj.items.append(item)
            with self.assertRaisesRegex(ValueError, "report in non-result"):
                obj.validate()
            obj.items.clear()

    def test_validate_rejects_fields_for_results_if_report(self):
        field = forms_xso.Field()
        field.type_ = "fixed"
        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.fields.append(field)
        obj.reported = forms_xso.Reported()

        with self.assertRaisesRegex(ValueError, "field in report result"):
            obj.validate()

        obj.reported = None
        obj.items.append(forms_xso.Item())

        with self.assertRaisesRegex(ValueError, "field in report result"):
            obj.validate()

    def test_validate_accepts_fields_for_results_without_report(self):
        field = forms_xso.Field()
        field.type_ = "fixed"
        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.fields.append(field)

        obj.validate()

    def test_validate_reject_empty_reported(self):
        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.reported = forms_xso.Reported()

        with self.assertRaisesRegex(ValueError, "empty report header"):
            obj.validate()

    def test_validate_reject_empty_items(self):
        f = forms_xso.Field()
        f.var = "foobar"

        obj = forms_xso.Data()
        obj.type_ = "result"
        obj.reported = forms_xso.Reported()
        obj.reported.fields.append(f)

        obj.items.append(forms_xso.Item())

        with self.assertRaisesRegex(ValueError,
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

        with self.assertRaisesRegex(ValueError,
                                     "field mismatch between row and header"):
            obj.validate()
