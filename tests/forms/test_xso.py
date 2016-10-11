########################################################################
# File name: test_xso.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import collections
import itertools
import unittest
import unittest.mock

import aioxmpp.stanza as stanza
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


class TestFieldType(unittest.TestCase):
    def test_covers_all_types(self):
        self.assertSetEqual(
            {v.value for v in forms_xso.FieldType},
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
            }
        )

    def test_has_options(self):
        positive = [
            forms_xso.FieldType.LIST_MULTI,
            forms_xso.FieldType.LIST_SINGLE,
        ]

        for enum_value in forms_xso.FieldType:
            self.assertEqual(
                enum_value in positive,
                enum_value.has_options
            )

    def test_is_multi_valued(self):
        positive = [
            forms_xso.FieldType.LIST_MULTI,
            forms_xso.FieldType.TEXT_MULTI,
            forms_xso.FieldType.JID_MULTI,
        ]

        for enum_value in forms_xso.FieldType:
            self.assertEqual(
                enum_value in positive,
                enum_value.is_multivalued,
            )

    def test_allow_upcast(self):
        allowed = {
            (forms_xso.FieldType.TEXT_SINGLE,
             forms_xso.FieldType.TEXT_PRIVATE)
        }

        for t1, t2 in itertools.product(forms_xso.FieldType,
                                        forms_xso.FieldType):
            self.assertEqual(
                t1 == t2 or (t1, t2) in allowed,
                t1.allow_upcast(t2)
            )


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
            xso.ChildFlag
        )
        self.assertEqual(
            (namespaces.xep0004_data, "required"),
            forms_xso.Field.required.tag
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
        self.assertEqual(
            forms_xso.Field.options.mapping_type,
            collections.OrderedDict,
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
            forms_xso.Field.type_.type_,
            xso.EnumType
        )
        self.assertIs(
            forms_xso.Field.type_.type_.enum_class,
            forms_xso.FieldType,
        )
        self.assertIsNone(forms_xso.Field.type_.validator)
        self.assertEqual(
            forms_xso.Field.type_.default,
            forms_xso.FieldType.TEXT_SINGLE,
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
        types = set(forms_xso.FieldType)
        types.discard(forms_xso.FieldType.FIXED)

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            with self.assertRaisesRegex(ValueError,
                                        "missing attribute var"):
                f.validate()

    def test_accept_missing_var_for_fixed_fields(self):
        f = forms_xso.Field()
        f.type_ = forms_xso.FieldType.FIXED
        f.validate()

        f.var = "foobar"
        f.validate()

    def test_reject_options_for_non_list_fields(self):
        types = set(forms_xso.FieldType)
        types.discard(forms_xso.FieldType.LIST_MULTI)
        types.discard(forms_xso.FieldType.LIST_SINGLE)

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.options["foo"] = "bar"

            with self.assertRaisesRegex(ValueError,
                                        "unexpected option on non-list field"):
                f.validate()

    def test_accept_options_for_list_fields(self):
        types = {
            forms_xso.FieldType.LIST_SINGLE,
            forms_xso.FieldType.LIST_MULTI,
        }

        option = forms_xso.Option()
        option.value = "foobar"

        for type_ in types:
            f = forms_xso.Field()
            f.type_ = type_
            f.var = "foobar"
            f.options["foo"] = "bar"

            f.validate()

    def test_reject_multiple_values_for_non_multi_fields(self):
        types = set(forms_xso.FieldType)
        types.discard(forms_xso.FieldType.LIST_MULTI)
        types.discard(forms_xso.FieldType.TEXT_MULTI)
        types.discard(forms_xso.FieldType.JID_MULTI)

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
        types = {
            forms_xso.FieldType.LIST_MULTI,
            forms_xso.FieldType.TEXT_MULTI,
            forms_xso.FieldType.JID_MULTI,
        }

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
        f.type_ = forms_xso.FieldType.LIST_MULTI
        f.var = "foobar"
        f.options["foo"] = "bar"
        f.options["baz"] = "bar"

        with self.assertRaisesRegex(
                ValueError,
                "duplicate option value"):
            f.validate()

    def test_init(self):
        f = forms_xso.Field()
        self.assertEqual(f.type_, forms_xso.FieldType.TEXT_SINGLE)
        self.assertSequenceEqual(f.values, [])
        self.assertDictEqual(f.options, {})
        self.assertFalse(f.required)
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
            type_=forms_xso.FieldType.LIST_MULTI,
            options=options,
            values=values,
            desc="description",
            required=True,
            label="fnord"
        )

        self.assertEqual(f.type_, forms_xso.FieldType.LIST_MULTI)

        self.assertDictEqual(f.options, options)
        self.assertIsNot(f.options, options)

        self.assertSequenceEqual(f.values, values)
        self.assertIsNot(f.values, values)

        self.assertEqual(f.desc, "description")

        self.assertIs(
            f.required,
            True,
        )

        self.assertEqual(f.label, "fnord")


class TestInstructions(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            forms_xso.Instructions,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0004_data, "instructions"),
            forms_xso.Instructions.TAG
        )

    def test_value(self):
        self.assertIsInstance(
            forms_xso.Instructions.value,
            xso.Text,
        )
        self.assertEqual(
            forms_xso.Instructions.value.default,
            ""
        )


