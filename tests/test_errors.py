########################################################################
# File name: test_errors.py
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
import contextlib
import enum
import gettext
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.errors as errors
import aioxmpp.i18n as i18n
import aioxmpp.structs as structs
import aioxmpp.xso as xso

from aioxmpp.utils import etree, namespaces


class Testformat_error_text(unittest.TestCase):
    def test_only_condition(self):
        self.assertEqual(
            "{urn:ietf:params:xml:ns:xmpp-stanzas}internal-server-error",
            errors.format_error_text(
                condition=errors.ErrorCondition.INTERNAL_SERVER_ERROR
            )
        )

    def test_with_text(self):
        self.assertEqual(
            "{urn:ietf:params:xml:ns:xmpp-stanzas}bad-request ('foobar')",
            errors.format_error_text(
                condition=errors.ErrorCondition.BAD_REQUEST,
                text="foobar",
            )
        )

    def test_with_application_defined(self):
        class Appcond:
            TAG = ("uri:bar", "value-error")

        self.assertEqual(
            "{urn:ietf:params:xml:ns:xmpp-stanzas}gone/{uri:bar}value-error",
            errors.format_error_text(
                condition=errors.ErrorCondition.GONE,
                application_defined_condition=Appcond(),
            )
        )

    def test_with_application_defined_and_text(self):
        class Appcond:
            TAG = ("uri:bar", "value-error")

        self.assertEqual(
            "{urn:ietf:params:xml:ns:xmpp-stanzas}undefined-condition/{uri:bar}value-error ('that’s not an integer')",
            errors.format_error_text(
                condition=errors.ErrorCondition.UNDEFINED_CONDITION,
                application_defined_condition=Appcond(),
                text="that’s not an integer"
            )
        )


class TestErrorCondition(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(errors.ErrorCondition, enum.Enum))

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_uses_compat_mixin(self):
        self.assertTrue(
            issubclass(
                errors.ErrorCondition,
                structs.CompatibilityMixin,
            )
        )

    def test_uses_xso_enum_mixin(self):
        self.assertTrue(issubclass(errors.ErrorCondition, xso.XSOEnumMixin))

    def test_gone_new_address(self):
        self.assertIsInstance(
            errors.ErrorCondition.GONE.xso_class.new_address,
            xso.Text,
        )
        self.assertIsInstance(
            errors.ErrorCondition.GONE.xso_class.new_address.type_,
            xso.String,
        )

    def test_gone_new_address(self):
        self.assertIsInstance(
            errors.ErrorCondition.REDIRECT.xso_class.new_address,
            xso.Text,
        )
        self.assertIsInstance(
            errors.ErrorCondition.REDIRECT.xso_class.new_address.type_,
            xso.String,
        )


class TestStreamError(unittest.TestCase):
    def test_init_formats_condition(self):
        with unittest.mock.patch("aioxmpp.errors.format_error_text") as format_:
            errors.StreamError(
                errors.StreamErrorCondition.INTERNAL_SERVER_ERROR,
                text=unittest.mock.sentinel.text,
            )

        format_.assert_called_once_with(
            errors.StreamErrorCondition.INTERNAL_SERVER_ERROR,
            unittest.mock.sentinel.text,
        )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_init_converts_tuple_to_condition_and_warns(self):
        with contextlib.ExitStack() as stack:
            format_ = stack.enter_context(unittest.mock.patch(
                "aioxmpp.errors.format_error_text"
            ))

            ctx = stack.enter_context(self.assertWarnsRegex(
                DeprecationWarning,
                r"as of aioxmpp 1\.0, stream error conditions must be members "
                r"of the aioxmpp\.errors\.StreamErrorCondition enumeration"
            ))

            errors.StreamError(
                (namespaces.streams, "not-authorized"),
                text=unittest.mock.sentinel.text,
            )

        format_.assert_called_once_with(
            errors.StreamErrorCondition.NOT_AUTHORIZED,
            unittest.mock.sentinel.text,
        )

        self.assertTrue(
            ctx.filename.endswith("test_errors.py"),
        )


