import unittest

import asyncio_xmpp.presence as presence

class TestPresenceState(unittest.TestCase):
    def test_immutable(self):
        p = presence.PresenceState()
        with self.assertRaises(AttributeError):
            p.available = True
        with self.assertRaises(AttributeError):
            p.show = "chat"
        # cannot fulfill that due to subclass ... FIXME?
        # with self.assertRaises(AttributeError):
        #     p.anything = 1

    def test_default_is_unavailable(self):
        p = presence.PresenceState()
        self.assertFalse(p.available)
        self.assertIsNone(p.show)
        self.assertFalse(p)

    def test_restrict_show(self):
        with self.assertRaises(ValueError):
            presence.PresenceState(available=True, show="foo")
        with self.assertRaises(ValueError):
            presence.PresenceState(available=False, show="chat")

    def test_init(self):
        p = presence.PresenceState(True, "chat")
        self.assertTrue(p)
        self.assertTrue(p.available)
        self.assertEqual(p.show, "chat")

    def test_order(self):
        l = [presence.PresenceState(*args)
             for args in [
                     (False, None),
                     (True, "dnd"),
                     (True, "xa"),
                     (True, "away"),
                     (True, None),
                     (True, "chat")
             ]
        ]

        for v1, v2 in zip(l[:-1], l[1:]):
            self.assertLess(v1, v2)
