import asyncio
import logging

from aioxmpp.utils import namespaces

import aioxmpp.e2etest
import aioxmpp.httpupload

from aioxmpp.e2etest import (
    require_feature,
    blocking_timed,
    blocking,
)


class TestE2E(aioxmpp.e2etest.TestCase):
    @require_feature(namespaces.xep0363_http_upload)
    @blocking_timed
    @asyncio.coroutine
    def setUp(self, target):
        self.client = yield from self.provisioner.get_connected_client()
        self.target = target

    @blocking_timed
    def test_upload(self):
        logging.debug("using %s", self.target)
        request = aioxmpp.IQ(
            to=self.target,
            type_=aioxmpp.IQType.GET,
            payload=aioxmpp.httpupload.Request(
                "filename.jpg",
                1024,
                "image/jpg",
            )
        )

        slot = yield from self.client.send(request)

        self.assertIsInstance(slot, aioxmpp.httpupload.xso.Slot)
        self.assertTrue(slot.get.url)
        self.assertTrue(slot.put.url)
