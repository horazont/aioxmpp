########################################################################
# File name: common.py
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
import abc


class AbstractKey(metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def path(self):
        """
        Return the file system path relative to the root of a file-system based
        caps database for this key.

        The path includes all information of the key. Components of the path do
        not exceed 255 codepoints and use only ASCII codepoints.

        If it is not possible to create such a path, :class:`ValueError` is
        raised.
        """

    @abc.abstractmethod
    def verify(self, query_response):
        """
        Verify whether the cache key matches a piece of service discovery
        information.

        :param query_response: The full :xep:`30` disco#info query response.
        :type query_response: :class:`~.disco.xso.InfoQuery`
        :rtype: :class:`bool`
        :return: true if the key matches and false otherwise.
        """


class AbstractImplementation(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def extract_keys(self, presence):
        """
        Extract cache keys from a presence stanza.

        :param presence: Presence stanza to extract cache keys from.
        :type presence: :class:`aioxmpp.Presence`
        :rtype: :class:`~collections.abc.Iterable` of :class:`AbstractKey`
        :return: The cache keys from the presence stanza.

        The resulting iterable may be empty if the presence stanza does not
        carry any capabilities information with it.

        The resulting iterable cannot be iterated over multiple times.
        """

    @abc.abstractmethod
    def put_keys(self, keys, presence):
        """
        Insert cache keys into a presence stanza.

        :param keys: An iterable of cache keys to insert.
        :type keys: :class:`~collections.abc.Iterable` of :class:`AbstractKey`
            objects
        :param presence: The presence stanza into which the cache keys shall be
            injected.
        :type presence: :class:`aioxmpp.Presence`

        The presence stanza is modified in-place.
        """

    @abc.abstractmethod
    def calculate_keys(self, query_response):
        """
        Calculate the cache keys for a disco#info response.

        :param query_response: The full :xep:`30` disco#info query response.
        :type query_response: :class:`~.disco.xso.InfoQuery`
        :rtype: :class:`~collections.abc.Iterable` of :class:`AbstractKey`
        :return: An iterable of the cache keys for the disco#info response.

        ..

            :param identities: The identities of the disco#info response.
            :type identities: :class:`~collections.abc.Iterable` of
                :class:`~.disco.xso.Identity`
            :param features: The features of the disco#info response.
            :type features: :class:`~collections.abc.Iterable` of
                :class:`str`
            :param features: The extensions of the disco#info response.
            :type features: :class:`~collections.abc.Iterable` of
                :class:`~.forms.xso.Data`
        """
