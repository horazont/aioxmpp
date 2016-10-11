########################################################################
# File name: test_form.py
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
import copy
import unittest
import unittest.mock

import aioxmpp

import aioxmpp.forms.fields as fields
import aioxmpp.forms.form as form
import aioxmpp.forms.xso as forms_xso


class FakeDescriptor(fields.AbstractDescriptor):
    def __init__(self, key):
        self._keys = [key]

    def descriptor_keys(self):
        return self._keys


class TestDescriptorClass(unittest.TestCase):
    def test_is_abcmeta(self):
        self.assertTrue(issubclass(
            form.DescriptorClass,
            abc.ABCMeta,
        ))

    def test_init(self):
        class Cls(metaclass=form.DescriptorClass):
            pass

        self.assertDictEqual(
            Cls.DESCRIPTOR_MAP,
            {},
        )

        self.assertSequenceEqual(
            list(Cls.DESCRIPTORS),
            [],
        )

        self.assertSequenceEqual(
            Cls.__slots__,
            (),
        )

    def test_use_slots_from_declaration(self):
        class Cls(metaclass=form.DescriptorClass):
            __slots__ = ("foo", )

        self.assertSequenceEqual(
            Cls.__slots__,
            ("foo",)
        )

    def test_inherit_slots(self):
        class Base(metaclass=form.DescriptorClass):
            __slots__ = ("foo", )

        class Child(Base):
            pass

        self.assertSequenceEqual(
            Child.__slots__,
            ()
        )

    def test_disable_slots_via_kwarg(self):
        class Cls(metaclass=form.DescriptorClass, protect=False):
            pass

        self.assertFalse(hasattr(Cls, "__slots__"))

    def test_collect_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor(("foo", "bar"))
            x2 = FakeDescriptor(("baz",))

        self.assertDictEqual(
            Cls.DESCRIPTOR_MAP,
            {
                ("foo", "bar"): Cls.x1,
                ("baz", ): Cls.x2,
            }
        )

        self.assertSetEqual(
            set(Cls.DESCRIPTORS),
            {
                Cls.x1,
                Cls.x2,
            }
        )

    def test_single_inheritance(self):
        class ClsA(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        class ClsB(ClsA):
            x2 = FakeDescriptor("x2")

        self.assertDictEqual(
            ClsA.DESCRIPTOR_MAP,
            {
                "x1": ClsA.x1,
            }
        )

        self.assertSetEqual(
            ClsA.DESCRIPTORS,
            {
                ClsA.x1,
            }
        )

        self.assertDictEqual(
            ClsB.DESCRIPTOR_MAP,
            {
                "x1": ClsA.x1,
                "x2": ClsB.x2,
            }
        )

        self.assertSetEqual(
            ClsB.DESCRIPTORS,
            {
                ClsA.x1,
                ClsB.x2,
            }
        )

    def test_multi_inheritance(self):
        class ClsA(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        class ClsB(ClsA):
            x2 = FakeDescriptor("x2")

        class ClsC(ClsA):
            x3 = FakeDescriptor("x3")

        class ClsD(ClsB, ClsC):
            x4 = FakeDescriptor("x4")

        self.assertDictEqual(
            ClsD.DESCRIPTOR_MAP,
            {
                "x1": ClsD.x1,
                "x2": ClsD.x2,
                "x3": ClsD.x3,
                "x4": ClsD.x4,
            }
        )

        self.assertSetEqual(
            ClsD.DESCRIPTORS,
            {
                ClsD.x1,
                ClsD.x2,
                ClsD.x3,
                ClsD.x4,
            }
        )

    def test_reject_conflicts(self):
        with self.assertRaisesRegex(
                TypeError,
                "descriptor with key .* already declared at .*"):
            class ClsA(metaclass=form.DescriptorClass):
                x1 = FakeDescriptor("x1")
                x2 = FakeDescriptor("x1")

    def test_reject_conflicts_at_multi_inheritance(self):
        class ClsA(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        class ClsB(metaclass=form.DescriptorClass):
            x2 = FakeDescriptor("x1")

        with self.assertRaisesRegex(
                TypeError,
                "descriptor with key .* already declared at .*"):
            class ClsC(ClsA, ClsB):
                pass

    def test_late_addition_of_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        Cls.x2 = FakeDescriptor("bar")

        self.assertDictEqual(
            Cls.DESCRIPTOR_MAP,
            {
                "foo": Cls.x1,
                "bar": Cls.x2,
            }
        )

        self.assertSetEqual(
            Cls.DESCRIPTORS,
            {
                Cls.x1,
                Cls.x2,
            }
        )

    def test_reject_conflict_on_late_addition_of_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        with self.assertRaisesRegex(
                TypeError,
                r"descriptor with key .* already declared at .*"):
            Cls.x2 = FakeDescriptor("foo")

        self.assertDictEqual(
            Cls.DESCRIPTOR_MAP,
            {
                "foo": Cls.x1,
            }
        )

        self.assertSetEqual(
            Cls.DESCRIPTORS,
            {
                Cls.x1,
            }
        )

    def test_reject_late_addition_for_subclassed(self):
        class ClsA(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        class ClsB(ClsA):
            pass

        with self.assertRaisesRegex(
                TypeError,
                r"cannot add descriptors to classes with subclasses"):
            ClsA.x2 = FakeDescriptor("bar")

    def test_reject_removal_of_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        with self.assertRaisesRegex(
                AttributeError,
                r"removal of descriptors is not allowed"):
            del Cls.x1

    def test_allow_removal_of_other_attributes(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")
            x2 = "foo"

        del Cls.x2
        self.assertFalse(hasattr(Cls, "x2"))

    def test_reject_overwriting_descriptor_attribute(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        with self.assertRaisesRegex(
                AttributeError,
                r"descriptor attributes cannot be set"):
            Cls.x1 = "foo"

    def test_allow_setting_and_overwriting_other_attributes(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("x1")

        Cls.x2 = "foo"
        Cls.x3 = "bar"
        Cls.x2 = 10

    def test_set_attribute_name_on_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")
            x2 = FakeDescriptor("bar")

        self.assertEqual(Cls.x1.attribute_name, "x1")
        self.assertEqual(Cls.x2.attribute_name, "x2")

    def test_set_root_class_on_descriptors(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")
            x2 = FakeDescriptor("bar")

        self.assertIs(Cls.x1.root_class, Cls)
        self.assertIs(Cls.x2.root_class, Cls)

    def test_reject_descriptor_used_twice(self):
        d = FakeDescriptor("foo")

        class ClsA(metaclass=form.DescriptorClass):
            x1 = d

        with self.assertRaisesRegex(
                ValueError,
                r"descriptor cannot be used on multiple classes"):
            class ClsB(metaclass=form.DescriptorClass):
                x1 = d

    def test_register_descriptor_keys(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        Cls._register_descriptor_keys(
            Cls.x1,
            ["bar", "baz"]
        )

        self.assertDictEqual(
            Cls.DESCRIPTOR_MAP,
            {
                "foo": Cls.x1,
                "bar": Cls.x1,
                "baz": Cls.x1,
            }
        )

    def test_reject_conflict_on__register_descriptor_keys(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")
            x2 = FakeDescriptor("bar")

        with self.assertRaisesRegex(
                TypeError,
                r"descriptor with key .* already declared at .*"):
            Cls._register_descriptor_keys(Cls.x1, ["bar"])

    def test_reject__register_descriptor_keys_for_subclassed(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        class Subclass(Cls):
            pass

        with self.assertRaisesRegex(
                TypeError,
                r"descriptors cannot be modified on classes with subclasses"):
            Cls._register_descriptor_keys(Cls.x1, ["bar"])

    def test_reject__register_descriptor_keys_if_not_root_class(self):
        class Cls(metaclass=form.DescriptorClass):
            x1 = FakeDescriptor("foo")

        class Subclass(Cls):
            pass

        with self.assertRaisesRegex(
                TypeError,
                r"descriptors cannot be modified on classes with subclasses"):
            Subclass._register_descriptor_keys(
                Subclass.x1,
                ["bar"]
            )


class TestFormClass(unittest.TestCase):
    def test_is_DescriptorClass(self):
        self.assertTrue(issubclass(
            form.FormClass,
            form.DescriptorClass,
        ))


class TestForm(unittest.TestCase):
    def test_init(self):
        class F(form.Form):
            field = fields.TextSingle(
                "foovar",
            )

        f = F()
        self.assertDictEqual(
            f._descriptor_data,
            {},
        )

        f2 = F()
        self.assertIsNot(
            f._descriptor_data,
            f2._descriptor_data
        )

        self.assertIsNone(
            f._recv_xso,
        )

    def test___new___creates_data_dict(self):
        class F(form.Form):
            pass

        f = F.__new__(F)
        self.assertDictEqual(f._descriptor_data, {})

    def test_from_xso_checks_FORM_TYPE(self):
        class F(form.Form):
            FORM_TYPE = "foo"

        tree = forms_xso.Data(type_=forms_xso.DataType.FORM)
        tree.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.HIDDEN,
                values=["bar"],
                var="FORM_TYPE"
            )
        )

        with self.assertRaisesRegex(
                ValueError,
                "mismatching FORM_TYPE"):
            F.from_xso(tree)

    def test_from_xso_checks_data_type(self):
        reject = [
            forms_xso.DataType.RESULT,
            forms_xso.DataType.CANCEL,
        ]

        class F(form.Form):
            pass

        for t in forms_xso.DataType:
            tree = forms_xso.Data(type_=t)

            if t in reject:
                with self.assertRaisesRegex(
                        ValueError,
                        r"unexpected form type",
                        msg="for {}".format(t)):
                    F.from_xso(tree)
            else:
                F.from_xso(tree)

    def test_from_xso_single_field(self):
        class F(form.Form):
            field = fields.TextSingle(
                "foobar",
            )

        tree = forms_xso.Data(type_=forms_xso.DataType.FORM)
        tree.fields.append(
            forms_xso.Field(values=["value"], var="foobar")
        )

        f = F.from_xso(tree)
        self.assertIsInstance(f, F)
        self.assertEqual(
            f.field.value,
            "value",
        )

    def test_copies_have_independent_descriptor_data(self):
        class F(form.Form):
            field = fields.TextSingle(
                "foovar",
            )

        f = F()
        f.field.value = "foo"

        copied = copy.copy(f)
        self.assertDictEqual(
            f._descriptor_data,
            copied._descriptor_data,
        )

        self.assertIsNot(
            f._descriptor_data,
            copied._descriptor_data,
        )

    def test_deepcopy_does_not_copy_descriptors(self):
        class F(form.Form):
            field = fields.TextSingle(
                "foovar",
            )

        f = F()
        f.field.value = "foo"

        copied = copy.deepcopy(f)
        self.assertIsNot(
            f._descriptor_data,
            copied._descriptor_data,
        )

        self.assertIsNot(
            f.field,
            copied.field,
        )

    def test_from_xso_complex(self):
        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        data.fields.append(
            forms_xso.Field(
                var="FORM_TYPE",
                type_=forms_xso.FieldType.HIDDEN,
                values=["some-uri"],
            )
        )

        data.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.FIXED,
                values=["This is some heading."],
            )
        )

        data.fields.append(
            forms_xso.Field(
                var="jid",
                type_=forms_xso.FieldType.JID_SINGLE,
                values=[],
                desc="some description",
                label="some label",
            )
        )

        class F(form.Form):
            jid = fields.JIDSingle(
                var="jid",
            )

        f = F.from_xso(data)
        self.assertIsNone(f.jid.value)
        self.assertIs(f._recv_xso, data)

    def test_from_xso_rejects_mismatching_type(self):
        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        data.fields.append(
            forms_xso.Field(
                var="FORM_TYPE",
                type_=forms_xso.FieldType.HIDDEN,
                values=["some-uri"],
            )
        )

        data.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.FIXED,
                values=["This is some heading."],
            )
        )

        data.fields.append(
            forms_xso.Field(
                var="jid",
                type_=forms_xso.FieldType.JID_SINGLE,
                values=[],
                desc="some description",
                label="some label",
            )
        )

        class F(form.Form):
            jid = fields.TextSingle(
                var="jid",
            )

        with self.assertRaisesRegex(
                ValueError,
                r"mismatching type (.+ != .+) on field .+"):
            F.from_xso(data)

    def test_from_xso_allows_upcast(self):
        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        data.fields.append(
            forms_xso.Field(
                var="FORM_TYPE",
                type_=forms_xso.FieldType.HIDDEN,
                values=["some-uri"],
            )
        )

        data.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.FIXED,
                values=["This is some heading."],
            )
        )

        data.fields.append(
            forms_xso.Field(
                var="jid",
                type_=forms_xso.FieldType.TEXT_SINGLE,
                values=[],
                desc="some description",
                label="some label",
            )
        )

        class F(form.Form):
            jid = fields.TextPrivate(
                var="jid",
            )

        F.from_xso(data)

    def test_render_reply(self):
        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        data.fields.append(
            forms_xso.Field(
                var="FORM_TYPE",
                type_=forms_xso.FieldType.HIDDEN,
                values=["some-uri"],
            )
        )

        data.fields.append(
            forms_xso.Field(
                type_=forms_xso.FieldType.FIXED,
                values=["This is some heading."],
            )
        )

        data.fields.append(
            forms_xso.Field(
                var="jid",
                type_=forms_xso.FieldType.JID_SINGLE,
                values=[],
                desc="some description",
            )
        )

        class F(form.Form):
            jid = fields.JIDSingle(
                var="jid",
                label="Foobar"
            )

            other = fields.TextSingle(
                var="foo",
            )

        f = F.from_xso(data)
        f.jid.value = aioxmpp.JID.fromstr("foo@bar.baz")

        result = f.render_reply()
        self.assertIsInstance(result, forms_xso.Data)
        self.assertEqual(
            result.type_,
            forms_xso.DataType.SUBMIT,
        )
        self.assertEqual(
            len(result.fields),
            3
        )

        self.assertIs(
            data.fields[0],
            result.fields[0]
        )
        self.assertIs(
            data.fields[1],
            result.fields[1],
        )

        self.assertIsNot(
            data.fields[2],
            result.fields[2],
        )

        jid_field = result.fields[2]
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"]
        )
        self.assertEqual(
            jid_field.desc,
            "some description",
        )
        self.assertIsNone(
            jid_field.label
        )

    def test_render_reply_includes_unknown_field(self):
        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        data.fields.append(
            forms_xso.Field(
                var="jid",
                type_=forms_xso.FieldType.JID_SINGLE,
                values=[],
                desc="some description",
            )
        )

        data.fields.append(
            forms_xso.Field(
                var="foo",
                type_=forms_xso.FieldType.TEXT_SINGLE,
                values=[],
            )
        )

        class F(form.Form):
            jid = fields.JIDSingle(
                var="jid",
                label="Foobar"
            )

        f = F.from_xso(data)
        f.jid.value = aioxmpp.JID.fromstr("foo@bar.baz")

        result = f.render_reply()
        self.assertIsInstance(result, forms_xso.Data)
        self.assertEqual(
            len(result.fields),
            2
        )

        self.assertIs(
            data.fields[1],
            result.fields[1]
        )

        self.assertIsNot(
            data.fields[0],
            result.fields[0],
        )

        jid_field = result.fields[0]
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"]
        )
        self.assertEqual(
            jid_field.desc,
            "some description",
        )
        self.assertIsNone(
            jid_field.label
        )

    def test_render_request(self):
        class F(form.Form):
            jid = fields.JIDSingle(
                var="jid",
                required=True,
                desc="Enter a valid JID here",
                label="Your JID",
            )

            something_else = fields.TextSingle(
                var="other",
                label="Something else",
            )

        f = F()
        f.jid.value = aioxmpp.JID.fromstr("foo@bar.baz")
        f.something_else.value = "some_text"

        data = f.render_request()

        self.assertIsInstance(
            data,
            forms_xso.Data,
        )

        self.assertEqual(
            len(data.fields),
            2
        )

        for field in data.fields:
            self.assertIsInstance(
                field,
                forms_xso.Field,
            )

        jid_field = [field for field in data.fields
                     if field.var == "jid"].pop()
        self.assertEqual(
            jid_field.type_,
            forms_xso.FieldType.JID_SINGLE,
        )
        self.assertEqual(
            jid_field.label,
            "Your JID"
        )
        self.assertEqual(
            jid_field.desc,
            "Enter a valid JID here",
        )
        self.assertIs(
            jid_field.required,
            True
        )
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"],
        )

        other_field = [field for field in data.fields
                       if field.var == "other"].pop()
        self.assertEqual(
            other_field.type_,
            forms_xso.FieldType.TEXT_SINGLE,
        )
        self.assertEqual(
            other_field.label,
            "Something else"
        )
        self.assertIsNone(
            other_field.desc,
        )
        self.assertIs(
            other_field.required,
            False,
        )
        self.assertSequenceEqual(
            other_field.values,
            ["some_text"],
        )

    def test_render_request_with_layout(self):
        class F(form.Form):
            jid = fields.JIDSingle(
                var="jid",
                required=True,
                desc="Enter a valid JID here",
                label="Your JID",
            )

            something_else = fields.TextSingle(
                var="other",
                label="Something else",
            )

            LAYOUT = [
                "Metadata",
                jid,
                "Captcha",
                something_else,
            ]

        f = F()
        f.jid.value = aioxmpp.JID.fromstr("foo@bar.baz")
        f.something_else.value = "some_text"

        data = f.render_request()

        self.assertIsInstance(
            data,
            forms_xso.Data,
        )

        self.assertEqual(
            len(data.fields),
            4
        )

        for field in data.fields:
            self.assertIsInstance(
                field,
                forms_xso.Field,
            )

        text_field = data.fields[0]
        self.assertEqual(
            text_field.type_,
            forms_xso.FieldType.FIXED,
        )
        self.assertIsNone(text_field.var)
        self.assertSequenceEqual(
            text_field.values,
            ["Metadata"]
        )

        jid_field = data.fields[1]
        self.assertEqual(
            jid_field.type_,
            forms_xso.FieldType.JID_SINGLE,
        )
        self.assertEqual(
            jid_field.label,
            "Your JID"
        )
        self.assertEqual(
            jid_field.desc,
            "Enter a valid JID here",
        )
        self.assertIs(
            jid_field.required,
            True
        )
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"],
        )

        text_field = data.fields[2]
        self.assertEqual(
            text_field.type_,
            forms_xso.FieldType.FIXED,
        )
        self.assertIsNone(text_field.var)
        self.assertSequenceEqual(
            text_field.values,
            ["Captcha"]
        )

        other_field = data.fields[3]
        self.assertEqual(
            other_field.type_,
            forms_xso.FieldType.TEXT_SINGLE,
        )
        self.assertEqual(
            other_field.label,
            "Something else"
        )
        self.assertIsNone(
            other_field.desc,
        )
        self.assertIs(
            other_field.required,
            False,
        )
        self.assertSequenceEqual(
            other_field.values,
            ["some_text"],
        )
