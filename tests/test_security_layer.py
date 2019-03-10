########################################################################
# File name: test_security_layer.py
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
import random
import ssl
import unittest

import OpenSSL.crypto
import OpenSSL.SSL

import aiosasl

import aioxmpp.errors as errors
import aioxmpp.structs as structs
import aioxmpp.security_layer as security_layer
import aioxmpp.nonza as nonza

from aioxmpp.utils import namespaces

from aioxmpp.testutils import (
    XMLStreamMock,
    run_coroutine,
    run_coroutine_with_peer,
    CoroutineMock
)
from aioxmpp import xmltestutils


# class SSLVerificationTestBase(unittest.TestCase):
#     def setUp(self):
#         self.server_ctx = OpenSSL.SSL.Context(
#             OpenSSL.SSL.SSLv23_METHOD,
#         )
#         self.server_raw_sock, self.client_raw_sock = socket.socketpair()
#         self.server_sock = OpenSSL.SSL.Connection(
#             self.server_ctx,
#             self.server_raw_sock
#         )
#         self.server_sock.set_accept_state()

#     def tearDown(self):
#         self.server_sock.close()
#         self.server_raw_sock.close()
#         self.client_raw_sock.close()

# NOTE: the variables contents following this comment are distributed under the
# following license:
#
# 1. Terms
#
# "CAcert Inc" means CAcert Incorporated, a non-profit association incorporated
# in New South Wales, Australia.
# "CAcert Community Agreement" means the agreement entered into by each person
# wishing to RELY.
# "Member" means a natural or legal person who has agreed to the CAcert
# Community Agreement.
# "Certificate" means any certificate or like device to which CAcert Inc's
# digital signature has been affixed.
# "CAcert Root Certificates" means any certificate issued by CAcert Inc to
# itself for the purposes of signing further CAcert Roots or for signing
# certificates of Members.
# "RELY" means the human act in taking on a risk or liability on the basis of
# the claim(s) bound within a certificate issued by CAcert.
# "Embedded" means a certificate that is contained within a software
# application or hardware system, when and only when, that software application
# or system is distributed in binary form only.
#
# 2. Copyright
#
# CAcert Root Certificates are Copyright CAcert Incorporated. All rights
# reserved.
#
# 3. License
#
# You may copy and distribute CAcert Root Certificates only in accordance with
# this license.
#
# CAcert Inc grants you a free, non-exclusive license to copy and distribute
# CAcert Root Certificates in any medium, with or without modification,
# provided that the following conditions are met:
#
# *    Redistributions of Embedded CAcert Root Certificates must take reasonable
# steps to inform the recipient of the disclaimer in section 4 or reproduce
# this license and copyright notice in full in the documentation provided with
# the distribution.
#
# *    Redistributions in all other forms must reproduce this license and
# copyright notice in full.
#
# 4. Disclaimer
#
# THE CACERT ROOT CERTIFICATES ARE PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED TO THE
# MAXIMUM EXTENT PERMITTED BY LAW. IN NO EVENT SHALL CACERT INC, ITS MEMBERS,
# AGENTS, SUBSIDIARIES OR RELATED PARTIES BE LIABLE TO THE LICENSEE OR ANY THIRD
# PARTY FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THESE CERTIFICATES, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE. IN ANY EVENT, CACERT'S LIABILITY SHALL NOT
# EXCEED $1,000.00 AUSTRALIAN DOLLARS.
#
# THIS LICENSE SPECIFICALLY DOES NOT PERMIT YOU TO RELY UPON ANY CERTIFICATES
# ISSUED BY CACERT INC. IF YOU WISH TO RELY ON CERTIFICATES ISSUED BY CACERT
# INC, YOU MUST ENTER INTO A SEPARATE AGREEMENT WITH CACERT INC.
#
# 5. Statutory Rights
#
# Nothing in this license affects any statutory rights that cannot be waived or
# limited by contract. In the event that any provision of this license is held
# to be invalid or unenforceable, the remaining provisions of this license
# remain in full force and effect.
#
# END OF license for the following variable
crt_cacert_root = b"""\
-----BEGIN CERTIFICATE-----
MIIHPTCCBSWgAwIBAgIBADANBgkqhkiG9w0BAQQFADB5MRAwDgYDVQQKEwdSb290
IENBMR4wHAYDVQQLExVodHRwOi8vd3d3LmNhY2VydC5vcmcxIjAgBgNVBAMTGUNB
IENlcnQgU2lnbmluZyBBdXRob3JpdHkxITAfBgkqhkiG9w0BCQEWEnN1cHBvcnRA
Y2FjZXJ0Lm9yZzAeFw0wMzAzMzAxMjI5NDlaFw0zMzAzMjkxMjI5NDlaMHkxEDAO
BgNVBAoTB1Jvb3QgQ0ExHjAcBgNVBAsTFWh0dHA6Ly93d3cuY2FjZXJ0Lm9yZzEi
MCAGA1UEAxMZQ0EgQ2VydCBTaWduaW5nIEF1dGhvcml0eTEhMB8GCSqGSIb3DQEJ
ARYSc3VwcG9ydEBjYWNlcnQub3JnMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIIC
CgKCAgEAziLA4kZ97DYoB1CW8qAzQIxL8TtmPzHlawI229Z89vGIj053NgVBlfkJ
8BLPRoZzYLdufujAWGSuzbCtRRcMY/pnCujW0r8+55jE8Ez64AO7NV1sId6eINm6
zWYyN3L69wj1x81YyY7nDl7qPv4coRQKFWyGhFtkZip6qUtTefWIonvuLwphK42y
fk1WpRPs6tqSnqxEQR5YYGUFZvjARL3LlPdCfgv3ZWiYUQXw8wWRBB0bF4LsyFe7
w2t6iPGwcswlWyCR7BYCEo8y6RcYSNDHBS4CMEK4JZwFaz+qOqfrU0j36NK2B5jc
G8Y0f3/JHIJ6BVgrCFvzOKKrF11myZjXnhCLotLddJr3cQxyYN/Nb5gznZY0dj4k
epKwDpUeb+agRThHqtdB7Uq3EvbXG4OKDy7YCbZZ16oE/9KTfWgu3YtLq1i6L43q
laegw1SJpfvbi1EinbLDvhG+LJGGi5Z4rSDTii8aP8bQUWWHIbEZAWV/RRyH9XzQ
QUxPKZgh/TMfdQwEUfoZd9vUFBzugcMd9Zi3aQaRIt0AUMyBMawSB3s42mhb5ivU
fslfrejrckzzAeVLIL+aplfKkQABi6F1ITe1Yw1nPkZPcCBnzsXWWdsC4PDSy826
YreQQejdIOQpvGQpQsgi3Hia/0PsmBsJUUtaWsJx8cTLc6nloQsCAwEAAaOCAc4w
ggHKMB0GA1UdDgQWBBQWtTIb1Mfz4OaO873SsDrusjkY0TCBowYDVR0jBIGbMIGY
gBQWtTIb1Mfz4OaO873SsDrusjkY0aF9pHsweTEQMA4GA1UEChMHUm9vdCBDQTEe
MBwGA1UECxMVaHR0cDovL3d3dy5jYWNlcnQub3JnMSIwIAYDVQQDExlDQSBDZXJ0
IFNpZ25pbmcgQXV0aG9yaXR5MSEwHwYJKoZIhvcNAQkBFhJzdXBwb3J0QGNhY2Vy
dC5vcmeCAQAwDwYDVR0TAQH/BAUwAwEB/zAyBgNVHR8EKzApMCegJaAjhiFodHRw
czovL3d3dy5jYWNlcnQub3JnL3Jldm9rZS5jcmwwMAYJYIZIAYb4QgEEBCMWIWh0
dHBzOi8vd3d3LmNhY2VydC5vcmcvcmV2b2tlLmNybDA0BglghkgBhvhCAQgEJxYl
aHR0cDovL3d3dy5jYWNlcnQub3JnL2luZGV4LnBocD9pZD0xMDBWBglghkgBhvhC
AQ0ESRZHVG8gZ2V0IHlvdXIgb3duIGNlcnRpZmljYXRlIGZvciBGUkVFIGhlYWQg
b3ZlciB0byBodHRwOi8vd3d3LmNhY2VydC5vcmcwDQYJKoZIhvcNAQEEBQADggIB
ACjH7pyCArpcgBLKNQodgW+JapnM8mgPf6fhjViVPr3yBsOQWqy1YPaZQwGjiHCc
nWKdpIevZ1gNMDY75q1I08t0AoZxPuIrA2jxNGJARjtT6ij0rPtmlVOKTV39O9lg
18p5aTuxZZKmxoGCXJzN600BiqXfEVWqFcofN8CCmHBh22p8lqOOLlQ+TyGpkO/c
gr/c6EWtTZBzCDyUZbAEmXZ/4rzCahWqlwQ3JNgelE5tDlG+1sSPypZt90Pf6DBl
Jzt7u0NDY8RD97LsaMzhGY4i+5jhe1o+ATc7iwiwovOVThrLm82asduycPAtStvY
sONvRUgzEv/+PDIqVPfE94rwiCPCR/5kenHA0R6mY7AHfqQv0wGP3J8rtsYIqQ+T
SCX8Ev2fQtzzxD72V7DX3WnRBnc0CkvSyqD/HMaMyRa+xMwyN2hzXwj7UfdJUzYF
CpUCTPJ5GhD22Dp1nPMd8aINcGeGG7MW9S/lpOt5hvk9C8JzC6WZrG/8Z7jlLwum
GCSNe9FINSkYQKyTYOGWhlC0elnYjyELn8+CkcY7v2vcB5G5l1YjqrZslMZIBjzk
zk6q5PYvCdxTby78dOs6Y5nCpqyJvKeyRKANihDjbPIky/qbn3BHLt4Ui9SyIAmW
omTxJBzcoTWcFbLUvFUufQb1nA5V9FrWk9p2rSVzTMVD
-----END CERTIFICATE-----\n"""
# END OF variable covered by the above license

