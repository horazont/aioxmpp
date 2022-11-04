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
import unittest.mock

import aioxmpp
import aioxmpp.service

import aioxmpp.rpc.service as rpc_service
import aioxmpp.rpc.xso as rpc_xso
import aioxmpp.disco

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_FROM_JID = aioxmpp.JID.fromstr("foo@bar.baz/fnord")
TEST_TO_JID = aioxmpp.JID.fromstr("bar@bar.baz/fnord")

class TestRPCServer(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM_JID
        self.disco_service = unittest.mock.Mock()

        self.s = rpc_service.RPCServer(
            self.cc,
            dependencies={
                aioxmpp.disco.DiscoServer: self.disco_service,
            }
        )
        self.disco_service.reset_mock()

    def tearDown(self):
        del self.s, self.disco_service, self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            rpc_service.RPCServer,
            aioxmpp.service.Service,
        ))

    def test_is_disco_node(self):
        self.assertTrue(issubclass(
                rpc_service.RPCServer,
                aioxmpp.disco.Node,
            )
        )

    def test_register_as_node(self):
        self.assertIsInstance(
            rpc_service.RPCServer.disco_node,
            aioxmpp.disco.mount_as_node
        )
    
    def test_registers_iq_handler(self):
        self.assertTrue(
            aioxmpp.service.is_iq_handler(
                aioxmpp.IQType.SET,
                rpc_xso.Query,
                rpc_service.RPCServer._handle_method_call
            )
        )

    def test_registers_as_node(self):
        self.assertIsInstance(
            rpc_service.RPCServer.disco_node,
            aioxmpp.disco.mount_as_node
        )

        self.assertEqual(
            rpc_service.RPCServer.disco_node.mountpoint,
            "http://jabber.org/protocol/rpc"
        )

    def test_methods_empty_by_default(self):
        stanza = unittest.mock.Mock()
        
        self.assertSequenceEqual(
            list(self.s.iter_items(stanza)),
            []
        )

    def test_identity(self):
        self.assertEqual(
            {
                ("automation", "rpc", None, None)
            },
            set(self.s.iter_identities(unittest.mock.sentinel.stanza))
        )

    def test__handle_method_raises_tem_not_found_for_unknown_method(self):
        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_FROM_JID,
            to=TEST_TO_JID,
            payload=rpc_xso.Query(
                rpc_xso.MethodCall(
                    rpc_xso.MethodName(
                        "method"
                    )
                )
            )
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError) as ctx:
            run_coroutine(self.s._handle_method_call(req))

        self.assertEqual(
            ctx.exception.condition,
            aioxmpp.ErrorCondition.ITEM_NOT_FOUND,
        )

        self.assertRegex(
            ctx.exception.text,
            "no such method: 'method'"
        )

    def test__handle_method_raises_forbidden_for_disallowed_peer(self):
        handler = unittest.mock.Mock()
        handler.return_value = unittest.mock.sentinel.result
        is_allowed = unittest.mock.Mock()
        is_allowed.return_value = False

        self.s.register_method(
            handler=handler,
            method_name="method name",
            is_allowed=is_allowed
        )

        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_FROM_JID,
            to=TEST_TO_JID,
            payload=rpc_xso.Query(
                rpc_xso.MethodCall(
                    rpc_xso.MethodName(
                        "method name"
                    )
                )
            )
        )

        with self.assertRaises(aioxmpp.errors.XMPPCancelError) as ctx:
            run_coroutine(self.s._handle_method_call(req))

        is_allowed.assert_called_once_with(req.from_)

        self.assertEqual(
            ctx.exception.condition,
            aioxmpp.ErrorCondition.FORBIDDEN
        )

        handler.assert_not_called()

    def test__handle_method_dispatches_to_method_response(self):
        handler = unittest.mock.Mock()
        handler.return_value = unittest.mock.sentinel.result
        is_allowed = unittest.mock.Mock()
        is_allowed.return_value = True

        self.s.register_method(
            handler=handler,
            method_name="method name",
            is_allowed=is_allowed
        )

        req = aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            from_=TEST_FROM_JID,
            to=TEST_TO_JID,
            payload=rpc_xso.Query(
                rpc_xso.MethodCall(
                    rpc_xso.MethodName(
                        "method name"
                    )
                )
            )
        )

        result = run_coroutine(self.s._handle_method_call(req))

        handler.assert_called_once()

        self.assertEqual(
            result, 
            unittest.mock.sentinel.result
        )
        
