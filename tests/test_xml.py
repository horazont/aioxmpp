from asyncio_xmpp.xml import XMLStreamReceiverContext, XMLStreamSenderContext
from asyncio_xmpp.utils import etree
import asyncio_xmpp.errors as errors
import asyncio_xmpp.stanza as stanza

from .testutils import XMLTestCase


class TestXMLStreamReceiverContext(XMLTestCase):
    PEER_STREAM_HEADER_TEMPLATE = '''\
<stream:stream xmlns:stream="http://etherx.jabber.org/streams" \
xmlns="jabber:client" \
from="bar.example" \
to="foo@bar.example" \
id="abc" \
version="{major}.{minor}">'''

    def _make_peer_header(self, version=(1, 0)):
        return self.PEER_STREAM_HEADER_TEMPLATE.format(
            minor=version[1],
            major=version[0]).encode("utf-8")

    def _start(self):
        self.ctx.feed(self._make_peer_header())
        self.assertTrue(self.ctx.start())

    def setUp(self):
        self.ctx = XMLStreamReceiverContext()

    def test_valid_stream_header(self):
        self.assertFalse(self.ctx.start())
        self.ctx.feed(self._make_peer_header())
        self.assertTrue(self.ctx.start())
        self.assertEqual(
            "abc",
            self.ctx.stream_id)
        self.assertIsNotNone(self.ctx.root)
        self.assertTrue(self.ctx.ready)

    def test_partial_feed(self):
        self.assertFalse(self.ctx.start())

        blob = self._make_peer_header()
        fed = b""
        n = 16

        while blob:
            part = blob[:n]
            blob = blob[n:]
            fed += part
            self.ctx.feed(part)
            self.assertEqual(
                not bool(blob),
                self.ctx.start(),
                "unexpected result after feeding "+repr(fed)
            )

        self.assertEqual("abc", self.ctx.stream_id)

    def test_shutdown(self):
        self.assertFalse(self.ctx.ready)
        self.ctx.feed(self._make_peer_header())
        self.assertTrue(self.ctx.start())
        self.assertTrue(self.ctx.ready)
        self.ctx.feed(b"</stream:stream>")
        self.assertSequenceEqual(
            [None],
            list(self.ctx.read_stream_level_nodes())
        )
        self.assertFalse(self.ctx.ready)
        self.assertIsNone(self.ctx.root)

    def test_node(self):
        buf = (b'<iq xmlns="jabber:client" type="set">'
               b'<query xmlns="http://example.invalid/" />'
               b'</iq>')

        el = etree.fromstring(buf)

        self.ctx.feed(self._make_peer_header())
        self.assertTrue(self.ctx.start())
        self.ctx.feed(buf)
        node, = list(self.ctx.read_stream_level_nodes())
        self.assertSubtreeEqual(el, node)

    def test_duplicate_stream_header(self):
        self.ctx.feed(self._make_peer_header())
        self.assertTrue(self.ctx.start())

        self.ctx.feed(self._make_peer_header())
        with self.assertRaises(errors.SendStreamError) as cm:
            list(self.ctx.read_stream_level_nodes())

        self.assertEqual(
            "unsupported-stanza-type",
            cm.exception.error_tag)

    def test_unsupported_version(self):
        self.ctx.feed(self._make_peer_header(version=(2, 0)))
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.start()
        self.assertEqual(
            "unsupported-version",
            cm.exception.error_tag)
        self.assertIn(
            "unsupported version",
            cm.exception.text)

    def test_malformed_version(self):
        self.ctx.feed(self._make_peer_header(version=("abc", 0)))
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.start()
        self.assertEqual(
            "unsupported-version",
            cm.exception.error_tag)
        self.assertIn(
            "malformed version",
            cm.exception.text)

    def test_missing_version(self):
        buf = b'''<stream:stream xmlns:stream="http://etherx.jabber.org/streams" \
xmlns="jabber:client" \
from="bar.example" \
to="foo@bar.example" \
id="abc">'''
        self.ctx.feed(buf)
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.start()
        self.assertEqual(
            "unsupported-version",
            cm.exception.error_tag)
        self.assertIn(
            "missing version tag",
            cm.exception.text)

    def test_reject_comments(self):
        self._start()
        self.ctx.feed(b"<foo><!-- foo --></foo>")
        with self.assertRaises(errors.SendStreamError) as cm:
            list(self.ctx.read_stream_level_nodes())
        self.assertEqual(
            cm.exception.error_tag,
            "restricted-xml")

    def test_reject_processing_instruction(self):
        self._start()
        self.ctx.feed(b"<?foo ?>")
        with self.assertRaises(errors.SendStreamError) as cm:
            list(self.ctx.read_stream_level_nodes())
        self.assertEqual(
            cm.exception.error_tag,
            "restricted-xml")

    def test_reject_entities(self):
        self._start()
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.feed(b"<foo>&foo;</foo>")
        self.assertEqual(
            cm.exception.error_tag,
            "restricted-xml")

    def test_reject_external_dtd(self):
        self.ctx.feed(b'<?xml version="1.0"?>\n')
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.feed(b'<!DOCTYPE foo SYSTEM "bar.dtd">\n')
            self._start()
        self.assertEqual(
            cm.exception.error_tag,
            "restricted-xml")

    def test_reject_internal_dtd(self):
        self.ctx.feed(b'<?xml version="1.0"?>\n')
        with self.assertRaises(errors.SendStreamError) as cm:
            self.ctx.feed(b'<!DOCTYPE foo [\n<!ELEMENT foo (#PCDATA)>\n]>')
            self._start()
        self.assertEqual(
            cm.exception.error_tag,
            "restricted-xml")

    def tearDown(self):
        del self.ctx