crt_zombofant_net = b"""\
-----BEGIN CERTIFICATE-----
MIIGSTCCBDGgAwIBAgIDEFeyMA0GCSqGSIb3DQEBDQUAMHkxEDAOBgNVBAoTB1Jv
b3QgQ0ExHjAcBgNVBAsTFWh0dHA6Ly93d3cuY2FjZXJ0Lm9yZzEiMCAGA1UEAxMZ
Q0EgQ2VydCBTaWduaW5nIEF1dGhvcml0eTEhMB8GCSqGSIb3DQEJARYSc3VwcG9y
dEBjYWNlcnQub3JnMB4XDTE1MDMwNzExMzE1N1oXDTE1MDkwMzExMzE1N1owGDEW
MBQGA1UEAxMNem9tYm9mYW50Lm5ldDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCC
AgoCggIBALzAsX9qMkd2nECtTApw0zMVHs5HUkyGHW0hSRR0Q7MHm4HTm6I8xzD2
yZxX/TyYBDo/JcdOqtVmKSht7l4oxU8xd5QyOFHTnHUGElwxKNhtBTCRf5mIWrd6
8CUWAgvhCmQk2qD2w1z0hiPCl5dVnxQccZRNJlwyNEBAbk5cHajEQjOvT+NxBX3w
q9lVlyJjuFzXaJRTlDNWfBd7mC077ag3LqFiR2D1IHi0R6b6gjSE9rfjAZxyon98
sgKA20nbmVNiSCSmqVBoC6ELQdzCa4HEP0jrw1OrmIqRJVIAjouYQkALGHzozBYy
x/9vIGI8vmG2TFgdLDQ8rr1nXrwY7m/fvnw43vb0nPsCNnFjI8IkB0ind44ajXWP
oBV4FQlg+hx9eL/+XkPhLP5BJ1kHttvda/NXV5zSk8Z6y2dt4tYHWDjXykA1nWMW
7tjwvb6pqp8kahKzlQF9rKCBOL4PpcPctZ9ookwCU1aPGvjCS6H7cRIzM4U+ZKHq
yvlSlFe7KrrUGgR8dx6I6csD0jiOD3d+gbK7Oiu6NG7fxXELCCIAfFQIFEY79yz6
z2qZBjqQaNuNP3QkmZLDPEyvHZCWPpMIyIuUK8k3oWt0OdCUBRV6p+3EYEcPeamt
aMWXc1PQMioj3W1ndCehyOZ9tlXmvVaSHTLuZXyFm6/4+2rKj84jAgMBAAGjggE5
MIIBNTAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIDqDA0BgNVHSUELTArBggr
BgEFBQcDAgYIKwYBBQUHAwEGCWCGSAGG+EIEAQYKKwYBBAGCNwoDAzAzBggrBgEF
BQcBAQQnMCUwIwYIKwYBBQUHMAGGF2h0dHA6Ly9vY3NwLmNhY2VydC5vcmcvMDEG
A1UdHwQqMCgwJqAkoCKGIGh0dHA6Ly9jcmwuY2FjZXJ0Lm9yZy9yZXZva2UuY3Js
MHcGA1UdEQRwMG6CDXpvbWJvZmFudC5uZXSgGwYIKwYBBQUHCAWgDwwNem9tYm9m
YW50Lm5ldIIYY29uZmVyZW5jZS56b21ib2ZhbnQubmV0oCYGCCsGAQUFBwgFoBoM
GGNvbmZlcmVuY2Uuem9tYm9mYW50Lm5ldDANBgkqhkiG9w0BAQ0FAAOCAgEAd7hJ
KdfqC0pdFLlIKzaLSuhK2FbqrZAd+wAZs1OfHPxZ1m0ygvCN3t2fm01DXKk34Wj7
ZTnZSgmsIudFBSco8z+ne6rHKd9qqJd7C/YR/pz53UnZR+ost26shr2ARb1+ve+6
OyCiDi81IV2FxahMzqvYbxzr0XxkOZlmkgNOWNz9Da29wvgvVCyhzbdH8oVohOSw
Vq/aP56vBbTwDK2LKMAU+m3AgDwjauRt96HhBMMS9yH2Ct5S8OFSFHd58AtLu6fP
LIsp75t4RVoShci1HiVudeCCfcPdvzGsxp1BxPx5OnTZerbHZ30WuS4QF9Nfo+yE
4S9reB5qaNQxzlFplmJCoDN6mLshvZ3CMwR9d8Al6Cv6X/sneNOWu5fmAXSAHjdu
jbAg2J/Ohw+WWJ6NfvbUYWVuvO3NPFoSenDopMSWSjM70BeVApl/t3gAgUBHFYgB
DKkO6BDIyEuopYlyVoiBBQbzJTG2/P5/tzHZJGOjy4R9wZERj3Ol4COvVFnM28sU
tv785oJggyTqCsRHxFxv3ouYrC6O3imDdhfuWTBep4o+OwII9K0T2/i3aPsX92Zg
d11q4Mhgsy1A8B1T+cwPzRQ8aa1//QGOa7KQ5lIYRQGq6Clg7XfZWeKsYOAoUGaS
74eNdQYv+etdKem7oSf/oA/aSKGeyVqgvf2/WH0=
-----END CERTIFICATE-----\n"""


class Testextract_python_dict_from_x509(unittest.TestCase):
    def test_zombofant_net(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        d = security_layer.extract_python_dict_from_x509(x509)

        self.assertDictEqual(
            {
                "subject": (
                    (("commonName", "zombofant.net"),),
                ),
                "subjectAltName": [
                    ("DNS", "zombofant.net"),
                    ("DNS", "conference.zombofant.net"),
                ]
            },
            d
        )


class Testextract_blob(unittest.TestCase):
    def test_generic(self):
        x509 = object()

        with unittest.mock.patch(
                "OpenSSL.crypto.dump_certificate"
        ) as dump_certificate:
            blob = security_layer.extract_blob(x509)

        self.assertSequenceEqual(
            [
                unittest.mock.call(OpenSSL.crypto.FILETYPE_ASN1,
                                   x509),
            ],
            dump_certificate.mock_calls
        )

        self.assertEqual(
            dump_certificate(),
            blob
        )


class Testblob_to_pyasn1(unittest.TestCase):
    def test_generic(self):
        blob = object()

        with contextlib.ExitStack() as stack:
            decode = stack.enter_context(unittest.mock.patch(
                "pyasn1.codec.der.decoder.decode"
            ))

            Certificate = stack.enter_context(unittest.mock.patch(
                "pyasn1_modules.rfc2459.Certificate"
            ))

            pyasn1_struct = security_layer.blob_to_pyasn1(blob)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            Certificate.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    blob,
                    asn1Spec=Certificate()
                ),
            ],
            decode.mock_calls[:1]
        )

        self.assertEqual(
            decode()[0],
            pyasn1_struct
        )


