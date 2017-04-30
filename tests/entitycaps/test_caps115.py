########################################################################
# File name: test_caps115.py
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
import functools
import unittest
import unittest.mock

import aioxmpp.disco as disco
import aioxmpp.entitycaps.caps115 as caps115
import aioxmpp.forms.xso as forms_xso
import aioxmpp.structs as structs


class Testbuild_identities_string(unittest.TestCase):
    def test_identities(self):
        identities = [
            disco.xso.Identity(category="fnord",
                               type_="bar"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp library"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp Bibliothek",
                               lang=structs.LanguageTag.fromstr("de-de")),
        ]

        self.assertEqual(
            b"client/bot//aioxmpp library<"
            b"client/bot/de-de/aioxmpp Bibliothek<"
            b"fnord/bar//<",
            caps115.build_identities_string(identities)
        )

    def test_escaping(self):
        identities = [
            disco.xso.Identity(category="fnord",
                               type_="bar"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp library > 0.5"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp Bibliothek <& 0.5",
                               lang=structs.LanguageTag.fromstr("de-de")),
        ]

        self.assertEqual(
            b"client/bot//aioxmpp library &gt; 0.5<"
            b"client/bot/de-de/aioxmpp Bibliothek &lt;&amp; 0.5<"
            b"fnord/bar//<",
            caps115.build_identities_string(identities)
        )

    def test_reject_duplicate_identities(self):
        identities = [
            disco.xso.Identity(category="fnord",
                               type_="bar"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp library > 0.5"),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp Bibliothek <& 0.5",
                               lang=structs.LanguageTag.fromstr("de-de")),
            disco.xso.Identity(category="client",
                               type_="bot",
                               name="aioxmpp library > 0.5"),
        ]

        with self.assertRaisesRegex(ValueError,
                                    "duplicate identity"):
            caps115.build_identities_string(identities)


class Testbuild_features_string(unittest.TestCase):
    def test_features(self):
        features = [
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
        ]

        self.assertEqual(
            b"http://jabber.org/protocol/caps<"
            b"http://jabber.org/protocol/disco#info<"
            b"http://jabber.org/protocol/disco#items<",
            caps115.build_features_string(features)
        )

    def test_escaping(self):
        features = [
            "http://jabber.org/protocol/c<>&aps",
        ]

        self.assertEqual(
            b"http://jabber.org/protocol/c&lt;&gt;&amp;aps<",
            caps115.build_features_string(features)
        )

    def test_reject_duplicate_features(self):
        features = [
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/caps",
        ]

        with self.assertRaisesRegex(ValueError,
                                    "duplicate feature"):
            caps115.build_features_string(features)


class Testbuild_forms_string(unittest.TestCase):
    def test_xep_form(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM)]
        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),

            forms_xso.Field(
                var="os",
                values=[
                    "Mac",
                ]
            ),

            forms_xso.Field(
                var="ip_version",
                values=[
                    "ipv4",
                    "ipv6",
                ]
            ),

            forms_xso.Field(
                var="software",
                values=[
                    "Psi",
                ]
            ),

            forms_xso.Field(
                var="software_version",
                values=[
                    "0.11",
                ]
            ),
        ])

        self.assertEqual(
            b"urn:xmpp:dataforms:softwareinfo<"
            b"ip_version<ipv4<ipv6<"
            b"os<Mac<"
            b"os_version<10.5.1<"
            b"software<Psi<"
            b"software_version<0.11<",
            caps115.build_forms_string(forms)
        )

    def test_value_and_var_escaping(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM)]
        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:<dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.&5.1",
                ]
            ),

            forms_xso.Field(
                var="os>",
                values=[
                    "Mac",
                ]
            ),
        ])

        self.assertEqual(
            b"urn:xmpp:&lt;dataforms:softwareinfo<"
            b"os&gt;<Mac<"
            b"os_version<10.&amp;5.1<",
            caps115.build_forms_string(forms)
        )

    def test_reject_multiple_identical_form_types(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM),
                 forms_xso.Data(type_=forms_xso.DataType.FORM)]

        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),

            forms_xso.Field(
                var="os",
                values=[
                    "Mac",
                ]
            ),
        ])

        forms[1].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),

            forms_xso.Field(
                var="os",
                values=[
                    "Mac",
                ]
            ),
        ])

        with self.assertRaisesRegex(
                ValueError,
                "multiple forms of type b'urn:xmpp:dataforms:softwareinfo'"):
            caps115.build_forms_string(forms)

    def test_reject_form_with_multiple_different_types(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM)]

        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                    "urn:xmpp:dataforms:softwarefoo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),

            forms_xso.Field(
                var="os",
                values=[
                    "Mac",
                ]
            ),
        ])

        with self.assertRaisesRegex(
                ValueError,
                "form with multiple types"):
            caps115.build_forms_string(forms)

    def test_ignore_form_without_type(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM),
                 forms_xso.Data(type_=forms_xso.DataType.FORM)]

        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),
        ])

        forms[1].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),

            forms_xso.Field(
                var="os",
                values=[
                    "Mac",
                ]
            ),
        ])

        self.assertEqual(
            b"urn:xmpp:dataforms:softwareinfo<"
            b"os<Mac<"
            b"os_version<10.5.1<",
            caps115.build_forms_string(forms)
        )

    def test_accept_form_with_multiple_identical_types(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM)]

        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo",
                    "urn:xmpp:dataforms:softwareinfo",
                ]
            ),

            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),
        ])

        caps115.build_forms_string(forms)

    def test_multiple(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM),
                 forms_xso.Data(type_=forms_xso.DataType.FORM)]

        forms[0].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "uri:foo",
                ]
            ),
        ])

        forms[1].fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "uri:bar",
                ]
            ),
        ])

        self.assertEqual(
            b"uri:bar<uri:foo<",
            caps115.build_forms_string(forms)
        )


