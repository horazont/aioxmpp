import asyncio
import contextlib
import itertools
import random
import socket
import ssl
import unittest

import OpenSSL.crypto
import OpenSSL.SSL

import aioxmpp.errors as errors
import aioxmpp.sasl as sasl
import aioxmpp.structs as structs
import aioxmpp.security_layer as security_layer
import aioxmpp.stream_xsos as stream_xsos

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
-----END CERTIFICATE-----
"""
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
-----END CERTIFICATE-----
"""


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
            (19, None),
            (18, 0),
            (27, 0),
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
            )
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

    def test_verify_recorded_rejects_non_deferrable_errors(self):
        for i in range(800//2):
            errno = random.randint(1, 100)
            depth = 0
            self._test_hardwired(errno, depth)

        for i in range(200//2):
            errno = random.randint(1, 100)
            depth = random.randint(1, 10)
            self._test_hardwired(errno, depth)

    def test_verify_recorded_calls_quick_check_for_deferrable_error(self):
        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1
            self.quick_check.return_value = True

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

    def test_verify_recorded_quick_check_rejects(self):
        for errno, errdepth in self.deferrable_errors:
            errdepth = errdepth if errdepth is not None else 1
            self.quick_check.return_value = False

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

    def test_post_handshake_deferred_failure_returns_false_value(self):
        self.verifier.deferred = True

        for value in [None, False, ""]:
            self.post_handshake_deferred_failure.return_value = value

            with self.assertRaisesRegex(errors.TLSFailure,
                                        "certificate verification failed"):
                run_coroutine(self.verifier.post_handshake(self.transport))


class TestSTARTTLSProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.ssl_context_factory = unittest.mock.Mock()
        self.certificate_verifier_factory = unittest.mock.Mock()

        self.ssl_context = self.ssl_context_factory()
        self.ssl_context_factory.return_value = self.ssl_context
        self.ssl_context_factory.mock_calls.clear()

        self.verifier = self.certificate_verifier_factory()
        self.verifier.pre_handshake = CoroutineMock()
        self.verifier.post_handshake = CoroutineMock()
        self.certificate_verifier_factory.return_value = self.verifier
        self.certificate_verifier_factory.mock_calls.clear()

    def _test_provider(self, provider, features, actions=[], stimulus=None):
        return run_coroutine_with_peer(
            provider.execute(self.client_jid,
                             features,
                             self.xmlstream),
            self.xmlstream.run_test(actions, stimulus=stimulus),
            loop=self.loop)

    def test_require_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "not supported by peer"):
            self._test_provider(provider, features)

    def test_pass_without_required_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=False)

        features = stream_xsos.StreamFeatures()

        self.assertIsNone(self._test_provider(provider, features))

    def test_fail_if_peer_requires_starttls_but_we_cannot_do_starttls(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=False)

        features = stream_xsos.StreamFeatures()
        instance = security_layer.STARTTLSFeature()
        instance.required = security_layer.STARTTLSFeature.STARTTLSRequired()
        features[...] = instance

        self.xmlstream.can_starttls_value = False

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "not supported by us"):
            self._test_provider(provider, features)

    def test_fail_if_peer_reports_failure(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        with self.assertRaisesRegexp(errors.TLSUnavailable,
                                     "failed on remote side"):
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSFailure()
                        )
                    )
                ]
            )

    def test_engage_starttls_on_proceed(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        result = self._test_provider(
            provider, features,
            actions=[
                XMLStreamMock.Send(
                    security_layer.STARTTLS(),
                    response=XMLStreamMock.Receive(
                        security_layer.STARTTLSProceed()
                    )
                ),
                XMLStreamMock.STARTTLS(
                    ssl_context=self.ssl_context,
                    post_handshake_callback=self.verifier.post_handshake
                )
            ]
        )

        self.assertIs(result, self.transport)

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            self.ssl_context_factory.mock_calls
        )

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
                unittest.mock.call().pre_handshake(self.xmlstream.transport),
                unittest.mock.call().setup_context(
                    self.ssl_context, self.xmlstream.transport),
                unittest.mock.call().post_handshake(
                    self.xmlstream.transport)
            ],
            self.certificate_verifier_factory.mock_calls
        )

    def test_propagate_and_wrap_error(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        exc = ValueError("foobar")
        self.certificate_verifier_factory().post_handshake.side_effect = exc

        with self.assertRaisesRegexp(errors.TLSFailure,
                                     "TLS connection failed: foobar"):
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSProceed()
                        )
                    ),
                    XMLStreamMock.STARTTLS(
                        ssl_context=self.ssl_context_factory(),
                        post_handshake_callback=
                        self.certificate_verifier_factory().post_handshake
                    )
                ]
            )

    def test_propagate_tls_error(self):
        provider = security_layer.STARTTLSProvider(
            self.ssl_context_factory,
            self.certificate_verifier_factory,
            require_starttls=True)

        features = stream_xsos.StreamFeatures()
        features[...] = security_layer.STARTTLSFeature()

        self.xmlstream.can_starttls_value = True

        exc = errors.TLSFailure("foobar")
        self.certificate_verifier_factory().post_handshake.side_effect = exc

        with self.assertRaises(errors.TLSFailure) as ctx:
            self._test_provider(
                provider, features,
                actions=[
                    XMLStreamMock.Send(
                        security_layer.STARTTLS(),
                        response=XMLStreamMock.Receive(
                            security_layer.STARTTLSProceed()
                        )
                    ),
                    XMLStreamMock.STARTTLS(
                        ssl_context=self.ssl_context_factory(),
                        post_handshake_callback=
                        self.certificate_verifier_factory().post_handshake
                    )
                ]
            )

        self.assertIs(ctx.exception, exc)

    def tearDown(self):
        del self.ssl_context_factory
        del self.certificate_verifier_factory
        del self.xmlstream
        del self.loop
        del self.client_jid


