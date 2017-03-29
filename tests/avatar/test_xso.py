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
import contextlib
import unittest
import unittest.mock

import aioxmpp.xso as xso
import aioxmpp.avatar.xso as avatar_xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_data_namespace(self):
        self.assertEqual(
            "urn:xmpp:avatar:data",
            namespaces.xep0084_data
        )

    def test_metadata_namespace(self):
        self.assertEqual(
            "urn:xmpp:avatar:metadata",
            namespaces.xep0084_metadata
        )


class TestData(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(avatar_xso.Data, xso.XSO))

    def test_init(self):
        data = avatar_xso.Data(b"foo")
        self.assertEqual(
            data.data,
            b"foo"
        )

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0084_data, "data"),
            avatar_xso.Data.TAG
        )

    def test_data(self):
        self.assertIsInstance(
            avatar_xso.Data.data,
            xso.Text
        )

        self.assertIsInstance(
            avatar_xso.Data.data.type_,
            xso.Base64Binary
        )


class TestMetadata(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(avatar_xso.Metadata, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0084_metadata, "metadata"),
            avatar_xso.Metadata.TAG
        )

    def test_info(self):
        self.assertIsInstance(
            avatar_xso.Metadata.info,
            xso.ChildMap
        )

    def test_pointer(self):
        self.assertIsInstance(
            avatar_xso.Metadata.pointer,
            xso.ChildList
        )

    def test_iter_info_nodes(self):
        info_list = [
            avatar_xso.Info(id_="123",
                            mime_type="image/png",
                            nbytes=3),
            avatar_xso.Info(id_="123",
                            mime_type="image/png",
                            nbytes=3,
                            width=10),
            avatar_xso.Info(id_="345",
                            nbytes=4,
                            mime_type="image/gif",
                            url="http://example.com/avatar.gif"),
        ]

        metadata = avatar_xso.Metadata()
        for item in info_list:
            metadata.info[item.mime_type].append(item)

        self.assertCountEqual(
            list(metadata.iter_info_nodes()),
            info_list
        )


class TestInfo(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(avatar_xso.Info, xso.XSO))

    def test_init(self):
        info = avatar_xso.Info(id_="123",
                               mime_type="image/png",
                               nbytes=3)
        self.assertEqual(info.id_, "123")
        self.assertEqual(info.mime_type, "image/png")
        self.assertEqual(info.nbytes, 3)
        self.assertEqual(info.width, None)
        self.assertEqual(info.height, None)
        self.assertEqual(info.url, None)

        info = avatar_xso.Info(id_="123",
                               mime_type="image/png",
                               nbytes=3,
                               width=10)
        self.assertEqual(info.id_, "123")
        self.assertEqual(info.mime_type, "image/png")
        self.assertEqual(info.nbytes, 3)
        self.assertEqual(info.width, 10)
        self.assertEqual(info.height, None)
        self.assertEqual(info.url, None)

        info = avatar_xso.Info(id_="123",
                               mime_type="image/png",
                               nbytes=3,
                               height=10)
        self.assertEqual(info.id_, "123")
        self.assertEqual(info.mime_type, "image/png")
        self.assertEqual(info.nbytes, 3)
        self.assertEqual(info.width, None)
        self.assertEqual(info.height, 10)
        self.assertEqual(info.url, None)

        info = avatar_xso.Info(id_="123",
                               mime_type="image/png",
                               nbytes=3,
                               url="http://example.com/avatar")
        self.assertEqual(info.id_, "123")
        self.assertEqual(info.mime_type, "image/png")
        self.assertEqual(info.nbytes, 3)
        self.assertEqual(info.width, None)
        self.assertEqual(info.height, None)
        self.assertEqual(info.url, "http://example.com/avatar")

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0084_metadata, "info"),
            avatar_xso.Info.TAG
        )

    def test_nbytes(self):
        self.assertIsInstance(
            avatar_xso.Info.nbytes,
            xso.Attr
        )

        self.assertEqual(
            (None, "bytes"),
            avatar_xso.Info.nbytes.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.nbytes.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Info.nbytes.default,
            xso.NO_DEFAULT
        )

    def test_height(self):
        self.assertIsInstance(
            avatar_xso.Info.height,
            xso.Attr
        )

        self.assertEqual(
            (None, "height"),
            avatar_xso.Info.height.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.height.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Info.height.default,
            None
        )

    def test_id(self):
        self.assertIsInstance(
            avatar_xso.Info.id_,
            xso.Attr
        )

        self.assertEqual(
            (None, "id"),
            avatar_xso.Info.id_.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.id_.type_,
            xso.String
        )

        self.assertIs(
            avatar_xso.Info.id_.default,
            xso.NO_DEFAULT
        )

    def test_mime_type(self):
        self.assertIsInstance(
            avatar_xso.Info.mime_type,
            xso.Attr
        )

        self.assertEqual(
            (None, "type"),
            avatar_xso.Info.mime_type.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.mime_type.type_,
            xso.String
        )

        self.assertIs(
            avatar_xso.Info.mime_type.default,
            xso.NO_DEFAULT
        )

    def test_url(self):
        self.assertIsInstance(
            avatar_xso.Info.url,
            xso.Attr
        )

        self.assertEqual(
            (None, "url"),
            avatar_xso.Info.url.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.url.type_,
            xso.String
        )

        self.assertIs(
            avatar_xso.Info.height.default,
            None
        )

    def test_width(self):
        self.assertIsInstance(
            avatar_xso.Info.width,
            xso.Attr
        )

        self.assertEqual(
            (None, "width"),
            avatar_xso.Info.width.tag
        )

        self.assertIsInstance(
            avatar_xso.Info.width.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Info.height.default,
            None
        )


