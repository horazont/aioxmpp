########################################################################
# File name: test_fields.py
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
import collections
import contextlib
import copy
import itertools
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.xso as xso

import aioxmpp.forms.fields as fields
import aioxmpp.forms.xso as forms_xso


TEST_JID = aioxmpp.JID.fromstr("foo@bar.baz/fnord")


def instance_mock():
    mock = unittest.mock.Mock()
    mock._descriptor_data = {}
    return mock


def generate_values(prefix):
    i = 0
    while True:
        yield getattr(unittest.mock.sentinel, prefix + str(i))
        i += 1


class TestBoundField(unittest.TestCase):
    class FakeBoundField(fields.BoundField):
        def load(self, field_xso):
            return super().load(field_xso)

        def render(self, **kwargs):
            return super().render(**kwargs)

    def setUp(self):
        self.field = unittest.mock.Mock()
        self.instance = unittest.mock.sentinel.instance
        self.bf = self.FakeBoundField(
            self.field,
            self.instance
        )

    def tearDown(self):
        del self.instance

    def test_is_abstract(self):
        with self.assertRaisesRegex(TypeError, r"abstract.* load, render"):
            fields.BoundField(unittest.mock.sentinel.foo,
                              unittest.mock.sentinel.bar)

    def test_repr(self):
        self.assertRegex(
            repr(self.bf),
            r"<bound <Mock .*> for sentinel\.instance at 0x[0-9a-f]+>"
        )

    def test_reading_desc_reads_from_field(self):
        self.assertEqual(
            self.bf.desc,
            self.field.desc,
        )

    def test_setting_desc_stores_locally(self):
        self.bf.desc = unittest.mock.sentinel.desc

        self.assertEqual(
            self.bf.desc,
            unittest.mock.sentinel.desc,
        )

        self.assertNotEqual(
            self.field.desc,
            unittest.mock.sentinel.desc,
        )

    def test_reading_label_reads_from_field(self):
        self.assertEqual(
            self.bf.label,
            self.field.label,
        )

    def test_setting_label_stores_locally(self):
        self.bf.label = unittest.mock.sentinel.label

        self.assertEqual(
            self.bf.label,
            unittest.mock.sentinel.label,
        )

        self.assertNotEqual(
            self.field.label,
            unittest.mock.sentinel.label,
        )

    def test_reading_required_reads_from_field(self):
        self.assertEqual(
            self.bf.required,
            self.field.required,
        )

    def test_setting_required_stores_locally(self):
        self.bf.required = unittest.mock.sentinel.required

        self.assertEqual(
            self.bf.required,
            unittest.mock.sentinel.required,
        )

        self.assertNotEqual(
            self.field.required,
            unittest.mock.sentinel.required,
        )

    def test_instance_is_settable(self):
        self.assertEqual(
            self.bf.instance,
            self.instance,
        )

        self.bf.instance = unittest.mock.sentinel.other_instance

        self.assertRegex(
            repr(self.bf),
            r"<bound <Mock .*> for sentinel\.other_instance at 0x[0-9a-f]+>"
        )

    def test_field_is_not(self):
        self.assertEqual(
            self.bf.field,
            self.field,
        )

        with self.assertRaises(AttributeError):
            self.bf.field = "foo"

    def test_deepcopy_leaves_instance_and_field_identical(self):
        self.bf.desc = ["foo"]

        copied = copy.deepcopy(self.bf)

        self.assertIsNot(copied.desc, self.bf.desc)

        self.assertIs(copied.instance, self.bf.instance)
        self.assertIs(copied.field, self.bf.field)

    def test_clone_for(self):
        with unittest.mock.patch("copy.deepcopy") as deepcopy:
            other_bf = self.bf.clone_for(
                unittest.mock.sentinel.other_instance
            )

        deepcopy.assert_called_with(self.bf)

        self.assertEqual(
            other_bf,
            deepcopy(),
        )

        self.assertEqual(
            other_bf.instance,
            unittest.mock.sentinel.other_instance,
        )

    def test_clone_for_passes_memo(self):
        with unittest.mock.patch("copy.deepcopy") as deepcopy:
            other_bf = self.bf.clone_for(
                unittest.mock.sentinel.other_instance,
                memo=unittest.mock.sentinel.memo,
            )

        deepcopy.assert_called_with(
            self.bf,
            unittest.mock.sentinel.memo
        )

        self.assertEqual(
            other_bf,
            deepcopy(),
        )

        self.assertEqual(
            other_bf.instance,
            unittest.mock.sentinel.other_instance,
        )

    def test_load_loads_desc(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            desc="foobar",
        )

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.desc,
            "foobar",
        )

    def test_load_leaves_desc_unmodified_if_unset(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
        )

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.desc,
            self.field.desc
        )

        self.bf.desc = "foobar"

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.desc,
            "foobar",
        )

    def test_load_loads_label(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            label="foobar"
        )

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.label,
            "foobar",
        )

    def test_load_leaves_label_unmodified_if_unset(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
        )

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.label,
            self.field.label
        )

        self.bf.label = "foobar"

        self.bf.load(field_xso)

        self.assertEqual(
            self.bf.label,
            "foobar",
        )

    def test_load_overrides_required(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            required=True,
        )

        self.bf.load(field_xso)

        self.assertIs(
            self.bf.required,
            True,
        )

        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            required=False,
        )

        self.bf.load(field_xso)

        self.assertIs(
            self.bf.required,
            False,
        )

    def test_render_defers_to_field_by_default(self):
        self.field.desc = "some description"
        self.field.label = "some label"
        self.field.required = unittest.mock.sentinel.required

        self.field.FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE
        self.field.var = "some var"

        field_xso = self.bf.render()

        self.assertIsInstance(
            field_xso,
            forms_xso.Field,
        )

        self.assertEqual(
            field_xso.var,
            self.field.var
        )

        self.assertEqual(
            field_xso.type_,
            self.field.FIELD_TYPE,
        )

        self.assertSequenceEqual(
            field_xso.values,
            []
        )

        self.assertEqual(
            field_xso.desc,
            "some description",
        )

        self.assertEqual(
            field_xso.label,
            "some label",
        )

        self.assertEqual(
            field_xso.required,
            unittest.mock.sentinel.required,
        )

        self.assertSequenceEqual(
            field_xso.options,
            [],
        )

    def test_render_uses_local_values(self):
        self.bf.desc = "some description"
        self.bf.label = "some label"
        self.bf.required = unittest.mock.sentinel.required

        self.field.FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE
        self.field.var = "some var"

        field_xso = self.bf.render(
            use_local_metadata=False
        )

        self.assertIsInstance(
            field_xso,
            forms_xso.Field,
        )

        self.assertEqual(
            field_xso.var,
            self.field.var
        )

        self.assertEqual(
            field_xso.type_,
            self.field.FIELD_TYPE,
        )

        self.assertSequenceEqual(
            field_xso.values,
            []
        )

        self.assertEqual(
            field_xso.desc,
            "some description",
        )

        self.assertEqual(
            field_xso.label,
            "some label",
        )

        self.assertEqual(
            field_xso.required,
            unittest.mock.sentinel.required,
        )

        self.assertSequenceEqual(
            field_xso.options,
            [],
        )

    def test_render_inhibit_inheritance_of_metadata(self):
        self.field.FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE
        self.field.var = "some var"

        field_xso = self.bf.render(
            use_local_metadata=False
        )

        self.assertIsInstance(
            field_xso,
            forms_xso.Field,
        )

        self.assertEqual(
            field_xso.var,
            self.field.var
        )

        self.assertEqual(
            field_xso.type_,
            self.field.FIELD_TYPE,
        )

        self.assertSequenceEqual(
            field_xso.values,
            []
        )

        self.assertIsNone(
            field_xso.desc,
        )

        self.assertIsNone(
            field_xso.label,
        )

        self.assertFalse(
            field_xso.required,
        )

        self.assertSequenceEqual(
            field_xso.options,
            [],
        )


