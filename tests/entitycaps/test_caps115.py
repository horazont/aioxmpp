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
import io
import pathlib
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.disco as disco
import aioxmpp.entitycaps.caps115 as caps115
import aioxmpp.entitycaps.xso as caps_xso
import aioxmpp.forms.xso as forms_xso
import aioxmpp.structs as structs


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


class TestKey(unittest.TestCase):
    def test_init_via_args(self):
        k = caps115.Key("algo", "node")

        self.assertEqual(
            k.algo,
            "algo",
        )
        self.assertEqual(
            k.node,
            "node",
        )

    def test_init_via_kwargs(self):
        k = caps115.Key(algo="somealgo", node="somenode")

        self.assertEqual(
            k.algo,
            "somealgo",
        )
        self.assertEqual(
            k.node,
            "somenode",
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            caps115.Key()

    def test_hashable(self):
        k1 = caps115.Key("algo", "node")
        k2 = caps115.Key("algo", "node")

        self.assertEqual(hash(k1), hash(k2))

    def test_equality(self):
        k1 = caps115.Key("algo", "node")
        k2 = caps115.Key("algo", "node")
        k3 = caps115.Key("somealgo", "somenode")

        self.assertTrue(k1 == k2)
        self.assertFalse(k1 != k2)
        self.assertFalse(k1 == k3)
        self.assertTrue(k1 != k3)

        self.assertTrue(k2 == k1)
        self.assertFalse(k2 != k1)
        self.assertFalse(k2 == k3)
        self.assertTrue(k2 != k3)

        self.assertFalse(k3 == k1)
        self.assertTrue(k3 != k1)
        self.assertFalse(k3 == k2)
        self.assertTrue(k3 != k2)

    def test_path(self):
        k1 = caps115.Key("algo", "node")
        k2 = caps115.Key("somealgo", "somenode")

        self.assertEqual(
            k1.path,
            pathlib.Path("hashes") / "{}_{}.xml".format("algo", "node"),
        )

        self.assertEqual(
            k2.path,
            pathlib.Path("hashes") /
            "{}_{}.xml".format("somealgo", "somenode"),
        )

    def test_path_uses_urlescape(self):
        k = caps115.Key("algo", unittest.mock.sentinel.node)

        with contextlib.ExitStack() as stack:
            urlescape = stack.enter_context(
                unittest.mock.patch("urllib.parse.quote"),
            )
            urlescape.return_value = "urlescape_result"

            path = k.path

            urlescape.assert_called_once_with(
                unittest.mock.sentinel.node,
                safe=""
            )

            self.assertEqual(
                path,
                pathlib.Path("hashes") / "algo_urlescape_result.xml"
            )

    def test_ver(self):
        pieces = unittest.mock.Mock()
        node = unittest.mock.Mock()
        node.rsplit.return_value = [
            pieces.wrong,
            pieces.ver,
        ]
        k = caps115.Key("algo", node)

        ver = k.ver

        node.rsplit.assert_called_once_with("#", 1)

        self.assertEqual(ver, pieces.ver)

    def test_verify_detects_correct_hash(self):
        info = unittest.mock.Mock(spec=disco.xso.InfoQuery)
        info.node = "http://foo"
        key = unittest.mock.Mock(spec=caps115.Key)
        key.ver = "hash_query_result"
        key.verify = functools.partial(caps115.Key.verify, key)

        with contextlib.ExitStack() as stack:
            hash_query = stack.enter_context(
                unittest.mock.patch("aioxmpp.entitycaps.caps115.hash_query")
            )
            hash_query.return_value = "hash_query_result"

            result = key.verify(info)

            key.algo.replace.assert_called_once_with("-", "")

            hash_query.assert_called_once_with(
                info,
                key.algo.replace(),
            )

            self.assertTrue(result)

    def test_verify_detects_ignores_node(self):
        info = unittest.mock.Mock(spec=disco.xso.InfoQuery)
        info.node = "http://fnord"
        key = unittest.mock.Mock(spec=caps115.Key)
        key.ver = "hash_query_result"
        key.verify = functools.partial(caps115.Key.verify, key)

        with contextlib.ExitStack() as stack:
            hash_query = stack.enter_context(
                unittest.mock.patch("aioxmpp.entitycaps.caps115.hash_query")
            )
            hash_query.return_value = "hash_query_result"

            result = key.verify(info)

            key.algo.replace.assert_called_once_with("-", "")

            hash_query.assert_called_once_with(
                info,
                key.algo.replace(),
            )

            self.assertTrue(result)

    def test_verify_detects_mismatching_digest(self):
        info = unittest.mock.Mock(spec=disco.xso.InfoQuery)
        info.node = "http://foo"
        key = unittest.mock.Mock(spec=caps115.Key)
        key.ver = "hash_query_result"
        key.verify = functools.partial(caps115.Key.verify, key)

        with contextlib.ExitStack() as stack:
            hash_query = stack.enter_context(
                unittest.mock.patch("aioxmpp.entitycaps.caps115.hash_query")
            )
            hash_query.return_value = "other_hash_query_result"

            result = key.verify(info)

            key.algo.replace.assert_called_once_with("-", "")

            hash_query.assert_called_once_with(
                info,
                key.algo.replace(),
            )

            self.assertFalse(result)


class TestImplementation(unittest.TestCase):
    def setUp(self):
        self.node = "testnode"
        self.i = caps115.Implementation(self.node)

    def test_extract_keys_returns_empty_for_capsless_presence(self):
        p = unittest.mock.Mock(spec=aioxmpp.Presence)
        p.xep0115_caps = None

        self.assertSequenceEqual(
            [],
            list(self.i.extract_keys(p)),
        )

    def test_extract_keys_returns_empty_for_legacy_format(self):
        p = unittest.mock.Mock(spec=aioxmpp.Presence)
        p.xep0115_caps.ver = "ver"
        p.xep0115_caps.node = "node"
        p.xep0115_caps.hash_ = None
        p.xep0115_caps.ext = "something"

        self.assertSequenceEqual(
            [],
            list(self.i.extract_keys(p)),
        )

    def test_extract_keys_obtains_Key_from_Caps115_info(self):
        p = unittest.mock.Mock(spec=aioxmpp.Presence)
        p.xep0115_caps.ver = "ver"
        p.xep0115_caps.node = "node"
        p.xep0115_caps.hash_ = "hashfun"
        p.xep0115_caps.ext = None

        self.assertSequenceEqual(
            [
                caps115.Key("hashfun", "node#ver")
            ],
            list(self.i.extract_keys(p)),
        )

    def test_put_keys_generates_Caps115_object(self):
        key = caps115.Key("algo", "node#ver_from_key")

        p = unittest.mock.Mock(["xep0115_caps"])
        p.xep0115_caps = None

        self.i.put_keys(iter([key]), p)

        self.assertIsInstance(
            p.xep0115_caps,
            caps_xso.Caps115,
        )

        self.assertEqual(
            p.xep0115_caps.node,
            self.node,
        )

        self.assertEqual(
            p.xep0115_caps.ver,
            key.ver
        )

        self.assertEqual(
            p.xep0115_caps.hash_,
            key.algo,
        )

    def test_put_keys_raises_ValueError_if_no_keys_passed(self):
        with self.assertRaisesRegexp(ValueError, "values to unpack"):
            self.i.put_keys(iter([]), unittest.mock.sentinel.presence)

    def test_put_keys_raises_ValueError_if_too_many_keys_passed(self):
        with self.assertRaisesRegexp(ValueError, "too many values"):
            self.i.put_keys(
                iter([unittest.mock.sentinel.k1, unittest.mock.sentinel.k2]),
                unittest.mock.sentinel.presence
            )

    def test_calculate_keys_hashes_query_and_yields_key(self):
        info = unittest.mock.Mock(spec=disco.xso.InfoQuery)

        with contextlib.ExitStack() as stack:
            hash_query = stack.enter_context(
                unittest.mock.patch("aioxmpp.entitycaps.caps115.hash_query")
            )
            hash_query.return_value = "hash_query_result"

            Key = stack.enter_context(
                unittest.mock.patch("aioxmpp.entitycaps.caps115.Key")
            )

            result = list(self.i.calculate_keys(info))

            hash_query.assert_called_once_with(
                info,
                "sha1",
            )

            Key.assert_called_once_with(
                "sha-1",
                "{}#{}".format(self.node, "hash_query_result")
            )

            self.assertSequenceEqual(
                result,
                [Key()],
            )

    def test_calculate_keys_on_real_data(self):
        key, = self.i.calculate_keys(TEST_DB_ENTRY)
        self.assertEqual(
            key,
            caps115.Key(
                TEST_DB_ENTRY_HASH,
                "{}#{}".format(self.node, TEST_DB_ENTRY_VER),
            )
        )

    def test_calculate_keys_verify_roundtrip(self):
        key, = self.i.calculate_keys(TEST_DB_ENTRY)

        self.assertTrue(
            key.verify(TEST_DB_ENTRY)
        )
