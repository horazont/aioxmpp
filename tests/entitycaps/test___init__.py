import unittest

import aioxmpp.entitycaps
import aioxmpp.entitycaps.service
import aioxmpp.entitycaps.xso


class TestExports(unittest.TestCase):
    def test_exports(self):
        self.assertIs(aioxmpp.entitycaps.Service,
                      aioxmpp.entitycaps.service.Service)
        self.assertIs(aioxmpp.entitycaps.Cache,
                      aioxmpp.entitycaps.service.Cache)
