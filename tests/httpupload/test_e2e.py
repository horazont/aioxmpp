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
    async def setUp(self, target):
        self.client = await self.provisioner.get_connected_client()
        self.target = target

    @blocking_timed
    async def test_upload(self):
        logging.debug("using %s", self.target)

        slot = await aioxmpp.httpupload.request_slot(
            self.client,
            self.target,
            "filename.jpg",
            1024,
            "image/jpg",
        )

        self.assertIsInstance(slot, aioxmpp.httpupload.xso.Slot)
        self.assertTrue(slot.get.url)
        self.assertTrue(slot.put.url)