class TestInstructionsElement(unittest.TestCase):
    def test_is_type(self):
        self.assertTrue(issubclass(
            forms_xso.InstructionsElement,
            xso.AbstractType
        ))

    def test_get_formatted_type(self):
        t = forms_xso.InstructionsElement()
        self.assertIs(
            t.get_formatted_type(),
            forms_xso.Instructions
        )

    def test_parse(self):
        t = forms_xso.InstructionsElement()
        v = forms_xso.Instructions()
        v.value = "foobar"
        self.assertEqual(
            v.value,
            t.parse(v)
        )

    def test_format(self):
        t = forms_xso.InstructionsElement()
        v = t.format("foo")
        self.assertIsInstance(
            v,
            forms_xso.Instructions
        )
        self.assertEqual(v.value, "foo")


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


class TestDataType(unittest.TestCase):
    def test_covers_all_types(self):
        self.assertSetEqual(
            {v.value for v in forms_xso.DataType},
            {
                "form",
                "submit",
                "cancel",
                "result",
            }
        )


class TestData(unittest.TestCase):
    def test_is_abstract_item(self):
        self.assertTrue(issubclass(
            forms_xso.Data,
            forms_xso.AbstractItem
        ))

    def test_init_requires_type(self):
        with self.assertRaises(TypeError):
            forms_xso.Data()

    def test_init(self):
        f = forms_xso.Data(type_=forms_xso.DataType.FORM)
        self.assertEqual(f.type_, forms_xso.DataType.FORM)

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
            forms_xso.Data.type_.type_,
            xso.EnumType
        )
        self.assertEqual(
            forms_xso.Data.type_.type_.enum_class,
            forms_xso.DataType,
        )

    def test_title_attr(self):
        self.assertIsInstance(
            forms_xso.Data.title,
            xso.ChildText
        )
        self.assertEqual(
            forms_xso.Data.title.tag,
            (namespaces.xep0004_data, "title"),
        )
        self.assertIsNone(
            forms_xso.Data.title.default,
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
            xso.ChildValueList
        )
        self.assertSetEqual(
            {
                forms_xso.Instructions
            },
            set(forms_xso.Data.instructions._classes)
        )
        self.assertIsInstance(
            forms_xso.Data.instructions.type_,
            forms_xso.InstructionsElement,
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
        types = [
            forms_xso.DataType.FORM,
            forms_xso.DataType.SUBMIT,
            forms_xso.DataType.CANCEL,
        ]

        rep = forms_xso.Reported()
        item = forms_xso.Item()

        for type_ in types:
            obj = forms_xso.Data(type_=type_)
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
        field.type_ = forms_xso.FieldType.FIXED
        obj = forms_xso.Data(type_=forms_xso.DataType.RESULT)
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
        field.type_ = forms_xso.FieldType.FIXED
        obj = forms_xso.Data(type_=forms_xso.DataType.RESULT)
        obj.fields.append(field)

        obj.validate()

    def test_validate_reject_empty_reported(self):
        obj = forms_xso.Data(forms_xso.DataType.RESULT)
        obj.reported = forms_xso.Reported()

        with self.assertRaisesRegex(ValueError, "empty report header"):
            obj.validate()

    def test_validate_reject_empty_items(self):
        f = forms_xso.Field()
        f.var = "foobar"

        obj = forms_xso.Data(forms_xso.DataType.RESULT)
        obj.reported = forms_xso.Reported()
        obj.reported.fields.append(f)

        obj.items.append(forms_xso.Item())

        with self.assertRaisesRegex(
                ValueError,
                "field mismatch between row and header"):
            obj.validate()

    def test_validate_reject_mismatching_items(self):
        f = forms_xso.Field()
        f.var = "foobar"

        obj = forms_xso.Data(forms_xso.DataType.RESULT)
        obj.reported = forms_xso.Reported()
        obj.reported.fields.append(f)

        f2 = forms_xso.Field()
        f2.var = "fnord"

        item = forms_xso.Item()
        item.fields.append(f2)
        obj.items.append(item)

        with self.assertRaisesRegex(
                ValueError,
                "field mismatch between row and header"):
            obj.validate()

    def test_data_attribute_on_Message(self):
        self.assertIsInstance(
            stanza.Message.xep0004_data,
            xso.ChildList,
        )
        self.assertSetEqual(
            stanza.Message.xep0004_data._classes,
            {
                forms_xso.Data,
            }
        )

    def test_get_form_type(self):
        d = forms_xso.Data(type_=forms_xso.DataType.FORM)
        d.fields.append(
            forms_xso.Field(),
        )
        d.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.HIDDEN,
                var="FORM_TYPE",
                values=[unittest.mock.sentinel.form_type]
            ),
        )
        d.fields.append(
            forms_xso.Field(),
        )

        self.assertEqual(
            d.get_form_type(),
            unittest.mock.sentinel.form_type,
        )

    def test_get_form_type_returns_none_without_FORM_TYPE(self):
        d = forms_xso.Data(type_=forms_xso.DataType.FORM)
        d.fields.append(
            forms_xso.Field(),
        )
        d.fields.append(
            forms_xso.Field(),
        )

        self.assertIsNone(
            d.get_form_type(),
        )

    def test_get_form_type_detects_incorrect_FORM_TYPE(self):
        d = forms_xso.Data(type_=forms_xso.DataType.FORM)
        d.fields.append(
            forms_xso.Field(),
        )
        d.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.TEXT_SINGLE,
                var="FORM_TYPE",
                values=[unittest.mock.sentinel.form_type]
            ),
        )
        d.fields.append(
            forms_xso.Field(),
        )

        self.assertIsNone(
            d.get_form_type(),
        )

    def test_get_form_type_copes_with_malformed_FORM_TYPE(self):
        d = forms_xso.Data(type_=forms_xso.DataType.FORM)
        d.fields.append(
            forms_xso.Field(),
        )
        d.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.HIDDEN,
                var="FORM_TYPE",
                values=[]
            ),
        )
        d.fields.append(
            forms_xso.Field(),
        )

        self.assertIsNone(
            d.get_form_type(),
        )

    def test_get_form_type_copes_with_too_many_values(self):
        d = forms_xso.Data(type_=forms_xso.DataType.FORM)
        d.fields.append(
            forms_xso.Field(),
        )
        d.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.HIDDEN,
                var="FORM_TYPE",
                values=["foo", "bar"]
            ),
        )
        d.fields.append(
            forms_xso.Field(),
        )

        self.assertIsNone(
            d.get_form_type(),
        )