class Testextract_pk_blob_from_pyasn1(unittest.TestCase):
    def test_generic(self):
        pyasn1_struct = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            encode = stack.enter_context(unittest.mock.patch(
                "pyasn1.codec.der.encoder.encode"
            ))

            result = security_layer.extract_pk_blob_from_pyasn1(
                pyasn1_struct
            )

        self.assertSequenceEqual(
            [
                unittest.mock.call.getComponentByName("tbsCertificate"),
                unittest.mock.call.getComponentByName().getComponentByName(
                    "subjectPublicKeyInfo")
            ],
            pyasn1_struct.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    pyasn1_struct.getComponentByName().getComponentByName()
                )
            ],
            encode.mock_calls
        )

        self.assertEqual(
            encode(),
            result
        )


class Testcheck_x509_hostname(unittest.TestCase):
    def test_pass(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        hostname = object()

        with contextlib.ExitStack() as stack:
            extract_python_dict_from_x509 = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.extract_python_dict_from_x509"
                )
            )
            match_hostname = stack.enter_context(unittest.mock.patch(
                "ssl.match_hostname"
            ))
            match_hostname.return_value = None

            result = security_layer.check_x509_hostname(
                x509,
                hostname
            )

        self.assertTrue(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509)
            ],
            extract_python_dict_from_x509.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    extract_python_dict_from_x509(),
                    hostname
                )
            ],
            match_hostname.mock_calls
        )

    def test_fail(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        hostname = object()

        with contextlib.ExitStack() as stack:
            extract_python_dict_from_x509 = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.extract_python_dict_from_x509"
                )
            )
            match_hostname = stack.enter_context(unittest.mock.patch(
                "ssl.match_hostname"
            ))
            match_hostname.side_effect = ssl.CertificateError("foo")

            result = security_layer.check_x509_hostname(
                x509,
                hostname
            )

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509)
            ],
            extract_python_dict_from_x509.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    extract_python_dict_from_x509(),
                    hostname
                )
            ],
            match_hostname.mock_calls
        )


