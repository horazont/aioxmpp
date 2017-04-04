########################################################################
# File name: test_service.py
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
import asyncio
import contextlib
import io
import unittest
import unittest.mock
import urllib.parse

import aioxmpp.callbacks as callbacks
import aioxmpp.disco as disco
import aioxmpp.service as service
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.forms.xso as forms_xso
import aioxmpp.xml

import aioxmpp.entitycaps.service as entitycaps_service
import aioxmpp.entitycaps.xso as entitycaps_xso

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_FROM = structs.JID.fromstr("foo@bar.example/r1")


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
            entitycaps_service.build_identities_string(identities)
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
            entitycaps_service.build_identities_string(identities)
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
            entitycaps_service.build_identities_string(identities)


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
            entitycaps_service.build_features_string(features)
        )

    def test_escaping(self):
        features = [
            "http://jabber.org/protocol/c<>&aps",
        ]

        self.assertEqual(
            b"http://jabber.org/protocol/c&lt;&gt;&amp;aps<",
            entitycaps_service.build_features_string(features)
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
            entitycaps_service.build_features_string(features)


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
            entitycaps_service.build_forms_string(forms)
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
            entitycaps_service.build_forms_string(forms)
        )

    def test_reject_multiple_identical_form_types(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM), forms_xso.Data(type_=forms_xso.DataType.FORM)]

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
            entitycaps_service.build_forms_string(forms)

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
            entitycaps_service.build_forms_string(forms)

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
            entitycaps_service.build_forms_string(forms)
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

        entitycaps_service.build_forms_string(forms)

    def test_multiple(self):
        forms = [forms_xso.Data(type_=forms_xso.DataType.FORM), forms_xso.Data(type_=forms_xso.DataType.FORM)]

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
            entitycaps_service.build_forms_string(forms)
        )


class Testhash_query(unittest.TestCase):
    def test_impl(self):
        self.maxDiff = None
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_identities_string",
                new=base.build_identities_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_features_string",
                new=base.build_features_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_forms_string",
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

            result = entitycaps_service.hash_query(
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
            entitycaps_service.hash_query(info, "sha1")
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
            entitycaps_service.hash_query(info, "sha1")
        )


_src = io.BytesIO(b"""\
<?xml version="1.0" ?><query node="http://tkabber.jabber.ru/#+0mnUAF1ozCEc37cm\
dPPsYbsfhg=" xmlns="http://jabber.org/protocol/disco#info"><identity category=\
"client" name="Tkabber" type="pc"/><feature var="games:board"/><feature var="h\
ttp://jabber.org/protocol/activity"/><feature var="http://jabber.org/protocol/\
activity+notify"/><feature var="http://jabber.org/protocol/bytestreams"/><feat\
ure var="http://jabber.org/protocol/chatstates"/><feature var="http://jabber.o\
rg/protocol/commands"/><feature var="http://jabber.org/protocol/disco#info"/><\
feature var="http://jabber.org/protocol/disco#items"/><feature var="http://jab\
ber.org/protocol/geoloc"/><feature var="http://jabber.org/protocol/geoloc+noti\
fy"/><feature var="http://jabber.org/protocol/ibb"/><feature var="http://jabbe\
r.org/protocol/iqibb"/><feature var="http://jabber.org/protocol/mood"/><featur\
e var="http://jabber.org/protocol/mood+notify"/><feature var="http://jabber.or\
g/protocol/rosterx"/><feature var="http://jabber.org/protocol/si"/><feature va\
r="http://jabber.org/protocol/si/profile/file-transfer"/><feature var="http://\
jabber.org/protocol/tune"/><feature var="jabber:iq:avatar"/><feature var="jabb\
er:iq:browse"/><feature var="jabber:iq:last"/><feature var="jabber:iq:oob"/><f\
eature var="jabber:iq:privacy"/><feature var="jabber:iq:roster"/><feature var=\
"jabber:iq:time"/><feature var="jabber:iq:version"/><feature var="jabber:x:dat\
a"/><feature var="jabber:x:event"/><feature var="jabber:x:oob"/><feature var="\
urn:xmpp:ping"/><feature var="urn:xmpp:time"/><x type="result" xmlns="jabber:x\
:data"><field type="hidden" var="FORM_TYPE"><value>urn:xmpp:dataforms:software\
info</value></field><field var="software"><value>Tkabber</value></field><field\
 var="software_version"><value>1.0-svn-20140122 (Tcl/Tk 8.4.20)</value></field\
><field var="os"><value>FreeBSD</value></field><field var="os_version"><value>\
10.0-STABLE</value></field></x></query>""")
TEST_DB_ENTRY = aioxmpp.xml.read_single_xso(_src, disco.xso.InfoQuery)
TEST_DB_ENTRY_VER = "+0mnUAF1ozCEc37cmdPPsYbsfhg="
TEST_DB_ENTRY_HASH = "sha-1"
TEST_DB_ENTRY_NODE_BARE = "http://tkabber.jabber.ru/"


