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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import unittest

import aioxmpp
import aioxmpp.roster as roster
import aioxmpp.roster.xso as roster_xso
import aioxmpp.roster.service as roster_service


class TestExports(unittest.TestCase):
    def test_Service(self):
        self.assertIs(roster.Service, roster_service.RosterClient)

    def test_RosterClient(self):
        self.assertIs(roster.RosterClient, roster_service.RosterClient)
        self.assertIs(aioxmpp.RosterClient, roster_service.RosterClient)

    def test_xso(self):
        self.assertIs(roster.xso, roster_xso)

    def test_Item(self):
        self.assertIs(roster.Item, roster_service.Item)