class TestPasswordSASLProvider(xmltestutils.XMLTestCase):
    def setUp(self):
        sasl._system_random = unittest.mock.MagicMock()
        sasl._system_random.getrandbits.return_value = int.from_bytes(
            b"foo",
            "little")

        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = stream_xsos.StreamFeatures()
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

        with self.assertRaisesRegexp(errors.SASLUnavailable,
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

        with self.assertRaisesRegexp(errors.AuthenticationFailure,
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

        with self.assertRaisesRegexp(errors.SASLFailure,
                                     "malformed-request"):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(mechanism="PLAIN",
                                      payload=payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "malformed-request")
                            )
                        )
                    )
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
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLSuccess())
                    )
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
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "invalid-mechanism")
                            ))
                    ),
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLSuccess()
                        )
                    ),
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

        plain_payload = (b"\0"+str(self.client_jid.localpart).encode("utf-8")+
                         b"\0"+"foobar".encode("utf-8"))

        with self.assertRaises(errors.AuthenticationFailure):
            self._test_provider(
                provider,
                actions=[
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="PLAIN",
                            payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl, "not-authorized")
                            )
                        )
                    ),
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
                    XMLStreamMock.Send(
                        sasl.SASLAuth(
                            mechanism="SCRAM-SHA-1",
                            payload=b"n,,n=foo,r=Zm9vAAAAAAAAAAAAAAAA"),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "invalid-mechanism")
                            )
                        )
                    ),
                    XMLStreamMock.Send(
                        sasl.SASLAuth(mechanism="PLAIN",
                                      payload=plain_payload),
                        response=XMLStreamMock.Receive(
                            sasl.SASLFailure(
                                condition=(namespaces.sasl,
                                           "mechanism-too-weak")
                            )
                        )
                    )
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
        sasl._system_random = random.SystemRandom()


