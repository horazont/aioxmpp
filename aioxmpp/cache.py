"""
:mod:`~aioxmpp.cache` --- Utilities for implementing caches
###########################################################

.. versionadded:: 0.9

    This module was added in version 0.9.

.. autoclass:: LRUDict

"""

import collections.abc


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
        self.__data = {}
        self.__data_used = {}
        self.__maxsize = 1
        self.__ctr = 0

    def _purge_old(self, n):
        keys_in_age_order = sorted(
            self.__data_used.items(),
            key=lambda x: x[1]
        )
        keys_to_delete = keys_in_age_order[:n]
        for key, _ in keys_to_delete:
            del self.__data[key]
            del self.__data_used[key]
        keys_to_keep = keys_in_age_order[n:]
        # avoid the counter becoming large
        self.__ctr = len(keys_to_keep)
        for i, (key, _) in enumerate(keys_to_keep):
            self.__data_used[key] = i

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
        if self.__maxsize is not None and len(self.__data) > self.__maxsize:
            self._purge_old(len(self.__data) - self.__maxsize)

    def __len__(self):
        return len(self.__data)

    def __iter__(self):
        return iter(self.__data)

    def __setitem__(self, key, value):
        if self.__maxsize is not None and len(self.__data) >= self.__maxsize:
            self._purge_old(len(self.__data) - (self.__maxsize-1))
        self.__data[key] = value
        self.__data_used[key] = self.__ctr

    def __getitem__(self, key):
        result = self.__data[key]
        counter = self.__ctr
        counter += 1
        self.__ctr = counter
        self.__data_used[key] = counter
        return result

    def __delitem__(self, key):
        del self.__data[key]
        del self.__data_used[key]
