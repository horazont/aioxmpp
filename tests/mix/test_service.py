########################################################################
# File name: test_service.py
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
import unittest

import aioxmpp
import aioxmpp.service
import aioxmpp.im.conversation as im_conversation
import aioxmpp.im.dispatcher as im_dispatcher
import aioxmpp.im.service as im_service
import aioxmpp.mix.service as mix_service
import aioxmpp.mix.xso as mix_xso
import aioxmpp.mix.xso.core0 as core0_xso
import aioxmpp.mix.xso.pam0 as pam0_xso

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
)


TEST_USER = aioxmpp.JID.fromstr("hag66@shakespeare.example/resource")
TEST_CHANNEL = aioxmpp.JID.fromstr("coven@mix.shakespeare.example")
TEST_NODES = [mix_xso.Node.MESSAGES, mix_xso.Node.PARTICIPANTS]


class TestMIXClient(unittest.TestCase):
    def test_is_service(self):
        self.assertTrue(issubclass(
            mix_service.MIXClient,
            aioxmpp.service.Service,
        ))

    def test_is_conversation_service(self):
        self.assertTrue(issubclass(
            mix_service.MIXClient,
            im_conversation.AbstractConversationService,
        ))

    def setUp(self):
        self.cc = make_connected_client()
        self.im_dispatcher = im_dispatcher.IMDispatcher(self.cc)
        self.im_service = unittest.mock.Mock(
            spec=im_service.ConversationService
        )
        self.disco_client = unittest.mock.Mock(
            spec=aioxmpp.DiscoClient,
        )
        self.s = mix_service.MIXClient(self.cc, dependencies={
            im_dispatcher.IMDispatcher: self.im_dispatcher,
            im_service.ConversationService: self.im_service,
            aioxmpp.DiscoClient: self.disco_client,
        })

    def tearDown(self):
        del self.cc
        del self.s

    def test_join(self):
        reply = pam0_xso.ClientJoin0()
        reply.join = core0_xso.Join0()
        reply.join.participant_id = "abcdef"

        self.cc.send.return_value = reply

        result = run_coroutine(self.s.join(TEST_CHANNEL, TEST_NODES))

        self.cc.send.assert_called_once_with(unittest.mock.ANY)

        _, (request, ), _ = self.cc.send.mock_calls[0]

        self.assertIsInstance(
            request,
            aioxmpp.IQ,
        )
        self.assertEqual(
            request.type_,
            aioxmpp.IQType.SET,
        )
        self.assertEqual(
            request.to,
            None,
        )
        self.assertIsInstance(
            request.payload,
            pam0_xso.ClientJoin0,
        )

        cj0 = request.payload
        self.assertEqual(
            cj0.channel,
            TEST_CHANNEL,
        )
        self.assertIsInstance(
            cj0.join,
            core0_xso.Join0,
        )
        self.assertCountEqual(
            cj0.join.subscribe,
            TEST_NODES,
        )

        self.assertIs(result, reply.join)

    def test_create(self):
        reply = core0_xso.Create0("foo")

        self.cc.send.return_value = reply

        run_coroutine(self.s.create(TEST_CHANNEL))

        self.cc.send.assert_called_once_with(unittest.mock.ANY)

        _, (request, ), _ = self.cc.send.mock_calls[0]

        self.assertIsInstance(
            request,
            aioxmpp.IQ,
        )
        self.assertEqual(
            request.type_,
            aioxmpp.IQType.SET,
        )
        self.assertEqual(
            request.to,
            TEST_CHANNEL.replace(localpart=None)
        )
        self.assertIsInstance(
            request.payload,
            core0_xso.Create0,
        )

        c0 = request.payload
        self.assertEqual(
            c0.channel,
            TEST_CHANNEL.localpart,
        )

    def test_leave(self):
        reply = pam0_xso.ClientLeave0(TEST_CHANNEL)

        self.cc.send.return_value = reply

        run_coroutine(self.s.leave(TEST_CHANNEL))

        self.cc.send.assert_called_once_with(unittest.mock.ANY)

        _, (request, ), _ = self.cc.send.mock_calls[0]

        self.assertIsInstance(
            request,
            aioxmpp.IQ,
        )
        self.assertEqual(
            request.type_,
            aioxmpp.IQType.SET,
        )
        self.assertIsNone(request.to)
        self.assertIsInstance(
            request.payload,
            pam0_xso.ClientLeave0
        )

        cl0 = request.payload
        self.assertEqual(cl0.channel, TEST_CHANNEL)
        self.assertIsInstance(cl0.leave, core0_xso.Leave0)
