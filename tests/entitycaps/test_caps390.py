########################################################################
# File name: test_caps390.py
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
import io
import pathlib
import unittest
import unittest.mock
import urllib.parse

import aioxmpp
import aioxmpp.entitycaps.caps390 as caps390
import aioxmpp.entitycaps.xso as caps_xso


def _parse_testcase(data):
    src = io.BytesIO(data)
    return aioxmpp.xml.read_single_xso(src, aioxmpp.disco.xso.InfoQuery)


TEST_SMALL = _parse_testcase(b"""\
<query xmlns="http://jabber.org/protocol/disco#info">
  <identity category="client" name="BombusMod" type="mobile"/>
  <feature var="http://jabber.org/protocol/si"/>
  <feature var="http://jabber.org/protocol/bytestreams"/>
  <feature var="http://jabber.org/protocol/chatstates"/>
  <feature var="http://jabber.org/protocol/disco#info"/>
  <feature var="http://jabber.org/protocol/disco#items"/>
  <feature var="urn:xmpp:ping"/>
  <feature var="jabber:iq:time"/>
  <feature var="jabber:iq:privacy"/>
  <feature var="jabber:iq:version"/>
  <feature var="http://jabber.org/protocol/rosterx"/>
  <feature var="urn:xmpp:time"/>
  <feature var="jabber:x:oob"/>
  <feature var="http://jabber.org/protocol/ibb"/>
  <feature var="http://jabber.org/protocol/si/profile/file-transfer"/>
  <feature var="urn:xmpp:receipts"/>
  <feature var="jabber:iq:roster"/>
  <feature var="jabber:iq:last"/>
</query>""")

TEST_LARGE = _parse_testcase("""\
<query xmlns="http://jabber.org/protocol/disco#info">
  <identity category="client" name="Tkabber" type="pc" xml:lang="en"/>
  <identity category="client" name="Ткаббер" type="pc" xml:lang="ru"/>
  <feature var="games:board"/>
  <feature var="http://jabber.org/protocol/activity"/>
  <feature var="http://jabber.org/protocol/activity+notify"/>
  <feature var="http://jabber.org/protocol/bytestreams"/>
  <feature var="http://jabber.org/protocol/chatstates"/>
  <feature var="http://jabber.org/protocol/commands"/>
  <feature var="http://jabber.org/protocol/disco#info"/>
  <feature var="http://jabber.org/protocol/disco#items"/>
  <feature var="http://jabber.org/protocol/evil"/>
  <feature var="http://jabber.org/protocol/feature-neg"/>
  <feature var="http://jabber.org/protocol/geoloc"/>
  <feature var="http://jabber.org/protocol/geoloc+notify"/>
  <feature var="http://jabber.org/protocol/ibb"/>
  <feature var="http://jabber.org/protocol/iqibb"/>
  <feature var="http://jabber.org/protocol/mood"/>
  <feature var="http://jabber.org/protocol/mood+notify"/>
  <feature var="http://jabber.org/protocol/rosterx"/>
  <feature var="http://jabber.org/protocol/si"/>
  <feature var="http://jabber.org/protocol/si/profile/file-transfer"/>
  <feature var="http://jabber.org/protocol/tune"/>
  <feature var="http://www.facebook.com/xmpp/messages"/>
  <feature var="http://www.xmpp.org/extensions/xep-0084.html#ns-metadata+notify"/>
  <feature var="jabber:iq:avatar"/>
  <feature var="jabber:iq:browse"/>
  <feature var="jabber:iq:dtcp"/>
  <feature var="jabber:iq:filexfer"/>
  <feature var="jabber:iq:ibb"/>
  <feature var="jabber:iq:inband"/>
  <feature var="jabber:iq:jidlink"/>
  <feature var="jabber:iq:last"/>
  <feature var="jabber:iq:oob"/>
  <feature var="jabber:iq:privacy"/>
  <feature var="jabber:iq:roster"/>
  <feature var="jabber:iq:time"/>
  <feature var="jabber:iq:version"/>
  <feature var="jabber:x:data"/>
  <feature var="jabber:x:event"/>
  <feature var="jabber:x:oob"/>
  <feature var="urn:xmpp:avatar:metadata+notify"/>
  <feature var="urn:xmpp:ping"/>
  <feature var="urn:xmpp:receipts"/>
  <feature var="urn:xmpp:time"/>
  <x xmlns="jabber:x:data" type="result">
    <field type="hidden" var="FORM_TYPE">
      <value>urn:xmpp:dataforms:softwareinfo</value>
    </field>
    <field var="software">
      <value>Tkabber</value>
    </field>
    <field var="software_version">
      <value>0.11.1-svn-20111216-mod (Tcl/Tk 8.6b2)</value>
    </field>
    <field var="os">
      <value>Windows</value>
    </field>
    <field var="os_version">
      <value>XP</value>
    </field>
  </x>
</query>""".encode("utf-8"))


