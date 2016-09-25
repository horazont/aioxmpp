import contextlib
import unittest
import unittest.mock

import aioxmpp.xso as xso
import aioxmpp.forms.fields as fields


class TestBoundField(unittest.TestCase):
    def setUp(self):
        self.f = fields.Field(
            "foo",
            type_=xso.Integer(),
            validator=xso.RestrictToSet({1, 2, 3}),
            default=0,
        )
        self.bf = fields.BoundField(self.f)

    def test_init(self):
        self.assertIs(
            self.bf.unbound_field,
            self.f
        )
        self.assertEqual(self.bf.data, self.f.default)

    def test_write_uses_validator_and_type_coercion_chain(self):
        o = object()
        o2 = object()

        with contextlib.ExitStack() as stack:
            validate = stack.enter_context(
                unittest.mock.patch.object(self.f.validator, "validate")
            )
            coerce = stack.enter_context(
                unittest.mock.patch.object(self.f.type_, "coerce")
            )

            coerce.return_value = o2
            validate.return_value = True
            self.bf.data = o

        self.assertIs(self.bf.data, o2)

        self.assertSequenceEqual(
            [
                unittest.mock.call(o),
            ],
            coerce.mock_calls
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call(o2),
            ],
            validate.mock_calls
        )

    def test_reject_invalid_value(self):
        with contextlib.ExitStack() as stack:
            validate = stack.enter_context(
                unittest.mock.patch.object(self.f.validator, "validate")
            )

            validate.return_value = False
            with self.assertRaisesRegex(ValueError, "invalid value"):
                self.bf.data = 1

    def test_work_without_validator(self):
        self.f.validator = None
        self.bf.data = 10
        self.assertEqual(self.bf.data, 10)

    def test_delete_reverts_to_default(self):
        self.f.default = 123
        self.bf.data = 2
        self.assertEqual(self.bf.data, 2)
        del self.bf.data
        self.assertEqual(self.bf.data, 123)

    def tearDown(self):
        del self.f


class TestField(unittest.TestCase):
    def test_init(self):
        f = fields.Field(
            "foo-bar",
            type_=xso.Integer(),
            validator=xso.RestrictToSet({1, 2, 3}),
            default=0,
        )

        self.assertEqual(
            "foo-bar",
            f.var,
        )
        self.assertIsInstance(
            f.type_,
            xso.Integer
        )
        self.assertIsInstance(
            f.validator,
            xso.RestrictToSet,
        )
        self.assertSetEqual(
            {1, 2, 3},
            f.validator.values,
        )
        self.assertEqual(
            0,
            f.default
        )

    def test_init_defaults(self):
        f = fields.Field("foo")

        self.assertEqual("foo", f.var)

        self.assertIsInstance(
            f.type_,
            xso.String
        )

        self.assertIsNone(f.validator)

        self.assertIsNone(f.default)

    def test_class_attribute_access_returns_descriptor(self):
        field = fields.Field("foo")

        class Cls:
            f = field

        self.assertIs(Cls.f, field)

    def test_return_bound_field_on_read(self):
        class Cls:
            f = fields.Field("foo")

        o1 = Cls()
        o2 = Cls()

        self.assertIsInstance(
            o1.f,
            fields.BoundField
        )
        self.assertIs(
            o1.f.unbound_field,
            Cls.f
        )

        f1, f2 = o1.f, o1.f

        self.assertIs(f1, f2)
        self.assertIsNot(o1.f, o2.f)
        self.assertIs(o2.f, o2.f)

    def test_prohibit_writing(self):
        class Cls:
            f = fields.Field("foo")

        o = Cls()
        with self.assertRaises(AttributeError):
            o.f = "foobar"

    def test_prohibit_deleting(self):
        class Cls:
            f = fields.Field("foo")

        o = Cls()
        f = o.f
        with self.assertRaises(AttributeError):
            del o.f
        self.assertIs(o.f, f)