class TestBoundSingleValueField(unittest.TestCase):
    def setUp(self):
        self.field = unittest.mock.Mock()
        self.instance = unittest.mock.sentinel.instance
        self.bf = fields.BoundSingleValueField(
            self.field,
            self.instance
        )

    def tearDown(self):
        del self.bf
        del self.instance
        del self.field

    def test_setting_value_uses_field_type(self):
        self.bf.value = unittest.mock.sentinel.value

        self.field.type_.coerce.assert_called_with(
            unittest.mock.sentinel.value,
        )

        self.assertEqual(
            self.bf.value,
            self.field.type_.coerce(),
        )

    def test_access_without_setting_calls_through_to_field(self):
        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertEqual(
            result,
            self.field.default(),
        )

    def test_deleting_reverts_to_initial_behaviour(self):
        self.bf.value = "foo"

        del self.bf.value
        del self.bf.value

        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertEqual(
            result,
            self.field.default(),
        )

    def test_load_loads_value_with_parse(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            values=[unittest.mock.sentinel.value],
        )

        self.bf.load(field_xso)

        self.field.type_.parse.assert_called_with(
            unittest.mock.sentinel.value,
        )

        self.assertEqual(
            self.bf.value,
            self.field.type_.parse(),
        )

    def test_load_defaults_if_no_values_present(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
        )

        self.bf.load(field_xso)

        self.field.default.assert_called_with()

        self.assertEqual(
            self.bf.value,
            self.field.default(),
        )

    def test_load_ignores_additional_values(self):
        field_xso = forms_xso.Field(
            type_=forms_xso.FieldType.TEXT_SINGLE,
            values=[1, 2, 3]
        )

        self.bf.load(field_xso)

    def test_load_calls_base_impl(self):
        field_xso = forms_xso.Field()

        with unittest.mock.patch.object(
                fields.BoundField, "load") as load:
            self.bf.load(field_xso)

        load.assert_called_with(field_xso)

    def test_render_creates_Field_xso(self):
        self.field.type_.coerce.return_value = unittest.mock.sentinel.coerced

        self.bf.value = unittest.mock.sentinel.value

        self.field.FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE
        self.field.var = "some var"

        self.field.type_.format.return_value = "formatted value"

        with unittest.mock.patch.object(
                fields.BoundField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.field.type_.format.assert_called_with(
            unittest.mock.sentinel.coerced,
        )

        self.assertSequenceEqual(
            field_xso.values,
            ["formatted value"]
        )

        self.assertSequenceEqual(
            field_xso.options,
            [],
        )


class TestBoundMultiValueField(unittest.TestCase):
    def setUp(self):
        self.field = unittest.mock.Mock()
        self.field.default.return_value = [
            unittest.mock.sentinel.v1,
            unittest.mock.sentinel.v2,
            unittest.mock.sentinel.v2,
        ]
        self.instance = unittest.mock.sentinel.instance
        self.bf = fields.BoundMultiValueField(
            self.field,
            self.instance,
        )

    def tearDown(self):
        del self.bf
        del self.instance
        del self.field

    def test_is_bound_field(self):
        self.assertTrue(issubclass(
            fields.BoundMultiValueField,
            fields.BoundField
        ))

    def test_access_without_set_delegates_to_field_and_cast_to_tuple(self):
        self.field.type_.coerce.side_effect = generate_values("c")

        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertSequenceEqual(
            self.field.type_.coerce.mock_calls,
            [
                unittest.mock.call(unittest.mock.sentinel.v1),
                unittest.mock.call(unittest.mock.sentinel.v2),
                unittest.mock.call(unittest.mock.sentinel.v2),
            ]
        )

        self.assertSequenceEqual(
            result,
            [
                unittest.mock.sentinel.c0,
                unittest.mock.sentinel.c1,
                unittest.mock.sentinel.c2,
            ]
        )

        self.assertIsInstance(
            result,
            tuple,
        )

    def test_setting_field_coerces_and_casts_to_tuple(self):
        self.field.type_.coerce.side_effect = generate_values("c")

        self.bf.value = [1, 2, 3]

        self.assertSequenceEqual(
            self.field.type_.coerce.mock_calls,
            [
                unittest.mock.call(1),
                unittest.mock.call(2),
                unittest.mock.call(3),
            ]
        )

        self.assertSequenceEqual(
            self.bf.value,
            [
                unittest.mock.sentinel.c0,
                unittest.mock.sentinel.c1,
                unittest.mock.sentinel.c2,
            ]
        )

        self.assertIsInstance(
            self.bf.value,
            tuple,
        )

    def test_deleting_reverts_to_initial_behaviour(self):
        self.field.type_.coerce.side_effect = lambda x: x

        self.bf.value = ["foo", "bar"]

        del self.bf.value
        del self.bf.value

        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertSequenceEqual(
            result,
            self.field.default(),
        )

    def test_load_parses_values(self):
        values = ["10", "20", "30"]
        field_xso = forms_xso.Field(
            values=list(values),
        )

        self.field.type_.parse.side_effect = generate_values("parsed")

        self.bf.load(field_xso)

        self.assertSequenceEqual(
            self.field.type_.mock_calls,
            [
                unittest.mock.call.parse(v)
                for v in values
            ]
        )

        self.assertSequenceEqual(
            self.bf.value,
            [
                getattr(unittest.mock.sentinel, "parsed{}".format(i))
                for i in range(3)
            ]
        )

    def test_load_calls_base_impl(self):
        field_xso = forms_xso.Field()

        with unittest.mock.patch.object(
                fields.BoundField, "load") as load:
            self.bf.load(field_xso)

        load.assert_called_with(field_xso)

    def test_render_creates_Field_xso(self):
        def generate_coerced_values():
            i = 0
            while True:
                yield getattr(unittest.mock.sentinel, "coerced{}".format(i))
                i += 1

        def generate_formatted_values():
            i = 0
            while True:
                yield "value {}".format(i)
                i += 1

        self.field.type_.format.side_effect = generate_formatted_values()
        self.field.type_.coerce.side_effect = generate_coerced_values()

        self.bf.value = [
            1, 2, 3
        ]

        self.field.FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE
        self.field.var = "some var"

        with unittest.mock.patch.object(
                fields.BoundField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.assertSequenceEqual(
            self.field.type_.format.mock_calls,
            [
                unittest.mock.call(getattr(unittest.mock.sentinel,
                                           "coerced{}".format(i)))
                for i in range(3)
            ]
        )

        self.assertSequenceEqual(
            field_xso.values,
            ["value 0", "value 1", "value 2"]
        )

        self.assertSequenceEqual(
            field_xso.options,
            [],
        )


class TestBoundOptionsField(unittest.TestCase):
    def setUp(self):
        self.field = unittest.mock.Mock()
        self.field.options = collections.OrderedDict([
            ("foo", "The Foo"),
            ("bar", "The Bar"),
            ("baz", "The Baz"),
        ])
        self.instance = unittest.mock.sentinel.instance
        self.bf = fields.BoundOptionsField(
            self.field,
            self.instance,
        )

    def tearDown(self):
        del self.bf
        del self.instance
        del self.field

    def test_is_bound_field(self):
        self.assertTrue(issubclass(
            fields.BoundOptionsField,
            fields.BoundField
        ))

    def test_options_calls_through_to_field(self):
        self.assertEqual(
            self.bf.options,
            self.field.options,
        )

        self.field.options = unittest.mock.sentinel.options

        self.assertEqual(
            self.bf.options,
            self.field.options,
        )

    def test_setting_options_evaluates_into_ordered_dict_with_coerce(self):
        self.field.type_.coerce.side_effect = generate_values("coerced")

        options = (
            (0, "foo"),
            (1, "bar"),
            (2, "baz")
        )

        self.bf.options = options

        self.assertSequenceEqual(
            tuple(self.bf.options.keys()),
            [getattr(unittest.mock.sentinel, "coerced{}".format(i))
             for i, (k, v) in enumerate(options)]
        )

        self.assertDictEqual(
            self.bf.options,
            collections.OrderedDict([
                (getattr(unittest.mock.sentinel, "coerced{}".format(i)), v)
                for i, (k, v) in enumerate(options)
            ]),
        )

    def test_delete_resets_options_to_field(self):
        self.bf.options = []

        self.assertDictEqual(
            self.bf.options,
            {},
        )

        del self.bf.options
        del self.bf.options

        self.assertEqual(
            self.bf.options,
            self.field.options,
        )

    def test_load_loads_options_using_parse(self):
        options = (
            ("1", "First"),
            ("2", "Second"),
            ("3", "Third"),
        )

        field_xso = forms_xso.Field(
            options=options,
        )

        self.bf.load(field_xso)

        self.assertDictEqual(
            self.bf.options,
            collections.OrderedDict(options),
        )

        self.assertSequenceEqual(
            tuple(self.bf.options.keys()),
            [k for k, v in options]
        )

    def test_load_calls_base_impl(self):
        field_xso = forms_xso.Field()

        with unittest.mock.patch.object(
                fields.BoundField, "load") as load:
            self.bf.load(field_xso)

        load.assert_called_with(field_xso)

    def test_render_emits_base_options_using_format(self):
        self.field.type_.format.side_effect = str
        self.field.default.return_value = None

        with unittest.mock.patch.object(
                fields.BoundField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.assertSequenceEqual(
            self.field.type_.format.mock_calls,
            [
                unittest.mock.call(k)
                for k in self.field.options.keys()
            ]
        )

        self.assertDictEqual(
            field_xso.options,
            self.field.options
        )

    def test_render_emits_overridden_options_using_format(self):
        self.field.type_.coerce.side_effect = int
        self.field.type_.format.side_effect = str
        self.field.default.return_value = None

        self.bf.options = [(1, "foo")]

        with unittest.mock.patch.object(
                fields.BoundField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.field.type_.format.assert_called_with(
            1
        )

        self.assertDictEqual(
            field_xso.options,
            {"1": "foo"}
        )


class TestBoundSelectField(unittest.TestCase):
    def setUp(self):
        self.field = unittest.mock.Mock()
        self.field.options = collections.OrderedDict([
            ("foo", "The Foo"),
            ("bar", "The Bar"),
            ("baz", "The Baz"),
        ])
        self.instance = unittest.mock.sentinel.instance
        self.bf = fields.BoundSelectField(
            self.field,
            self.instance,
        )

    def tearDown(self):
        del self.bf
        del self.instance
        del self.field

    def test_is_bound_options_field(self):
        self.assertTrue(issubclass(
            fields.BoundSelectField,
            fields.BoundOptionsField
        ))

    def test_access_without_setting_calls_through_to_field(self):
        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertEqual(
            result,
            self.field.default(),
        )

    def test_setting_value_enforces_membership_in_options(self):
        with self.assertRaisesRegex(
                ValueError,
                r"not in field options: \('foo', 'bar', 'baz'\)"):
            self.bf.value = "fnord"

    def test_setting_value_with_correct_option_allowed(self):
        self.bf.value = "foo"
        self.assertEqual(
            self.bf.value,
            "foo",
        )

    def test_deleting_reverts_to_initial_behaviour(self):
        self.bf.value = "foo"

        del self.bf.value
        del self.bf.value

        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertEqual(
            result,
            self.field.default(),
        )

    def test_load_loads_value_with_parse(self):
        field_xso = forms_xso.Field(
            values=["x", "fnord", "1"],
        )

        self.bf.load(field_xso)

        self.field.type_.parse.assert_called_with("x")

        self.assertEqual(
            self.bf.value,
            self.field.type_.parse(),
        )

    def test_load_calls_base_impl(self):
        field_xso = forms_xso.Field()

        with unittest.mock.patch.object(
                fields.BoundOptionsField, "load") as load:
            self.bf.load(field_xso)

        load.assert_called_with(field_xso)

    def test_render_emits_no_value_if_None(self):
        self.field.default.return_value = None

        with unittest.mock.patch.object(
                fields.BoundOptionsField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.assertSequenceEqual(
            field_xso.values,
            [],
        )

    def test_render_emits_selected_value_with_format(self):
        self.field.options = {1: "foo"}
        self.field.type_.format.side_effect = str

        self.bf.value = 1

        with unittest.mock.patch.object(
                fields.BoundOptionsField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag,
        )

        self.field.type_.format.assert_called_with(1)

        self.assertSequenceEqual(
            field_xso.values,
            ["1"],
        )


class TestBoundMultiSelectField(unittest.TestCase):
    def setUp(self):
        self.field = unittest.mock.Mock()
        self.field.options = collections.OrderedDict([
            ("foo", "The Foo"),
            ("bar", "The Bar"),
            ("baz", "The Baz"),
        ])
        self.field.default.return_value = []
        self.instance = unittest.mock.sentinel.instance
        self.bf = fields.BoundMultiSelectField(
            self.field,
            self.instance,
        )

    def tearDown(self):
        del self.bf
        del self.instance
        del self.field

    def test_is_bound_options_field(self):
        self.assertTrue(issubclass(
            fields.BoundMultiSelectField,
            fields.BoundOptionsField
        ))

    def test_access_without_setting_calls_through_to_field(self):
        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertSetEqual(
            set(result),
            set(self.field.default()),
        )

    def test_setting_value_enforces_membership_in_options(self):
        with self.assertRaisesRegex(
                ValueError,
                r"not in field options: \('foo', 'bar', 'baz'\)"):
            self.bf.value = {"fnord"}

    def test_setting_value_with_correct_option_allowed(self):
        self.bf.value = ["foo", "bar"]
        self.assertSetEqual(
            self.bf.value,
            {"foo", "bar"},
        )

        self.assertIsInstance(
            self.bf.value,
            frozenset,
        )

    def test_deleting_reverts_to_initial_behaviour(self):
        self.bf.value = ["foo", "baz"]

        del self.bf.value
        del self.bf.value

        result = self.bf.value

        self.field.default.assert_called_with()

        self.assertSetEqual(
            set(result),
            set(self.field.default()),
        )

    def test_load_loads_values_with_parse(self):
        values = ["x", "fnord", "1"]

        self.field.type_.parse.side_effect = generate_values("parsed")

        field_xso = forms_xso.Field(
            values=values,
        )

        self.bf.load(field_xso)

        self.assertSequenceEqual(
            self.field.type_.parse.mock_calls,
            [
                unittest.mock.call("x"),
                unittest.mock.call("fnord"),
                unittest.mock.call("1"),
            ]
        )

        self.assertSetEqual(
            self.bf.value,
            set(itertools.islice(generate_values("parsed"), 3))
        )

    def test_load_calls_base_impl(self):
        field_xso = forms_xso.Field()

        with unittest.mock.patch.object(
                fields.BoundOptionsField, "load") as load:
            self.bf.load(field_xso)

        load.assert_called_with(field_xso)

    def test_render_emits_values_with_format(self):
        self.field.type_.format.side_effect = generate_values("formatted")

        self.bf.value = {"foo", "bar"}

        with unittest.mock.patch.object(
                fields.BoundOptionsField,
                "render") as render:
            render.return_value = forms_xso.Field()
            field_xso = self.bf.render(
                use_local_metadata=unittest.mock.sentinel.flag
            )

        render.assert_called_with(
            use_local_metadata=unittest.mock.sentinel.flag
        )

        self.assertSetEqual(
            {
                arg
                for _, (arg, ), _ in self.field.type_.format.mock_calls
            },
            {
                "foo", "bar"
            }
        )

        self.assertSetEqual(
            set(field_xso.values),
            {
                unittest.mock.sentinel.formatted0,
                unittest.mock.sentinel.formatted1,
            }
        )


class TestAbstractDescriptor(unittest.TestCase):
    def test_uses_abcmeta(self):
        self.assertIsInstance(
            fields.AbstractDescriptor,
            abc.ABCMeta,
        )

    def test_is_abstract(self):
        with self.assertRaisesRegex(TypeError, "descriptor_keys"):
            fields.AbstractDescriptor()


class TestAbstractField(unittest.TestCase):
    class FakeField(fields.AbstractField):
        FIELD_TYPE = forms_xso.FieldType.HIDDEN

        def __init__(self, var, type_=xso.String(), *args, **kwargs):
            super().__init__(var, type_, *args, **kwargs)

        def create_bound(self, for_instance):
            pass

        def default(self):
            pass

    def setUp(self):
        self.f = self.FakeField(unittest.mock.sentinel.var)
        self.instance = unittest.mock.Mock()
        self.instance._descriptor_data = {}

    def tearDown(self):
        del self.instance
        del self.f

    def test_init(self):
        f = self.FakeField(unittest.mock.sentinel.var)
        self.assertFalse(f.required)
        self.assertIsNone(f.desc)
        self.assertIsNone(f.label)
        self.assertEqual(f.var, unittest.mock.sentinel.var)

    def test_init_required(self):
        f = self.FakeField(unittest.mock.sentinel.var,
                           required=True)
        self.assertTrue(f.required)

    def test_init_desc(self):
        desc = "foobar"
        f = self.FakeField(unittest.mock.sentinel.var,
                           desc=desc)
        self.assertEqual(f.desc, desc)

    def test_init_label(self):
        f = self.FakeField(unittest.mock.sentinel.var,
                           label="foobar")
        self.assertEqual(f.label, "foobar")

    def test_init_rejects_desc_with_newlines(self):
        regex = r"desc must not contain newlines"

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(unittest.mock.sentinel.var,
                           desc="foo\r")

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(unittest.mock.sentinel.var,
                           desc="foo\nbar")

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(unittest.mock.sentinel.var,
                           desc="foo\r\nbar")

    def test_setting_desc_rejects_desc_with_newlines(self):
        regex = r"desc must not contain newlines"

        with self.assertRaisesRegex(ValueError, regex):
            self.f.desc = "foo\r"

        with self.assertRaisesRegex(ValueError, regex):
            self.f.desc = "foo\nbar"

        with self.assertRaisesRegex(ValueError, regex):
            self.f.desc = "foo\r\nbar"

    def test_type_is_not_writable(self):
        t = self.f.type_
        with self.assertRaises(AttributeError):
            self.f.type_ = t

    def test_init_type(self):
        f = self.FakeField("var", unittest.mock.sentinel.type_)
        self.assertEqual(
            f.type_,
            unittest.mock.sentinel.type_
        )

    def test_deleting_desc_sets_it_to_None(self):
        f = self.FakeField(unittest.mock.sentinel.var, desc="foobar")
        del f.desc
        self.assertIsNone(f.desc)

    def test_descriptor_keys(self):
        self.assertSequenceEqual(
            list(self.f.descriptor_keys()),
            [
                (fields.descriptor_ns, unittest.mock.sentinel.var),
            ]
        )

    def test_var_is_not_settable(self):
        with self.assertRaises(AttributeError):
            self.f.var = "foo"

    def test_make_bound_creates_new_and_stores_at_instance(self):
        with unittest.mock.patch.object(
                self.f,
                "create_bound") as create_bound:
            result = self.f.make_bound(self.instance)

        create_bound.assert_called_with(self.instance)

        self.assertEqual(
            result,
            create_bound(),
        )

        self.assertDictEqual(
            self.instance._descriptor_data,
            {
                self.f: result,
            }
        )

    def test_make_bound_returns_field_stored_at_instance(self):
        self.instance._descriptor_data[self.f] = \
            unittest.mock.sentinel.existing

        with unittest.mock.patch.object(
                self.f,
                "create_bound") as create_bound:
            result = self.f.make_bound(self.instance)

        self.assertFalse(create_bound.mock_calls)

        self.assertEqual(
            result,
            unittest.mock.sentinel.existing,
        )

        self.assertDictEqual(
            self.instance._descriptor_data,
            {
                self.f: unittest.mock.sentinel.existing,
            }
        )

    def test___get___uses_make_bound_and_returns(self):
        with unittest.mock.patch.object(
                self.f,
                "make_bound") as make_bound:
            result = self.f.__get__(self.instance, type(self.instance))

        make_bound.assert_called_with(self.instance)

        self.assertEqual(
            result,
            make_bound(),
        )

    def test___get___returns_self_for_None_instance(self):
        result = self.f.__get__(None, type(self.instance))

        self.assertIs(
            result,
            self.f,
        )


class TestTextSingle(unittest.TestCase):
    def setUp(self):
        self.f = fields.TextSingle(var="muc#foobar")

    def tearDown(self):
        del self.f

    def test_is_abstract_field(self):
        self.assertTrue(issubclass(
            fields.TextSingle,
            fields.AbstractField,
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.TextSingle.FIELD_TYPE,
            forms_xso.FieldType.TEXT_SINGLE,
        )

    def test_init(self):
        t = object()
        f = fields.TextSingle(var="muc#foobar", type_=t)
        self.assertEqual(f.var, "muc#foobar")
        self.assertIs(f.type_, t)

        f = fields.TextSingle("muc#foobar")
        self.assertEqual(f.var, "muc#foobar")

        with self.assertRaisesRegex(TypeError, "argument"):
            fields.TextSingle()

    def test_init_passes_to_abstract_field(self):
        f = fields.TextSingle(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_creates_single_value_bound(self):
        mock = instance_mock()
        with contextlib.ExitStack() as stack:
            BoundSingleValueField = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.forms.fields.BoundSingleValueField"
                )
            )

            result = self.f.create_bound(mock)

        BoundSingleValueField.assert_called_with(
            self.f,
            mock,
        )

        self.assertEqual(
            result,
            BoundSingleValueField(),
        )


class TestJIDSingle(unittest.TestCase):
    def setUp(self):
        self.f = fields.JIDSingle(var="muc#foobar")

    def tearDown(self):
        del self.f

    def test_is_abstract_field(self):
        self.assertTrue(issubclass(
            fields.JIDSingle,
            fields.AbstractField
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.JIDSingle.FIELD_TYPE,
            forms_xso.FieldType.JID_SINGLE,
        )

    def test_type_is_JID(self):
        f = fields.JIDSingle("foo")
        self.assertIsInstance(f.type_, xso.JID)

    def test_init_still_rejects_type__argument(self):
        t = object()
        with self.assertRaisesRegex(TypeError, "type_"):
            fields.JIDSingle("foo", type_=t)

    def test_init_passes_to_abstract_field(self):
        f = fields.JIDSingle(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_init_default(self):
        self.assertIsNone(self.f.default())

        f = fields.JIDSingle("foo", default=TEST_JID)

        self.assertEqual(
            f.default(),
            TEST_JID,
        )

    def test_creates_single_value_bound(self):
        mock = instance_mock()
        with contextlib.ExitStack() as stack:
            BoundSingleValueField = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.forms.fields.BoundSingleValueField"
                )
            )

            result = self.f.create_bound(mock)

        BoundSingleValueField.assert_called_with(
            self.f,
            mock,
        )

        self.assertEqual(
            result,
            BoundSingleValueField(),
        )


class TestBoolean(unittest.TestCase):
    def setUp(self):
        self.f = fields.Boolean(var="muc#foobar")

    def tearDown(self):
        del self.f

    def test_is_abstract_field(self):
        self.assertTrue(issubclass(
            fields.Boolean,
            fields.AbstractField
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.Boolean.FIELD_TYPE,
            forms_xso.FieldType.BOOLEAN,
        )

    def test_type_is_Bool(self):
        f = fields.Boolean("foo")
        self.assertIsInstance(f.type_, xso.Bool)

    def test_init_rejects_type__argument(self):
        t = object()
        with self.assertRaisesRegex(TypeError, "type_"):
            fields.Boolean("foo", type_=t)

    def test_init_passes_to_abstract_field(self):
        f = fields.Boolean(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_default_default(self):
        self.assertEqual(
            fields.Boolean("foo").default(),
            False,
        )

    def test_creates_single_value_bound(self):
        mock = instance_mock()
        with contextlib.ExitStack() as stack:
            BoundSingleValueField = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.forms.fields.BoundSingleValueField"
                )
            )

            result = self.f.create_bound(mock)

        BoundSingleValueField.assert_called_with(
            self.f,
            mock,
        )

        self.assertEqual(
            result,
            BoundSingleValueField(),
        )


class TestTextPrivate(unittest.TestCase):
    def test_is_text_single(self):
        self.assertTrue(issubclass(
            fields.TextPrivate,
            fields.TextSingle
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.TextPrivate.FIELD_TYPE,
            forms_xso.FieldType.TEXT_PRIVATE,
        )

    def test_init_still_accepts_type__argument(self):
        t = object()
        f = fields.TextPrivate("foo", type_=t)
        self.assertIs(f.type_, t)

    def test_init_passes_to_abstract_field(self):
        f = fields.TextPrivate(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")


class TestTextMulti(unittest.TestCase):
    def setUp(self):
        self.f = fields.TextMulti("foo")

    def tearDown(self):
        del self.f

    def test_field_type(self):
        self.assertEqual(
            fields.TextMulti.FIELD_TYPE,
            forms_xso.FieldType.TEXT_MULTI,
        )

    def test_is_abstract_field(self):
        self.assertTrue(
            issubclass(
                fields.TextMulti,
                fields.AbstractField,
            )
        )

    def test_init(self):
        t = object()
        f = fields.TextMulti(var="muc#foobar", type_=t)
        self.assertEqual(f.var, "muc#foobar")
        self.assertIs(f.type_, t)

        f = fields.TextMulti("muc#foobar")
        self.assertEqual(f.var, "muc#foobar")
        self.assertIsInstance(f.type_, xso.String)

        with self.assertRaisesRegex(TypeError, "argument"):
            fields.TextMulti()

    def test_init_passes_to_abstract_field(self):
        f = fields.TextMulti(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_type_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.f.type_ = self.f.type_

    def test_init_default(self):
        f = fields.TextMulti(
            var="muc#foobar",
            default=unittest.mock.sentinel.default
        )
        self.assertEqual(
            f.default(),
            unittest.mock.sentinel.default
        )

    def test_init_default_default(self):
        f = fields.TextMulti(
            var="muc#foobar",
        )
        self.assertEqual(
            f.default(),
            ()
        )

    def test_create_bound_creates_multi_value_field(self):
        with contextlib.ExitStack() as stack:
            BoundMultiValueField = stack.enter_context(unittest.mock.patch(
                "aioxmpp.forms.fields.BoundMultiValueField"
            ))

            result = self.f.create_bound(
                unittest.mock.sentinel.instance
            )

        BoundMultiValueField.assert_called_with(
            self.f,
            unittest.mock.sentinel.instance,
        )

        self.assertEqual(
            result,
            BoundMultiValueField(),
        )


class TestJIDMulti(unittest.TestCase):
    def setUp(self):
        self.f = fields.JIDMulti("foo")

    def tearDown(self):
        del self.f

    def test_is_abstract_field(self):
        self.assertTrue(
            issubclass(
                fields.JIDMulti,
                fields.AbstractField,
            )
        )

    def test_type_(self):
        self.assertIsInstance(
            self.f.type_,
            xso.JID,
        )

    def test_field_type(self):
        self.assertEqual(
            fields.JIDMulti.FIELD_TYPE,
            forms_xso.FieldType.JID_MULTI,
        )

    def test_create_bound_creates_multi_value_field(self):
        with contextlib.ExitStack() as stack:
            BoundMultiValueField = stack.enter_context(unittest.mock.patch(
                "aioxmpp.forms.fields.BoundMultiValueField"
            ))

            result = self.f.create_bound(
                unittest.mock.sentinel.instance
            )

        BoundMultiValueField.assert_called_with(
            self.f,
            unittest.mock.sentinel.instance,
        )

        self.assertEqual(
            result,
            BoundMultiValueField(),
        )


class TestAbstractChoiceField(unittest.TestCase):
    class FakeChoiceField(fields.AbstractChoiceField):
        FIELD_TYPE = forms_xso.FieldType.HIDDEN

        def create_bound(self, for_instance):
            pass

        def default(self):
            pass

    def setUp(self):
        self.f = self.FakeChoiceField("var")

    def tearDown(self):
        del self.f

    def test_is_abstract_field(self):
        self.assertTrue(issubclass(
            fields.AbstractChoiceField,
            fields.AbstractField,
        ))

    def test_is_abstract(self):
        with self.assertRaisesRegex(
                TypeError,
                r"abstract.* create_bound, default"):
            fields.AbstractChoiceField()

    def test_init_options_with_coerce(self):
        type_ = unittest.mock.Mock()
        type_.coerce.side_effect = generate_values("coerced")

        f = self.FakeChoiceField(
            "var",
            options=[
                ("1", "foo"),
                ("2", "bar"),
                ("3", "baz"),
            ],
            type_=type_
        )

        self.assertSequenceEqual(
            type_.coerce.mock_calls,
            [
                unittest.mock.call("1"),
                unittest.mock.call("2"),
                unittest.mock.call("3"),
            ]
        )

        self.assertDictEqual(
            f.options,
            {
                unittest.mock.sentinel.coerced0: "foo",
                unittest.mock.sentinel.coerced1: "bar",
                unittest.mock.sentinel.coerced2: "baz",
            }
        )

        self.assertSequenceEqual(
            tuple(f.options.keys()),
            list(itertools.islice(generate_values("coerced"), 3))
        )

        self.assertIsInstance(
            f.options,
            collections.OrderedDict,
        )

    def test_init_default_default(self):
        self.assertIsNone(self.f.default())

    def test_init_type(self):
        t = object()
        f = self.FakeChoiceField("foo", type_=t)
        self.assertIs(f.type_, t)

    def test_type_is_not_settable(self):
        with self.assertRaises(AttributeError):
            self.f.type_ = xso.JID()


class TestListSingle(unittest.TestCase):
    def setUp(self):
        self.f = fields.ListSingle(
            "var",
            options=[
                ("foo", "The Foo"),
                ("bar", "The Bar"),
                ("baz", "The Baz"),
            ]
        )

    def tearDown(self):
        del self.f

    def test_is_abstract_choice_field(self):
        self.assertTrue(issubclass(
            fields.ListSingle,
            fields.AbstractChoiceField
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.ListSingle.FIELD_TYPE,
            forms_xso.FieldType.LIST_SINGLE
        )

    def test_init_default_default(self):
        self.assertIsNone(self.f.default())

    def test_init_default_rejects_not_None_default_not_in_options(self):
        with self.assertRaisesRegex(ValueError,
                                    r"invalid default: not in options"):
            fields.ListSingle(
                "var",
                options=[("foo", "The Foo")],
                default="bar",
            )

    def test_init_default(self):
        f = fields.ListSingle(
            "var",
            options=[("foo", "The Foo")],
            default="foo",
        )

        self.assertEqual(
            f.default(),
            "foo",
        )

    def test_create_bound_creates_BoundSelectField(self):
        with contextlib.ExitStack() as stack:
            BoundSelectField = stack.enter_context(
                unittest.mock.patch("aioxmpp.forms.fields.BoundSelectField")
            )

            result = self.f.create_bound(unittest.mock.sentinel.instance)

        BoundSelectField.assert_called_with(
            self.f,
            unittest.mock.sentinel.instance,
        )

        self.assertEqual(
            result,
            BoundSelectField(),
        )


class TestListMulti(unittest.TestCase):
    def setUp(self):
        self.f = fields.ListMulti(
            "var",
            options=[
                ("foo", "The Foo"),
                ("bar", "The Bar"),
                ("baz", "The Baz"),
            ]
        )

    def tearDown(self):
        del self.f

    def test_is_abstract_choice_field(self):
        self.assertTrue(issubclass(
            fields.ListMulti,
            fields.AbstractChoiceField
        ))

    def test_field_type(self):
        self.assertEqual(
            fields.ListMulti.FIELD_TYPE,
            forms_xso.FieldType.LIST_MULTI
        )

    def test_init_default_default(self):
        self.assertSetEqual(
            self.f.default(),
            set(),
        )

    def test_init_default(self):
        f = fields.ListMulti(
            "var",
            options=self.f.options,
            default={"foo", "baz"}
        )

        self.assertSetEqual(
            f.default(),
            {"foo", "baz"}
        )

        self.assertIsInstance(
            f.default(),
            frozenset,
        )

    def test_init_rejects_default_with_values_not_in_options(self):
        with self.assertRaisesRegex(ValueError,
                                    r"invalid default: not in options"):
            fields.ListMulti(
                "var",
                options=[("foo", "The Foo")],
                default={"foo", "bar"},
            )

    def test_create_bound_creates_BoundMultiSelectField(self):
        with contextlib.ExitStack() as stack:
            BoundMultiSelectField = stack.enter_context(
                unittest.mock.patch("aioxmpp.forms.fields.BoundMultiSelectField")
            )

            result = self.f.create_bound(unittest.mock.sentinel.instance)

        BoundMultiSelectField.assert_called_with(
            self.f,
            unittest.mock.sentinel.instance,
        )

        self.assertEqual(
            result,
            BoundMultiSelectField(),
        )