class Test_process_features(unittest.TestCase):
    def test_on_small_testcase(self):
        self.assertEqual(
            caps390._process_features(TEST_SMALL.features),
            b'http://jabber.org/protocol/bytestreams\x1fhttp://jabber.org/prot'
            b'ocol/chatstates\x1fhttp://jabber.org/protocol/disco#info\x1fhttp'
            b'://jabber.org/protocol/disco#items\x1fhttp://jabber.org/protocol'
            b'/ibb\x1fhttp://jabber.org/protocol/rosterx\x1fhttp://jabber.org/'
            b'protocol/si\x1fhttp://jabber.org/protocol/si/profile/file-transf'
            b'er\x1fjabber:iq:last\x1fjabber:iq:privacy\x1fjabber:iq:roster'
            b'\x1fjabber:iq:time\x1fjabber:iq:version\x1fjabber:x:oob\x1furn:x'
            b'mpp:ping\x1furn:xmpp:receipts\x1furn:xmpp:time\x1f\x1c'
        )

    def test_on_large_testcase(self):
        self.assertEqual(
            caps390._process_features(TEST_LARGE.features),
            b'games:board\x1fhttp://jabber.org/protocol/activity\x1fhttp://jab'
            b'ber.org/protocol/activity+notify\x1fhttp://jabber.org/protocol/b'
            b'ytestreams\x1fhttp://jabber.org/protocol/chatstates\x1fhttp://ja'
            b'bber.org/protocol/commands\x1fhttp://jabber.org/protocol/disco#i'
            b'nfo\x1fhttp://jabber.org/protocol/disco#items\x1fhttp://jabber.o'
            b'rg/protocol/evil\x1fhttp://jabber.org/protocol/feature-neg\x1fht'
            b'tp://jabber.org/protocol/geoloc\x1fhttp://jabber.org/protocol/ge'
            b'oloc+notify\x1fhttp://jabber.org/protocol/ibb\x1fhttp://jabber.o'
            b'rg/protocol/iqibb\x1fhttp://jabber.org/protocol/mood\x1fhttp://j'
            b'abber.org/protocol/mood+notify\x1fhttp://jabber.org/protocol/ros'
            b'terx\x1fhttp://jabber.org/protocol/si\x1fhttp://jabber.org/proto'
            b'col/si/profile/file-transfer\x1fhttp://jabber.org/protocol/tune'
            b'\x1fhttp://www.facebook.com/xmpp/messages\x1fhttp://www.xmpp.org'
            b'/extensions/xep-0084.html#ns-metadata+notify\x1fjabber:iq:avatar'
            b'\x1fjabber:iq:browse\x1fjabber:iq:dtcp\x1fjabber:iq:filexfer\x1f'
            b'jabber:iq:ibb\x1fjabber:iq:inband\x1fjabber:iq:jidlink\x1fjabber'
            b':iq:last\x1fjabber:iq:oob\x1fjabber:iq:privacy\x1fjabber:iq:rost'
            b'er\x1fjabber:iq:time\x1fjabber:iq:version\x1fjabber:x:data\x1fja'
            b'bber:x:event\x1fjabber:x:oob\x1furn:xmpp:avatar:metadata+notify'
            b'\x1furn:xmpp:ping\x1furn:xmpp:receipts\x1furn:xmpp:time\x1f\x1c'
        )


