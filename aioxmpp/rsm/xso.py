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
import copy

import aioxmpp.xso as xso

from aioxmpp.utils import namespaces, magicmethod

namespaces.xep0059_rsm = "http://jabber.org/protocol/rsm"


class _RangeLimitBase(xso.XSO):
    value = xso.Text(default=None)

    def __init__(self, value=None):
        super().__init__()
        self.value = value


class After(_RangeLimitBase):
    """
    .. attribute:: value

       Identifier of the element which serves as a range limit for the query.
    """

    TAG = namespaces.xep0059_rsm, "after"


class Before(_RangeLimitBase):
    """
    .. attribute:: value

       Identifier of the element which serves as a range limit for the query.
    """

    TAG = namespaces.xep0059_rsm, "before"


class First(_RangeLimitBase):
    """
    .. attribute:: value

       Identifier of the first element in the result set.

    .. attribute:: index

       Approximate index of the first element in the result set.

       Can be used with :attr:`ResultSetMetadata.index` and
       :meth:`ResultSetMetadata.fetch_page` to approximately re-retrieve the
       page.

       .. seealso::

          :meth:`~ResultSetMetadata.fetch_page`
             for hints on caveats and inaccuracies
    """

    TAG = namespaces.xep0059_rsm, "first"

    index = xso.Attr(
        "index",
        type_=xso.Integer(),
        default=None,
    )


class Last(_RangeLimitBase):
    """
    .. attribute:: value

       Identifier of the last element in the result set.

    """

    TAG = namespaces.xep0059_rsm, "last"


class ResultSetMetadata(xso.XSO):
    """
    Represent the result set or query metadata.

    For requests, the following attributes are relevant:

    .. attribute:: after

       Either :data:`None` or a :class:`After` object.

       Generally mutually exclusive with :attr:`index`.

    .. attribute:: before

       Either :data:`None` or a :class:`Before` object.

       Generally mutually exclusive with :attr:`index`.

    .. attribute:: index

       The index of the first result to return, or :data:`None`.

       Generally mutually exclusive with :attr:`after` and :attr:`before`.

    .. attribute:: max

       The maximum number of items to return or :data:`None`.

       Setting :attr:`max` to zero will make the peer return a
       :class:`ResultSetMetadata` with the total number of items in the
       :attr:`count` field.

    These methods are useful when constructing queries:

    .. automethod:: fetch_page

    .. automethod:: limit

    .. automethod:: last_page

    For responses, the following attributes are relevant:

    .. attribute:: first

       Either :data:`None` or a :class:`First` object.

    .. attribute:: last

       Either :data:`None` or a :class:`Last` object.

    .. attribute:: count

       Either :data:`None` or the number of elements in the result set.

       If this is a response to a query with :attr:`max` set to zero, this is
       the total number of elements in the queried data.

    These methods are useful to construct a new request from a previous
    response:

    .. automethod:: next_page

    .. automethod:: previous_page
    """

    TAG = namespaces.xep0059_rsm, "set"

    after = xso.Child([After])

    before = xso.Child([Before])

    first = xso.Child([First])

    last = xso.Child([Last])

    count = xso.ChildText(
        (namespaces.xep0059_rsm, "count"),
        type_=xso.Integer(),
        default=None,
    )

    max_ = xso.ChildText(
        (namespaces.xep0059_rsm, "max"),
        type_=xso.Integer(),
        default=None,
    )

    index = xso.ChildText(
        (namespaces.xep0059_rsm, "index"),
        type_=xso.Integer(),
        default=None,
    )

    @classmethod
    def fetch_page(cls, index, max_=None):
        """
        Return a query set which requests a specific page.

        :param index: Index of the first element of the page to fetch.
        :type index: :class:`int`
        :param max_: Maximum number of elements to fetch
        :type max_: :class:`int` or :data:`None`
        :rtype: :class:`ResultSetMetadata`
        :return: A new request set up to request a page starting with the
                 element indexed by `index`.

        .. note::

           This way of retrieving items may be approximate. See :xep:`59` and
           the embedding protocol for which RSM is used for specifics.
        """

        result = cls()
        result.index = index
        result.max_ = max_
        return result

    @magicmethod
    def limit(self, max_):
        """
        Limit the result set to a given number of items.

        :param max_: Maximum number of items to return.
        :type max_: :class:`int` or :data:`None`
        :rtype: :class:`ResultSetMetadata`
        :return: A new request set up to request at most `max_` items.

        This method can be called on the class and on objects. When called on
        objects, it returns a copy of the object with :attr:`max_` set
        accordingly. When called on the class, it creates a fresh object with
        :attr:`max_` set accordingly.
        """

        if isinstance(self, type):
            result = self()
        else:
            result = copy.deepcopy(self)
        result.max_ = max_
        return result

    def next_page(self, max_=None):
        """
        Return a query set which requests the page after this response.

        :param max_: Maximum number of items to return.
        :type max_: :class:`int` or :data:`None`
        :rtype: :class:`ResultSetMetadata`
        :return: A new request set up to request the next page.

        Must be called on a result set which has :attr:`last` set.
        """

        result = type(self)()
        result.after = After(self.last.value)
        result.max_ = max_
        return result

    def previous_page(self, max_=None):
        """
        Return a query set which requests the page before this response.

        :param max_: Maximum number of items to return.
        :type max_: :class:`int` or :data:`None`
        :rtype: :class:`ResultSetMetadata`
        :return: A new request set up to request the previous page.

        Must be called on a result set which has :attr:`first` set.
        """

        result = type(self)()
        result.before = Before(self.first.value)
        result.max_ = max_
        return result

    @classmethod
    def last_page(self_or_cls, max_=None):
        """
        Return a query set which requests the last page.

        :param max_: Maximum number of items to return.
        :type max_: :class:`int` or :data:`None`
        :rtype: :class:`ResultSetMetadata`
        :return: A new request set up to request the last page.
        """
        result = self_or_cls()
        result.before = Before()
        result.max_ = max_
        return result