class Testnegotiate_stream_security(xmltestutils.XMLTestCase):
    def setUp(self):
        self.client_jid = structs.JID.fromstr("foo@bar.example")

        self.loop = asyncio.get_event_loop()

        self.transport = object()

        self.xmlstream = XMLStreamMock(self, loop=self.loop)
        self.xmlstream.transport = self.transport

        self.features = stream_xsos.StreamFeatures()
        self.mechanisms = security_layer.SASLMechanisms()
        self.features[...] = self.mechanisms
        self.features[...] = security_layer.STARTTLSFeature()

        self.post_tls_features = stream_xsos.StreamFeatures()
        self.features[...] = self.mechanisms

        self.post_sasl_features = stream_xsos.StreamFeatures()

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
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        sasl_provider3 = unittest.mock.MagicMock()
        sasl_provider3.execute.return_value = self._coro_return(True)

        result = self._test_provider(
            security_layer.negotiate_stream_security(
                tls_provider,
                [sasl_provider1,
                 sasl_provider2,
                 sasl_provider3],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features,
                xmlstream=self.xmlstream),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_tls_features
                    )),
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            (self.transport, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider3.execute.assert_not_called()

    def test_sasl_only_negotiation(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(None)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        sasl_provider3 = unittest.mock.MagicMock()
        sasl_provider3.execute.return_value = self._coro_return(True)

        result = self._test_provider(
            security_layer.negotiate_stream_security(
                tls_provider,
                [sasl_provider1,
                 sasl_provider2,
                 sasl_provider3],
                negotiation_timeout=1.0,
                jid=self.client_jid,
                features=self.features,
                xmlstream=self.xmlstream),
            [
                XMLStreamMock.Reset(
                    response=XMLStreamMock.Receive(
                        self.post_sasl_features
                    ))
            ]
        )

        self.assertEqual(
            (None, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            None)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream,
            None)

        sasl_provider3.execute.assert_not_called()

    def test_raise_if_sasl_fails(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.return_value = self._coro_return(False)

        with self.assertRaisesRegexp(errors.SASLUnavailable,
                                     "No common mechanisms"):
            self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        ))
                ]
            )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

    def test_delay_and_propagate_auth_error(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        exc = errors.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(False)

        with self.assertRaises(errors.AuthenticationFailure) as ctx:
            self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        ))
                ]
            )

        self.assertIs(ctx.exception, exc)

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

    def test_swallow_auth_error_if_auth_succeeds_with_different_mech(self):
        tls_provider = unittest.mock.MagicMock()
        tls_provider.execute.return_value = self._coro_return(self.transport)

        exc = errors.AuthenticationFailure("credentials-expired")

        sasl_provider1 = unittest.mock.MagicMock()
        sasl_provider1.execute.side_effect = exc

        sasl_provider2 = unittest.mock.MagicMock()
        sasl_provider2.execute.return_value = self._coro_return(True)

        result = self._test_provider(
                security_layer.negotiate_stream_security(
                    tls_provider,
                    [sasl_provider1,
                     sasl_provider2],
                    negotiation_timeout=1.0,
                    jid=self.client_jid,
                    features=self.features,
                    xmlstream=self.xmlstream),
                [
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_tls_features
                        )),
                    XMLStreamMock.Reset(
                        response=XMLStreamMock.Receive(
                            self.post_sasl_features
                        ))
                ]
            )

        self.assertEqual(
            (self.transport, self.post_sasl_features),
            result
        )

        tls_provider.execute.assert_called_once_with(
            self.client_jid,
            self.features,
            self.xmlstream)

        sasl_provider1.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)

        sasl_provider2.execute.assert_called_once_with(
            self.client_jid,
            self.post_tls_features,
            self.xmlstream,
            self.transport)


class Testsecurity_layer(unittest.TestCase):
    def test_sanity_checks_on_providers(self):
        with self.assertRaises(AttributeError):
            security_layer.security_layer(object(), [unittest.mock.MagicMock()])
        with self.assertRaises(AttributeError):
            security_layer.security_layer(unittest.mock.MagicMock(), [object()])

    def test_require_sasl_provider(self):
        with self.assertRaises(ValueError):
            security_layer.security_layer(unittest.mock.MagicMock(), [])

    @unittest.mock.patch("functools.partial")
    def test_uses_partial(self, partial):
        tls_provider = unittest.mock.MagicMock()
        sasl_providers = [unittest.mock.MagicMock()]
        security_layer.security_layer(tls_provider, sasl_providers)

        partial.assert_called_once_with(
            security_layer.negotiate_stream_security,
            tls_provider,
            sasl_providers)


class Testtls_with_password_based_authentication(unittest.TestCase):
    @unittest.mock.patch("aioxmpp.security_layer.PasswordSASLProvider")
    @unittest.mock.patch("aioxmpp.security_layer.STARTTLSProvider")
    @unittest.mock.patch("aioxmpp.security_layer.security_layer")
    def test_constructs_security_layer(self,
                                       security_layer_fun,
                                       STARTTLSProvider,
                                       PasswordSASLProvider):
        password_provider = object()
        ssl_context_factory = object()
        certificate_verifier_factory = object()
        max_auth_attempts = 4

        security_layer.tls_with_password_based_authentication(
            password_provider,
            ssl_context_factory,
            max_auth_attempts,
            certificate_verifier_factory)

        security_layer_fun.assert_called_once_with(
            tls_provider=STARTTLSProvider(
                ssl_context_factory,
                require_starttls=True,
                certificate_verifier_factory=certificate_verifier_factory),
            sasl_providers=[
                PasswordSASLProvider(
                    password_provider,
                    max_auth_attempts=max_auth_attempts)
            ]
        )