class Test_process_identities(unittest.TestCase):
    def test_on_small_testcase(self):
        self.assertEqual(
            caps390._process_identities(TEST_SMALL.identities),
            b'client\x1fmobile\x1f\x1fBombusMod\x1f\x1e\x1c'
        )

    def test_on_large_testcase(self):
        self.assertEqual(
            caps390._process_identities(TEST_LARGE.identities),
            b'client\x1fpc\x1fen\x1fTkabber\x1f\x1eclient\x1fpc\x1fru\x1f\xd0'
            b'\xa2\xd0\xba\xd0\xb0\xd0\xb1\xd0\xb1\xd0\xb5\xd1\x80\x1f\x1e\x1c'
        )


class Test_process_extensions(unittest.TestCase):
    def test_on_small_testcase(self):
        self.assertEqual(
            caps390._process_extensions(TEST_SMALL.exts),
            b'\x1c'
        )

    def test_on_large_testcase(self):
        self.assertEqual(
            caps390._process_extensions(TEST_LARGE.exts),
            b'FORM_TYPE\x1furn:xmpp:dataforms:softwareinfo\x1f\x1eos\x1fWindow'
            b's\x1f\x1eos_version\x1fXP\x1f\x1esoftware\x1fTkabber\x1f\x1esoft'
            b'ware_version\x1f0.11.1-svn-20111216-mod (Tcl/Tk 8.6b2)\x1f\x1e'
            b'\x1d\x1c'
        )


class Test_get_hash_input(unittest.TestCase):
    def test_on_small_testcase(self):
        self.assertEqual(
            caps390._get_hash_input(TEST_SMALL),
            b'http://jabber.org/protocol/bytestreams\x1fhttp://jabber.org/prot'
            b'ocol/chatstates\x1fhttp://jabber.org/protocol/disco#info\x1fhttp'
            b'://jabber.org/protocol/disco#items\x1fhttp://jabber.org/protocol'
            b'/ibb\x1fhttp://jabber.org/protocol/rosterx\x1fhttp://jabber.org/'
            b'protocol/si\x1fhttp://jabber.org/protocol/si/profile/file-transf'
            b'er\x1fjabber:iq:last\x1fjabber:iq:privacy\x1fjabber:iq:roster'
            b'\x1fjabber:iq:time\x1fjabber:iq:version\x1fjabber:x:oob\x1furn:x'
            b'mpp:ping\x1furn:xmpp:receipts\x1furn:xmpp:time\x1f\x1cclient\x1f'
            b'mobile\x1f\x1fBombusMod\x1f\x1e\x1c\x1c'
        )

    def test_on_large_testcase(self):
        self.assertEqual(
            caps390._get_hash_input(TEST_LARGE),
            b'games:board\x1fhttp://jabber.org/protocol/activity\x1fhttp://jab'
            b'ber.org/protocol/activity+notify\x1fhttp://jabber.org/protocol/b'
            b'ytestreams\x1fhttp://jabber.org/protocol/chatstates\x1fhttp://ja'
            b'bber.org/protocol/commands\x1fhttp://jabber.org/protocol/disco#i'
            b'nfo\x1fhttp://jabber.org/protocol/disco#items\x1fhttp://jabber.o'
            b'rg/protocol/evil\x1fhttp://jabber.org/protocol/feature-neg\x1fht'
            b'tp://jabber.org/protocol/geoloc\x1fhttp://jabber.org/protocol/ge'
            b'oloc+notify\x1fhttp://jabber.org/protocol/ibb\x1fhttp://jabber.o'
            b'rg/protocol/iqibb\x1fhttp://jabber.org/protocol/mood\x1fhttp://j'
            b'abber.org/protocol/mood+notify\x1fhttp://jabber.org/protocol/ros'
            b'terx\x1fhttp://jabber.org/protocol/si\x1fhttp://jabber.org/proto'
            b'col/si/profile/file-transfer\x1fhttp://jabber.org/protocol/tune'
            b'\x1fhttp://www.facebook.com/xmpp/messages\x1fhttp://www.xmpp.org'
            b'/extensions/xep-0084.html#ns-metadata+notify\x1fjabber:iq:avatar'
            b'\x1fjabber:iq:browse\x1fjabber:iq:dtcp\x1fjabber:iq:filexfer\x1f'
            b'jabber:iq:ibb\x1fjabber:iq:inband\x1fjabber:iq:jidlink\x1fjabber'
            b':iq:last\x1fjabber:iq:oob\x1fjabber:iq:privacy\x1fjabber:iq:rost'
            b'er\x1fjabber:iq:time\x1fjabber:iq:version\x1fjabber:x:data\x1fja'
            b'bber:x:event\x1fjabber:x:oob\x1furn:xmpp:avatar:metadata+notify'
            b'\x1furn:xmpp:ping\x1furn:xmpp:receipts\x1furn:xmpp:time\x1f\x1cc'
            b'lient\x1fpc\x1fen\x1fTkabber\x1f\x1eclient\x1fpc\x1fru\x1f\xd0'
            b'\xa2\xd0\xba\xd0\xb0\xd0\xb1\xd0\xb1\xd0\xb5\xd1\x80\x1f\x1e\x1c'
            b'FORM_TYPE\x1furn:xmpp:dataforms:softwareinfo\x1f\x1eos\x1fWindow'
            b's\x1f\x1eos_version\x1fXP\x1f\x1esoftware\x1fTkabber\x1f\x1esoft'
            b'ware_version\x1f0.11.1-svn-20111216-mod (Tcl/Tk 8.6b2)\x1f\x1e'
            b'\x1d\x1c'
        )


