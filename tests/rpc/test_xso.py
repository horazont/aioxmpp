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
import unittest
import unittest.mock

import aioxmpp.rpc.xso as rpc_xso
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

class TestNamespaces(unittest.TestCase):
    def test_rpc_namespace(self):
        self.assertEqual(
            namespaces.xep0009,
            "http://jabber.org/protocol/rpc"
        )

class TestQuery(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.Query,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.Query.TAG,
            (namespaces.xep0009, "query")
        )

    def test_payload_attr(self):
        self.assertIsInstance(
            rpc_xso.Query.payload,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.Query.payload._classes,
            [
                rpc_xso.MethodCall,
                rpc_xso.MethodResponse
            ]
        )

    def test_init(self):
        q = rpc_xso.Query()
        self.assertIsNone(q.payload)

        q = rpc_xso.Query(unittest.mock.sentinel.payload)
        self.assertEqual(q.payload, unittest.mock.sentinel.payload)

class TestMethodResponse(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.MethodResponse,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.MethodResponse.TAG,
            (namespaces.xep0009, "methodResponse")
        )

    def test_params_attr(self):
        self.assertIsInstance(
            rpc_xso.MethodResponse.params,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.MethodResponse.params._classes,
            [
                rpc_xso.Params,
            ]
        )

    def test_init(self):
        m = rpc_xso.MethodResponse()
        self.assertIsNone(m.params)

        m = rpc_xso.MethodResponse(unittest.mock.sentinel.params)
        self.assertEqual(m.params, unittest.mock.sentinel.params)

class TestMethodCall(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.MethodCall,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.MethodCall.TAG,
            (namespaces.xep0009, "methodCall")
        )

    def test_params_attr(self):
        self.assertIsInstance(
            rpc_xso.MethodCall.params,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.MethodCall.params._classes,
            [
                rpc_xso.Params,
            ]
        )

    def test_methodName_attr(self):
        self.assertIsInstance(
            rpc_xso.MethodCall.methodName,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.MethodCall.methodName._classes,
            [
                rpc_xso.MethodName,
            ]
        )

    def test_init(self):
        m = rpc_xso.MethodCall()
        self.assertIsNone(m.methodName)
        self.assertIsNone(m.params)

        m = rpc_xso.MethodCall(unittest.mock.sentinel.methodName, unittest.mock.sentinel.params)
        self.assertEqual(m.methodName, unittest.mock.sentinel.methodName)
        self.assertEqual(m.params, unittest.mock.sentinel.params)

class TestMethodName(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.MethodName,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.MethodName.TAG,
            (namespaces.xep0009, "methodName")
        )

    def test_methodName_attr(self):
        self.assertIsInstance(
            rpc_xso.MethodName.name,
            xso.Text
        )

    def test_init(self):
        with self.assertRaises(TypeError):
            rpc_xso.MethodName()

        m = rpc_xso.MethodName("foo")
        self.assertEqual(m.name, "foo")

class TestParams(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.Params,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.Params.TAG,
            (namespaces.xep0009, "params")
        )

    def test_params_attr(self):
        self.assertIsInstance(
            rpc_xso.Params.params,
            xso.ChildList
        )
        self.assertCountEqual(
            rpc_xso.Params.params._classes,
            [
                rpc_xso.Param,
            ]
        )

    def test_init(self):
        p = rpc_xso.Params()
        self.assertCountEqual(p.params, [])

        p = rpc_xso.Params([
            unittest.mock.sentinel.param1,
            unittest.mock.sentinel.param2
        ])
        self.assertSequenceEqual(p.params, [
            unittest.mock.sentinel.param1,
            unittest.mock.sentinel.param2
        ])

class TestParam(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.Param,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.Param.TAG,
            (namespaces.xep0009, "param")
        )
    
    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.Param.value,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.Param.value._classes,
            [
                rpc_xso.Value,
            ]
        )

    def test_init(self):
        p = rpc_xso.Param()
        self.assertIsNone(p.value)

        p = rpc_xso.Param(unittest.mock.sentinel.value)
        self.assertEqual(p.value, unittest.mock.sentinel.value)

