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
import aioxmpp
import aioxmpp.private_xml as private_xml
import aioxmpp.xso as xso


from aioxmpp.utils import namespaces


namespaces.xep0048 = "storage:bookmarks"


class Nick(xso.XSO):
    TAG = (namespaces.xep0049, "nick")
    text = Text(type_=xso.String())


class Password(xso.XSO):
    TAG = (namespaces.xep0049, "password")
    text = Text(type_=xso.String())


class Conference(xso.XSO):
    TAG = (namespaces.xep0049, "conference")

    autojoin = xso.Attr(tag="autojoin", type_=xso.Bool(), default=False)
    jid = xso.Attr(tag="jid", type_=xso.JID())
    name = xso.Attr(tag="name", type_=xso.String(), default=None)

    nick = xso.Child([Nick()])
    password = xso.Child([Password()])


class URL(xso.XSO):
    TAG = (namespaces.xep0049, "url")

    name = xso.Attr(tag="name", type_=xso.String(), default=None)
    # XXX: we might want to use a URL type once we have one
    url = xso.Attr(tag="url", type_=xso.String())


@private_xml.Query.as_payload_class
class Storage(xso.XSO):
    TAG = (namespaces.xep0049, "storage")

    bookmarks = xso.ChildList([URL, Conference])