class TestRPCClient(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.disco_service = unittest.mock.Mock()
        self.disco_service.query_info = CoroutineMock()
        self.disco_service.query_info.side_effect = AssertionError()
        self.disco_service.query_items = CoroutineMock()
        self.disco_service.query_items.side_effect = AssertionError()

        self.c = rpc_service.RPCClient(
            self.cc,
            dependencies={
                aioxmpp.disco.DiscoClient: self.disco_service,
            }
        )

    def tearDown(self):
        del self.c, self.cc

    def test_is_service(self):
        self.assertTrue(issubclass(
            rpc_service.RPCClient,
            aioxmpp.service.Service,
        ))

    def test_depends_on_disco(self):
        self.assertIn(
            aioxmpp.disco.DiscoClient,
            rpc_service.RPCClient.ORDER_AFTER,
        )

    def test_detect_support_using_disco(self):
        response = aioxmpp.disco.xso.InfoQuery(
            features={
                "http://jabber.org/protocol/rpc"
            }
        )
        self.disco_service.query_info.side_effect = None
        self.disco_service.query_info.return_value = response

        self.assertTrue(
            run_coroutine(self.c.supports_rpc(TEST_TO_JID)),
        )

        self.disco_service.query_info.assert_called_with(
            TEST_TO_JID,
        )

    def test_detect_absence_of_support_using_disco(self):
        response = aioxmpp.disco.xso.InfoQuery(
            features=set()
        )
        self.disco_service.query_info.side_effect = None
        self.disco_service.query_info.return_value = response

        self.assertFalse(
            run_coroutine(self.c.supports_rpc(TEST_TO_JID)),
        )

        self.disco_service.query_info.assert_called_with(
            TEST_TO_JID,
        )

    def test_method_call(self):
        run_coroutine(self.c.call_method(
            TEST_TO_JID,
            rpc_xso.Query(
                rpc_xso.MethodCall(
                    rpc_xso.MethodName("foo"),
                    rpc_xso.Params([
                        rpc_xso.Param(rpc_xso.Value(rpc_xso.string("bar"))),
                        rpc_xso.Param(rpc_xso.Value(rpc_xso.string("foobar")))
                    ])
                )
            )
        ))
        
        self.assertEqual(
            1,
            len(self.cc.send.mock_calls)
        )

        _, (request_iq, ), _ = self.cc.send.mock_calls[0]

        self.assertIsInstance(request_iq, aioxmpp.stanza.IQ)
        self.assertEqual(request_iq.type_, aioxmpp.structs.IQType.SET)
        self.assertEqual(request_iq.to, TEST_TO_JID)
        self.assertIsInstance(request_iq.payload, rpc_xso.Query)

        request = request_iq.payload
        self.assertIsInstance(request.payload, rpc_xso.MethodCall)
        self.assertIsInstance(request.payload.methodName, rpc_xso.MethodName)
        self.assertIsInstance(request.payload.params, rpc_xso.Params)

        self.assertEqual(request.payload.methodName.name, "foo")

        params = request.payload.params
        self.assertEqual(len(params.params), 2)
        self.assertIsInstance(params.params[0], rpc_xso.Param)
        self.assertIsInstance(params.params[1], rpc_xso.Param)

        self.assertIsInstance(params.params[0].value, rpc_xso.Value)
        self.assertIsInstance(params.params[1].value, rpc_xso.Value)

        param_value = params.params[0].value
        self.assertIsInstance(param_value.value, rpc_xso.string)
        self.assertEqual(param_value.value.value, "bar")

        param_value = params.params[1].value
        self.assertIsInstance(param_value.value, rpc_xso.string)
        self.assertEqual(param_value.value.value, "foobar")