class TestPKIXCertificateVerifier(unittest.TestCase):
    def test_verify_callback_checks_hostname_on_depth_0(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = True

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                True)

        self.assertTrue(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509, verifier.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

    def test_verify_callback_returns_false_on_hostname_mismatch(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = False

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                True)

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(x509, verifier.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

    def test_verify_callback_skip_hostname_check_on_precheck_fail(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = False

            result = verifier.verify_callback(
                None,
                x509,
                0, 0,
                False)

        self.assertFalse(result)

        self.assertSequenceEqual(
            [
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            check_x509_hostname.mock_calls
        )

    def test_verify_callback_skip_hostname_check_on_nonzero_depth(self):
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        verifier = security_layer.PKIXCertificateVerifier()
        verifier.transport = unittest.mock.Mock()

        with unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
        ) as check_x509_hostname:
            check_x509_hostname.return_value = False

            result = verifier.verify_callback(
                None,
                x509,
                0, 1,
                True)

        self.assertSequenceEqual(
            [
            ],
            verifier.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            check_x509_hostname.mock_calls
        )

        self.assertTrue(result)


class TestHookablePKIXCertificateVerifier(unittest.TestCase):
    def setUp(self):
        self.transport = unittest.mock.Mock()
        self.quick_check = unittest.mock.Mock()
        self.post_handshake_deferred_failure = CoroutineMock()
        self.post_handshake_success = CoroutineMock()

        self.x509_root = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_cacert_root)
        self.x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)

        self.verifier = security_layer.HookablePKIXCertificateVerifier(
            self.quick_check,
            self.post_handshake_deferred_failure,
            self.post_handshake_success
        )
        self.verifier.transport = self.transport

        self.deferrable_errors = [
            (20, None),
            (19, None),
            (18, 0),
            (27, 0),
            (21, 0),
        ]

    def test_is_certificate_verifier(self):
        self.assertTrue(issubclass(
            security_layer.HookablePKIXCertificateVerifier,
            security_layer.CertificateVerifier
        ))

    def _test_hardwired_set(self, s):
        self.assertIs(
            False,
            self.verifier.verify_recorded(
                self.x509,
                s
            ),
            s
        )

        self.assertSequenceEqual([], self.quick_check.mock_calls)

        self.quick_check.reset_mock()

    def _test_hardwired(self, errno, errdepth):
        if   ((errno, errdepth) in self.deferrable_errors or
              (errno, None) in self.deferrable_errors):
            return

        self._test_hardwired_set(
            {
                (self.x509_root, errno, errdepth),
            }
        )

        self._test_hardwired_set(
            {
                (self.x509_root, errno, errdepth),
            }|{
                (self.x509_root, )+random.choice(self.deferrable_errors)
            }
        )

    def test_verify_callback_records_and_returns_true(self):
        x509_2 = object()
        x509_1 = object()
        x509_0 = object()

        with contextlib.ExitStack() as stack:
            verify_recorded = stack.enter_context(
                unittest.mock.patch.object(self.verifier, "verify_recorded")
            )

            self.assertSetEqual(
                set(),
                self.verifier.recorded_errors
            )

            self.assertTrue(
                self.verifier.verify_callback(None, x509_2, 10, 2, False)
            )
            self.assertSetEqual(
                {
                    (x509_2, 10, 2),
                },
                self.verifier.recorded_errors
            )

            self.assertTrue(
                self.verifier.verify_callback(None, x509_2, 0, 2, True)
            )
            self.assertSetEqual(
                {
                    (x509_2, 10, 2),
                },
                self.verifier.recorded_errors
            )

            self.assertTrue(
                self.verifier.verify_callback(None, x509_1, 19, 1, False)
            )
            self.assertSetEqual(
                {
                    (x509_2, 10, 2),
                    (x509_1, 19, 1),
                },
                self.verifier.recorded_errors
            )

            self.assertTrue(
                self.verifier.verify_callback(None, x509_1, 0, 1, True)
            )
            self.assertSetEqual(
                {
                    (x509_2, 10, 2),
                    (x509_1, 19, 1),
                },
                self.verifier.recorded_errors
            )

            self.assertTrue(
                self.verifier.verify_callback(None, x509_0, 18, 0, True)
            )
            self.assertSetEqual(
                {
                    (x509_2, 10, 2),
                    (x509_1, 19, 1),
                    (x509_0, 18, 0),
                },
                self.verifier.recorded_errors
            )

        self.assertSequenceEqual([], verify_recorded.mock_calls)

    def test_verify_callback_checks_recorded_and_determines_hostname_matchon_last(self):
        errors = object()
        self.verifier.recorded_errors = errors

        self.assertFalse(self.verifier.hostname_matches)
        self.assertIsNone(self.verifier.leaf_x509)

        with contextlib.ExitStack() as stack:
            verify_recorded = stack.enter_context(
                unittest.mock.patch.object(self.verifier, "verify_recorded")
            )

            check_x509_hostname = stack.enter_context(unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
            ))

            result = self.verifier.verify_callback(
                None,
                self.x509,
                0, 0,
                True)

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            self.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.x509, self.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.x509, errors)
            ],
            verify_recorded.mock_calls
        )

        self.assertEqual(
            verify_recorded(),
            result
        )

        self.assertEqual(
            check_x509_hostname(),
            self.verifier.hostname_matches
        )

        self.assertIs(
            self.x509,
            self.verifier.leaf_x509
        )

    def test_verify_callback_treats_errno_21_on_leaf_as_last(self):
        errors = set()
        self.verifier.recorded_errors = errors

        self.assertFalse(self.verifier.hostname_matches)
        self.assertIsNone(self.verifier.leaf_x509)

        with contextlib.ExitStack() as stack:
            verify_recorded = stack.enter_context(
                unittest.mock.patch.object(self.verifier, "verify_recorded")
            )

            check_x509_hostname = stack.enter_context(unittest.mock.patch(
                "aioxmpp.security_layer.check_x509_hostname"
            ))

            result = self.verifier.verify_callback(
                None,
                self.x509,
                21, 0,
                True)

        self.assertIn(
            (self.x509, 21, 0),
            self.verifier.recorded_errors,
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ],
            self.transport.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.x509, self.transport.get_extra_info()),
            ],
            check_x509_hostname.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.x509, errors)
            ],
            verify_recorded.mock_calls
        )

        self.assertEqual(
            verify_recorded(),
            result
        )

        self.assertEqual(
            check_x509_hostname(),
            self.verifier.hostname_matches
        )

        self.assertIs(
            self.x509,
            self.verifier.leaf_x509
        )

    def test_verify_recorded_rejects_non_deferrable_errors(self):
        for i in range(800//2):
            errno = random.randint(1, 100)
            depth = 0

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                self._test_hardwired(errno, depth)

        for i in range(200//2):
            errno = random.randint(1, 100)
            depth = random.randint(1, 10)

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                self._test_hardwired(errno, depth)

    def test_verify_recorded_calls_quick_check_for_deferrable_error(self):
        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1
            self.quick_check.return_value = True

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                result = self.verifier.verify_recorded(
                    self.x509,
                    {
                        (self.x509_root, errno, errdepth)
                    }
                )

            self.assertSequenceEqual(
                [
                    unittest.mock.call(self.x509)
                ],
                self.quick_check.mock_calls
            )

            self.assertTrue(result)
            self.assertFalse(self.verifier.deferred)

            self.quick_check.reset_mock()

    def test_verify_recorded_quick_check_unsure(self):
        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1
            self.quick_check.return_value = None

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                result = self.verifier.verify_recorded(
                    self.x509,
                    {
                        (self.x509_root, errno, errdepth)
                    }
                )

            self.assertSequenceEqual(
                [
                    unittest.mock.call(self.x509)
                ],
                self.quick_check.mock_calls
            )

            self.assertTrue(result)
            self.assertTrue(self.verifier.deferred)

            self.quick_check.reset_mock()

    def test_verify_recorded_quick_check_None_is_unsure(self):
        verifier = security_layer.HookablePKIXCertificateVerifier(
            None, None, None)
        verifier.transport = self.transport

        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                result = verifier.verify_recorded(
                    self.x509,
                    {
                        (self.x509_root, errno, errdepth)
                    }
                )

            self.assertSequenceEqual(
                [],
                self.quick_check.mock_calls
            )

            self.assertTrue(result)
            self.assertTrue(verifier.deferred)

            self.quick_check.reset_mock()

    def test_verify_recorded_quick_check_rejects(self):
        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1
            self.quick_check.return_value = False

            with contextlib.ExitStack() as stack:
                check_x509_hostname = stack.enter_context(unittest.mock.patch(
                    "aioxmpp.security_layer.check_x509_hostname"
                ))
                check_x509_hostname.return_value = True

                result = self.verifier.verify_recorded(
                    self.x509,
                    {
                        (self.x509_root, errno, errdepth)
                    }
                )

            self.assertSequenceEqual(
                [
                    unittest.mock.call(self.x509)
                ],
                self.quick_check.mock_calls
            )

            self.assertFalse(result)
            self.assertFalse(self.verifier.deferred)

            self.quick_check.reset_mock()

    def test_verify_recorded_does_not_call_quick_check_on_no_errors(self):
        result = self.verifier.verify_recorded(
            self.x509,
            {
            }
        )

        self.assertTrue(result)

        self.assertSequenceEqual(
            [
            ],
            self.quick_check.mock_calls
        )

    def test_post_handshake_success_on_non_deferred(self):
        self.verifier.deferred = False

        run_coroutine(self.verifier.post_handshake(self.transport))

        self.assertSequenceEqual(
            [],
            self.post_handshake_deferred_failure.mock_calls)
        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            self.post_handshake_success.mock_calls
        )

    def test_post_handshake_success_not_called_if_None(self):
        verifier = security_layer.HookablePKIXCertificateVerifier(
            self.quick_check,
            self.post_handshake_deferred_failure,
            None
        )

        verifier.deferred = False

        run_coroutine(verifier.post_handshake(self.transport))

        self.assertSequenceEqual(
            [],
            self.post_handshake_deferred_failure.mock_calls)
        self.assertSequenceEqual(
            [],
            self.post_handshake_success.mock_calls
        )

    def test_post_handshake_deferred_failure_passes(self):
        self.verifier.deferred = True

        self.post_handshake_deferred_failure.return_value = True

        run_coroutine(self.verifier.post_handshake(self.transport))

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.verifier),
            ],
            self.post_handshake_deferred_failure.mock_calls
        )

        self.assertSequenceEqual(
            [
            ],
            self.post_handshake_success.mock_calls
        )

    def test_post_handshake_deferred_failure_not_called_if_None_and_fails(self):
        verifier = security_layer.HookablePKIXCertificateVerifier(
            self.quick_check,
            None,
            self.post_handshake_success
        )

        verifier.deferred = True

        with self.assertRaises(errors.TLSFailure):
            run_coroutine(verifier.post_handshake(self.transport))

        self.assertSequenceEqual(
            [],
            self.post_handshake_deferred_failure.mock_calls)
        self.assertSequenceEqual(
            [],
            self.post_handshake_success.mock_calls
        )

    def test_post_handshake_deferred_failure_returns_false_value(self):
        self.verifier.deferred = True

        for value in [None, False, ""]:
            self.post_handshake_deferred_failure.return_value = value

            with self.assertRaisesRegex(errors.TLSFailure,
                                        "certificate verification failed"):
                run_coroutine(self.verifier.post_handshake(self.transport))


