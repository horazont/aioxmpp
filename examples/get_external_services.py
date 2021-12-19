########################################################################
# File name: get_external_services.py
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
import itertools

import aioxmpp.extservice
import aioxmpp.forms

from framework import Example, exec_example


class ExternalServices(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "target_entity",
            default=None,
            nargs="?",
            type=jid,
            help="Entity to query (leave empty to query account)"
        )

    async def run_simple_example(self):
        services = await aioxmpp.extservice.get_external_services(
            self.client,
            self.args.target_entity,
        )

        for svc in services.services:
            print("Service:")
            print(f"  type={svc.type_!r}")
            print(f"  transport={svc.transport!r}")
            print(f"  host={svc.host!r}")
            print(f"  port={svc.port!r}")
            print(f"  username={svc.username!r}")
            print(f"  password={svc.password!r}")


if __name__ == "__main__":
    exec_example(ExternalServices())
