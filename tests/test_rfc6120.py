import unittest

import aioxmpp.rfc6120 as rfc6120
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.nonza as nonza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestBindFeature(unittest.TestCase):
    def test_registered_at_StreamFeatures(self):
        self.assertIn(
            rfc6120.BindFeature.TAG,
            nonza.StreamFeatures.CHILD_MAP
        )


class TestBind(unittest.TestCase):
    def test_declare_ns(self):
        self.assertDictEqual(
            rfc6120.Bind.DECLARE_NS,
            {
                None: namespaces.rfc6120_bind,
            }
        )

    def test_tag(self):
        self.assertEqual(
            rfc6120.Bind.TAG,
            (namespaces.rfc6120_bind, "bind")
        )

    def test_jid(self):
        self.assertIsInstance(
            rfc6120.Bind.jid,
            xso.ChildText
        )
        self.assertEqual(
            rfc6120.Bind.jid.tag,
            (namespaces.rfc6120_bind, "jid")
        )
        self.assertIsInstance(
            rfc6120.Bind.jid.type_,
            xso.JID
        )
        self.assertIs(
            rfc6120.Bind.jid.default,
            None
        )

    def test_resource(self):
        self.assertIsInstance(
            rfc6120.Bind.resource,
            xso.ChildText
        )
        self.assertEqual(
            rfc6120.Bind.resource.tag,
            (namespaces.rfc6120_bind, "resource")
        )
        self.assertIs(
            rfc6120.Bind.resource.default,
            None
        )

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
