import unittest

import aioxmpp.roster as roster
import aioxmpp.roster.xso as roster_xso
import aioxmpp.roster.service as roster_service


class TestExports(unittest.TestCase):
    def test_Service(self):
        self.assertIs(roster.Service, roster_service.Service)

    def test_xso(self):
        self.assertIs(roster.xso, roster_xso)

    def test_Item(self):
        self.assertIs(roster.Item, roster_service.Item)
