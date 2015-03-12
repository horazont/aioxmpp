import unittest

import asyncio_xmpp.stream_elements as stream_elements
import asyncio_xmpp.errors as errors

from asyncio_xmpp.utils import namespaces


class TestStreamError(unittest.TestCase):
    def test_from_exception(self):
        obj = stream_elements.StreamError.from_exception(errors.StreamError(
            (namespaces.streams, "undefined-condition"),
            text="foobar"))
        self.assertEqual(
            (namespaces.streams, "undefined-condition"),
            obj.condition
        )
        self.assertEqual(
            "foobar",
            obj.text
        )

    def test_to_exception(self):
        obj = stream_elements.StreamError()
        obj.condition = (namespaces.streams, "restricted-xml")
        obj.text = "foobar"

        exc = obj.to_exception()
        self.assertIsInstance(
            exc,
            errors.StreamError)
        self.assertEqual(
            (namespaces.streams, "restricted-xml"),
            exc.condition
        )
        self.assertEqual(
            "foobar",
            exc.text
        )