class TestAbstractPinStore(unittest.TestCase):
    class FakePinStore(security_layer.AbstractPinStore):
        def _x509_key(self, x509):
            pass

        def _encode_key(self, *args, **kwargs):
            self._encode_key_rec(*args, **kwargs)
            return super()._encode_key(*args, **kwargs)

        def _decode_key(self, *args, **kwargs):
            self._decode_key_rec(*args, **kwargs)
            return super()._decode_key(*args, **kwargs)

    def setUp(self):
        self.x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_zombofant_net)
        self.x509_other = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            crt_cacert_root)
        self.store = self.FakePinStore()
        self.x509_key = unittest.mock.Mock()
        self.encode_key = unittest.mock.Mock()
        self.decode_key = unittest.mock.Mock()
        self.store._x509_key = self.x509_key
        self.store._encode_key_rec = self.encode_key
        self.store._decode_key_rec = self.decode_key

    def test_is_abstract(self):
        with self.assertRaisesRegex(TypeError, "abstract"):
            security_layer.AbstractPinStore()

    def test_pin_uses__x509_key_method(self):
        x509 = object()

        self.store.pin("host.example", x509)

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

    def test_query_returns_true_for_matching_hostname_and_key(self):
        x509 = object()

        self.x509_key.return_value = 1

        self.store.pin("host.example", x509)

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )
        self.x509_key.mock_calls.clear()

        self.assertIs(
            self.store.query("host.example", x509),
            True
        )

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

    def test_query_returns_None_for_mismatching_hostname(self):
        x509 = object()

        self.x509_key.return_value = 1

        self.store.pin("host.example", x509)

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )
        self.x509_key.mock_calls.clear()

        self.assertIsNone(
            self.store.query("host.invalid", x509)
        )

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

    def test_query_returns_None_for_mismatching_key(self):
        x509 = object()

        self.x509_key.return_value = 1

        self.store.pin("host.example", x509)

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )
        self.x509_key.mock_calls.clear()

        self.x509_key.return_value = 2
        self.assertIsNone(
            self.store.query("host.example", x509)
        )

        self.assertSequenceEqual(
            self.x509_key.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

    def test_pin_multiple(self):
        x509 = object()

        self.x509_key.return_value = 1
        self.store.pin("host.example", x509)

        self.x509_key.return_value = 2
        self.store.pin("host.example", x509)

        self.assertIs(
            self.store.query("host.example", x509),
            True
        )

        self.x509_key.return_value = 1

        self.assertIs(
            self.store.query("host.example", x509),
            True
        )

        self.x509_key.return_value = 3

        self.assertIs(
            self.store.query("host.example", x509),
            None
        )

    def test_get_pinned_for_host(self):
        x509 = object()

        self.x509_key.return_value = 456
        self.store.pin("host.example", x509)

        self.x509_key.return_value = 123
        self.store.pin("host.example", x509)

        self.assertSetEqual(
            set(self.store.get_pinned_for_host("host.example")),
            {123, 456},
        )

    def test_get_pinned_for_host_with_unknown_host(self):
        self.assertSetEqual(
            set(self.store.get_pinned_for_host("host.invalid")),
            set(),
        )

    def test_export_to_json(self):
        x509 = object()

        self.x509_key.return_value = 456
        self.store.pin("host.example", x509)

        self.x509_key.return_value = 123
        self.store.pin("host.example", x509)

        self.x509_key.return_value = 789
        self.store.pin("another.example", x509)

        d1 = self.store.export_to_json()

        self.assertIn(
            unittest.mock.call(123),
            self.encode_key.mock_calls
        )

        self.assertIn(
            unittest.mock.call(456),
            self.encode_key.mock_calls
        )

        self.assertIn(
            unittest.mock.call(789),
            self.encode_key.mock_calls
        )

        self.assertEqual(len(self.encode_key.mock_calls), 3)

        self.assertDictEqual(
            d1,
            {
                "host.example": [123, 456],
                "another.example": [789]
            }
        )

        d2 = self.store.export_to_json()
        self.assertDictEqual(
            d2,
            {
                "host.example": [123, 456],
                "another.example": [789]
            }
        )

        self.assertIsNot(d1, d2)

    def test_import_from_json_override(self):
        x509 = object()

        self.x509_key.return_value = 1000
        self.store.pin("host.example", x509)

        self.store.import_from_json(
            {
                "host.example": [123],
                "another.example": [234],
            },
            override=True)

        self.assertIn(
            unittest.mock.call(123),
            self.decode_key.mock_calls
        )

        self.assertIn(
            unittest.mock.call(234),
            self.decode_key.mock_calls
        )

        self.assertEqual(len(self.decode_key.mock_calls), 2)

        self.assertSetEqual(
            set(self.store.get_pinned_for_host("host.example")),
            {123}
        )

        self.assertSetEqual(
            set(self.store.get_pinned_for_host("another.example")),
            {234}
        )

    def test_import_from_json_default(self):
        x509 = object()

        self.x509_key.return_value = 1000
        self.store.pin("host.example", x509)

        self.store.import_from_json(
            {
                "host.example": [123],
                "another.example": [234],
            }
        )

        self.assertIn(
            unittest.mock.call(123),
            self.decode_key.mock_calls
        )

        self.assertIn(
            unittest.mock.call(234),
            self.decode_key.mock_calls
        )

        self.assertEqual(len(self.decode_key.mock_calls), 2)

        self.assertSetEqual(
            set(self.store.get_pinned_for_host("host.example")),
            {123, 1000}
        )

        self.assertSetEqual(
            set(self.store.get_pinned_for_host("another.example")),
            {234}
        )

    def tearDown(self):
        del self.store
        del self.x509


class TestPublicKeyPinStore(unittest.TestCase):
    def setUp(self):
        self.store = security_layer.PublicKeyPinStore()

    def test_is_abstract_pin_store(self):
        self.assertTrue(issubclass(
            security_layer.PublicKeyPinStore,
            security_layer.AbstractPinStore
        ))

    def test__x509_key_extracts_public_key_blob(self):
        x509 = object()

        with contextlib.ExitStack() as stack:
            extract_blob = stack.enter_context(unittest.mock.patch(
                "aioxmpp.security_layer.extract_blob"
            ))
            blob_to_pyasn1 = stack.enter_context(unittest.mock.patch(
                "aioxmpp.security_layer.blob_to_pyasn1"
            ))
            extract_pk_blob_from_pyasn1 = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.extract_pk_blob_from_pyasn1"
                )
            )

            result = self.store._x509_key(x509)

        self.assertSequenceEqual(
            extract_blob.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

        self.assertSequenceEqual(
            blob_to_pyasn1.mock_calls,
            [
                unittest.mock.call(extract_blob()),
            ]
        )

        self.assertSequenceEqual(
            extract_pk_blob_from_pyasn1.mock_calls,
            [
                unittest.mock.call(blob_to_pyasn1()),
            ]
        )

        self.assertEqual(
            result,
            extract_pk_blob_from_pyasn1()
        )

    def test__encode_key_applies_base64(self):
        key = object()

        with unittest.mock.patch("base64.b64encode") as b64encode:
            result = self.store._encode_key(key)

        self.assertSequenceEqual(
            b64encode.mock_calls,
            [
                unittest.mock.call(key),
                unittest.mock.call().decode("ascii")
            ]
        )

        self.assertEqual(
            result,
            b64encode().decode()
        )

    def test__decode_key_unapplies_base64(self):
        obj = unittest.mock.Mock()

        with unittest.mock.patch("base64.b64decode") as b64decode:
            result = self.store._decode_key(obj)

        self.assertSequenceEqual(
            obj.mock_calls,
            [
                unittest.mock.call.encode("ascii"),
            ]
        )

        self.assertSequenceEqual(
            b64decode.mock_calls,
            [
                unittest.mock.call(obj.encode())
            ]
        )

        self.assertEqual(
            result,
            b64decode()
        )

    def tearDown(self):
        del self.store


class TestCertificatePinStore(unittest.TestCase):
    def setUp(self):
        self.store = security_layer.CertificatePinStore()

    def test_is_abstract_pin_store(self):
        self.assertTrue(issubclass(
            security_layer.CertificatePinStore,
            security_layer.AbstractPinStore
        ))

    def test__x509_key_extracts_public_key_blob(self):
        x509 = object()

        with contextlib.ExitStack() as stack:
            extract_blob = stack.enter_context(unittest.mock.patch(
                "aioxmpp.security_layer.extract_blob"
            ))

            result = self.store._x509_key(x509)

        self.assertSequenceEqual(
            extract_blob.mock_calls,
            [
                unittest.mock.call(x509),
            ]
        )

        self.assertEqual(
            result,
            extract_blob()
        )

    def test__encode_key_applies_base64(self):
        key = object()

        with unittest.mock.patch("base64.b64encode") as b64encode:
            result = self.store._encode_key(key)

        self.assertSequenceEqual(
            b64encode.mock_calls,
            [
                unittest.mock.call(key),
                unittest.mock.call().decode("ascii")
            ]
        )

        self.assertEqual(
            result,
            b64encode().decode()
        )

    def test__decode_key_unapplies_base64(self):
        obj = unittest.mock.Mock()

        with unittest.mock.patch("base64.b64decode") as b64decode:
            result = self.store._decode_key(obj)

        self.assertSequenceEqual(
            obj.mock_calls,
            [
                unittest.mock.call.encode("ascii"),
            ]
        )

        self.assertSequenceEqual(
            b64decode.mock_calls,
            [
                unittest.mock.call(obj.encode())
            ]
        )

        self.assertEqual(
            result,
            b64decode()
        )

    def tearDown(self):
        del self.store


class TestPinningPKIXCertificateVerifier(unittest.TestCase):
    def setUp(self):
        self.query_pin = unittest.mock.Mock()
        self.decide = CoroutineMock()
        self.post_handshake_success = CoroutineMock()
        self.transport = unittest.mock.Mock()
        self.verifier = security_layer.PinningPKIXCertificateVerifier(
            self.query_pin,
            self.decide
        )
        self.verifier.transport = self.transport

    def test_is_hookable_pkix_certificate_verifier(self):
        self.assertTrue(issubclass(
            security_layer.PinningPKIXCertificateVerifier,
            security_layer.HookablePKIXCertificateVerifier
        ))

    def test_call_query_pin_on_quick_check(self):
        x509 = object()
        result = self.verifier._quick_check(x509)

        self.assertSequenceEqual(
            self.transport.mock_calls,
            [
                unittest.mock.call.get_extra_info("server_hostname"),
            ]
        )

        self.assertSequenceEqual(
            self.query_pin.mock_calls,
            [
                unittest.mock.call(
                    self.transport.get_extra_info(),
                    x509)
            ]
        )

        self.assertEqual(
            result,
            self.query_pin()
        )

    def test_decide_is_used_as_post_handshake_deferred_failure_callback(self):
        self.assertIs(
            self.decide,
            self.verifier._post_handshake_deferred_failure
        )

    def tearDown(self):
        del self.verifier
        del self.query_pin


class TestPasswordSASLProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        aiosasl._system_random = unittest.mock.MagicMock()
        aiosasl._system_random.getrandbits.return_value = int.from_bytes(
            b"foo",
            "little")

        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = nonza.StreamFeatures()
        self.mechanisms = security_layer.SASLMechanisms()
        self.features[...] = self.mechanisms

        self.password_provider = unittest.mock.MagicMock()

    @asyncio.coroutine
    def _password_provider_wrapper(self, client_jid, nattempt):
        return self.password_provider(client_jid, nattempt)

    def _test_provider(self, provider,
                       actions=[], stimulus=None,
                       tls_transport=None):
        return run_coroutine_with_peer(
            provider.execute(self.client_jid,
                             self.features,
                             self.xmlstream,
                             tls_transport),
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop
        )

    def test_raise_sasl_unavailable_if_sasl_is_not_supported(self):
        del self.features[security_layer.SASLMechanisms]

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        with self.assertRaisesRegex(errors.SASLUnavailable,
                                    "does not support SASL"):
            self._test_provider(provider)

    def test_reject_plain_auth_over_non_tls_stream(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.assertFalse(self._test_provider(provider))

    def test_raise_authentication_error_if_password_provider_returns_None(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = None

        with self.assertRaisesRegex(aiosasl.AuthenticationFailure,
                                    "aborted by user"):
            self._test_provider(provider, tls_transport=True)

    def test_raise_sasl_error_on_permanent_error(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        payload = b"\0foo\0foo"
        self.password_provider.return_value = "foo"

        with self.assertRaisesRegex(aiosasl.SASLFailure,
                                    "malformed-request"):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(mechanism="PLAIN",
                                       payload=payload),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl,
                                           "malformed-request")
                            )
                        )
                    ),
                    XMLStreamMock.Unmute(),
                ],
                tls_transport=True)

    def test_perform_mechanism_on_match(self):
        self.mechanisms.mechanisms.append(
            security_layer.SASLMechanism(name="PLAIN")
        )

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                   b"\0"+"foobar".encode("utf-8"))

        self.assertTrue(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(
                            mechanism="PLAIN",
                            payload=payload),
                        response=XMLStreamMock.Receive(
                            nonza.SASLSuccess())
                    ),
                    XMLStreamMock.Unmute(),
                ],
                tls_transport=True)
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
            ],
            self.password_provider.mock_calls
        )

    def test_cycle_through_mechanisms_if_mechanisms_fail(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="SCRAM-SHA-1"),
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        self.assertTrue(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl, "invalid-mechanism")
                            ))
                    ),
                    XMLStreamMock.Unmute(),
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            nonza.SASLSuccess()
                        )
                    ),
                    XMLStreamMock.Unmute(),
                ],
                tls_transport=True)
        )

        # make sure that the password provider is called only once when a
        # non-credential-related error occurs
        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
            ],
            self.password_provider.mock_calls
        )

    def test_re_query_for_credentials_on_auth_failure(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper,
            max_auth_attempts=3)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8") +
                         b"\0"+"foobar".encode("utf-8"))

        with self.assertRaises(aiosasl.AuthenticationFailure):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl, "not-authorized")
                            )
                        )
                    ),
                    XMLStreamMock.Unmute(),
                ]*3,
                tls_transport=True)

        # make sure that the password provider is called each time a
        # not-authorized is received
        self.assertSequenceEqual(
            [
                unittest.mock.call(self.client_jid.bare(), 0),
                unittest.mock.call(self.client_jid.bare(), 1),
                unittest.mock.call(self.client_jid.bare(), 2),
            ],
            self.password_provider.mock_calls
        )

    def test_re_query_for_credentials_on_value_error(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper,
            max_auth_attempts=3)

        self.password_provider.return_value = "foobar"

        with contextlib.ExitStack() as stack:
            authenticate = stack.enter_context(unittest.mock.patch.object(
                aiosasl.PLAIN,
                "authenticate",
            ))
            authenticate.side_effect = ValueError
            stack.enter_context(self.assertRaises(ValueError))

            self._test_provider(
                provider,
                actions=[],
                tls_transport=True
            )

        self.assertSequenceEqual(
            authenticate.mock_calls,
            [
                unittest.mock.call(unittest.mock.ANY, unittest.mock.ANY),
                unittest.mock.call(unittest.mock.ANY, unittest.mock.ANY),
                unittest.mock.call(unittest.mock.ANY, unittest.mock.ANY),
            ]
        )

    def test_fail_if_out_of_mechanisms(self):
        self.mechanisms.mechanisms.extend([
            security_layer.SASLMechanism(name="SCRAM-SHA-1"),
            security_layer.SASLMechanism(name="PLAIN")
        ])

        provider = security_layer.PasswordSASLProvider(
            self._password_provider_wrapper)

        self.password_provider.return_value = "foobar"

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        self.assertFalse(
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl,
                                           "invalid-mechanism")
                            )
                        )
                    ),
                    XMLStreamMock.Unmute(),
                    XMLStreamMock.Mute(),
                    XMLStreamMock.Send(
                        nonza.SASLAuth(mechanism="PLAIN",
                                       payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            nonza.SASLFailure(
                                condition=(namespaces.sasl,
                                           "mechanism-too-weak")
                            )
                        )
                    ),
                    XMLStreamMock.Unmute(),
                ],
                tls_transport=True
            )
        )

    def tearDown(self):
        del self.xmlstream
        del self.transport
        del self.loop
        del self.client_jid

        import random
        aiosasl._system_random = random.SystemRandom()


