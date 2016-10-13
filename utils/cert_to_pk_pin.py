#!/usr/bin/env python3
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
