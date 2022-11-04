########################################################################
# File name: xso.py
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
import aioxmpp.forms
import aioxmpp.stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0009 = "http://jabber.org/protocol/rpc"

class i4(xso.XSO):
    TAG = (namespaces.xep0009, "i4")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class integer(xso.XSO):
    TAG = (namespaces.xep0009, "int")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class string(xso.XSO):
    TAG = (namespaces.xep0009, "string")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class double(xso.XSO):
    TAG = (namespaces.xep0009, "double")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class base64(xso.XSO):
    TAG = (namespaces.xep0009, "base64")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class boolean(xso.XSO):
    TAG = (namespaces.xep0009, "boolean")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class datetime(xso.XSO):
    TAG = (namespaces.xep0009, "dateTime.iso8601")

    value = xso.Text()

    def __init__(self, value):
        super().__init__()
        if value is not None:
            self.value = str(value)

class name(xso.XSO):
    TAG = (namespaces.xep0009, "name")

    name = xso.Text()

    def __init__(self, name):
        super().__init__()
        if name is not None:
            self.name = str(name)

class member(xso.XSO):
    TAG = (namespaces.xep0009, "member")

    name = xso.Child([name])

    def __init__(self, name, value):
        super().__init__()
        if name is not None:
            self.name = name
        if value is not None:
            self.value = value

class struct(xso.XSO):
    TAG = (namespaces.xep0009, "struct")

    members = xso.ChildList([member])

    def __init__(self, members=None):
        super().__init__()
        self.members = members

class data(xso.XSO):
    TAG = (namespaces.xep0009, "data")

    def __init__(self, data=[]):
        super().__init__()
        self.data = data

class array(xso.XSO):
    TAG = (namespaces.xep0009, "array")

    data = xso.Child([data])

    def __init__(self, data=None):
        super().__init__()
        self.data = data

class Value(xso.XSO):
    TAG = (namespaces.xep0009, "value")

    value = xso.Child([i4, integer, string, double, base64, boolean, datetime, array, struct])

    def __init__(self, value=None):
        super().__init__()
        self.value = value

member.value = xso.Child([Value])
data.data = xso.ChildList([Value])

class Param(xso.XSO):
    TAG = (namespaces.xep0009, "param")
    value = xso.Child([Value])

    def __init__(self, value=None):
        super().__init__()
        self.value = value

class Params(xso.XSO):
    TAG = (namespaces.xep0009, "params")
    params = xso.ChildList([Param])

    def __init__(self, params=[]):
        super().__init__()
        self.params = params

class MethodName(xso.XSO):
    TAG = (namespaces.xep0009, "methodName")

    name = xso.Text()

    def __init__(self, name):
        super().__init__()
        self.name = name

class MethodCall(xso.XSO):
    TAG = (namespaces.xep0009, "methodCall")

    methodName = xso.Child([MethodName])
    params = xso.Child([Params])

    def __init__(self, methodName=None, params=None):
        super().__init__()
        self.methodName = methodName
        self.params = params

class MethodResponse(xso.XSO):
    TAG = (namespaces.xep0009, "methodResponse")

    params = xso.Child([Params])
            
    def __init__(self, params=None):
        super().__init__()
        self.params = params

@aioxmpp.stanza.IQ.as_payload_class
class Query(xso.XSO):
    TAG = (namespaces.xep0009, "query")

    payload = xso.Child([
        MethodCall,
        MethodResponse
    ])

    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload

aioxmpp.stanza.Message.xep0009_query = xso.Child([
    Query
])