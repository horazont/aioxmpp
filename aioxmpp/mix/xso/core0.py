########################################################################
# File name: core0.py
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
import typing

import aioxmpp.xso

from aioxmpp.utils import namespaces

from . import nodes

namespaces.xep0369_mix_core_0 = "urn:xmpp:mix:core:0"


class Subscribe0(aioxmpp.xso.XSO):
    TAG = namespaces.xep0369_mix_core_0, "subscribe"

    node = aioxmpp.xso.Attr(
        "node",
        type_=aioxmpp.xso.EnumCDataType(
            nodes.Node,
            accept_unknown=True,
            allow_unknown=True,
        )
    )

    def __init__(self, node):
        super().__init__()
        self.node = node


class Subscribe0Type(aioxmpp.xso.AbstractElementType):
    @classmethod
    def get_xso_types(cls):
        return [Subscribe0]

    def pack(self, node: nodes.Node) -> Subscribe0:
        return Subscribe0(node)

    def unpack(self, obj: Subscribe0) -> nodes.Node:
        return obj.node


class Join0(aioxmpp.xso.XSO):
    TAG = namespaces.xep0369_mix_core_0, "join"

    subscribe = aioxmpp.xso.ChildValueList(Subscribe0Type())

    def __init__(self, subscribe_to_nodes: typing.Iterable[nodes.Node] = []):
        super().__init__()
        self.subscribe[:] = subscribe_to_nodes


class Leave0(aioxmpp.xso.XSO):
    TAG = namespaces.xep0369_mix_core_0, "leave"