class TestPointer(unittest.TestCase):

    def test_is_xso(self):
        self.assertTrue(issubclass(avatar_xso.Pointer, xso.XSO))

    def test_tag(self):
        self.assertEqual(
            (namespaces.xep0084_metadata, "pointer"),
            avatar_xso.Pointer.TAG
        )

    def test_registered_payload(self):
        self.assertIsInstance(
            avatar_xso.Pointer.registered_payload,
            xso.Child
        )

    def test_unregistered_payload(self):
        self.assertIsInstance(
            avatar_xso.Pointer.unregistered_payload,
            xso.Collector
        )

    def test_nbytes(self):
        self.assertIsInstance(
            avatar_xso.Pointer.nbytes,
            xso.Attr
        )

        self.assertEqual(
            (None, "bytes"),
            avatar_xso.Pointer.nbytes.tag
        )

        self.assertIsInstance(
            avatar_xso.Pointer.nbytes.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Pointer.nbytes.default,
            None
        )

    def test_height(self):
        self.assertIsInstance(
            avatar_xso.Pointer.height,
            xso.Attr
        )

        self.assertEqual(
            (None, "height"),
            avatar_xso.Pointer.height.tag
        )

        self.assertIsInstance(
            avatar_xso.Pointer.height.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Pointer.height.default,
            None
        )

    def test_id(self):
        self.assertIsInstance(
            avatar_xso.Pointer.id_,
            xso.Attr
        )

        self.assertEqual(
            (None, "id"),
            avatar_xso.Pointer.id_.tag
        )

        self.assertIsInstance(
            avatar_xso.Pointer.id_.type_,
            xso.String
        )

        self.assertIs(
            avatar_xso.Pointer.id_.default,
            None
        )

    def test_mime_type(self):
        self.assertIsInstance(
            avatar_xso.Pointer.mime_type,
            xso.Attr
        )

        self.assertEqual(
            (None, "type"),
            avatar_xso.Pointer.mime_type.tag
        )

        self.assertIsInstance(
            avatar_xso.Pointer.mime_type.type_,
            xso.String
        )

        self.assertIs(
            avatar_xso.Pointer.mime_type.default,
            None
        )

    def test_width(self):
        self.assertIsInstance(
            avatar_xso.Pointer.width,
            xso.Attr
        )

        self.assertEqual(
            (None, "width"),
            avatar_xso.Pointer.width.tag
        )

        self.assertIsInstance(
            avatar_xso.Pointer.width.type_,
            xso.Integer
        )

        self.assertIs(
            avatar_xso.Pointer.height.default,
            None
        )

    def test_as_payload_class(self):
        with contextlib.ExitStack() as stack:
            at_Pointer = stack.enter_context(
                unittest.mock.patch.object(
                    avatar_xso.Pointer,
                    "register_child"
                )
            )

            result = avatar_xso.Pointer.as_payload_class(
                unittest.mock.sentinel.cls
            )

        self.assertIs(result, unittest.mock.sentinel.cls)

        at_Pointer.assert_called_with(
            avatar_xso.Pointer.registered_payload,
            unittest.mock.sentinel.cls
        )