class TestCache(unittest.TestCase):
    def setUp(self):
        self.c = entitycaps_service.Cache()

    def test_lookup_in_database_key_errors_if_no_such_entry(self):
        with self.assertRaises(KeyError):
            self.c.lookup_in_database("sha-1", "+9oi6+VEwgu5cRmjErECReGvCC0=")

    def test_system_db_path_used_in_lookup(self):
        base = unittest.mock.Mock()
        base.p = unittest.mock.MagicMock()
        base.quote = unittest.mock.Mock(wraps=urllib.parse.quote)
        node = "http://foobar/#baz"
        self.c.set_system_db_path(base.p)

        with contextlib.ExitStack() as stack:
            quote = stack.enter_context(unittest.mock.patch(
                "urllib.parse.quote",
                new=base.quote
            ))

            read_single_xso = stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.read_single_xso",
                new=base.read_single_xso
            ))

            result = self.c.lookup_in_database("sha-1", node)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.quote(node, safe=""),
                unittest.mock.call.p.__truediv__(
                    "sha-1_http%3A%2F%2Ffoobar%2F%23baz.xml"),
                unittest.mock.call.p.__truediv__().open("rb"),
                unittest.mock.call.p.__truediv__().open().__enter__(),
                unittest.mock.call.read_single_xso(
                    base.p.__truediv__().open(),
                    disco.xso.InfoQuery,
                ),
                unittest.mock.call.p.__truediv__().open().__exit__(
                    None, None, None
                ),
            ]
        )

        self.assertEqual(
            result,
            base.read_single_xso()
        )

    def test_user_db_path_used_in_lookup_as_fallback(self):
        base = unittest.mock.Mock()
        base.p = unittest.mock.MagicMock()
        base.userp = unittest.mock.MagicMock()
        base.quote = unittest.mock.Mock(wraps=urllib.parse.quote)
        node = "http://foobar/#baz"
        self.c.set_system_db_path(base.p)
        self.c.set_user_db_path(base.userp)

        with contextlib.ExitStack() as stack:
            quote = stack.enter_context(unittest.mock.patch(
                "urllib.parse.quote",
                new=base.quote
            ))

            read_single_xso = stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.read_single_xso",
                new=base.read_single_xso
            ))

            base.p.__truediv__().open.side_effect = FileNotFoundError()
            base.mock_calls.clear()

            result = self.c.lookup_in_database("sha-1", node)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.quote(node, safe=""),
                unittest.mock.call.p.__truediv__(
                    "sha-1_http%3A%2F%2Ffoobar%2F%23baz.xml"),
                unittest.mock.call.p.__truediv__().open("rb"),
                unittest.mock.call.userp.__truediv__(
                    "sha-1_http%3A%2F%2Ffoobar%2F%23baz.xml"),
                unittest.mock.call.userp.__truediv__().open("rb"),
                unittest.mock.call.userp.__truediv__().open().__enter__(),
                unittest.mock.call.read_single_xso(
                    base.userp.__truediv__().open(),
                    disco.xso.InfoQuery,
                ),
                unittest.mock.call.userp.__truediv__().open().__exit__(
                    None, None, None
                ),
            ]
        )

        self.assertEqual(
            result,
            base.read_single_xso()
        )

    def test_user_db_path_used_if_system_db_is_unset(self):
        base = unittest.mock.Mock()
        base.p = unittest.mock.MagicMock()
        base.userp = unittest.mock.MagicMock()
        base.quote = unittest.mock.Mock(wraps=urllib.parse.quote)
        node = "http://foobar/#baz"
        self.c.set_user_db_path(base.userp)

        with contextlib.ExitStack() as stack:
            quote = stack.enter_context(unittest.mock.patch(
                "urllib.parse.quote",
                new=base.quote
            ))

            read_single_xso = stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.read_single_xso",
                new=base.read_single_xso
            ))

            result = self.c.lookup_in_database("sha-1", node)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.quote(node, safe=""),
                unittest.mock.call.userp.__truediv__(
                    "sha-1_http%3A%2F%2Ffoobar%2F%23baz.xml"),
                unittest.mock.call.userp.__truediv__().open("rb"),
                unittest.mock.call.userp.__truediv__().open().__enter__(),
                unittest.mock.call.read_single_xso(
                    base.userp.__truediv__().open(),
                    disco.xso.InfoQuery,
                ),
                unittest.mock.call.userp.__truediv__().open().__exit__(
                    None, None, None
                ),
            ]
        )

        self.assertEqual(
            result,
            base.read_single_xso()
        )

    def test_lookup_uses_lookup_in_database(self):
        hash_ = object()
        node = object()

        with unittest.mock.patch.object(
                self.c,
                "lookup_in_database") as lookup_in_database:
            result = run_coroutine(self.c.lookup(hash_, node))

        lookup_in_database.assert_called_with(hash_, node)
        self.assertEqual(result, lookup_in_database())

    def test_create_query_future_used_by_lookup(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_, base.node),
                fut,
            )

            task = asyncio.async(
                self.c.lookup(base.hash_, base.node)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut.set_result(base.result)

            run_coroutine(asyncio.sleep(0))

            self.assertIs(task.result(), base.result)

    def test_lookup_key_errors_if_no_matching_entry_or_future(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_, base.node),
                fut,
            )

            with self.assertRaises(KeyError):
                run_coroutine(self.c.lookup(base.hash_, base.other_node))

    def test_lookup_loops_on_query_futures(self):
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut1
            self.c.create_query_future(base.hash_, base.node)

            task = asyncio.async(
                self.c.lookup(base.hash_, base.node)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut1.set_exception(ValueError())

            base.Future.return_value = fut2
            self.c.create_query_future(base.hash_, base.node)

            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut2.set_exception(ValueError())

            base.Future.return_value = fut3
            self.c.create_query_future(base.hash_, base.node)

            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut3.set_result(base.result)

            run_coroutine(asyncio.sleep(0))

            self.assertIs(task.result(), base.result)

    def test_lookup_key_errors_if_last_query_future_fails(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_, base.node),
                fut,
            )

            task = asyncio.async(
                self.c.lookup(base.hash_, base.node)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut.set_exception(ValueError())

            run_coroutine(asyncio.sleep(0))

            with self.assertRaises(KeyError):
                run_coroutine(task)

    def test_add_cache_entry_is_immediately_visible_in_lookup_and_defers_writeback(self):
        q = disco.xso.InfoQuery()
        p = unittest.mock.Mock()
        hash_ = object()
        node = object()
        self.c.set_user_db_path(p)

        with contextlib.ExitStack() as stack:
            copy = stack.enter_context(unittest.mock.patch(
                "copy.copy"
            ))

            run_in_executor = stack.enter_context(unittest.mock.patch.object(
                asyncio.get_event_loop(),
                "run_in_executor"
            ))

            async = stack.enter_context(unittest.mock.patch(
                "asyncio.async"
            ))

            self.c.add_cache_entry(
                hash_,
                node,
                q,
            )

        copy.assert_called_with(q)
        run_in_executor.assert_called_with(
            None,
            entitycaps_service.writeback,
            p,
            hash_,
            node,
            q.captured_events,
        )
        async.assert_called_with(run_in_executor())

        result = self.c.lookup_in_database(hash_, node)
        self.assertEqual(result, copy())
        self.assertEqual(result.node, node)

    def test_add_cache_entry_does_not_perform_writeback_if_no_userdb_is_set(self):
        q = disco.xso.InfoQuery()
        p = unittest.mock.Mock()
        hash_ = object()
        node = object()

        with contextlib.ExitStack() as stack:
            copy = stack.enter_context(unittest.mock.patch(
                "copy.copy"
            ))

            run_in_executor = stack.enter_context(unittest.mock.patch.object(
                asyncio.get_event_loop(),
                "run_in_executor"
            ))

            async = stack.enter_context(unittest.mock.patch(
                "asyncio.async"
            ))

            self.c.add_cache_entry(
                hash_,
                node,
                q,
            )

        copy.assert_called_with(q)
        self.assertFalse(run_in_executor.mock_calls)
        self.assertFalse(async.mock_calls)

        result = self.c.lookup_in_database(hash_, node)
        self.assertEqual(result, copy())
        self.assertEqual(result.node, node)

    def tearDown(self):
        del self.c


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.disco_client = unittest.mock.Mock()
        self.disco_client.query_info = CoroutineMock()
        self.disco_client.query_info.side_effect = AssertionError()
        self.disco_server = unittest.mock.Mock()
        self.disco_server.on_info_changed.context_connect = \
            unittest.mock.MagicMock()
        self.s = entitycaps_service.EntityCapsService(
            self.cc,
            dependencies={
                disco.DiscoClient: self.disco_client,
                disco.DiscoServer: self.disco_server,
            }
        )

        self.disco_client.mock_calls.clear()
        self.disco_server.mock_calls.clear()
        self.cc.mock_calls.clear()

        self.disco_server.iter_features.return_value = [
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ]

        self.disco_server.iter_identities.return_value = [
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ]

    def test_is_Service_subclass(self):
        self.assertTrue(issubclass(
            entitycaps_service.EntityCapsService,
            service.Service
        ))

    def test_after_disco(self):
        self.assertLess(
            disco.DiscoServer,
            entitycaps_service.EntityCapsService
        )
        self.assertLess(
            disco.DiscoClient,
            entitycaps_service.EntityCapsService
        )

    def test_setup_and_shutdown(self):
        cc = make_connected_client()
        disco_service = unittest.mock.Mock()
        disco_service.on_info_changed.context_connect = \
            unittest.mock.MagicMock()

        cc.mock_calls.clear()
        s = entitycaps_service.EntityCapsService(cc, dependencies={
            disco.DiscoServer: disco_service,
            disco.DiscoClient: None,  # unused, but queried during init
        })

        cc.mock_calls.clear()

        self.maxDiff = None
        self.assertSequenceEqual(
            disco_service.mock_calls,
            [
                # make sure that the callback is connected first, this will
                # make us receive the on_info_changed which causes the hash to
                # update
                unittest.mock.call.on_info_changed.context_connect(
                    s._info_changed,
                    callbacks.AdHocSignal.STRONG,
                ),
                unittest.mock.call.on_info_changed.context_connect(
                    s._info_changed
                ).__enter__(unittest.mock.ANY),
                unittest.mock.call.register_feature(
                    "http://jabber.org/protocol/caps"
                ),
            ]
        )
        disco_service.mock_calls.clear()

        run_coroutine(s.shutdown())

        calls = list(disco_service.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.unregister_feature(
                    "http://jabber.org/protocol/caps"
                ),
                unittest.mock.call.on_info_changed.context_connect().__exit__(
                    unittest.mock.ANY,
                    None,
                    None,
                    None,
                )
            ]
        )

    def test_handle_outbound_presence_is_decorated(self):
        self.assertTrue(
            service.is_outbound_presence_filter(
                entitycaps_service.EntityCapsService.handle_outbound_presence,
            )
        )

    def test_handle_inbound_presence_is_decorated(self):
        self.assertTrue(
            service.is_inbound_presence_filter(
                entitycaps_service.EntityCapsService.handle_inbound_presence,
            )
        )

    def test_cache_defaults(self):
        self.assertIsInstance(
            self.s.cache,
            entitycaps_service.Cache
        )

    def test_cache_defaults_when_deleted(self):
        c1 = self.s.cache
        del self.s.cache
        c2 = self.s.cache
        self.assertIsNot(c1, c2)
        self.assertIsInstance(c2, entitycaps_service.Cache)

    def test_cache_can_be_set(self):
        c = unittest.mock.Mock()
        self.s.cache = c
        self.assertIs(self.s.cache, c)

    def test_handle_inbound_presence_queries_disco(self):
        caps = entitycaps_xso.Caps(
            TEST_DB_ENTRY_NODE_BARE,
            TEST_DB_ENTRY_VER,
            TEST_DB_ENTRY_HASH,
        )

        presence = stanza.Presence()
        presence.from_ = TEST_FROM
        presence.xep0115_caps = caps

        with contextlib.ExitStack() as stack:
            async = stack.enter_context(
                unittest.mock.patch("asyncio.async")
            )

            lookup_info = stack.enter_context(
                unittest.mock.patch.object(self.s, "lookup_info")
            )

            result = self.s.handle_inbound_presence(presence)

        lookup_info.assert_called_with(
            presence.from_,
            caps.node, caps.ver, caps.hash_
        )

        async.assert_called_with(
            lookup_info()
        )

        self.disco_client.set_info_future.assert_called_with(
            TEST_FROM,
            None,
            async(),
        )

        self.assertIs(
            result,
            presence
        )

        self.assertIs(presence.xep0115_caps, caps)

    def test_handle_inbound_presence_deals_with_None(self):
        presence = stanza.Presence()
        presence.from_ = TEST_FROM
        presence.xep0115_caps = None

        with contextlib.ExitStack() as stack:
            async = stack.enter_context(
                unittest.mock.patch("asyncio.async")
            )

            lookup_info = stack.enter_context(
                unittest.mock.patch.object(self.s, "lookup_info")
            )

            result = self.s.handle_inbound_presence(presence)

        self.assertFalse(lookup_info.mock_calls)
        self.assertFalse(async.mock_calls)
        self.assertFalse(self.disco_client.mock_calls)
        self.assertIs(
            result,
            presence
        )

        self.assertIsNone(presence.xep0115_caps)

    def test_handle_inbound_presence_discards_if_hash_unset(self):
        caps = entitycaps_xso.Caps(
            TEST_DB_ENTRY_NODE_BARE,
            TEST_DB_ENTRY_VER,
            TEST_DB_ENTRY_HASH,
        )

        # we have to hack deeply here, the validators are too smart for us
        # it is still possible to receive such a stanza, as the validator is
        # set to FROM_CODE
        caps._xso_contents[entitycaps_xso.Caps.hash_.xq_descriptor] = None
        self.assertIsNone(caps.hash_)

        presence = stanza.Presence()
        presence.xep0115_caps = caps

        with unittest.mock.patch("asyncio.async") as async:
            result = self.s.handle_inbound_presence(presence)

        self.assertFalse(async.mock_calls)

        self.assertIs(
            result,
            presence
        )

        self.assertIs(presence.xep0115_caps, caps)

    def test_query_and_cache(self):
        self.maxDiff = None

        ver = TEST_DB_ENTRY_VER
        response = TEST_DB_ENTRY

        base = unittest.mock.Mock()
        base.disco = self.disco_client
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            base.hash_query.return_value = ver

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.add_cache_entry(
                    "sha-1",
                    "foobar#"+ver,
                    response,
                ),
                unittest.mock.call.fut.set_result(
                    result,
                )
            ]
        )

        self.assertEqual(result, response)

    def test_query_and_cache_checks_hash(self):
        self.maxDiff = None

        ver = TEST_DB_ENTRY_VER
        response = TEST_DB_ENTRY

        base = unittest.mock.Mock()
        base.disco = self.disco_client
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            base.hash_query.return_value = ver[:2]

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.fut.set_exception(unittest.mock.ANY)
            ]
        )

        _, (exc,), _ = base.fut.mock_calls[0]
        self.assertIsInstance(exc, ValueError)

        self.assertEqual(result, response)

    def test_query_and_cache_does_not_cache_on_ValueError(self):
        self.maxDiff = None

        ver = TEST_DB_ENTRY_VER
        response = TEST_DB_ENTRY

        base = unittest.mock.Mock()
        base.disco = self.disco_client
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            exc = ValueError()
            base.hash_query.side_effect = exc

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.fut.set_exception(exc)
            ]
        )

        self.assertEqual(result, response)

    def test_lookup_info_asks_cache_first_and_returns_value(self):
        base = unittest.mock.Mock()
        base.disco = self.disco_client
        base.disco.query_info.side_effect = None
        base.query_and_cache = CoroutineMock()
        base.lookup = CoroutineMock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "lookup",
                new=base.lookup,
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s,
                "query_and_cache",
                new=base.query_and_cache
            ))

            cache_result = {}
            base.lookup.return_value = cache_result

            result = run_coroutine(self.s.lookup_info(
                TEST_FROM,
                "foobar",
                "ver",
                "hash"
            ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.lookup("hash", "foobar#ver"),
            ]
        )

        self.assertIs(result, cache_result)

    def test_lookup_info_delegates_to_query_and_cache_on_miss(self):
        base = unittest.mock.Mock()
        base.disco = self.disco_client
        base.disco.query_info.side_effect = None
        base.query_and_cache = CoroutineMock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "lookup",
                new=base.lookup
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "create_query_future",
                new=base.create_query_future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s,
                "query_and_cache",
                new=base.query_and_cache
            ))

            query_result = {}
            base.lookup.side_effect = KeyError()
            base.query_and_cache.return_value = query_result

            result = run_coroutine(self.s.lookup_info(
                TEST_FROM,
                "foobar",
                "ver",
                "hash"
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.lookup("hash", "foobar#ver"),
                unittest.mock.call.create_query_future("hash", "foobar#ver"),
                unittest.mock.call.query_and_cache(
                    TEST_FROM,
                    "foobar",
                    "ver",
                    "hash",
                    base.create_query_future()
                )
            ]
        )

        self.assertIs(result, query_result)

    def test_update_hash(self):
        iter_features_result = iter([
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ])

        self.disco_server.iter_features.return_value = iter_features_result

        self.disco_server.iter_identities.return_value = iter([
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ])

        self.s.ver = "old_ver"
        old_ver = self.s.ver

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.disco.xso.InfoQuery",
                new=base.InfoQuery
            ))

            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        base.InfoQuery.assert_called_with(
            identities=[
                disco.xso.Identity(category="client",
                                   type_="pc"),
                disco.xso.Identity(category="client",
                                   type_="pc",
                                   lang=structs.LanguageTag.fromstr("en"),
                                   name="foo"),
            ],
            features=iter_features_result
        )

        base.hash_query.assert_called_with(
            base.InfoQuery(),
            "sha1",
        )

        calls = list(self.disco_server.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.unmount_node(
                    "http://aioxmpp.zombofant.net/#"+old_ver
                ),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco_server,
                ),
            ]
        )

        self.assertEqual(
            self.s.ver,
            base.hash_query()
        )

    def test_update_hash_emits_on_ver_changed(self):
        self.disco_server.iter_features.return_value = iter([
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ])

        self.disco_server.iter_identities.return_value = iter([
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ])

        self.s.ver = "old_ver"

        cb = unittest.mock.Mock()

        self.s.on_ver_changed.connect(cb)

        self.s.update_hash()

        cb.assert_called_with()

    def test_update_hash_noop_if_unchanged(self):
        self.s.ver = "hash_query_result"

        cb = unittest.mock.Mock()

        self.s.on_ver_changed.connect(cb)

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        self.assertFalse(cb.mock_calls)
        calls = list(self.disco_server.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
            ]
        )

    def test_update_hash_no_unmount_if_previous_was_None(self):
        self.s.ver = None

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        calls = list(self.disco_server.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco_server
                ),
            ]
        )

    def test_update_hash_unmount_on_shutdown(self):
        self.s.ver = None

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        calls = list(self.disco_server.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco_server
                ),
            ]
        )

        self.disco_server.mock_calls.clear()

        run_coroutine(self.s.shutdown())

        calls = list(self.disco_server.mock_calls)
        self.assertIn(
            unittest.mock.call.unmount_node(
                "http://aioxmpp.zombofant.net/#"+base.hash_query(),
            ),
            calls
        )

    def test__info_changed_calls_update_hash_soon(self):
        with contextlib.ExitStack() as stack:
            get_event_loop = stack.enter_context(unittest.mock.patch(
                "asyncio.get_event_loop"
            ))

            self.s._info_changed()

        get_event_loop.assert_called_with()
        get_event_loop().call_soon.assert_called_with(
            self.s.update_hash
        )

    def test_handle_outbound_presence_does_not_attach_caps_if_ver_is_None(
            self):
        self.s.ver = None

        presence = stanza.Presence()
        result = self.s.handle_outbound_presence(presence)
        self.assertIs(result, presence)

        self.assertIsNone(presence.xep0115_caps, None)

    def test_handle_outbound_presence_attaches_caps_if_not_None(self):
        self.s.ver = "foo"

        presence = stanza.Presence()
        result = self.s.handle_outbound_presence(presence)
        self.assertIs(result, presence)

        self.assertIsInstance(
            presence.xep0115_caps,
            entitycaps_xso.Caps
        )
        self.assertEqual(
            presence.xep0115_caps.ver,
            self.s.ver
        )
        self.assertEqual(
            presence.xep0115_caps.node,
            self.s.NODE
        )
        self.assertEqual(
            presence.xep0115_caps.hash_,
            "sha-1"
        )
        self.assertEqual(
            presence.xep0115_caps.ext,
            None
        )

    def test_handle_outbound_presence_does_not_attach_caps_to_non_available(
            self):
        self.s.ver = "foo"

        types = [
            structs.PresenceType.UNAVAILABLE,
            structs.PresenceType.SUBSCRIBE,
            structs.PresenceType.SUBSCRIBED,
            structs.PresenceType.UNSUBSCRIBE,
            structs.PresenceType.UNSUBSCRIBED,
            structs.PresenceType.ERROR,
        ]

        for type_ in types:
            presence = stanza.Presence(type_=type_)
            result = self.s.handle_outbound_presence(presence)
            self.assertIs(result, presence)
            self.assertIsNone(result.xep0115_caps)


