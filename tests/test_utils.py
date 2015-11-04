import unittest

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_aioxmpp(self):
        self.assertEqual(
            namespaces.aioxmpp_internal,
            "https://zombofant.net/xmlns/aioxmpp#internal"
        )
