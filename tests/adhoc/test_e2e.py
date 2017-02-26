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

import aioxmpp.adhoc

from aioxmpp.utils import namespaces

from aioxmpp.e2etest import (
    require_feature,
    blocking,
    blocking_timed,
    TestCase,
    skip_with_quirk,
    Quirk,
)


class TestAdHocClient(TestCase):
    @require_feature(namespaces.xep0050_commands, multiple=True)
    @blocking
    @asyncio.coroutine
    def setUp(self, commands_providers):
        services = [aioxmpp.AdHocClient]

        self.peers = commands_providers

        self.client, = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=services,
            ),
        )
        self.svc = self.client.summon(aioxmpp.AdHocClient)

    @asyncio.coroutine
    def _get_ping_peer(self):
        for peer in self.peers:
            for item in (yield from self.svc.get_commands(peer)):
                if item.node == "ping":
                    return peer
        self.assertTrue(
            False,
            "found no peer which offers ad-hoc-ping; consider setting "
            "the #no-adhoc-ping quirk"
        )

    @blocking_timed
    @asyncio.coroutine
    def test_get_list(self):
        items = []
        for peer in self.peers:
            items.extend((yield from self.svc.get_commands(
                peer
            )))

        self.assertTrue(items)

    @skip_with_quirk(Quirk.NO_ADHOC_PING)
    @blocking_timed
    @asyncio.coroutine
    def test_ping(self):
        ping_peer = yield from self._get_ping_peer()
        session = yield from self.svc.execute(ping_peer, "ping")
        self.assertTrue(session.response.notes)
        yield from session.close()

    @skip_with_quirk(Quirk.NO_ADHOC_PING)
    @blocking_timed
    @asyncio.coroutine
    def test_ping_with_async_cm(self):
        # TODO: port this to python 3.5+ once we require its
        ping_peer = yield from self._get_ping_peer()
        session = yield from self.svc.execute(ping_peer, "ping")
        yield from session.__aenter__()
        self.assertTrue(session.response.notes)
        yield from session.__aexit__(None, None, None)


class TestAdHocServer(TestCase):
    @blocking
    @asyncio.coroutine
    def setUp(self):
        self.client, self.server = yield from asyncio.gather(
            self.provisioner.get_connected_client(
                services=[aioxmpp.adhoc.AdHocClient],
            ),
            self.provisioner.get_connected_client(
                services=[aioxmpp.adhoc.AdHocServer],
            ),
        )

        self.client_svc = self.server.summon(aioxmpp.adhoc.AdHocClient)
        self.server_svc = self.server.summon(aioxmpp.adhoc.AdHocServer)

    @asyncio.coroutine
    def _trivial_handler(self, stanza):
        return aioxmpp.adhoc.xso.Command(
            "simple",
            notes=[
                aioxmpp.adhoc.xso.Note(
                    aioxmpp.adhoc.xso.NoteType.INFO,
                    "some info!"
                )
            ]
        )

    @blocking_timed
    @asyncio.coroutine
    def test_advertises_command_support(self):
        self.assertTrue(
            (yield from self.client_svc.supports_commands(
                self.server.local_jid,
            ))
        )

    @blocking_timed
    @asyncio.coroutine
    def test_respond_to_command_listing(self):
        self.server_svc.register_stateless_command(
            "simple",
            {
                None: "Simple command",
                aioxmpp.structs.LanguageTag.fromstr("de"): "Einfacher Befehl",
            },
            self._trivial_handler,
        )

        commands = yield from self.client_svc.get_commands(
            self.server.local_jid
        )
        self.assertEqual(len(commands), 1)

        self.assertEqual(
            commands[0].node,
            "simple",
        )

        self.assertEqual(
            commands[0].name,
            "Simple command",
        )

    @blocking_timed
    @asyncio.coroutine
    def test_respond_to_command_info_query(self):
        self.server_svc.register_stateless_command(
            "simple",
            {
                None: "Simple command",
                aioxmpp.structs.LanguageTag.fromstr("de"): "Einfacher Befehl",
            },
            self._trivial_handler,
            features={"foo"},
        )

        info = yield from self.client_svc.get_command_info(
            self.server.local_jid,
            "simple",
        )

        self.assertSetEqual(
            info.features,
            {
                namespaces.xep0050_commands,
                namespaces.xep0030_info,
                "foo",
            }
        )

        self.assertCountEqual(
            [
                ("automation", "command-node", None, "Simple command"),
                ("automation", "command-node",
                 aioxmpp.structs.LanguageTag.fromstr("de"), "Einfacher Befehl"),
            ],
            [
                (ident.category, ident.type_, ident.lang, ident.name)
                for ident in info.identities
            ]
        )

    @blocking_timed
    @asyncio.coroutine
    def test_execute_simple_command(self):
        self.server_svc.register_stateless_command(
            "simple",
            {
                None: "Simple command",
                aioxmpp.structs.LanguageTag.fromstr("de"): "Einfacher Befehl",
            },
            self._trivial_handler,
        )

        session = yield from self.client_svc.execute(
            self.server.local_jid,
            "simple",
        )

        self.assertEqual(
            len(session.response.notes),
            1
        )
        self.assertEqual(session.response.notes[0].body, "some info!")
        self.assertIsNone(session.first_payload)

        yield from session.close()

    @blocking_timed
    @asyncio.coroutine
    def test_properly_fail_for_unknown_command(self):
        with self.assertRaises(aioxmpp.errors.XMPPCancelError) as ctx:
            session = yield from self.client_svc.execute(
                self.server.local_jid,
                "simple",
            )

        self.assertEqual(
            ctx.exception.condition,
            (namespaces.stanzas, "item-not-found")
        )
