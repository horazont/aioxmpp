########################################################################
# File name: test___init__.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import unittest

import aioxmpp.disco as disco
import aioxmpp.disco.service as disco_service
import aioxmpp.disco.xso as disco_xso


class TestExports(unittest.TestCase):
    def test_Service(self):
        self.assertIs(disco.Service, disco_service.Service)

    def test_xso(self):
        self.assertIs(disco.xso, disco_xso)

    def test_Node(self):
        self.assertIs(disco.Node, disco_service.Node)

    def test_StaticNode(self):
        self.assertIs(disco.StaticNode, disco_service.StaticNode)
