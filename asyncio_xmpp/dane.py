import asyncio
import hashlib
import logging
import sys

import OpenSSL.crypto

from . import network, security_layer

logger = logging.getLogger(__name__)

DIGEST_MAP = {
    1: "sha256",
    2: "sha512"
}

def dane_verify_peer_cert(records, peercert):
    peercert_full_digest = bytes(
        int(v, 16)
        for v in peercert.digest("sha256").split(b":")
    )

    for _, selector, match_type, value in records:
        if selector != 0:
            logger.warning("TLSA selector %s unsupported", match_type)
            continue

        if match_type == 0:
            logger.warning("TLSA matching type %s unsupported", match_type)
            continue

        try:
            digest_name = DIGEST_MAP[match_type]
        except KeyError as err:
            logger.warning("Unknown TLSA matching type field value: %s", err)
            continue

        if peercert_full_digest == value:
            logger.debug("found match in usage=3,selector=%s,matching_type=%s "
                         "record: %s", selector, match_type, value)
            return True

    return False


def dane_verify(tlsa_records, peercert, certmap):
    usagemap = {i: [] for i in range(4)}
    for record in tlsa_records:
        usage, *_ = record
        try:
            usagemap[usage].append(record)
        except KeyError as err:
            logger.warning("Unknown TLSA usage field value: %s", err)

    if dane_verify_peer_cert(usagemap[3], peercert):
        return True

    return False


class DANECertifcateVerifier(security_layer.ErrorRecordingVerifier):
    def __init__(self, allow_pkix=True):
        super().__init__()
        self._allow_pkix = allow_pkix

    def setup_context(self, ctx):
        ctx.set_verify(OpenSSL.SSL.VERIFY_NONE, self._callback_wrapper)

    @asyncio.coroutine
    def post_handshake_callback(self, transport):
        if self._allow_pkix and all(errno == 0 for _, errno, _ in self._errors):
            logger.debug("certificate passed through OpenSSL, no DANE used")
            return

        peer_hostname = transport.get_extra_info("peer_hostname")
        if peer_hostname is None:
            logger.error("cannot check DANE (peer_hostname on transport is"
                         " unset)")

        logger.debug("attempting check on DANE")
        try:
            records = yield from network.find_xmpp_host_tlsa(
                transport._loop,
                domain=peer_hostname)
        except ValueError as err:
            raise errors.TLSFailure("Failed to query TLSA records: {}".format(
                err))

        certmap = {
            depth: x509
            for x509, _, depth in self._errors
        }

        if not dane_verify(records,
                           transport.get_extra_info("peercert"),
                           certmap):
            raise errors.TLSFailure("Certificate validation failed (DANE)")

        logger.info("DANE verification successful")
