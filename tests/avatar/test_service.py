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
import base64
import hashlib
import unittest

import aioxmpp
import aioxmpp.errors as errors
import aioxmpp.avatar.service as avatar_service
import aioxmpp.avatar.xso as avatar_xso
import aioxmpp.disco.xso as disco_xso
import aioxmpp.pubsub.xso as pubsub_xso

from aioxmpp.utils import namespaces
from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_IMAGE = base64.decodebytes(b"""
iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAAABmJLR0QA/wD/AP+gvaeTAAAACXBI
WXMAAA3XAAAN1wFCKJt4AAAAB3RJTUUH1wEPAzgt9urhBgAAERlJREFUeNrt3XuwVtV9h/HncLhY
L0c0lUwxgxEV0TEVxKTUUpFbm9Z6GaeNUWKrZlrFRMeYyUTiLUEbmHaiTknFNDdtY73UsVFiklYu
ahOLjVYcYwRqFBjRRKpcAkrkcvrHWgznHKmHc867915r7+cz847z4px3rf1be3/ffXv3AkmSJEmS
JEmSJEmSJEmSJEmSJEmSJEmSlJq2Fn3ODGCa5ZRKsxh4JIUAmA78ewvDRFLvOoE/ABYN5EMGtaAj
U9z4pUr23qcM9ENaEQCDHAupEgPe9gYX0KkpwFrHppuZwJwu788FnrIs3ZwM3Nvl/fXAXZalm1HA
0lZ+YBEB8JIB8C7/2+P9q7FO2mPkXmpmjbrbkdwuhKQGH0NIMgAkGQCSDABJBoAkA0BSogZbgsYY
DYwHxgBHAsOBjvj/NgMbgZeBVcAzeA3eAFD2e3dTgfMIv9Q8oo9/v4bwi7O7gSXALkvqIYDS1wHM
JtyN+QhwcT82fuLfXBw/Y238zA7LawAoTUOBq4HVwJeBw1v42YfHz1wd2xhquQ0ApWMS8CwwFzik
wHYOiW08G9uUAaCKx+864FFgbIntjo1tXuc6ZACoGvsBDxB+ZtxeQfvtse0HYl9kAKgkBwM/BM5K
oC9nxb4c7LAYACre0PitOzmhPk2OffLkoAGgArURrstPTbBvU2PffD6kAaCCXAWck3D/zol9lAGg
FptAuBafui/HvsoAUIu0A1/L5Bh7aOxru8NmAKg1/jKzb9UJsc8yANSCb9RrM+z3tXhVwADQgF1I
a+/rL8vhse8yADQAs+y7DIBm+hAwLuP+j4vLIANA/fCxGizDnzmMBoD6Z2oNlmGaw2gAqO8OAD5c
g+X4cFwWGQDqg7HAkBosxxDKfVaBDIDaBIDLIgOgoUa5LDIAmqvDZZEBYAC4LDIAGmiHyyIDoLm2
uCwyAJrrTZdFBkBzveiyyABorlUuiwyAZgfAphosxyYDwABQ3+0EHq/Bcjwel0UGgProEZdBBkBz
3Uve19B3xGWQAaB+eJ0w716ufhiXQQaA+ulW+y4DoLkWA8sy7Pey2HcZABqgq4HOjPrbGfssA0At
8BjwnYz6+53YZxkAapHPAq9m0M9XY19lAKiF1gPnk/ZNNTtjH9c7XAaAijkUuDzh/l3urr8BoGIt
AOYl2K95sW8yAFSw2cCchPozJ/ZJBoBKcgNh8s3tFfZhe+zDDQ6HAaDy3Q6cCqytoO21se3bHQYD
QNVZBpwIfBXYVUJ7u2Jbv02edyjKAKidjYQz8CcDD1PMXYOd8bNPjm1tsuwGgNLyDPAnwATg2y3a
SDfFz5oQP/sZy1wfgy1BbYPgYuBTwOmEKbqnAGOAtn34pl8FLCX8mOdh4G1LagAoP28D98cXhGm6
xwAfBA4BDoz/vgXYAKyOG/9WS2cAqH62xr0Dd+PlOQDJAJBkAEgyACQZAJIMAEkGgKR6KuI+gPNx
PvieJvV4fyZwvGXp5ui91Mw5Bbs7NIcAmOs49epzlmCfvkjOtwweAkgyACTlcAgwEyeE7OkM4Iou
7z8D/NSydHMCcEuX938HLLQs3YwA7ko9AH5ENY+oStkxPd4/FeukPbb1eL8CWGRZuhnlIYAkA0CS
ASDJAJBkAEgyACQZAJJ64UNBpT3aCfdsjAVGA+8jPDl5CLCZMEfCGmAl4T6FrQaAlLcRwLnADGAy
0LGPf7cDeJIwf8J9wHMGgJSPqcBn44Y/pJ/bzu/F17XAcmABcAfwjucApDSdCvwnYdajP+7nxr83
44CvAT8nTJk+yACQ0nEY8I/Ao8DEAtv5AHAb8F+EiVQNAKlikwmzIV1A73MjtsoE4AnCLz/bDACp
GpfH3f3DK2h7CHAz4SThMANAKtdNhOcKtFfcjz8FfsC+X2EwAKQBuhG4JqH+TAEeBPY3AKRizSJc
mkvNacDdKW13BoDqZiJwa8L9OxOYbQBIrTccuAcYmng/vwT8vgEgtdZNwBEZ9LMd+IcUgsoAUF2c
BFyaUX/HEu4RMACkFphD9Zf7+upqKr40aACoDsYR7uvPzXDgMgNAGpjLSfh22158qsrt0ABQ7vYn
3GmXqw8QfppsAEj98EckeIttH51nAEj9M70GyzDNAJD6Z0oNluEIwjMIDQCpDw4AxtRkWcYZAFLf
HEO+Z/97OtYAkPrm6Boty1EGgNQ3B9VoWToMAKm5AXCgASDJAJD20a9qtCxbDACpuQGw2QCQ+ubF
Gi3Lzw0AqW/+B+isybKsNACkvtkKrKrJsiw3AKS+W1qDZVgDvGQASH23qAbLsLiqhg0A5e4HVHQG
vYXuNgCk/nkLuD/j/r8CLDEApP6bT75XA/4e2GUASP23HPh+hv3eCNxWZQcMANXF9cDOzPo8j4rP
XxgAqov/Bm7PqL8rgFuq7oQBoDq5lnBNPXU7gb8C3jEApNYeU388hQ2rFzcA/5FCRwwA1c0y4MqE
+/cQMDeVzhgAqqMFhKnCU/MoYRKQXQaAVKzrgL9OqD9LgbMINy5hAEjFuxa4guovD95PmMIsuVuW
DQDV3XzC1FvrKmh7O3AV8DHg1ykWxwBQEzwGjAf+ifJuGX4aOIVwrT/Z25QNADXFeuDPgdMIVwqK
8gpwGfAR4KnUi2IAqGkeB343HhZ8P+6mt8Jy4BLCDD8LSOhM/3sZ7PqghloSXyOAc4EZwGT2fYae
HcCThLP79wHP5VgEA0BN9zrhROF8oJ0w4ehYwnTd7yPM2DOEcAZ/E+FW45WEe/m35r7wBoC0x864
Ya9oygJ7DkBqMANAMgAkGQCSDABJBoAkA0BSXRVxH8Akws0V2mNsj/cnA/tZlm5O2EvNpluWbkbk
EAB3OU69usUS9OqK+JKHAJIMAEnJHwLMBt60tN1MBs7v8v5vgRctSzdHA5/r8v6fCQ/y0B6HktAT
hXebS3jiye7XKMfpXWb1qNEkS/Iuk3rUaJYleZdRPWo04DDwEEDyHIAkA0CSASDJAJBkAEgyACTV
Tp0eCnowcCzhWukhwAGERzdvATYQbrx5kUSnaCrJAcAY4IOxRgfGf99do9XAKmrwtNsBGEa4Keno
LjUaHGuyAVhLeCrwJgOgWsOBMwi/GDuNfbsBaSfwU8Lz4P8t/nd7jVfm3wBOJ0yCMSVu/G29/E1n
DIGlwGLgYeDtGtdoCDAV+MP43xMIjwfvzVrCdN+LgIXAxqYmZtl3Ak4hTMSwrUe7/Xn9EriZ8Az4
IpV9J+B44FtxpRxojTbGzxpfcJ/LvhNwdBz7X7agRtviOjml4D63/E7AnAJgOvDjFgzW3l7bCRNH
js48AMYD3yNMS9XqGu2Knz0+8wAYHcd6e0Hr0o8p7jkGjQyAw2O6dpbwegu4Ph4H5hQAwwkz2+ws
oUY7Y1vDMwuAYXFs3yppXbovrrsGwACcDbxR0oB1fT1DmCIqhwCYSJiuquwarYlt5xAAx8QxLbtG
b8R1ONkASPUyYBswD3iA8BPIso0jTO18euLnXy4lzHZbxS8wR8W2L028RqfHsRxXQduHxnV4Hr2f
fK1EigEwBLgT+HzFResAvgtcmOiK/SXCNNRDKh6rBbEvKbowjmFHhX1oi+vynRWP1V6ldhmwDfg2
MDOh+nwr7m7dmVCd5gJXJ9Sf64GhhIfBpOIv4til8s17QfzCvSCuT+4B7MVXE9r4u4bSN4EzE+nP
rMQ2/t2uJp2HeJwZxyy13e6ZcR33EOD/SezLEt2VbCdcOjqm4n5MJpyBT9X82McqHRPHqj3RGl0W
13UDoIvjgdtIWwdwL62/RLivDiM8J6894Rq1xz4eVlH7w+IYdSS+Lt0W13kDIO6mfR3Yn/SNJ5zQ
qcJXgJEZ1Ghk7GsVPk/xdyy2wv5xnW8zAOAi4BTyMRs4soJd/09kVKNPVHAocCRpnYTszSlx3W90
AAwDbiQv+wFzSm4z2evI77FXN6/kNueQ33RrN1Z4SJlEAFyUyW5tTx+n+B8Q7TaN1t5xV5aJse9l
GB3HJDcjq94LqDoAriRPg4FPW6Nk+v5p8v1p+5VNDYDfITzAI1czS1jpRgAfzbhGH6WAGW33EsYz
M67RsXFbaFwAnE/eRgAzCm7jXPJ+aMvguAxFmlFCyNR2W6gyAGaQv+nWqPJlmG6N8guAkcBxNRi4
Ik9ytQOn1qBGp1LszUvTalCj46joZHhVAXAS9XAC4UcwRRhDeNBp7g6Oy1KEoXEM6uCkJgXAcTUZ
tPYCV+4x1EeRNWqvSY2Oa1IAHFWjlfvozD7XGqXpqCYFwPAaDVxRu+mH1qhGh2ZW+8ZsE1UFwIE1
GriDrFFly3KQNcozAOo0I9Fga2SNcl2WqgJgS40G7lcFfe7mGtVoc2a1b8w2MahmG02dBs4A8Iuk
tgGwukYD93JBn7u2RjVam1ntG7NNVBUAq2o0cCsL+twVNarRisxq35htoqoAeLYmg7aG4qaJXkE9
Zi7eXmAAbIpjUAfPNikAXgBer8GgPVbgZ28FflKDGv0kLkuOY1CW1+M20ZgA6ASW1GDgFhX8+XWo
0eLMx6AMS6hospAqfw78L5kP2jZgYcFt3FeDlbvocV4Yx8IaZRYA3wPezHjQFgIbC27jOWB5xjVa
HpehSBtLCOIivRm3hcYFwDvANzIeuNtLamdBxjVaULOxKMI34rbQuAAAuAV4O8NBe6LE4/M7gHUZ
1mhd7HtZx9BPZFijt+M2QFMD4BeZfsN9seQ9pZsyrNFNJX+zfTHDGi2I20BjAwDC3PI5fcPdBzxS
cptfB57OqEZPxz6X6RHyOrG8Lq77ND0ANpPPs+/fBK6qoN2dwCVVHiv2cY/lktjnsn2GfE4sX0kC
v/dIZXbg+zM4FOgkzOJS1d7K08AXMlixv1Dh3sq6OEadiddoQVznMQD2uAp4MuFBmwc8VHEfbgYe
SLhGD8Q+Vukhyp+XsC+erGgvMvkA2AacQZo/FLoLuCaRvZDzSPMOwSWxbyl8+14Txyw1q+I6vs0A
2Lv1hOe8p/RLuHuAixParXwHOIe07oF/LPYplXMUnXHM7kmoRiviur0+pQ0utQAAeAWYlMjhwHzC
vHOpnXzbRJh378EE+vJg7MumxGr0Thy7+Yns9k+K6zYGQO/eAE6juju83iKcTLoC2JVojbbFb93r
qeaM+87Y9jmkey/+rjiGF8UxrcLtcV1+I8UCpRoAu1fwWXEFe63Edp8APkJ5d7ENdAW/Ma5gZR42
rYht3phwQHZ1RxzTMu8WfC2uu7MSDsikA2C3fyVMofyVggu5Dvhk3FV7nrz8CDgRmA1sKLCdDbGN
E2ObOXk+ju0nKfZS7ra4rh4b193am0s46bL7NarAtt4P/E3cneps0esFwo0rwwrs96webU4qsK2O
uJG+0sIavRI/s6PAfk/q0easAtsaFsf8hRbW6I24br6/wH6P6tHm3KYFQNcBPBu4m3AvdV8H62fA
rcDEkmpUZgB03bubDnyT8MDJvtZodfzb6SXtKZYZAF1NjOvCz/pRo1/EdfDsgr9ACguAXCdW+DXw
3fhqA44HPhR3u44gzLJyCOF5dFsIl15eJjxE8qmSzylUeX5gEXuemDMaGE+YUPNIwlRUu7/RNxN+
V/8y4Vr1M8BLNMOy+AL4LeDkuB4dCRwW16Uh8fBnC+EZhCsJzznYHRrZqsPMKp3x+O559F5eatBG
3V+vER4usrApCzzIMZeaywCQDABJBoAkA0CSASDJAJBUV0XcBzCaetxf0Eq/2eP9yFgnda9Jz5pZ
o+5G5RAASx2nXt1rCXo1J76U+CHALssoVWJXCgGwlMzvh5Yy1NmKve22FnVmBuF5Z5LKsZjyJ6iR
JEmSJEmSJEmSJEmSJEmSJEmSJEmSJEkl+D+B9JFB0vqGWgAAAABJRU5ErkJggg==
""")