class TestValue(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.Value,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.Value.TAG,
            (namespaces.xep0009, "value")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.Value.value,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.Value.value._classes,
            [
                rpc_xso.i4,
                rpc_xso.integer,
                rpc_xso.string,
                rpc_xso.double,
                rpc_xso.base64,
                rpc_xso.boolean,
                rpc_xso.datetime,
                rpc_xso.array,
                rpc_xso.struct
            ]
        )

    def test_init(self):
        v = rpc_xso.Value()
        self.assertIsNone(v.value)

        v = rpc_xso.Value(unittest.mock.sentinel.value)
        self.assertEqual(v.value, unittest.mock.sentinel.value)

class Testi4(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.i4,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.i4.TAG,
            (namespaces.xep0009, "i4")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.i4.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.i4("foo")
        self.assertEqual(v.value, "foo")

class TestInteger(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.integer,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.integer.TAG,
            (namespaces.xep0009, "int")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.integer.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.integer("foo")
        self.assertEqual(v.value, "foo")

class TestString(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.string,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.string.TAG,
            (namespaces.xep0009, "string")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.string.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.string("foo")
        self.assertEqual(v.value, "foo")

class TestDouble(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.double,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.double.TAG,
            (namespaces.xep0009, "double")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.double.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.double("foo")
        self.assertEqual(v.value, "foo")

class TestBase64(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.base64,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.base64.TAG,
            (namespaces.xep0009, "base64")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.base64.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.base64("foo")
        self.assertEqual(v.value, "foo")

class TestBoolean(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.boolean,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.boolean.TAG,
            (namespaces.xep0009, "boolean")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.boolean.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.boolean("foo")
        self.assertEqual(v.value, "foo")

class TestDatetime(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.datetime,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.datetime.TAG,
            (namespaces.xep0009, "dateTime.iso8601")
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.datetime.value,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.datetime("foo")
        self.assertEqual(v.value, "foo")

class TestName(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.name,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.name.TAG,
            (namespaces.xep0009, "name")
        )

    def test_name_attr(self):
        self.assertIsInstance(
            rpc_xso.name.name,
            xso.Text
        )
    
    def test_init(self):
        v = rpc_xso.name("foo")
        self.assertEqual(v.name, "foo")


class TestMember(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.member,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.member.TAG,
            (namespaces.xep0009, "member")
        )

    def test_name_attr(self):
        self.assertIsInstance(
            rpc_xso.member.name,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.member.name._classes,
            [rpc_xso.name]
        )

    def test_value_attr(self):
        self.assertIsInstance(
            rpc_xso.member.value,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.member.value._classes,
            [rpc_xso.Value]
        )
    
    def test_init(self):
        v = rpc_xso.member(unittest.mock.sentinel.name, unittest.mock.sentinel.value)
        self.assertEqual(v.name, unittest.mock.sentinel.name)
        self.assertEqual(v.value, unittest.mock.sentinel.value)

class TestStruct(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.struct,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.struct.TAG,
            (namespaces.xep0009, "struct")
        )

    def test_members_attr(self):
        self.assertIsInstance(
            rpc_xso.struct.members,
            xso.ChildList
        )
        self.assertCountEqual(
            rpc_xso.struct.members._classes,
            [rpc_xso.member]
        )
    
    def test_init(self):
        v = rpc_xso.struct(
            [
                unittest.mock.sentinel.member1,
                unittest.mock.sentinel.member2
            ]
        )
        self.assertCountEqual(v.members, 
            [
                unittest.mock.sentinel.member1,
                unittest.mock.sentinel.member2
            ]
        )

class TestData(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.data,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.data.TAG,
            (namespaces.xep0009, "data")
        )

    def test_data_attr(self):
        self.assertIsInstance(
            rpc_xso.data.data,
            xso.ChildList
        )
        self.assertCountEqual(
            rpc_xso.data.data._classes,
            [rpc_xso.Value]
        )
    
    def test_init(self):
        v = rpc_xso.data(
            [
                unittest.mock.sentinel.value1,
                unittest.mock.sentinel.value2
            ]
        )
        self.assertCountEqual(v.data, 
            [
                unittest.mock.sentinel.value1,
                unittest.mock.sentinel.value2
            ]
        )

class TestArray(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            rpc_xso.array,
            xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            rpc_xso.array.TAG,
            (namespaces.xep0009, "array")
        )

    def test_data_attr(self):
        self.assertIsInstance(
            rpc_xso.array.data,
            xso.Child
        )
        self.assertCountEqual(
            rpc_xso.array.data._classes,
            [rpc_xso.data]
        )
    
    def test_init(self):
        v = rpc_xso.array(unittest.mock.sentinel.data)
        self.assertEqual(v.data, unittest.mock.sentinel.data)