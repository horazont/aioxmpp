#!/usr/bin/env python3
########################################################################
# File name: cert_to_pk_pin.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################
import argparse
import base64

import OpenSSL.crypto

import aioxmpp.security_layer as sl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "infile",
        type=argparse.FileType("rb"),
        metavar="CERTFILE",
        help="Certificate file to read"
    )

    args = parser.parse_args()

    with args.infile as f:
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            f.read()
        )

    print(base64.b64encode(
        sl.extract_pk_blob_from_pyasn1(sl.blob_to_pyasn1(
            sl.extract_blob(x509)
        ))
    ).decode("ascii"))

if __name__ == "__main__":
    main()