@unittest.skipUnless(hasattr(aiosasl, "ANONYMOUS"),
                     "version of aiosasl does not support ANONYMOUS")
class TestAnonymousSASLProvider(unittest.TestCase):
    def setUp(self):
        self.token = unittest.mock.sentinel.trace_token
        self.sp = security_layer.AnonymousSASLProvider(
            self.token
        )

        self.transport = object()
        self.loop = asyncio.get_event_loop()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = nonza.StreamFeatures()
        self.mechanisms = security_layer.SASLMechanisms()
        self.features[...] = self.mechanisms

    def tearDown(self):
        del self.sp
        del self.token
        del self.transport
        del self.xmlstream
        del self.features
        del self.mechanisms

    def test_return_false_if__find_supported_returns_None(self):
        with contextlib.ExitStack() as stack:
            _find_supported = stack.enter_context(
                unittest.mock.patch.object(self.sp, "_find_supported")
            )
            _find_supported.return_value = None, None

            _execute = stack.enter_context(
                unittest.mock.patch.object(
                    self.sp,
                    "_execute",
                    new=CoroutineMock()
                )
            )
            _execute.return_value = unittest.mock.sentinel.execute_result

            result = run_coroutine(self.sp.execute(
                unittest.mock.sentinel.client_jid,
                unittest.mock.sentinel.features,
                unittest.mock.sentinel.xmlstream,
                unittest.mock.sentinel.tls_transport,
            ))

        self.assertFalse(_execute.mock_calls)

        self.assertFalse(result)

        _find_supported.assert_called_with(
            unittest.mock.sentinel.features,
            [aiosasl.ANONYMOUS],
        )

    def test_call__execute_and_return_result_if__find_supported_passes(self):
        with contextlib.ExitStack() as stack:
            anon_mechanism = stack.enter_context(
                unittest.mock.patch("aiosasl.ANONYMOUS"),
            )
            anon_mechanism.return_value = unittest.mock.sentinel.anon

            _find_supported = stack.enter_context(
                unittest.mock.patch.object(self.sp, "_find_supported")
            )
            _find_supported.return_value = (
                aiosasl.ANONYMOUS, unittest.mock.sentinel.token
            )

            _execute = stack.enter_context(
                unittest.mock.patch.object(
                    self.sp,
                    "_execute",
                    new=CoroutineMock()
                )
            )
            _execute.return_value = unittest.mock.sentinel.execute_result

            SASLXMPPInterface = stack.enter_context(
                unittest.mock.patch("aioxmpp.sasl.SASLXMPPInterface"),
            )
            SASLXMPPInterface.return_value = unittest.mock.sentinel.intf

            result = run_coroutine(self.sp.execute(
                unittest.mock.sentinel.client_jid,
                unittest.mock.sentinel.features,
                unittest.mock.sentinel.xmlstream,
                unittest.mock.sentinel.tls_transport,
            ))

        _find_supported.assert_called_once_with(
            unittest.mock.sentinel.features,
            [anon_mechanism],
        )

        SASLXMPPInterface.assert_called_once_with(
            unittest.mock.sentinel.xmlstream,
        )

        anon_mechanism.assert_called_once_with(
            self.token,
        )

        _execute.assert_called_with(
            unittest.mock.sentinel.intf,
            unittest.mock.sentinel.anon,
            unittest.mock.sentinel.token,
        )

        self.assertEqual(
            result,
            unittest.mock.sentinel.execute_result,
        )