class Testwriteback(unittest.TestCase):
    def test_uses_tempfile_atomically_and_serialises_xso(self):
        base = unittest.mock.Mock()
        base.p = unittest.mock.MagicMock()
        base.NamedTemporaryFile = unittest.mock.MagicMock()
        base.hash_ = "sha-1"
        base.node = "http://fnord/#foo"

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "tempfile.NamedTemporaryFile",
                new=base.NamedTemporaryFile
            ))

            stack.enter_context(unittest.mock.patch(
                "os.replace",
                new=base.replace
            ))

            stack.enter_context(unittest.mock.patch(
                "os.unlink",
                new=base.unlink
            ))

            base.quote = unittest.mock.Mock(wraps=urllib.parse.quote)
            stack.enter_context(unittest.mock.patch(
                "urllib.parse.quote",
                new=base.quote,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.XMPPXMLGenerator",
                new=base.XMPPXMLGenerator
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xso.events_to_sax",
                new=base.events_to_sax
            ))

            entitycaps_service.writeback(base.p,
                                         base.hash_,
                                         base.node,
                                         base.data)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.quote(base.node, safe=""),
                unittest.mock.call.p.__truediv__(
                    "sha-1_http%3A%2F%2Ffnord%2F%23foo.xml"
                ),
                unittest.mock._Call(("p.__str__", (), {})),
                unittest.mock.call.NamedTemporaryFile(
                    dir=str(base.p),
                    delete=False
                ),
                unittest.mock.call.NamedTemporaryFile().__enter__(),
                unittest.mock.call.XMPPXMLGenerator(
                    base.NamedTemporaryFile().__enter__(),
                    short_empty_elements=True,
                ),
                unittest.mock.call.XMPPXMLGenerator().startDocument(),
                unittest.mock.call.events_to_sax(
                    base.data,
                    base.XMPPXMLGenerator()
                ),
                unittest.mock.call.XMPPXMLGenerator().endDocument(),
                unittest.mock._Call(("p.__truediv__().__str__", (), {})),
                unittest.mock.call.replace(
                    base.NamedTemporaryFile().__enter__().name,
                    str(base.p.__truediv__()),
                ),
                unittest.mock.call.NamedTemporaryFile().__exit__(
                    None, None, None
                ),
            ]
        )

    def test_unlinks_tempfile_on_error(self):
        base = unittest.mock.Mock()
        base.p = unittest.mock.MagicMock()
        base.NamedTemporaryFile = unittest.mock.MagicMock()
        base.hash_ = "sha-1"
        base.node = "http://fnord/#foo"

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "tempfile.NamedTemporaryFile",
                new=base.NamedTemporaryFile
            ))

            stack.enter_context(unittest.mock.patch(
                "os.replace",
                new=base.replace
            ))

            stack.enter_context(unittest.mock.patch(
                "os.unlink",
                new=base.unlink
            ))

            base.quote = unittest.mock.Mock(wraps=urllib.parse.quote)
            stack.enter_context(unittest.mock.patch(
                "urllib.parse.quote",
                new=base.quote,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xml.XMPPXMLGenerator",
                new=base.XMPPXMLGenerator
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.xso.events_to_sax",
                new=base.events_to_sax
            ))

            exc = Exception()
            base.events_to_sax.side_effect = exc

            with self.assertRaises(Exception) as ctx:
                entitycaps_service.writeback(
                    base.p,
                    base.hash_,
                    base.node,
                    base.data)


        self.assertIs(ctx.exception, exc)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.quote(base.node, safe=""),
                unittest.mock.call.p.__truediv__(
                    "sha-1_http%3A%2F%2Ffnord%2F%23foo.xml"
                ),
                unittest.mock._Call(("p.__str__", (), {})),
                unittest.mock.call.NamedTemporaryFile(
                    dir=str(base.p),
                    delete=False
                ),
                unittest.mock.call.NamedTemporaryFile().__enter__(),
                unittest.mock.call.XMPPXMLGenerator(
                    base.NamedTemporaryFile().__enter__(),
                    short_empty_elements=True,
                ),
                unittest.mock.call.XMPPXMLGenerator().startDocument(),
                unittest.mock.call.events_to_sax(
                    base.data,
                    base.XMPPXMLGenerator()
                ),
                unittest.mock.call.unlink(
                    base.NamedTemporaryFile().__enter__().name
                ),
                unittest.mock.call.NamedTemporaryFile().__exit__(
                    unittest.mock.ANY,
                    unittest.mock.ANY,
                    unittest.mock.ANY,
                ),
            ]
        )

# foo