class TestXMLStreamSenderContext(XMLTestCase):
    def setUp(self):
        self.ctx = XMLStreamSenderContext("jabber:client")

    def test_make_iq(self):
        iq = self.ctx.make_iq(
            to="to",
            from_="from",
            type_="set",
            id_="id")
        self.assertIsInstance(
            iq,
            stanza.IQ)
        self.assertEqual(
            "{jabber:client}iq",
            iq.tag)
        self.assertEqual(
            "to",
            iq.get("to"))
        self.assertEqual(
            "from",
            iq.get("from"))
        self.assertEqual(
            "set",
            iq.get("type"))
        self.assertEqual(
            "id",
            iq.get("id"))
        self.assertEqual(
            b'<iq xmlns="jabber:client" to="to" from="from" type="set" id="id"/>',
            etree.tostring(iq))

    def test_make_presence(self):
        presence = self.ctx.make_presence(
            to="to",
            from_="from",
            type_="unavailable",
            id_="id")
        self.assertIsInstance(
            presence,
            stanza.Presence)
        self.assertEqual(
            "{jabber:client}presence",
            presence.tag)
        self.assertEqual(
            "to",
            presence.get("to"))
        self.assertEqual(
            "from",
            presence.get("from"))
        self.assertEqual(
            "unavailable",
            presence.get("type"))
        self.assertEqual(
            "id",
            presence.get("id"))
        self.assertEqual(
            b'<presence xmlns="jabber:client" to="to" from="from" '
            b'type="unavailable" id="id"/>',
            etree.tostring(presence))

    def test_make_message(self):
        message = self.ctx.make_message(
            to="to",
            from_="from",
            type_="chat",
            id_="id")
        self.assertIsInstance(
            message,
            stanza.Message)
        self.assertEqual(
            "{jabber:client}message",
            message.tag)
        self.assertEqual(
            "to",
            message.get("to"))
        self.assertEqual(
            "from",
            message.get("from"))
        self.assertEqual(
            "chat",
            message.get("type"))
        self.assertEqual(
            "id",
            message.get("id"))
        self.assertEqual(
            b'<message xmlns="jabber:client" to="to" from="from" '
            b'type="chat" id="id"/>',
            etree.tostring(message))

    def test_makeelement(self):
        el = self.ctx.makeelement("foo")
        self.assertDictEqual(
            {None: "jabber:client"},
            el.nsmap)

    def test_default_ns_builder(self):
        E = self.ctx.default_ns_builder("foo")
        self.assertDictEqual(
            {None: "foo"},
            E("foo").nsmap)

    def test_custom_builder(self):
        E = self.ctx.custom_builder()
        self.assertDictEqual(
            {},
            E("foo").nsmap)

    def tearDown(self):
        del self.ctx
