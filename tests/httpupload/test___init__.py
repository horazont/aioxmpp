import unittest
import unittest.mock

import aioxmpp

import aioxmpp.httpupload as httpupload

from aioxmpp.testutils import (
    make_connected_client,
    run_coroutine,
)


SERVICE_JID = aioxmpp.JID.fromstr("upload.domain.example")


class Testrequest_slot(unittest.TestCase):
    def setUp(self):
        self.client = make_connected_client()
        self.client.send.return_value = unittest.mock.sentinel.slot

    def test_composes_and_sends_iq(self):
        result = run_coroutine(httpupload.request_slot(
            self.client,
            SERVICE_JID,
            "the filename",
            1234,
            "the content type",
        ))

        self.client.send.assert_called_once_with(unittest.mock.ANY)

        _, (st, ), _ = self.client.send.mock_calls[-1]

        self.assertIsInstance(st, aioxmpp.IQ)
        self.assertEqual(st.to, SERVICE_JID)
        self.assertEqual(st.type_, aioxmpp.IQType.GET)
        self.assertIsInstance(st.payload, httpupload.Request)

        self.assertEqual(st.payload.filename, "the filename")
        self.assertEqual(st.payload.size, 1234)
        self.assertEqual(st.payload.content_type, "the content type")

        self.assertEqual(
            result,
            unittest.mock.sentinel.slot
        )
