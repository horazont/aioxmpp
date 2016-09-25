import abc
import copy
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

import aioxmpp.forms.form as form
import aioxmpp.forms.xso as form_xso


def instance_mock():
    mock = unittest.mock.Mock()
    mock._descriptor_data = {}
    return mock


class TestAbstractDescriptor(unittest.TestCase):
    def test_uses_abcmeta(self):
        self.assertIsInstance(
            form.AbstractDescriptor,
            abc.ABCMeta,
        )

    def test_is_abstract(self):
        with self.assertRaisesRegex(TypeError, "descriptor_keys"):
            form.AbstractDescriptor()


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


class FakeDescriptor(form.AbstractDescriptor):
    def __init__(self, key):
        self._keys = [key]

    def descriptor_keys(self):
        return self._keys


class TestAbstractField(unittest.TestCase):
    class FakeField(form.AbstractField):
        def descriptor_keys(self):
            return []

    def test_init(self):
        f = self.FakeField()
        self.assertFalse(f.required)
        self.assertIsNone(f.desc)
        self.assertIsNone(f.label)

    def test_init_required(self):
        f = self.FakeField(required=True)
        self.assertTrue(f.required)

    def test_init_desc(self):
        desc = "foobar"
        f = self.FakeField(desc=desc)
        self.assertEqual(f.desc, desc)

    def test_init_label(self):
        f = self.FakeField(label="foobar")
        self.assertEqual(f.label, "foobar")

    def test_init_rejects_desc_with_newlines(self):
        regex = r"desc must not contain newlines"

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(desc="foo\r")

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(desc="foo\nbar")

        with self.assertRaisesRegex(ValueError, regex):
            self.FakeField(desc="foo\r\nbar")

    def test_setting_desc_rejects_desc_with_newlines(self):
        regex = r"desc must not contain newlines"
        f = self.FakeField()

        with self.assertRaisesRegex(ValueError, regex):
            f.desc = "foo\r"

        with self.assertRaisesRegex(ValueError, regex):
            f.desc = "foo\nbar"

        with self.assertRaisesRegex(ValueError, regex):
            f.desc = "foo\r\nbar"

    def test_deleting_desc_sets_it_to_None(self):
        f = self.FakeField(desc="foobar")
        del f.desc
        self.assertIsNone(f.desc)

    def test_render_into_sets_required_desc_label(self):
        f = self.FakeField()
        mock = unittest.mock.Mock()
        f.render_into(unittest.mock.sentinel.any_, mock)
        self.assertIsNone(mock.desc)
        self.assertIsNone(mock.label)
        self.assertIsNone(mock.required)

    def test_render_into_fills_required_desc_label(self):
        f = self.FakeField(
            desc="foobar",
            label="baz",
            required=True,
        )
        mock = unittest.mock.Mock()
        f.render_into(unittest.mock.sentinel.any_, mock)
        self.assertEqual(mock.desc, "foobar")
        self.assertEqual(mock.label, "baz")
        self.assertEqual(
            mock.required,
            (namespaces.xep0004_data, "required"),
        )