class Testnegotiate_sasl(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = unittest.mock.Mock()
        self.transport.get_extra_info.return_value = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.mechanisms = security_layer.SASLMechanisms()
        self.features = nonza.StreamFeatures()
        self.features[...] = self.mechanisms

        self.post_sasl_features = nonza.StreamFeatures()

        self.password_provider = unittest.mock.MagicMock()

    def _test_provider(self, main_coro,
                       actions=[], stimulus=None):
        return run_coroutine_with_peer(
            main_coro,
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop
        )

    def _coro_return(self, value):
        return value
        yield None

    def test_full_negotiation(self):
        sasl_provider1 = unittest.mock.Mock()
        sasl_provider1.execute = CoroutineMock()
        sasl_provider1.execute.return_value = False

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute = CoroutineMock()
        sasl_provider2.execute.return_value = True

        sasl_provider3 = unittest.mock.MagicMock()
        sasl_provider3.execute = CoroutineMock()
        sasl_provider3.execute.return_value = True

        result = self._test_provider(
            security_layer.negotiate_sasl(
                self.transport,
                self.xmlstream,
                [sasl_provider1,
                 sasl_provider2,
                 sasl_provider3],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            result,
            self.post_sasl_features,
        )

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

        sasl_provider3.execute.assert_not_called()

    def test_raise_if_sasl_fails(self):
        sasl_provider1 = unittest.mock.Mock()
        sasl_provider1.execute = CoroutineMock()
        sasl_provider1.execute.return_value = False

        with self.assertRaisesRegex(errors.SASLUnavailable,
                                    "No common mechanisms"):
            self._test_provider(
                security_layer.negotiate_sasl(
                    self.transport,
                    self.xmlstream,
                    [sasl_provider1],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features),
                [

                ]
            )

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

    def test_delay_and_propagate_auth_error(self):
        exc = aiosasl.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.Mock()
        sasl_provider1.execute = CoroutineMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.Mock()
        sasl_provider2.execute = CoroutineMock()
        sasl_provider2.execute.return_value = False

        with self.assertRaises(aiosasl.AuthenticationFailure) as ctx:
            self._test_provider(
                security_layer.negotiate_sasl(
                    self.transport,
                    self.xmlstream,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features),
                [
                ]
            )

        self.assertIs(ctx.exception, exc)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

    def test_wrap_ValueError_in_StreamNegotiationFailure(self):
        exc = ValueError("invalid codepoint")

        sasl_provider1 = unittest.mock.Mock()
        sasl_provider1.execute = CoroutineMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.Mock()
        sasl_provider2.execute = CoroutineMock()
        sasl_provider2.execute.return_value = False

        with self.assertRaises(errors.StreamNegotiationFailure) as ctx:
            self._test_provider(
                security_layer.negotiate_sasl(
                    self.transport,
                    self.xmlstream,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features),
                [
                ]
            )

        self.assertIs(ctx.exception.__cause__, exc)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_not_called()

    def test_swallow_auth_error_if_auth_succeeds_with_different_mech(self):
        exc = aiosasl.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.Mock()
        sasl_provider1.execute = CoroutineMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.Mock()
        sasl_provider2.execute = CoroutineMock()
        sasl_provider2.execute.return_value = True

        result = self._test_provider(
            security_layer.negotiate_sasl(
                self.transport,
                self.xmlstream,
                [sasl_provider1,
                 sasl_provider2],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            self.post_sasl_features,
            result
        )

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            self.transport)


class TestSTARTTLSProvider(unittest.TestCase):
    def test_init(self):
        obj = security_layer.STARTTLSProvider(
            unittest.mock.sentinel.ssl_ctx_factory,
            unittest.mock.sentinel.certificate_verifier_factory,
            require_starttls=unittest.mock.sentinel.tls_required,
        )

        self.assertEqual(
            obj.ssl_context_factory,
            unittest.mock.sentinel.ssl_ctx_factory,
        )

        self.assertEqual(
            obj.certificate_verifier_factory,
            unittest.mock.sentinel.certificate_verifier_factory,
        )

        self.assertEqual(
            obj.tls_required,
            unittest.mock.sentinel.tls_required,
        )


class Test_default_ssl_context(unittest.TestCase):

    def test_default_ssl_context(self):
        with unittest.mock.patch.object(OpenSSL.SSL, "Context") as ctxt:
            security_layer.default_ssl_context()

        self.assertCountEqual(
            ctxt.mock_calls,
            [
                unittest.mock.call(OpenSSL.SSL.SSLv23_METHOD),
                unittest.mock.call().set_options(
                    OpenSSL.SSL.OP_NO_SSLv2 | OpenSSL.SSL.OP_NO_SSLv3),
                unittest.mock.call().set_verify(
                    OpenSSL.SSL.VERIFY_PEER,
                    security_layer.default_verify_callback),
            ]
        )


class Testsecurity_layer(unittest.TestCase):
    def test_sanity_checks_on_providers(self):
        with self.assertRaises(AttributeError):
            security_layer.security_layer(object(), [unittest.mock.MagicMock()])
        with self.assertRaises(AttributeError):
            security_layer.security_layer(unittest.mock.MagicMock(), [object()])

    def test_require_sasl_provider(self):
        with self.assertRaises(ValueError):
            security_layer.security_layer(unittest.mock.MagicMock(), [])

    @unittest.mock.patch("aioxmpp.security_layer.SecurityLayer")
    def test_creates_SecurityLayer(self, SecurityLayer):
        tls_provider = unittest.mock.MagicMock()
        sasl_providers = [unittest.mock.MagicMock()]
        result = security_layer.security_layer(
            tls_provider,
            sasl_providers
        )

        SecurityLayer.assert_called_with(
            tls_provider.ssl_context_factory,
            tls_provider.certificate_verifier_factory,
            tls_provider.tls_required,
            tuple(sasl_providers)
        )

        self.assertEqual(
            result,
            SecurityLayer()
        )


class Testtls_with_password_based_authentication(unittest.TestCase):
    @unittest.mock.patch("aioxmpp.security_layer.PasswordSASLProvider")
    @unittest.mock.patch("aioxmpp.security_layer.SecurityLayer")
    @unittest.mock.patch("aioxmpp.security_layer.STARTTLSProvider")
    def test_constructs_security_layer(self,
                                       STARTTLSProvider,
                                       SecurityLayer,
                                       PasswordSASLProvider):
        password_provider = object()
        ssl_context_factory = object()
        certificate_verifier_factory = object()
        max_auth_attempts = 4

        result = security_layer.tls_with_password_based_authentication(
            password_provider,
            ssl_context_factory,
            max_auth_attempts,
            certificate_verifier_factory)

        self.assertFalse(STARTTLSProvider.mock_calls)

        SecurityLayer.assert_called_once_with(
            ssl_context_factory,
            certificate_verifier_factory,
            True,
            (
                PasswordSASLProvider(
                    password_provider,
                    max_auth_attempts=max_auth_attempts),
            )
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )


class Testmake(unittest.TestCase):
    def test_simple(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            (PasswordSASLProvider(),)
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_simple_with_ssl_context_factory(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                ssl_context_factory=unittest.mock.sentinel.factory
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        SecurityLayer.assert_called_with(
            unittest.mock.sentinel.factory,
            PKIXCertificateVerifier,
            True,
            (PasswordSASLProvider(),)
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_with_static_password(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                "foo",
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.ANY,
        )

        _, (password_provider, ), _ = PasswordSASLProvider.mock_calls[0]

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            (PasswordSASLProvider(),)
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

        self.assertEqual(
            run_coroutine(password_provider(unittest.mock.sentinel.jid, 0)),
            "foo",
        )

        self.assertIsNone(
            run_coroutine(password_provider(unittest.mock.sentinel.jid, 1)),
        )

    def test_with_pin_store_substitutes_phdf(self):
        pin_data = {"foo": unittest.mock.sentinel.bar}

        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            PublicKeyPinStore = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PublicKeyPinStore"
                )
            )

            security_layer.make(
                unittest.mock.sentinel.password_provider,
                pin_store=pin_data,
            )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            unittest.mock.ANY,
            True,
            (PasswordSASLProvider(),)
        )

        _, (_, factory, *_), _ = SecurityLayer.mock_calls[0]

        with contextlib.ExitStack() as stack:
            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            verifier = factory()

        PinningPKIXCertificateVerifier.assert_called_with(
            PublicKeyPinStore().query,
            unittest.mock.ANY,
        )

        _, (_, phdf), _ = PinningPKIXCertificateVerifier.mock_calls[0]

        self.assertEqual(verifier, PinningPKIXCertificateVerifier())

        self.assertTrue(
            asyncio.iscoroutinefunction(phdf)
        )

        self.assertFalse(
            run_coroutine(phdf(unittest.mock.sentinel.foo))
        )

    def test_with_public_key_pin_store_with_static_data(self):
        pin_data = {"foo": unittest.mock.sentinel.bar}

        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            PublicKeyPinStore = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PublicKeyPinStore"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                pin_store=pin_data,
                post_handshake_deferred_failure=unittest.mock.sentinel.phdf
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        self.assertSequenceEqual(
            PublicKeyPinStore.mock_calls,
            [
                unittest.mock.call(),
                unittest.mock.call().import_from_json(
                    pin_data,
                )
            ]
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            unittest.mock.ANY,
            True,
            (PasswordSASLProvider(),)
        )

        _, (_, callable, _, _), _ = SecurityLayer.mock_calls[0]

        self.assertEqual(
            result,
            SecurityLayer(),
        )

        with contextlib.ExitStack() as stack:
            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            callback_result = callable()

        PinningPKIXCertificateVerifier.assert_called_with(
            PublicKeyPinStore().query,
            unittest.mock.sentinel.phdf
        )

        self.assertEqual(
            callback_result,
            PinningPKIXCertificateVerifier()
        )

    def test_with_certificate_pin_store_with_static_data(self):
        pin_data = {"foo": unittest.mock.sentinel.bar}

        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            CertificatePinStore = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.CertificatePinStore"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                pin_store=pin_data,
                pin_type=security_layer.PinType.CERTIFICATE,
                post_handshake_deferred_failure=unittest.mock.sentinel.phdf
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        self.assertSequenceEqual(
            CertificatePinStore.mock_calls,
            [
                unittest.mock.call(),
                unittest.mock.call().import_from_json(
                    pin_data,
                )
            ]
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            unittest.mock.ANY,
            True,
            (PasswordSASLProvider(),)
        )

        _, (_, callable, _, _), _ = SecurityLayer.mock_calls[0]

        self.assertEqual(
            result,
            SecurityLayer(),
        )

        with contextlib.ExitStack() as stack:
            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            callback_result = callable()

        PinningPKIXCertificateVerifier.assert_called_with(
            CertificatePinStore().query,
            unittest.mock.sentinel.phdf
        )

        self.assertEqual(
            callback_result,
            PinningPKIXCertificateVerifier()
        )

    def test_with_pin_store_object(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            pin_store = unittest.mock.Mock(
                spec=security_layer.AbstractPinStore
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                pin_store=pin_store,
                post_handshake_deferred_failure=unittest.mock.sentinel.phdf
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            unittest.mock.ANY,
            True,
            (PasswordSASLProvider(),)
        )

        _, (_, callable, _, _), _ = SecurityLayer.mock_calls[0]

        self.assertEqual(
            result,
            SecurityLayer(),
        )

        with contextlib.ExitStack() as stack:
            PinningPKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PinningPKIXCertificateVerifier"
                )
            )

            callback_result = callable()

        PinningPKIXCertificateVerifier.assert_called_with(
            pin_store.query,
            unittest.mock.sentinel.phdf
        )

        self.assertEqual(
            callback_result,
            PinningPKIXCertificateVerifier()
        )

    def test_no_verify(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            _NullVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer._NullVerifier"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                no_verify=True,
            )

        PasswordSASLProvider.assert_called_with(
            unittest.mock.sentinel.password_provider,
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            _NullVerifier,
            True,
            (PasswordSASLProvider(),)
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_anonymous_and_password_provider(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            AnonymousSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.AnonymousSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                unittest.mock.sentinel.password_provider,
                anonymous=unittest.mock.sentinel.token,
            )

        PasswordSASLProvider.assert_called_once_with(
            unittest.mock.sentinel.password_provider,
        )

        AnonymousSASLProvider.assert_called_once_with(
            unittest.mock.sentinel.token,
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            (
                AnonymousSASLProvider(),
                PasswordSASLProvider(),
            )
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_anonymous_without_password_provider(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            AnonymousSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.AnonymousSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                None,
                anonymous=unittest.mock.sentinel.token,
            )

        PasswordSASLProvider.assert_not_called()

        AnonymousSASLProvider.assert_called_once_with(
            unittest.mock.sentinel.token,
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            (
                AnonymousSASLProvider(),
            )
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_not_anonymous_without_password_provider(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            AnonymousSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.AnonymousSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                None
            )

        PasswordSASLProvider.assert_not_called()

        AnonymousSASLProvider.assert_not_called()

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            ()
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_anonymous_with_empty_string(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            AnonymousSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.AnonymousSASLProvider"
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            result = security_layer.make(
                None,
                anonymous="",
            )

        PasswordSASLProvider.assert_not_called()

        AnonymousSASLProvider.assert_called_once_with(
            "",
        )

        SecurityLayer.assert_called_with(
            security_layer.default_ssl_context,
            PKIXCertificateVerifier,
            True,
            (
                AnonymousSASLProvider(),
            )
        )

        self.assertEqual(
            result,
            SecurityLayer(),
        )

    def test_anonymous_without_AnonymousSASLProvider(self):
        with contextlib.ExitStack() as stack:
            SecurityLayer = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.SecurityLayer"
                )
            )

            PasswordSASLProvider = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PasswordSASLProvider"
                )
            )

            stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.AnonymousSASLProvider",
                    new=None
                )
            )

            PKIXCertificateVerifier = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.PKIXCertificateVerifier"
                )
            )

            default_ssl_context = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.security_layer.default_ssl_context"
                )
            )

            with self.assertRaisesRegex(
                    RuntimeError,
                    r"aiosasl does not support ANONYMOUS, please upgrade"):
                security_layer.make(
                    None,
                    anonymous="",
                )
