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

import aioxmpp

from aioxmpp.e2etest import (
    TestCase,
    blocking_timed,
    blocking,
)


class TestPresence(TestCase):
    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.a, self.b = yield from asyncio.gather(
            self.provisioner.get_connected_client(),
            self.provisioner.get_connected_client(),
        )

    @blocking_timed
    @asyncio.coroutine
    def test_events_on_presence(self):
        pres = aioxmpp.Presence(
            to=self.b.local_jid.bare(),
            type_=aioxmpp.PresenceType.AVAILABLE,
        )

        svc = self.b.summon(aioxmpp.PresenceClient)

        bare_fut = asyncio.Future()
        avail_fut = asyncio.Future()
        changed_fut = asyncio.Future()

        def on_bare_available(stanza):
            if stanza.from_ == self.b.local_jid:
                return False
            bare_fut.set_result(stanza)
            return True

        def on_available(full_jid, stanza):
            if full_jid == self.b.local_jid:
                return False
            avail_fut.set_result((full_jid, stanza))
            return True

        def on_changed(full_jid, stanza):
            changed_fut.set_result((full_jid, stanza))
            return True

        svc.on_bare_available.connect(on_bare_available)
        svc.on_available.connect(on_available)
        svc.on_changed.connect(on_changed)

        yield from self.a.stream.send(pres)

        stanza = yield from bare_fut
        self.assertIsInstance(stanza, aioxmpp.Presence)
        self.assertEqual(stanza.type_, aioxmpp.PresenceType.AVAILABLE)
        self.assertEqual(stanza.from_, self.a.local_jid)

        full_jid, stanza = yield from avail_fut
        self.assertIsInstance(stanza, aioxmpp.Presence)
        self.assertEqual(stanza.type_, aioxmpp.PresenceType.AVAILABLE)
        self.assertEqual(stanza.from_, self.a.local_jid)
        self.assertEqual(full_jid, stanza.from_)

        self.assertFalse(changed_fut.done())

        pres.show = aioxmpp.PresenceShow.DND
        yield from self.a.stream.send(pres)

        full_jid, stanza = yield from changed_fut
        self.assertIsInstance(stanza, aioxmpp.Presence)
        self.assertEqual(stanza.type_, aioxmpp.PresenceType.AVAILABLE)
        self.assertEqual(stanza.show, aioxmpp.PresenceShow.DND)
        self.assertEqual(stanza.from_, self.a.local_jid)
        self.assertEqual(full_jid, stanza.from_)

    @blocking_timed
    @asyncio.coroutine
    def test_presence_bookkeeping(self):
        pres = aioxmpp.Presence(
            to=self.b.local_jid.bare(),
            type_=aioxmpp.PresenceType.AVAILABLE,
        )

        svc = self.b.summon(aioxmpp.PresenceClient)

        bare_fut = asyncio.Future()

        # we use the future as a synchronisation primitive to avoid reading
        # from the service before the stanza has actually been received
        def on_bare_available(stanza):
            if stanza.from_ == self.b.local_jid:
                return False
            bare_fut.set_result(None)
            return True

        svc.on_bare_available.connect(on_bare_available)

        yield from self.a.stream.send(pres)

        yield from bare_fut

        most_available = svc.get_most_available_stanza(
            self.a.local_jid.bare()
        )
        self.assertIsNotNone(most_available)

        peer_resources = svc.get_peer_resources(
            self.a.local_jid.bare()
        )
        self.assertIn(
            self.a.local_jid.resource,
            peer_resources,
        )

        last_presence = svc.get_stanza(
            self.a.local_jid
        )
        self.assertIsNotNone(last_presence)