class TestInputLine(unittest.TestCase):
    def setUp(self):
        self.f = form.InputLine(var="muc#foobar")

    def test_is_abstract_field(self):
        self.assertTrue(issubclass(
            form.InputLine,
            form.AbstractField,
        ))

    def test_init(self):
        t = object()
        f = form.InputLine(var="muc#foobar", type_=t)
        self.assertEqual(f.var, "muc#foobar")
        self.assertIs(f.type_, t)

        f = form.InputLine("muc#foobar")
        self.assertEqual(f.var, "muc#foobar")

        with self.assertRaisesRegex(TypeError, "argument"):
            form.InputLine()

    def test_init_passes_to_abstract_field(self):
        f = form.InputLine(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_descriptor_keys(self):
        t = object()
        f = form.InputLine(var="muc#foobar", type_=t)

        self.assertSequenceEqual(
            list(f.descriptor_keys()),
            [
                (form.descriptor_ns, "muc#foobar"),
            ]
        )

    def test_var_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.f.var = "muc#foobar"

    def test_type_is_not_writable(self):
        with self.assertRaises(AttributeError):
            self.f.type_ = self.f.type_

    def test_set_modifies_field_data(self):
        mock = instance_mock()
        self.f.__set__(mock, "foobar")
        self.assertDictEqual(
            mock._descriptor_data,
            {
                self.f: "foobar",
            }
        )

    def test_set_rejects_newlines(self):
        mock = instance_mock()
        rx = "newlines not allowed"
        with self.assertRaisesRegex(ValueError, rx):
            self.f.__set__(mock, "foobar\nbar")
        with self.assertRaisesRegex(ValueError, rx):
            self.f.__set__(mock, "foobar\rbar")
        with self.assertRaisesRegex(ValueError, rx):
            self.f.__set__(mock, "foobar\r\nbar")

    def test_set_coerces(self):
        mock = instance_mock()
        f = form.InputLine("foo", type_=xso.Float())
        f.__set__(mock, 10)
        self.assertIsInstance(mock._descriptor_data[f], float)

    def test_get_applies_type(self):
        mock = instance_mock()
        f = form.InputLine("foo", type_=xso.Integer())
        f.__set__(mock, 10)
        self.assertEqual(
            f.__get__(mock, type(mock)),
            10
        )

    def test_get_returns_descriptor_for_None_instance(self):
        self.assertIs(self.f, self.f.__get__(None, type))

    def test_load_parses_and_sets_instance_data(self):
        mock = instance_mock()
        field_xso = unittest.mock.Mock()
        field_xso.values = ["10.2"]
        f = form.InputLine("foo", type_=xso.Float())
        f.load(mock, field_xso)
        self.assertDictEqual(
            mock._descriptor_data,
            {
                f: 10.2,
            }
        )

    def test_load_uses_default_if_xso_has_no_values(self):
        mock = instance_mock()
        field_xso = unittest.mock.Mock()
        field_xso.values = []
        f = form.InputLine(
            "foo",
            default=unittest.mock.sentinel.default
        )
        f.load(mock, field_xso)

        self.assertDictEqual(
            mock._descriptor_data,
            {
                f: unittest.mock.sentinel.default,
            }
        )

    def test_render_into(self):
        mock = instance_mock()

        f = form.InputLine(
            "foo",
            type_=xso.Integer()
        )

        mock._descriptor_data[f] = 10

        field_xso = unittest.mock.Mock()
        field_xso.values = []
        f.render_into(mock, field_xso)

        self.assertEqual(
            field_xso.var,
            f.var,
        )
        self.assertEqual(
            field_xso.type_,
            "text-single",
        )
        self.assertEqual(
            field_xso.values,
            ["10"],
        )

        # check that call to super happens
        self.assertIsNone(field_xso.required)

    def tearDown(self):
        del self.f


class TestInputJID(unittest.TestCase):
    def test_is_input_line(self):
        self.assertTrue(issubclass(
            form.InputJID,
            form.InputLine
        ))

    def test_type_is_JID(self):
        f = form.InputJID("foo")
        self.assertIsInstance(f.type_, xso.JID)

    def test_init_rejects_type_argument(self):
        with self.assertRaises(TypeError):
            form.InputJID("foo", type_=xso.JID())

    def test_init_passes_to_abstract_field(self):
        f = form.InputJID(
            var="muc#foobar",
            required=True,
            desc="foobar"
        )
        self.assertTrue(f.required)
        self.assertEqual(f.desc, "foobar")

    def test_render_into(self):
        mock = instance_mock()

        f = form.InputJID(
            "foo",
        )

        mock._descriptor_data[f] = aioxmpp.JID.fromstr(
            "foo@bar.baz"
        )

        field_xso = unittest.mock.Mock()
        field_xso.values = []
        f.render_into(mock, field_xso)

        self.assertEqual(
            field_xso.var,
            f.var,
        )
        self.assertEqual(
            field_xso.type_,
            "jid-single",
        )
        self.assertEqual(
            field_xso.values,
            ["foo@bar.baz"],
        )

        # check that call to super happens
        self.assertIsNone(field_xso.required)


class TestFormClass(unittest.TestCase):
    def test_is_DescriptorClass(self):
        self.assertTrue(issubclass(
            form.FormClass,
            form.DescriptorClass,
        ))


class TestForm(unittest.TestCase):
    def test_init(self):
        class F(form.Form):
            field = form.InputLine(
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

    def test_from_xso_single_field(self):
        class F(form.Form):
            field = form.InputLine(
                "foobar",
            )

        tree = form_xso.Data()
        tree.fields.append(
            form_xso.Field(values=["value"], var="foobar")
        )

        f = F.from_xso(tree)
        self.assertIsInstance(f, F)
        self.assertEqual(
            f.field,
            "value",
        )

    def test_copies_have_independent_descriptor_data(self):
        class F(form.Form):
            field = form.InputLine(
                "foovar",
            )

        x = object()

        f = F()
        f.field = "foo"
        f._descriptor_data["foo"] = x
        self.assertDictEqual(
            f._descriptor_data,
            {
                F.field: "foo",
                "foo": x,
            }
        )

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
            field = form.InputLine(
                "foovar",
            )

        x = object()

        f = F()
        f.field = "foo"
        f._descriptor_data["foo"] = x
        self.assertDictEqual(
            f._descriptor_data,
            {
                F.field: "foo",
                "foo": x,
            }
        )

        copied = copy.deepcopy(f)
        self.assertDictEqual(
            copied._descriptor_data,
            {
                F.field: "foo",
                "foo": unittest.mock.ANY,
            }
        )

        self.assertIsNot(
            f._descriptor_data["foo"],
            copied._descriptor_data["foo"],
        )

        self.assertIsNot(
            f._descriptor_data,
            copied._descriptor_data,
        )

    def test_from_xso_complex(self):
        data = form_xso.Data()

        data.fields.append(
            form_xso.Field(
                var="FORM_TYPE",
                type_="hidden",
                values=["some-uri"],
            )
        )

        data.fields.append(
            form_xso.Field(
                type_="fixed",
                values=["This is some heading."],
            )
        )

        data.fields.append(
            form_xso.Field(
                var="jid",
                type_="jid-single",
                values=[],
                desc="some description",
                label="some label",
            )
        )

        class F(form.Form):
            jid = form.InputJID(
                var="jid",
            )

        f = F.from_xso(data)
        self.assertIsNone(f.jid)
        self.assertIs(f._recv_xso, data)

    def test_render_reply(self):
        data = form_xso.Data()

        data.fields.append(
            form_xso.Field(
                var="FORM_TYPE",
                type_="hidden",
                values=["some-uri"],
            )
        )

        data.fields.append(
            form_xso.Field(
                type_="fixed",
                values=["This is some heading."],
            )
        )

        data.fields.append(
            form_xso.Field(
                var="jid",
                type_="jid-single",
                values=[],
                desc="some description",
                label="some label",
            )
        )

        class F(form.Form):
            jid = form.InputJID(
                var="jid",
            )

            other = form.InputLine(
                var="foo",
            )

        f = F.from_xso(data)
        f.jid = aioxmpp.JID.fromstr("foo@bar.baz")

        result = f.render_reply()
        self.assertIsInstance(result, form_xso.Data)
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

    def test_render_request(self):
        class F(form.Form):
            jid = form.InputJID(
                var="jid",
                required=True,
                desc="Enter a valid JID here",
                label="Your JID",
            )

            something_else = form.InputLine(
                var="other",
                label="Something else",
            )

        f = F()
        f.jid = aioxmpp.JID.fromstr("foo@bar.baz")
        f.something_else = "some_text"

        data_xso = f.render_request()

        self.assertIsInstance(
            data_xso,
            form_xso.Data,
        )

        self.assertEqual(
            len(data_xso.fields),
            2
        )

        for field in data_xso.fields:
            self.assertIsInstance(
                field,
                form_xso.Field,
            )

        jid_field = [field for field in data_xso.fields
                     if field.var == "jid"].pop()
        self.assertEqual(
            jid_field.type_,
            "jid-single"
        )
        self.assertEqual(
            jid_field.label,
            "Your JID"
        )
        self.assertEqual(
            jid_field.desc,
            "Enter a valid JID here",
        )
        self.assertEqual(
            jid_field.required,
            (namespaces.xep0004_data, "required"),
        )
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"],
        )

        other_field = [field for field in data_xso.fields
                       if field.var == "other"].pop()
        self.assertEqual(
            other_field.type_,
            "text-single"
        )
        self.assertEqual(
            other_field.label,
            "Something else"
        )
        self.assertIsNone(
            other_field.desc,
        )
        self.assertIsNone(
            other_field.required,
        )
        self.assertSequenceEqual(
            other_field.values,
            ["some_text"],
        )

    def test_render_request_with_layout(self):
        class F(form.Form):
            jid = form.InputJID(
                var="jid",
                required=True,
                desc="Enter a valid JID here",
                label="Your JID",
            )

            something_else = form.InputLine(
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
        f.jid = aioxmpp.JID.fromstr("foo@bar.baz")
        f.something_else = "some_text"

        data_xso = f.render_request()

        self.assertIsInstance(
            data_xso,
            form_xso.Data,
        )

        self.assertEqual(
            len(data_xso.fields),
            4
        )

        for field in data_xso.fields:
            self.assertIsInstance(
                field,
                form_xso.Field,
            )

        text_field = data_xso.fields[0]
        self.assertEqual(
            text_field.type_,
            "fixed"
        )
        self.assertIsNone(text_field.var)
        self.assertSequenceEqual(
            text_field.values,
            ["Metadata"]
        )

        jid_field = data_xso.fields[1]
        self.assertEqual(
            jid_field.type_,
            "jid-single"
        )
        self.assertEqual(
            jid_field.label,
            "Your JID"
        )
        self.assertEqual(
            jid_field.desc,
            "Enter a valid JID here",
        )
        self.assertEqual(
            jid_field.required,
            (namespaces.xep0004_data, "required"),
        )
        self.assertSequenceEqual(
            jid_field.values,
            ["foo@bar.baz"],
        )

        text_field = data_xso.fields[2]
        self.assertEqual(
            text_field.type_,
            "fixed"
        )
        self.assertIsNone(text_field.var)
        self.assertSequenceEqual(
            text_field.values,
            ["Captcha"]
        )

        other_field = data_xso.fields[3]
        self.assertEqual(
            other_field.type_,
            "text-single"
        )
        self.assertEqual(
            other_field.label,
            "Something else"
        )
        self.assertIsNone(
            other_field.desc,
        )
        self.assertIsNone(
            other_field.required,
        )
        self.assertSequenceEqual(
            other_field.values,
            ["some_text"],
        )
