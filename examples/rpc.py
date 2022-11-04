########################################################################
# File name: rpc.py
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
from tracemalloc import start
import aioxmpp
import aioxmpp.rpc
import aioxmpp.xml

import aioxmpp.rpc.xso as rpc_xso

from framework import Example, exec_example

import time

class RPCExample(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    def _handler(self, stanza):
        param1 = stanza.payload.payload.params.params[0].value.value.value;
        param2 = stanza.payload.payload.params.params[1].value.value.value

        start_time = time.time()
        sum_result = param1 + param2
        end_time = time.time()
        
        return rpc_xso.Query(
            rpc_xso.MethodResponse(
                rpc_xso.Params([
                    rpc_xso.Param(rpc_xso.Value(rpc_xso.double(sum_result))),
                    rpc_xso.Param(rpc_xso.Value(rpc_xso.double(end_time - start_time)))
                ])
            )
        )

    async def run_simple_example(self):
        rpc_server = self.client.summon(aioxmpp.RPCServer)
        rpc_server.register_method(self._handler, 'sum')  
        
        rpc_client = self.client.summon(aioxmpp.RPCClient)

        supports_rpc = await rpc_client.supports_rpc(self.client.local_jid)
        print('Peer supports RPC: {}'.format(supports_rpc))

        if supports_rpc:
            response = await rpc_client.call_method(
                self.client.local_jid,
                rpc_xso.Query(
                    rpc_xso.MethodCall(
                        rpc_xso.MethodName("sum"),
                        rpc_xso.Params([
                            rpc_xso.Param(rpc_xso.Value(rpc_xso.string("foo"))),
                            rpc_xso.Param(rpc_xso.Value(rpc_xso.string("bar")))
                        ])
                    )
                )
            )
            time = response.payload.params.params[1].value.value.value
            result = response.payload.params.params[0].value.value.value
            print("{} executed method {} in {} s, giving as result: '{}'".format(self.client.local_jid, "sum", time, result))

if __name__ == "__main__":
    exec_example(RPCExample())
