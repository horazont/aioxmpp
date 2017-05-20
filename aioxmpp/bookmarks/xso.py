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


class Conference(xso.XSO):
    """
    An bookmark for a groupchat.

    .. attribute:: name

       The name of the bookmark.

    .. attribute:: jid

       The jid under which the groupchat is accessible.

    .. attribute:: autojoin

       Whether to join automatically, when the client starts.

    .. attribute:: nick

       The nick to use in the groupchat.

    .. attribute:: password

       The password used to access the groupchat.
    """

    TAG = (namespaces.xep0048, "conference")

    autojoin = xso.Attr(tag="autojoin", type_=xso.Bool(), default=False)
    jid = xso.Attr(tag="jid", type_=xso.JID())
    name = xso.Attr(tag="name", type_=xso.String(), default=None)

    nick = xso.ChildText(
        (namespaces.xep0048, "nick"),
        default=None
    )
    password = xso.ChildText(
        (namespaces.xep0048, "password"),
        default=None
    )

    def __init__(self, name, jid, *, autojoin=False, nick=None, password=None):
        self.autojoin = autojoin
        self.jid = jid
        self.name = name
        self.nick = nick
        self.password = password

    def __eq__(self, other):
        return (isinstance(other, Conference) and
                other.name == self.name and
                other.jid == self.jid and
                other.autojoin == self.autojoin and
                other.name == self.name and
                other.password == self.password)


class URL(xso.XSO):
    """
    An URL bookmark.

    .. attribute:: name

       The name of the bookmark.

    .. attribute:: url

       The URL the bookmark saves.
    """
    TAG = (namespaces.xep0048, "url")

    name = xso.Attr(tag="name", type_=xso.String(), default=None)
    # XXX: we might want to use a URL type once we have one
    url = xso.Attr(tag="url", type_=xso.String())

    def __init__(self, name, url):
        self.name = name
        self.url = url

    def __eq__(self, other):
        return (isinstance(other, URL) and
                other.name == self.name and
                other.url == self.url)


@private_xml.Query.as_payload_class
class Storage(xso.XSO):
    """
    The container for storing bookmarks.

    .. attribute:: bookmarks

       A :class:`~xso.XSOList` of bookmarks.

    """
    TAG = (namespaces.xep0048, "storage")

    bookmarks = xso.ChildList([URL, Conference])