sha1 = hashlib.sha1()
sha1.update(TEST_IMAGE)
TEST_IMAGE_SHA1 = sha1.hexdigest()
del sha1

# jids used in the tests
TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")


class TestAvatarSet(unittest.TestCase):

    def test_construction(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="0000000000",
                              url="http://example.com/avatar")

        self.assertEqual(
            aset.image_bytes,
            TEST_IMAGE
        )

        self.assertEqual(
            aset.png_id,
            TEST_IMAGE_SHA1,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][0].nbytes,
            len(TEST_IMAGE)
        )

        self.assertEqual(
            aset.metadata.info["image/png"][0].id_,
            TEST_IMAGE_SHA1,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].nbytes,
            0,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].id_,
            "0000000000",
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].url,
            "http://example.com/avatar",
        )

    def test_png_id_is_normalized(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png",
                              image_bytes=TEST_IMAGE,
                              id_=TEST_IMAGE_SHA1.upper())
        self.assertEqual(
            aset.metadata.info["image/png"][0].id_,
            avatar_service.normalize_id(TEST_IMAGE_SHA1),
        )

    def test_error_checking(self):
        aset = avatar_service.AvatarSet()

        with self.assertRaises(RuntimeError):
            # the id_ and the
            aset.add_avatar_image("image/png", url="http://example.com/avatar")

        with self.assertRaises(RuntimeError):
            # either the image bytes or an url must be given
            aset.add_avatar_image("image/png",
                                  id_="00000000000000000000",
                                  nbytes=0)

        with self.assertRaises(RuntimeError):
            aset.add_avatar_image("image/gif",
                                  image_bytes=TEST_IMAGE)