class TestXMPPError(unittest.TestCase):
    def test_init_formats_condition(self):
        with unittest.mock.patch("aioxmpp.errors.format_error_text") as format_:
            errors.XMPPError(
                errors.ErrorCondition.INTERNAL_SERVER_ERROR,
                text=unittest.mock.sentinel.text,
                application_defined_condition=unittest.mock.sentinel.appcond,
            )

        format_.assert_called_once_with(
            errors.ErrorCondition.INTERNAL_SERVER_ERROR,
            text=unittest.mock.sentinel.text,
            application_defined_condition=unittest.mock.sentinel.appcond,
        )

    @unittest.skipIf(aioxmpp.version_info >= (1, 0, 0),
                     "does not apply to this version of aioxmpp")
    def test_init_converts_tuple_to_condition_and_warns(self):
        with contextlib.ExitStack() as stack:
            format_ = stack.enter_context(unittest.mock.patch(
                "aioxmpp.errors.format_error_text"
            ))

            ctx = stack.enter_context(self.assertWarnsRegex(
                DeprecationWarning,
                r"as of aioxmpp 1\.0, error conditions must be members of the "
                r"aioxmpp\.ErrorCondition enumeration"
            ))

            errors.XMPPError(
                (namespaces.stanzas, "bad-request"),
                text=unittest.mock.sentinel.text,
                application_defined_condition=unittest.mock.sentinel.appcond,
            )

        format_.assert_called_once_with(
            errors.ErrorCondition.BAD_REQUEST,
            text=unittest.mock.sentinel.text,
            application_defined_condition=unittest.mock.sentinel.appcond,
        )

        self.assertTrue(
            ctx.filename.endswith("test_errors.py"),
        )

    def test_init_sets_attributes_from_enum_member(self):
        appcond = unittest.mock.Mock(["TAG"])
        appcond.TAG = ("a", "b")

        exc = errors.XMPPError(
            errors.ErrorCondition.INTERNAL_SERVER_ERROR,
            text=unittest.mock.sentinel.text,
            application_defined_condition=appcond,
        )

        self.assertEqual(exc.condition,
                         errors.ErrorCondition.INTERNAL_SERVER_ERROR)
        self.assertEqual(exc.text, unittest.mock.sentinel.text)
        self.assertIsInstance(
            exc.condition_obj,
            errors.ErrorCondition.INTERNAL_SERVER_ERROR.xso_class
        )
        self.assertEqual(exc.application_defined_condition, appcond)

    def test_init_sets_attributes_from_xso(self):
        appcond = unittest.mock.Mock(["TAG"])
        appcond.TAG = ("a", "b")

        condition_obj = errors.ErrorCondition.GONE.to_xso()
        condition_obj.new_address = "foo"

        exc = errors.XMPPError(
            condition_obj,
            text=unittest.mock.sentinel.text,
            application_defined_condition=appcond,
        )

        self.assertEqual(exc.condition,
                         errors.ErrorCondition.GONE)
        self.assertEqual(exc.text, unittest.mock.sentinel.text)
        self.assertIs(
            exc.condition_obj,
            condition_obj
        )
        self.assertEqual(exc.application_defined_condition, appcond)


class TestErroneousStanza(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(
            errors.ErroneousStanza,
            errors.StanzaError
        ))

    def test_init(self):
        obj = object()
        exc = errors.ErroneousStanza(obj)
        self.assertIs(exc.partial_obj, obj)
        self.assertTrue(
            str(exc),
            "erroneous stanza received: {!r}".format(obj)
        )


class TestMultiOSError(unittest.TestCase):
    def test_message(self):
        exc = errors.MultiOSError("foo",
                                  [ValueError("bar"),
                                   ValueError("baz")])

        self.assertEqual(
            "foo: multiple errors: bar, baz",
            str(exc)
        )

    def test_flatten(self):
        base_excs1 = [OSError(), OSError()]
        base_excs2 = [OSError(), OSError()]
        exc3 = OSError()

        excs = [errors.MultiOSError("foo", base_excs1),
                errors.MultiOSError("foo", base_excs2),
                exc3]

        exc = errors.MultiOSError("bar", excs)

        self.assertSequenceEqual(
            base_excs1+base_excs2+[exc3],
            exc.exceptions
        )


class TestUserError(unittest.TestCase):
    def test_simple(self):
        s = unittest.mock.Mock()
        ue = errors.UserError(s)

        self.assertSequenceEqual(
            [
                unittest.mock.call.localize(
                    errors.UserError.DEFAULT_FORMATTER,
                    errors.UserError.DEFAULT_TRANSLATIONS,
                )
            ],
            s.mock_calls
        )

        self.assertEqual(
            str(s.localize()),
            str(ue),
        )

    def test_format(self):
        s = unittest.mock.Mock()
        ue = errors.UserError(s, 10, abc="baz")

        self.assertSequenceEqual(
            [
                unittest.mock.call.localize(
                    errors.UserError.DEFAULT_FORMATTER,
                    errors.UserError.DEFAULT_TRANSLATIONS,
                    10,
                    abc="baz"
                ),
            ],
            s.mock_calls
        )

        self.assertEqual(
            str(s.localize()),
            str(ue),
        )

    def test_localize(self):
        fmt = i18n.LocalizingFormatter()
        tx = gettext.NullTranslations()

        s = unittest.mock.Mock()
        ue = errors.UserError(s, 10, abc="baz")

        expected_result = s.localize()

        s.reset_mock()

        self.assertEqual(
            expected_result,
            ue.localize(fmt, tx)
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call.localize(
                    fmt,
                    tx,
                    10,
                    abc="baz")
            ],
            s.mock_calls
        )


class TestUserValueError(unittest.TestCase):
    def test_is_value_and_user_error(self):
        self.assertTrue(issubclass(
            errors.UserValueError,
            errors.UserError,
        ))
        self.assertTrue(issubclass(
            errors.UserValueError,
            ValueError
        ))
