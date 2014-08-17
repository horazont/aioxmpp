import asyncio
import unittest

import asyncio_xmpp.node_hooks as node_hooks

class TestNodeHooks(unittest.TestCase):
    def setUp(self):
        self._loop = asyncio.get_event_loop()
        self._hooks = node_hooks.NodeHooks(loop=self._loop)

    def test_hook_via_future(self):
        f = asyncio.Future()
        self._hooks.add_future("foo", f)
        self.assertIn("foo", self._hooks)
        self._hooks.unicast("foo", "bar")
        self.assertEqual(
            f.result(),
            "bar")
        self.assertNotIn("foo", self._hooks)
        with self.assertRaises(KeyError):
            self._hooks.unicast("foo", "baz")

    def test_hook_via_queue(self):
        q = asyncio.Queue()
        self._hooks.add_queue("foo", q)
        self.assertIn("foo", self._hooks)
        with self.assertRaises(asyncio.QueueEmpty):
            q.get_nowait()
        self._hooks.unicast("foo", "bar")
        self.assertEqual(
            q.get_nowait(),
            "bar")
        self._hooks.unicast("foo", "baz")
        self.assertEqual(
            q.get_nowait(),
            "baz")
        self.assertIn("foo", self._hooks)

    def test_hook_both(self):
        f = asyncio.Future()
        q = asyncio.Queue()
        self._hooks.add_queue("foo", q)
        self.assertIn("foo", self._hooks)
        with self.assertRaises(asyncio.QueueEmpty):
            q.get_nowait()
        self._hooks.unicast("foo", "bar")
        self.assertEqual(
            q.get_nowait(),
            "bar")
        self._hooks.add_future("foo", f)
        self._hooks.unicast("foo", "baz")
        self.assertEqual(
            q.get_nowait(),
            "baz")
        self.assertEqual(
            f.result(),
            "baz")

    def test_broadcast_error(self):
        f = asyncio.Future()
        q = asyncio.Queue()
        self._hooks.add_queue("foo", q)
        self._hooks.add_future("foo", f)

        self._hooks.broadcast_error(ValueError())

        self.assertIsInstance(f.exception(), ValueError)

        self.assertIn("foo", self._hooks)
        self._hooks.unicast("foo", "bar")
        self.assertEqual(
            q.get_nowait(),
            "bar")

    def test_close(self):
        f = asyncio.Future()
        q = asyncio.Queue()
        self._hooks.add_queue("foo", q)
        self._hooks.add_future("foo", f)

        self._hooks.close("foo", ValueError())

        self.assertIsInstance(f.exception(), ValueError)

        self.assertNotIn("foo", self._hooks)
        with self.assertRaises(KeyError):
            self._hooks.unicast("foo", "bar")

    def test_close_all(self):
        f = asyncio.Future()
        q = asyncio.Queue()
        self._hooks.add_queue("foo", q)
        self._hooks.add_future("bar", f)

        self._hooks.close_all(ValueError())

        self.assertIsInstance(f.exception(), ValueError)

        self.assertNotIn("foo", self._hooks)
        self.assertNotIn("bar", self._hooks)
        with self.assertRaises(KeyError):
            self._hooks.unicast("foo", "bar")
        with self.assertRaises(KeyError):
            self._hooks.unicast("bar", "bar")

    def test_add_remove_queue(self):
        q = asyncio.Queue()
        self.assertNotIn("foo", self._hooks)
        self._hooks.add_queue("foo", q)
        self.assertIn("foo", self._hooks)
        self._hooks.remove_queue("foo", q)
        self.assertNotIn("foo", self._hooks)
        with self.assertRaises(KeyError):
            self._hooks.remove_queue("foo", q)

    def test_add_remove_future(self):
        f = asyncio.Future()
        self.assertNotIn("foo", self._hooks)
        self._hooks.add_future("foo", f)
        self.assertIn("foo", self._hooks)
        self._hooks.remove_future("foo", f)
        self.assertNotIn("foo", self._hooks)
        with self.assertRaises(KeyError):
            self._hooks.remove_future("foo", f)

    def tearDown(self):
        del self._loop
        del self._hooks
