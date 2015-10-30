import unittest

import aioxmpp.presence as presence
import aioxmpp.presence.service as presence_service


class TestExports(unittest.TestCase):
    def test_Service(self):
        self.assertIs(presence.Service, presence_service.Service)
