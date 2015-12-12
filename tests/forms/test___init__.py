import unittest

import aioxmpp.forms as forms
import aioxmpp.forms.xso as forms_xso


class TestExports(unittest.TestCase):
    def test_Data(self):
        self.assertIs(
            forms.Data,
            forms_xso.Data
        )