class Testhash_query(unittest.TestCase):
    def test_impl(self):
        self.maxDiff = None
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.caps115.build_identities_string",
                new=base.build_identities_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.caps115.build_features_string",
                new=base.build_features_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.caps115.build_forms_string",
                new=base.build_forms_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "hashlib.new",
                new=base.hashlib_new,
            ))

            stack.enter_context(unittest.mock.patch(
                "base64.b64encode",
                new=base.base64_b64encode,
            ))

            result = caps115.hash_query(
                base.query,
                base.algo
            )

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.hashlib_new(base.algo),
                unittest.mock.call.build_identities_string(
                    base.query.identities,
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_identities_string()
                ),
                unittest.mock.call.build_features_string(
                    base.query.features
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_features_string()
                ),
                unittest.mock.call.build_forms_string(
                    base.query.exts
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_forms_string()
                ),
                unittest.mock.call.hashlib_new().digest(),
                unittest.mock.call.base64_b64encode(
                    base.hashlib_new().digest()
                ),
                unittest.mock.call.base64_b64encode().decode("ascii")
            ]
        )

        self.assertEqual(
            result,
            base.base64_b64encode().decode()
        )

    def test_simple_xep_data(self):
        info = disco.xso.InfoQuery()
        info.identities.extend([
            disco.xso.Identity(category="client",
                               name="Exodus 0.9.1",
                               type_="pc"),
        ])

        info.features.update({
                "http://jabber.org/protocol/caps",
                "http://jabber.org/protocol/disco#info",
                "http://jabber.org/protocol/disco#items",
                "http://jabber.org/protocol/muc",
        })

        self.assertEqual(
            "QgayPKawpkPSDYmwT/WM94uAlu0=",
            caps115.hash_query(info, "sha1")
        )

    def test_complex_xep_data(self):
        info = disco.xso.InfoQuery()
        info.identities.extend([
            disco.xso.Identity(category="client",
                               name="Psi 0.11",
                               type_="pc",
                               lang=structs.LanguageTag.fromstr("en")),
            disco.xso.Identity(category="client",
                               name="Ψ 0.11",
                               type_="pc",
                               lang=structs.LanguageTag.fromstr("el")),
        ])

        info.features.update({
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/muc",
        })

        ext_form = forms_xso.Data(type_=forms_xso.DataType.FORM)

        ext_form.fields.extend([
            forms_xso.Field(
                var="FORM_TYPE",
                values=[
                    "urn:xmpp:dataforms:softwareinfo"
                ]
            ),

            forms_xso.Field(
                var="ip_version",
                values=[
                    "ipv6",
                    "ipv4",
                ]
            ),
            forms_xso.Field(
                var="os",
                values=[
                    "Mac"
                ]
            ),
            forms_xso.Field(
                var="os_version",
                values=[
                    "10.5.1",
                ]
            ),
            forms_xso.Field(
                var="software",
                values=[
                    "Psi",
                ]
            ),
            forms_xso.Field(
                var="software_version",
                values=[
                    "0.11"
                ]
            ),
        ])

        info.exts.append(ext_form)

        self.assertEqual(
            "q07IKJEyjvHSyhy//CH0CxmKi8w=",
            caps115.hash_query(info, "sha1")
        )
