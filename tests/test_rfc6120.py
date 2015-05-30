import unittest

import aioxmpp.rfc6120 as rfc6120
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.stream_xsos as stream_xsos


class TestBindFeature(unittest.TestCase):
    def test_registered_at_StreamFeatures(self):
        self.assertIn(
            rfc6120.BindFeature.TAG,
            stream_xsos.StreamFeatures.CHILD_MAP
        )



class TestBind(unittest.TestCase):
    def test_default_init(self):
        obj = rfc6120.Bind()
        self.assertIsNone(obj.jid)
        self.assertIsNone(obj.resource)

    def test_init(self):
        jid = structs.JID.fromstr("foo@bar.example")
        obj = rfc6120.Bind(
            jid=jid,
            resource="foobar"
        )
        self.assertEqual(
            jid,
            obj.jid)
        self.assertEqual(
            "foobar",
            obj.resource)

    def test_registered_at_IQ(self):
        self.assertIn(
            rfc6120.Bind.TAG,
            stanza.IQ.CHILD_MAP
        )