class TestAvatarServer(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco = aioxmpp.DiscoClient(self.cc)
        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco
        })

        self.s = avatar_service.AvatarServer(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco,
            aioxmpp.PubSubClient: self.pubsub,
        })

        self.cc.mock_calls.clear()

    def tearDown(self):
        del self.s
        del self.cc
        del self.disco
        del self.pubsub

    def test_is_service(self):
        self.assertTrue(issubclass(
            avatar_service.AvatarServer,
            aioxmpp.service.Service
        ))

    def test_service_order(self):
        self.assertGreater(
            avatar_service.AvatarServer,
            aioxmpp.DiscoClient,
        )

        self.assertGreater(
            avatar_service.AvatarServer,
            aioxmpp.PubSubClient,
        )

    def test_handle_stream_destroyed_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.stream.StanzaStream,
            "on_stream_destroyed",
            self.s.handle_stream_destroyed
        ))

    def  test_check_for_pep(self):
        disco_info = disco_xso.InfoQuery()
        disco_info.identities.append(
            disco_xso.Identity(type_="pep", category="pubsub")
        )

        with unittest.mock.patch.object(self.disco, "query_info",
                                        new=CoroutineMock()):
            self.disco.query_info.return_value = disco_info

            # run twice, the second call must not query again but use the
            # cache
            run_coroutine(self.s._check_for_pep())
            run_coroutine(self.s._check_for_pep())

            self.assertEqual(1, len(self.disco.query_info.mock_calls))
            self.disco.query_info.assert_called_with(TEST_FROM.bare())

        # this should wipe the cache and recheck with disco
        mock_reason = unittest.mock.Mock()
        self.s.handle_stream_destroyed(mock_reason)

        with unittest.mock.patch.object(self.disco, "query_info",
                                        new=CoroutineMock()):
            self.disco.query_info.return_value = disco_info

            # run twice, the second call must not query again but use the
            # cache
            run_coroutine(self.s._check_for_pep())
            run_coroutine(self.s._check_for_pep())

            self.assertEqual(1, len(self.disco.query_info.mock_calls))
            self.disco.query_info.assert_called_with(TEST_FROM.bare())

    def test_check_for_pep_failure(self):

        with unittest.mock.patch.object(self.disco, "query_info",
                                        new=CoroutineMock()):
            self.disco.query_info.return_value = disco_xso.InfoQuery()

            # run twice, the second call must not query again but use the
            # cache
            with self.assertRaises(NotImplementedError):
                run_coroutine(self.s._check_for_pep())

            with self.assertRaises(NotImplementedError):
                run_coroutine(self.s._check_for_pep())

            self.assertEqual(
                1,
                len(self.disco.query_info.mock_calls)
            )

            self.disco.query_info.assert_called_with(
                TEST_FROM.bare()
            )

    def test_publish_avatar_set(self):
        # set the cache to indicate the server has PEP
        self.s._has_pep = True

        avatar_set = avatar_service.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)

        with unittest.mock.patch.object(self.pubsub, "publish",
                                        new=CoroutineMock()):
            run_coroutine(self.s.publish_avatar_set(avatar_set))

            self.assertSequenceEqual(
                self.pubsub.publish.mock_calls,
                [
                    unittest.mock.call(
                        None,
                        namespaces.xep0084_data,
                        unittest.mock.ANY,
                        id_=avatar_set.png_id
                    ),
                    unittest.mock.call(
                        None,
                        namespaces.xep0084_metadata,
                        avatar_set.metadata,
                        id_=avatar_set.png_id
                    )
                ],
            )

            _, args, _ = self.pubsub.publish.mock_calls[0]
            data = args[2]
            self.assertTrue(isinstance(data, avatar_xso.Data))
            self.assertEqual(data.data, avatar_set.image_bytes)

    def test_disable_avatar(self):
        # set the cache to indicate the server has PEP
        self.s._has_pep = True

        with unittest.mock.patch.object(self.pubsub, "publish",
                                        new=CoroutineMock()):
            run_coroutine(self.s.disable_avatar())

            self.assertSequenceEqual(
                self.pubsub.publish.mock_calls,
                [
                    unittest.mock.call(
                        None,
                        namespaces.xep0084_metadata,
                        unittest.mock.ANY,
                    ),
                ]
            )

            _, args, _ = self.pubsub.publish.mock_calls[0]
            metadata = args[2]

            self.assertTrue(isinstance(metadata, avatar_xso.Metadata))
            self.assertEqual(0, len(metadata.info))
            self.assertEqual(0, len(metadata.pointer))