class Test_calculate_hash(unittest.TestCase):
    def test_uses_and_hash_from_algo(self):
        with contextlib.ExitStack() as stack:
            hash_from_algo = stack.enter_context(
                unittest.mock.patch("aioxmpp.hashes.hash_from_algo")
            )

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )

            result = caps390._calculate_hash(
                unittest.mock.sentinel.algo,
                unittest.mock.sentinel.hash_input,
            )

        hash_from_algo.assert_called_once_with(unittest.mock.sentinel.algo)
        _get_hash_input.assert_not_called()

        hash_from_algo().update.assert_called_once_with(
            unittest.mock.sentinel.hash_input
        )
        hash_from_algo().digest.assert_called_once_with()

        self.assertEqual(
            result,
            hash_from_algo().digest(),
        )


class TestKey(unittest.TestCase):
    def test_init_default(self):
        with self.assertRaises(TypeError):
            caps390.Key()

    def test_init_args(self):
        k = caps390.Key("algo", b"digest")

        self.assertEqual(
            k.algo,
            "algo",
        )
        self.assertEqual(
            k.digest,
            b"digest",
        )

    def test_init_kwargs(self):
        k = caps390.Key(algo="somealgo", digest=b"somedigest")

        self.assertEqual(
            k.algo,
            "somealgo",
        )
        self.assertEqual(
            k.digest,
            b"somedigest",
        )

    def test_hashable(self):
        k1 = caps390.Key("algo", b"digest")
        k2 = caps390.Key("algo", b"digest")

        self.assertEqual(hash(k1), hash(k2))

    def test_equality(self):
        k1 = caps390.Key("algo", b"digest")
        k2 = caps390.Key("algo", b"digest")
        k3 = caps390.Key("somealgo", b"otherdigest")

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

    def test_node(self):
        k1 = caps390.Key("algo", b"digest")

        self.assertEqual(
            k1.node,
            "urn:xmpp:caps#algo.ZGlnZXN0"
        )

        k1 = caps390.Key("somealgo", b"otherdigest")

        self.assertEqual(
            k1.node,
            "urn:xmpp:caps#somealgo.b3RoZXJkaWdlc3Q="
        )

    def test_path(self):
        k1 = caps390.Key("algo", b"digest")

        self.assertEqual(
            k1.path,
            pathlib.Path("caps2") / "algo" / "mr" / "uw" / "ozltoq.xml",
        )

        k1 = caps390.Key("somealgo", b"otherdigest")

        self.assertEqual(
            k1.path,
            pathlib.Path("caps2") / "somealgo" / "n5" / "2g" /
            "qzlsmruwozltoq.xml",
        )

    def test_path_urlencodes_algo(self):
        quote = unittest.mock.Mock(wraps=urllib.parse.quote)
        k = caps390.Key("/.$?", b"digest")

        with unittest.mock.patch("urllib.parse.quote", new=quote):
            path = k.path

        quote.assert_called_once_with("/.$?", safe="")

        self.assertEqual(
            path,
            pathlib.Path("caps2") / "%2F.%24%3F" / "mr" / "uw" / "ozltoq.xml",
        )

    def test_verify_consults__calculate_hash(self):
        k = caps390.Key(
            unittest.mock.sentinel.key_algo,
            unittest.mock.sentinel.key_digest,
        )

        info = unittest.mock.Mock(
            spec=aioxmpp.disco.xso.InfoQuery
        )

        with contextlib.ExitStack() as stack:
            _calculate_hash = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._calculate_hash"
                )
            )
            _calculate_hash.return_value = unittest.mock.sentinel.key_digest

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )

            self.assertTrue(
                k.verify(info)
            )

            _get_hash_input.assert_called_once_with(
                info,
            )

            _calculate_hash.assert_called_once_with(
                unittest.mock.sentinel.key_algo,
                _get_hash_input(),
            )

    def test_verify_can_use_precalculated_hash_input(self):
        k = caps390.Key(
            unittest.mock.sentinel.key_algo,
            unittest.mock.sentinel.key_digest,
        )

        hash_input = unittest.mock.Mock(
            spec=bytes
        )

        with contextlib.ExitStack() as stack:
            _calculate_hash = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._calculate_hash"
                )
            )
            _calculate_hash.return_value = unittest.mock.sentinel.key_digest

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )

            self.assertTrue(
                k.verify(hash_input)
            )

            _get_hash_input.assert_not_called()

            _calculate_hash.assert_called_once_with(
                unittest.mock.sentinel.key_algo,
                hash_input,
            )

    def test_verify_detects_mismatch_with_precalculated_hash_input(self):
        k = caps390.Key(
            unittest.mock.sentinel.key_algo,
            unittest.mock.sentinel.key_digest,
        )

        hash_input = unittest.mock.Mock(
            spec=bytes
        )

        with contextlib.ExitStack() as stack:
            _calculate_hash = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._calculate_hash"
                )
            )
            _calculate_hash.return_value = unittest.mock.sentinel.other_digest

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )

            self.assertFalse(
                k.verify(hash_input)
            )

            _get_hash_input.assert_not_called()

            _calculate_hash.assert_called_once_with(
                unittest.mock.sentinel.key_algo,
                hash_input,
            )

    def test_verify_returns_false_if_digest_mismatches(self):
        k = caps390.Key(
            unittest.mock.sentinel.key_algo,
            unittest.mock.sentinel.key_digest,
        )

        info = unittest.mock.Mock(
            spec=aioxmpp.disco.xso.InfoQuery
        )

        with contextlib.ExitStack() as stack:
            _calculate_hash = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._calculate_hash"
                )
            )
            _calculate_hash.return_value = unittest.mock.sentinel.other_digest

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )

            self.assertFalse(
                k.verify(info)
            )

            _get_hash_input.assert_called_once_with(
                info,
            )

            _calculate_hash.assert_called_once_with(
                unittest.mock.sentinel.key_algo,
                _get_hash_input(),
            )

    def test_verify_small_input(self):
        k = caps390.Key(
            "sha-256",
            caps390._calculate_hash(
                "sha-256",
                caps390._get_hash_input(TEST_SMALL),
            ),
        )

        self.assertTrue(
            k.verify(TEST_SMALL)
        )

        self.assertFalse(
            k.verify(TEST_LARGE)
        )

    def test_verify_small_input_precalculated(self):
        hash_input_small = caps390._get_hash_input(TEST_SMALL)
        hash_input_large = caps390._get_hash_input(TEST_LARGE)

        k = caps390.Key(
            "sha-256",
            caps390._calculate_hash(
                "sha-256",
                hash_input_small,
            ),
        )

        self.assertTrue(
            k.verify(hash_input_small)
        )

        self.assertFalse(
            k.verify(hash_input_large)
        )

    def test_verify_large_input(self):
        k = caps390.Key(
            "sha-256",
            caps390._calculate_hash(
                "sha-256",
                caps390._get_hash_input(TEST_LARGE),
            ),
        )

        self.assertTrue(
            k.verify(TEST_LARGE)
        )

        self.assertFalse(
            k.verify(TEST_SMALL)
        )

    def test_verify_large_input_precalculated(self):
        hash_input_small = caps390._get_hash_input(TEST_SMALL)
        hash_input_large = caps390._get_hash_input(TEST_LARGE)

        k = caps390.Key(
            "sha-256",
            caps390._calculate_hash(
                "sha-256",
                hash_input_large,
            ),
        )

        self.assertTrue(
            k.verify(hash_input_large)
        )

        self.assertFalse(
            k.verify(hash_input_small)
        )


