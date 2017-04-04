########################################################################
# File name: test_e2e.py
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
import base64
import logging

import aioxmpp.avatar
import aioxmpp.e2etest

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    TestCase,
    require_pep,
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


class TestAvatar(TestCase):

    @require_pep
    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.client, = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[
                    aioxmpp.EntityCapsService,
                    aioxmpp.PresenceServer,
                    aioxmpp.avatar.AvatarServer,
                    aioxmpp.avatar.AvatarClient,
                ]
            ),
        )

    @blocking_timed
    @asyncio.coroutine
    def test_provide_and_retrieve_avatar(self):
        avatar_server = self.client.summon(aioxmpp.avatar.AvatarServer)
        avatar_client = self.client.summon(aioxmpp.avatar.AvatarClient)

        avatar_set = aioxmpp.avatar.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)

        yield from avatar_server.publish_avatar_set(avatar_set)

        avatar_info = yield from avatar_client.get_avatar_metadata(
            self.client.local_jid.bare()
        )

        self.assertEqual(
            len(avatar_info),
            1
        )

        (info, ), = avatar_info.values()

        test_image_retrieved = yield from info.get_image_bytes()

        self.assertEqual(
            test_image_retrieved,
            TEST_IMAGE
        )

    @blocking_timed
    @asyncio.coroutine
    def test_on_metadata_changed(self):
        avatar_server = self.client.summon(aioxmpp.avatar.AvatarServer)
        avatar_client = self.client.summon(aioxmpp.avatar.AvatarClient)

        done = asyncio.Event()

        def handler(jid, metadata):
            self.assertEqual(jid, self.client.local_jid.bare())
            self.assertEqual(len(metadata), 1)
            done.set()

        avatar_client.on_metadata_changed.connect(handler)

        avatar_set = aioxmpp.avatar.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)

        logging.info("publishing avatar")
        yield from avatar_server.publish_avatar_set(avatar_set)
        logging.info("waiting for completion")
        yield from done.wait()