class TestAvatarDescriptors(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco = aioxmpp.DiscoClient(self.cc)
        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco
        })

        self.cc.mock_calls.clear()

    def test_get_image_bytes(self):
        descriptor = avatar_service.PubsubAvatarDescriptor(
            TEST_JID1,
            "image/png",
            TEST_IMAGE_SHA1.upper(),
            len(TEST_IMAGE),
            pubsub=self.pubsub
        )

        self.assertEqual(TEST_IMAGE_SHA1, descriptor.normalized_id)

        items = pubsub_xso.Items(
            namespaces.xep0084_data,
        )
        item = pubsub_xso.Item(id_=TEST_IMAGE_SHA1)
        item.registered_payload = avatar_xso.Data(TEST_IMAGE)
        items.items.append(item)
        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items_by_id",
                                        new=CoroutineMock()):
            self.pubsub.get_items_by_id.return_value = pubsub_result

            res = run_coroutine(descriptor.get_image_bytes())

            self.assertSequenceEqual(
                self.pubsub.get_items_by_id.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_data,
                        [TEST_IMAGE_SHA1.upper()],
                    )
                ]
            )
            self.assertEqual(res, TEST_IMAGE)


class AvatarClient(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco_client = aioxmpp.DiscoClient(self.cc)
        self.disco = aioxmpp.DiscoServer(self.cc)

        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco
        })

        self.s = avatar_service.AvatarClient(self.cc, dependencies={
            aioxmpp.DiscoServer: self.disco,
            aioxmpp.PubSubClient: self.pubsub,
        })

        self.cc.mock_calls.clear()

    def test_handle_pubsub_publish(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.PubSubClient,
            "on_item_published",
            self.s.handle_pubsub_publish
        ))

        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        items = pubsub_xso.EventItems(
            namespaces.xep0084_metadata,
        )
        item = pubsub_xso.EventItem(aset.metadata, id_=aset.png_id)
        items.items.append(item)

        pubsub_result = pubsub_xso.Event(items)

        mock_handler = unittest.mock.Mock()
        self.s.on_metadata_changed.connect(mock_handler)

        self.s.handle_pubsub_publish(TEST_JID1, namespaces.xep0084_metadata,
                                     pubsub_result)

        descriptors = self.s._metadata_cache[TEST_JID1]
        self.assertEqual(len(descriptors), 1)
        self.assertEqual(len(descriptors["image/png"]), 2)

        png_descr = descriptors["image/png"]

        self.assertTrue(isinstance(png_descr[0],
                                   avatar_service.PubsubAvatarDescriptor))
        self.assertEqual(png_descr[0].mime_type, "image/png")
        self.assertEqual(png_descr[0].id_, TEST_IMAGE_SHA1)
        self.assertEqual(png_descr[0].nbytes, len(TEST_IMAGE))
        self.assertEqual(png_descr[0].url, None)

        self.assertTrue(isinstance(png_descr[0],
                                   avatar_service.PubsubAvatarDescriptor))

        self.assertEqual(png_descr[1].mime_type, "image/png")
        self.assertEqual(png_descr[1].id_, "00000000000000000000")
        self.assertEqual(png_descr[1].nbytes, 0)
        self.assertEqual(png_descr[1].url, "http://example.com/avatar")

        mock_handler.assert_called_with(TEST_JID1, descriptors)

    def test_get_avatar_metadata(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        items = pubsub_xso.Items(
            namespaces.xep0084_metadata,
        )
        item = pubsub_xso.Item(id_=aset.png_id)
        item.registered_payload = aset.metadata
        items.items.append(item)

        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):
            self.pubsub.get_items.return_value = pubsub_result

            descriptors = run_coroutine(self.s.get_avatar_metadata(TEST_JID1))

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

            self.assertEqual(len(descriptors), 1)
            self.assertEqual(len(descriptors["image/png"]), 2)

            png_descr = descriptors["image/png"]

            self.assertTrue(isinstance(png_descr[0],
                                       avatar_service.PubsubAvatarDescriptor))
            self.assertEqual(png_descr[0].mime_type, "image/png")
            self.assertEqual(png_descr[0].id_, TEST_IMAGE_SHA1)
            self.assertEqual(png_descr[0].nbytes, len(TEST_IMAGE))
            self.assertEqual(png_descr[0].url, None)

            self.assertTrue(isinstance(png_descr[0],
                                       avatar_service.PubsubAvatarDescriptor))

            self.assertEqual(png_descr[1].mime_type, "image/png")
            self.assertEqual(png_descr[1].id_, "00000000000000000000")
            self.assertEqual(png_descr[1].nbytes, 0)
            self.assertEqual(png_descr[1].url, "http://example.com/avatar")

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            cached_descriptors = run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1)
            )

            self.assertEqual(descriptors, cached_descriptors)

            # we must get the descriptors from the cache
            self.pubsub.get_items.assert_not_called()

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            self.pubsub.get_items.return_value = pubsub_result
            descriptors = run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1, require_fresh=True)
            )

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

    def test_get_avatar_metadata_with_require_fresh_does_not_crash(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        items = pubsub_xso.Items(
            namespaces.xep0084_metadata,
        )
        item = pubsub_xso.Item(id_=aset.png_id)
        item.registered_payload = aset.metadata
        items.items.append(item)

        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            self.pubsub.get_items.return_value = pubsub_result
            run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1, require_fresh=True)
            )

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

    def test_get_avatar_metadata_mask_xmpp_errors(self):
        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):
            self.pubsub.get_items.side_effect = errors.XMPPCancelError(
                (namespaces.stanzas, "feature-not-implemented")
            )

            res = run_coroutine(self.s.get_avatar_metadata(TEST_JID1))

            self.assertSequenceEqual(res, [])
            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    ),
                ]
            )

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):
            self.pubsub.get_items.side_effect = errors.XMPPCancelError(
                (namespaces.stanzas, "item-not-found")
            )

            res = run_coroutine(self.s.get_avatar_metadata(TEST_JID2))

            self.assertSequenceEqual(res, [])
            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID2,
                        namespaces.xep0084_metadata,
                        max_items=1
                    ),
                ]
            )

    def test_subscribe(self):
        with unittest.mock.patch.object(self.pubsub, "subscribe",
                                        new=CoroutineMock()):
            run_coroutine(self.s.subscribe(TEST_JID1))

            self.assertSequenceEqual(
                self.pubsub.subscribe.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata
                    ),
                ]
            )
