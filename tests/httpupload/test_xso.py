########################################################################
# File name: test_xso.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import io
import unittest
import unittest.mock

import multidict

import aioxmpp.xso
import aioxmpp.xml

from aioxmpp.utils import namespaces

import aioxmpp.httpupload.xso as httpupload_xso


class TestNamespace(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(namespaces.xep0363_http_upload,
                         "urn:xmpp:http:upload:0")


class TestRequest(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            httpupload_xso.Request,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(httpupload_xso.Request.TAG,
                         (namespaces.xep0363_http_upload, "request"))

    def test_is_iq_payload(self):
        self.assertIn(
            httpupload_xso.Request.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )

    def test_filename(self):
        self.assertIsInstance(
            httpupload_xso.Request.filename,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Request.filename.tag,
            (None, "filename"),
        )
        self.assertIsInstance(
            httpupload_xso.Request.filename.type_,
            aioxmpp.xso.String,
        )
        self.assertIs(httpupload_xso.Request.filename.default,
                      aioxmpp.xso.NO_DEFAULT)

    def test_size(self):
        self.assertIsInstance(
            httpupload_xso.Request.size,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Request.size.tag,
            (None, "size"),
        )
        self.assertIsInstance(
            httpupload_xso.Request.size.type_,
            aioxmpp.xso.Integer,
        )
        self.assertIs(httpupload_xso.Request.filename.default,
                      aioxmpp.xso.NO_DEFAULT)

    def test_content_type(self):
        self.assertIsInstance(
            httpupload_xso.Request.content_type,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Request.content_type.tag,
            (None, "content-type"),
        )
        self.assertIsInstance(
            httpupload_xso.Request.content_type.type_,
            aioxmpp.xso.String,
        )
        self.assertIs(httpupload_xso.Request.filename.default,
                      aioxmpp.xso.NO_DEFAULT)

    def test_init_requires_arguments(self):
        with self.assertRaisesRegex(TypeError, r"argument"):
            httpupload_xso.Request()

    def test_init(self):
        r = httpupload_xso.Request(
            "filename",
            1234,
            "content type",
        )

        self.assertEqual(r.filename, "filename")
        self.assertEqual(r.size, 1234)
        self.assertEqual(r.content_type, "content type")


class TestHeader(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            httpupload_xso.Header,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(httpupload_xso.Header.TAG,
                         (namespaces.xep0363_http_upload, "header"))

    def test_name(self):
        self.assertIsInstance(
            httpupload_xso.Header.name,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Header.name.tag,
            (None, "name"),
        )
        self.assertIsInstance(
            httpupload_xso.Header.name.type_,
            aioxmpp.xso.String,
        )
        self.assertIs(httpupload_xso.Header.name.default,
                      aioxmpp.xso.NO_DEFAULT)

    def test_value(self):
        self.assertIsInstance(
            httpupload_xso.Header.value,
            aioxmpp.xso.Text,
        )
        self.assertIsInstance(
            httpupload_xso.Header.name.type_,
            aioxmpp.xso.String,
        )


class TestHeaderType(unittest.TestCase):
    def test_is_element_type(self):
        self.assertTrue(issubclass(
            httpupload_xso.HeaderType,
            aioxmpp.xso.AbstractElementType,
        ))

    def test_get_xso_types(self):
        self.assertCountEqual(
            httpupload_xso.HeaderType.get_xso_types(),
            [httpupload_xso.Header]
        )

    def test_unpack(self):
        t = httpupload_xso.HeaderType
        el = unittest.mock.Mock(spec=httpupload_xso.Header)
        el.name = unittest.mock.sentinel.name
        el.value = unittest.mock.sentinel.value
        self.assertEqual(
            t.unpack(el),
            (unittest.mock.sentinel.name, unittest.mock.sentinel.value)
        )

    def test_pack(self):
        t = httpupload_xso.HeaderType
        with unittest.mock.patch("aioxmpp.httpupload.xso.Header") as Header:
            result = t.pack((unittest.mock.sentinel.name,
                             unittest.mock.sentinel.value))

        Header.assert_called_once_with()
        self.assertEqual(result, Header())

        self.assertEqual(result.name, unittest.mock.sentinel.name)
        self.assertEqual(result.value, unittest.mock.sentinel.value)


class TestPut(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            httpupload_xso.Put,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(httpupload_xso.Put.TAG,
                         (namespaces.xep0363_http_upload, "put"))

    def test_url(self):
        self.assertIsInstance(
            httpupload_xso.Put.url,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Put.url.tag,
            (None, "url"),
        )
        self.assertIsInstance(
            httpupload_xso.Put.url.type_,
            aioxmpp.xso.String,
        )
        self.assertIs(httpupload_xso.Put.url.default, aioxmpp.xso.NO_DEFAULT)

    def test_headers(self):
        self.assertIsInstance(
            httpupload_xso.Put.headers,
            aioxmpp.xso.ChildValueMultiMap,
        )
        self.assertIs(
            httpupload_xso.Put.headers.type_,
            httpupload_xso.HeaderType
        )
        self.assertIs(
            httpupload_xso.Put.headers.mapping_type,
            multidict.MultiDict,
        )

    def test_parses_multiple_headers_correctly(self):
        data = (
            "<put xmlns='{}' url='foo'>"
            "<header name='Authorization'>v1</header>"
            "<header name='Expires'>v2</header>"
            "<header name='Authorization'>v3</header>"
            "</put>"
        ).format(namespaces.xep0363_http_upload)
        buf = io.BytesIO(data.encode("utf-8"))
        result = aioxmpp.xml.read_single_xso(buf, httpupload_xso.Put)

        self.assertCountEqual(
            result.headers.items(),
            [
                ("Authorization", "v1"),
                ("Expires", "v2"),
                ("Authorization", "v3"),
            ]
        )

    def test_xso_after_load_keeps_valid_headers_intact(self):
        headers = {
            "Authorization": "xyz",
            "Cookie": "xyz",
            "Expires": "xyz",
        }

        p = httpupload_xso.Put()
        p.headers.update(headers)
        p.xso_after_load()

        self.assertCountEqual(
            p.headers.items(),
            headers.items(),
        )

    def test_xso_after_load_strips_newlines(self):
        headers = {
            "Authorization": "abc\ndef",
        }

        p = httpupload_xso.Put()
        p.headers.update(headers)
        p.xso_after_load()

        self.assertCountEqual(
            p.headers.items(),
            {
                "Authorization": "abcdef",
            }.items()
        )

    def test_xso_after_load_removes_non_whitelisted_headers(self):
        headers = {
            "foo": "bar"
        }

        p = httpupload_xso.Put()
        p.headers.update(headers)
        p.xso_after_load()

        self.assertCountEqual(
            p.headers.items(),
            {}.items()
        )


class TestGet(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            httpupload_xso.Get,
            aioxmpp.xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(httpupload_xso.Get.TAG,
                         (namespaces.xep0363_http_upload, "get"))

    def test_url(self):
        self.assertIsInstance(
            httpupload_xso.Get.url,
            aioxmpp.xso.Attr,
        )
        self.assertEqual(
            httpupload_xso.Get.url.tag,
            (None, "url"),
        )
        self.assertIsInstance(
            httpupload_xso.Get.url.type_,
            aioxmpp.xso.String,
        )
        self.assertIs(httpupload_xso.Get.url.default, aioxmpp.xso.NO_DEFAULT)


class TestSlot(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            httpupload_xso.Slot,
            aioxmpp.xso.XSO,
        ))

    def test_is_iq_payload(self):
        self.assertIn(
            httpupload_xso.Slot.TAG,
            aioxmpp.IQ.CHILD_MAP,
        )

    def test_tag(self):
        self.assertEqual(httpupload_xso.Slot.TAG,
                         (namespaces.xep0363_http_upload, "slot"))

    def test_put(self):
        self.assertIsInstance(
            httpupload_xso.Slot.put,
            aioxmpp.xso.Child,
        )
        self.assertCountEqual(
            httpupload_xso.Slot.put._classes,
            [httpupload_xso.Put]
        )

    def test_get(self):
        self.assertIsInstance(
            httpupload_xso.Slot.get,
            aioxmpp.xso.Child,
        )
        self.assertCountEqual(
            httpupload_xso.Slot.get._classes,
            [httpupload_xso.Get]
        )

    def test_validate_rejects_missing_put(self):
        s = httpupload_xso.Slot()
        s.get = unittest.mock.Mock(spec=httpupload_xso.Get)

        with self.assertRaisesRegex(ValueError, r"missing PUT information"):
            s.validate()

    def test_validate_rejects_missing_get(self):
        s = httpupload_xso.Slot()
        s.put = unittest.mock.Mock(spec=httpupload_xso.Put)

        with self.assertRaisesRegex(ValueError, r"missing GET information"):
            s.validate()

    def test_validate_passes_if_both_are_present(self):
        s = httpupload_xso.Slot()
        s.get = unittest.mock.Mock(spec=httpupload_xso.Get)
        s.put = unittest.mock.Mock(spec=httpupload_xso.Put)
