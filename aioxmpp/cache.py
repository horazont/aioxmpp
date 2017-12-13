########################################################################
# File name: cache.py
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
"""
:mod:`~aioxmpp.cache` --- Utilities for implementing caches
###########################################################

.. versionadded:: 0.9

    This module was added in version 0.9.

.. autoclass:: LRUDict

"""

import collections.abc


class Node:
    __slots__ = ("prev", "next_", "key", "value")


def _init_linked_list():
    root = Node()
    root.prev = root
    root.next_ = root
    root.key = None
    root.value = None
    return root


def _remove_node(node):
    node.next_.prev = node.prev
    node.prev.next_ = node.next_
    return node


def _insert_node(before, new_node):
    new_node.next_ = before.next_
    new_node.next_.prev = new_node
    new_node.prev = before
    before.next_ = new_node


def _length(node):
    # this is used only for testing
    cur = node.next_
    i = 0
    while cur is not node:
        i += 1
        cur = cur.next_
    return i


def _has_consistent_links(node, node_dict=None):
    # this is used only for testing
    cur = node.next_

    if cur.prev is not node:
        return False

    while cur is not node:
        if node_dict is not None and node_dict[cur.key] is not cur:
            return False
        if cur is not cur.next_.prev:
            return False
        cur = cur.next_
    return True


class LRUDict(collections.abc.MutableMapping):
    """
    Size-restricted dictionary with Least Recently Used expiry policy.

    .. versionadded:: 0.9

    The :class:`LRUDict` supports normal dictionary-style access and implements
    :class:`collections.abc.MutableMapping`.

    When the :attr:`maxsize` is exceeded, as many entries as needed to get
    below the :attr:`maxsize` are removed from the dict. Least recently used
    entries are purged first. Setting an entry does *not* count as use!

    .. autoattribute:: maxsize
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__links = {}
        self.__root = _init_linked_list()

        self.__maxsize = 1

    def _test_consistency(self):
        """
        This method is only used for testing to assert that the operations
        leave the LRUDict in a valid state.
        """
        return (_length(self.__root) == len(self.__links) and
                _has_consistent_links(self.__root, self.__links))

    def _purge(self):
        if self.__maxsize is None:
            return

        while len(self.__links) > self.__maxsize:
            link = _remove_node(self.__root.prev)
            del self.__links[link.key]

    @property
    def maxsize(self):
        """
        Maximum size of the cache. Changing this property purges overhanging
        entries immediately.

        If set to :data:`None`, no limit on the number of entries is imposed.
        Do **not** use a limit of :data:`None` for data where the `key` is
        under control of a remote entity.

        Use cases for :data:`None` are those where you only need the explicit
        expiry feature, but not the LRU feature.
        """
        return self.__maxsize

    @maxsize.setter
    def maxsize(self, value):
        if value is not None and value <= 0:
            raise ValueError("maxsize must be positive integer or None")
        self.__maxsize = value
        self._purge()

    def __len__(self):
        return len(self.__links)

    def __iter__(self):
        return iter(self.__links)

    def __setitem__(self, key, value):
        try:
            self.__links[key].value = value
        except KeyError:
            link = Node()
            link.key = key
            link.value = value
            self.__links[key] = link
            _insert_node(self.__root, link)
            self._purge()

    def __getitem__(self, key):
        link = self.__links[key]
        _remove_node(link)
        _insert_node(self.__root, link)
        return link.value

    def __delitem__(self, key):
        link = self.__links.pop(key)
        _remove_node(link)

    def clear(self):
        self.__links.clear()
        self.__root = _init_linked_list()
