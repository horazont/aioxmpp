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

import aioxmpp.entitycaps
import aioxmpp.entitycaps.service
import aioxmpp.entitycaps.xso


class TestExports(unittest.TestCase):
    def test_exports(self):
        self.assertIs(aioxmpp.entitycaps.EntityCapsService,
                      aioxmpp.entitycaps.service.EntityCapsService)
        self.assertIs(aioxmpp.entitycaps.Cache,
                      aioxmpp.entitycaps.service.Cache)
        self.assertIs(aioxmpp.entitycaps.Service,
                      aioxmpp.entitycaps.service.EntityCapsService)
        self.assertIs(aioxmpp.EntityCapsService,
                      aioxmpp.entitycaps.service.EntityCapsService)