class TestImplementation(unittest.TestCase):
    def setUp(self):
        self.algorithms = [
            unittest.mock.sentinel.algo1,
            unittest.mock.sentinel.algo2
        ]
        self.i = caps390.Implementation(self.algorithms)

    def test_extract_keys_returns_empty_if_caps_is_None(self):
        presence = unittest.mock.Mock(["xep0390_caps"])
        presence.xep0390_caps = None

        self.assertSetEqual(
            set(self.i.extract_keys(presence)),
            set(),
        )

    def test_extract_keys_creates_Key_objects_from_digests_and_checks_for_support(self):  # NOQA
        presence = unittest.mock.Mock(["xep0390_caps"])
        presence.xep0390_caps.digests = {
            unittest.mock.sentinel.palgo1: unittest.mock.sentinel.pdigest1,
            unittest.mock.sentinel.palgo2: unittest.mock.sentinel.pdigest2,
            unittest.mock.sentinel.palgo3: unittest.mock.sentinel.pdigest3,
        }

        def is_algo_supported_impl(algo):
            return algo != unittest.mock.sentinel.palgo2

        with contextlib.ExitStack() as stack:
            is_algo_supported = stack.enter_context(
                unittest.mock.patch("aioxmpp.hashes.is_algo_supported")
            )
            is_algo_supported.side_effect = is_algo_supported_impl

            result = set(self.i.extract_keys(presence))

        self.assertCountEqual(
            is_algo_supported.mock_calls,
            [
                unittest.mock.call(unittest.mock.sentinel.palgo1),
                unittest.mock.call(unittest.mock.sentinel.palgo2),
                unittest.mock.call(unittest.mock.sentinel.palgo3),
            ]
        )

        self.assertSetEqual(
            result,
            {
                caps390.Key(unittest.mock.sentinel.palgo1,
                            unittest.mock.sentinel.pdigest1),
                caps390.Key(unittest.mock.sentinel.palgo3,
                            unittest.mock.sentinel.pdigest3),
            }
        )

    def test_put_keys_inserts_keys_into_presence(self):
        keys = [
            caps390.Key(unittest.mock.sentinel.palgo1,
                        unittest.mock.sentinel.pdigest1),
            caps390.Key(unittest.mock.sentinel.palgo2,
                        unittest.mock.sentinel.pdigest2),
        ]

        presence = unittest.mock.Mock(["xep0390_caps"])
        presence.xep0390_caps = None

        self.i.put_keys(keys, presence)

        self.assertIsInstance(
            presence.xep0390_caps,
            caps_xso.Caps390,
        )

        self.assertDictEqual(
            presence.xep0390_caps.digests,
            {
                unittest.mock.sentinel.palgo1: unittest.mock.sentinel.pdigest1,
                unittest.mock.sentinel.palgo2: unittest.mock.sentinel.pdigest2,
            }
        )

    def test_calculate_keys_efficiently_builds_hashes_for_given_algorithms(self):  # NOQA
        def generate_digests(algo, _):
            assert isinstance(algo, type(unittest.mock.sentinel.foo))
            return getattr(unittest.mock.sentinel, "{}_digest".format(
                algo.name
            ))

        with contextlib.ExitStack() as stack:
            _calculate_hash = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._calculate_hash"
                )
            )
            _calculate_hash.side_effect = generate_digests

            _get_hash_input = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.entitycaps.caps390._get_hash_input"
                )
            )
            _get_hash_input.return_value = unittest.mock.sentinel.hash_input

            result = set(self.i.calculate_keys(unittest.mock.sentinel.info))

        _get_hash_input.assert_called_once_with(
            unittest.mock.sentinel.info
        )

        self.assertCountEqual(
            _calculate_hash.mock_calls,
            [
                unittest.mock.call(algo, unittest.mock.sentinel.hash_input)
                for algo in self.algorithms
            ]
        )

        self.assertSetEqual(
            result,
            {
                caps390.Key(unittest.mock.sentinel.algo1,
                            unittest.mock.sentinel.algo1_digest),
                caps390.Key(unittest.mock.sentinel.algo2,
                            unittest.mock.sentinel.algo2_digest),
            }
        )
