import unittest

import aioxmpp.roster.service as roster_service
import aioxmpp.roster.xso as roster_xso
import aioxmpp.service as service

from ..testutils import make_connected_client, run_coroutine


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.s = roster_service.Service(self.cc)

    def test_is_Service(self):
        self.assertIsInstance(
            self.s,
            service.Service
        )

    def test_request_initial_roster_before_stream_established(self):
        response = roster_xso.Query()

        self.cc.stream.send_iq_and_wait_for_reply.return_value = response

        run_coroutine(self.cc.before_stream_established())

        self.assertSequenceEqual(
            [
                unittest.mock.call(
                    unittest.mock.ANY,
                    timeout=self.cc.negotiation_timeout.total_seconds()
                ),
            ],
            self.cc.stream.send_iq_and_wait_for_reply.mock_calls
        )
