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
import unittest

import aioxmpp
import aioxmpp.private_xml as private_xml
import aioxmpp.xso as xso

from aioxmpp.utils import etree

from aioxmpp.e2etest import (
    blocking,
    blocking_timed,
    TestCase,
)


class TestPrivateXMLStorage(TestCase):

    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.client, = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[
                    private_xml.PrivateXMLService
                ]
            ),
        )

    @blocking_timed
    @asyncio.coroutine
    def test_store_and_retrieve_xml_unregistered(self):
        tree = etree.fromstring(
            '<example xmlns="urn:example:unregistered">'
            '<payload xmlns="urn:example:unregistered">'
            'foobar'
            '</payload>'
            '</example>'
        )

        query = private_xml.xso.Query(None)
        query.unregistered_payload.append(tree)

        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            payload=query,
        )

        yield from self.client.stream.send(iq)

        query.unregistered_payload[0].clear()

        iq = aioxmpp.IQ(
            type_=aioxmpp.IQType.GET,
            payload=query,
        )

        retrieved = yield from self.client.stream.send(iq)

        self.assertEqual(len(retrieved.unregistered_payload), 1)
        self.assertEqual(
            retrieved.unregistered_payload[0].tag,
            "{urn:example:unregistered}example"
        )
        self.assertEqual(len(retrieved.unregistered_payload[0]), 1)
        self.assertEqual(
            retrieved.unregistered_payload[0][0].tag,
            "{urn:example:unregistered}payload"
        )
        self.assertEqual(
            retrieved.unregistered_payload[0][0].text,
            "foobar"
        )

    @blocking_timed
    @asyncio.coroutine
    def test_store_and_retrieve_xml_registered(self):
        p = self.client.summon(private_xml.PrivateXMLService)

        @private_xml.Query.as_payload_class
        class Example(xso.XSO):
            TAG = ("urn:example:registered", "example")
            data = xso.Text(type_=xso.String())

            def __init__(self, text=""):
                self.data = text

        yield from p.set_private_xml(Example("foobar"))
        retrieved = yield from p.get_private_xml(Example())

        self.assertEqual(len(retrieved.unregistered_payload), 0)
        self.assertTrue(isinstance(retrieved.registered_payload, Example))
        self.assertEqual(retrieved.registered_payload.data, "foobar")
