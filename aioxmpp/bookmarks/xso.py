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
from abc import abstractproperty

import aioxmpp.private_xml as private_xml
import aioxmpp.xso as xso


from aioxmpp.utils import namespaces


namespaces.xep0048 = "storage:bookmarks"


class Bookmark(xso.XSO):
    """
    A bookmark XSO abstract base class.

    Every XSO class registered as child of :class:`Storage` must be
    a :class:`Bookmark` subclass.

    Bookmarks must provide the following interface:

    .. autoattribute:: primary

    .. autoattribute:: secondary

    .. autoattribute:: name

    Equality is defined in terms of those properties:

    .. automethod:: __eq__

    It is highly recommended not to redefine :meth:`__eq__` in a
    subclass, if you do so make sure that the following axiom
    relating :meth:`__eq__`, :attr:`primary` and :attr:`secondary`
    holds::

        (type(a) == type(b) and
         a.primary == b.primary and
         a.secondary == b.secondary)

    if and only if::

        a == b

    Otherwise the generation of bookmark change signals is not
    guaranteed to be correct.
    """

    def __eq__(self, other):
        """
        Compare for equality by value and type.

        The value of a bookmark must be fully determined by the values
        of the :attr:`primary` and :attr:`secondary` properties.

        This is used for generating the bookmark list change signals
        and for the get-modify-set methods.
        """
        return (type(self) == type(other) and
                self.primary == other.primary and
                self.secondary == other.secondary)

    @abstractproperty
    def primary(self):
        """
        Return the primary category of the bookmark.

        The internal structure of the category is opaque to the code
        using it; only equality and hashing must be provided and
        operate by value. It is recommended that this be either a
        single datum (e.g. a string or JID) or a tuple of data items.

        Together with the type and :attr:`secondary` this must *fully*
        determine the value of the bookmark.

        This is used in the computation of the change
        signals. Bookmarks with different type or :attr:`primary`
        keys cannot be identified as changed from/to one another.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractproperty
    def secondary(self):
        """
        Return the tuple of secondary categories of the bookmark.

        Together with the type and :attr:`primary` they must *fully*
        determine the value of the bookmark.

        This is used in the computation of the change signals. The
        categories in the tuple are ordered in decreasing precedence,
        when calculating which bookmarks have changed the ones which
        mismatch in the category with the lowest precedence are
        grouped together.

        The length of the tuple must be the same for all bookmarks of
        a type.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractproperty
    def name(self):
        """
        The human-readable label or description of the bookmark.
        """
        raise NotImplementedError  # pragma: no cover


class Conference(Bookmark):
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

    def __repr__(self):
        return "Conference({!r}, {!r}, autojoin={!r}, " \
            "nick={!r}, password{!r})".\
            format(self.name, self.jid, self.autojoin, self.nick,
                   self.password)

    @property
    def primary(self):
        return self.jid

    @property
    def secondary(self):
        return (self.name, self.nick, self.password, self.autojoin)


class URL(Bookmark):
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

    def __repr__(self):
        return "URL({!r}, {!r})".format(self.name, self.url)

    @property
    def primary(self):
        return self.url

    @property
    def secondary(self):
        return (self.name,)


@private_xml.Query.as_payload_class
class Storage(xso.XSO):
    """
    The container for storing bookmarks.

    .. attribute:: bookmarks

       A :class:`~xso.XSOList` of bookmarks.
    """

    TAG = (namespaces.xep0048, "storage")

    bookmarks = xso.ChildList([URL, Conference])


def as_bookmark_class(xso_class):
    """
    Decorator to register `xso_class` as a custom bookmark class.

    This is necessary to store and retrieve such bookmarks.
    The registered class must be a subclass of the abstract base class
    :class:`Bookmark`.

    :raises TypeError: if `xso_class` is not a subclass of :class:`Bookmark`.
    """

    if not issubclass(xso_class, Bookmark):
        raise TypeError(
            "Classes registered as bookmark types must be Bookmark subclasses"
        )

    Storage.register_child(
        Storage.bookmarks,
        xso_class
    )

    return xso_class
