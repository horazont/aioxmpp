########################################################################
# File name: service.py
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
import asyncio
import typing

import aioxmpp
import aioxmpp.disco
import aioxmpp.errors
import aioxmpp.service

from . import xso as version_xso


class VersionServer(aioxmpp.service.Service):
    """
    :class:`~aioxmpp.service.Service` which handles inbound :xep:`92` Software
    Version requests.

    .. warning::

        Do **not** depend on this service in another service. This service
        exposes possibly private or sensitive information over the XMPP
        network without any filtering. Implicitly summoning this service via
        a dependency is thus discouraged.

        *If* you absolutely need to do this for the implementation of another
        published XEP, please file an issue against :mod:`aioxmpp` so that we
        can work out a good solution.

    .. warning::

        This service does answer version queries, no matter who asks. This may
        not be desirable, in which case this service is not for you.

    .. seealso::

        :func:`~.version.query_version`
            for a function to obtain another entities software version.

    .. note::

        By default, this service does not reply to version queries. The
        :attr:`name` attribute needs to be set first.

    The response can be configured with the following attributes:

    .. autoattribute:: name
        :annotation: = None

    .. autoattribute:: version
        :annotation: = None

    .. autoattribute:: os
        :annotation: = distro.name() or platform.system()
    """

    ORDER_AFTER = [
        aioxmpp.disco.DiscoServer,
    ]

    disco_feature = aioxmpp.disco.register_feature(
        "jabber:iq:version",
    )

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        try:
            import distro
        except ImportError:
            import platform
            self._os = platform.system()
        else:
            self._os = distro.name()

        self._name = None
        self._version = None

    @property
    def os(self) -> typing.Optional[str]:
        """
        The operating system of this entity.

        Defaults to :func:`distro.name` or :func:`platform.system` (if
        :mod:`distro` is not available).

        This attribute can be set to :data:`None` or deleted to prevent
        inclusion of the OS element in the reply.
        """
        return self._os

    @os.setter
    def os(self, value: typing.Optional[str]):
        if value is None:
            self._os = None
        else:
            self._os = str(value)

    @os.deleter
    def os(self):
        self._os = None

    @property
    def name(self) -> typing.Optional[str]:
        """
        The software name of this entity.

        Defaults to :data:`None`.

        If this attribute is :data:`None`, version requests are not answered
        but fail with a ``service-unavailable`` error.
        """
        return self._name

    @name.setter
    def name(self, value: typing.Optional[str]):
        if value is None:
            self._name = None
        else:
            self._name = str(value)

    @name.deleter
    def name(self):
        self._name = None

    @property
    def version(self) -> typing.Optional[str]:
        """
        The software version of this entity.

        Defaults to :data:`None`.

        If this attribute is :data:`None` or the empty string, the version will
        be shown as ``"unspecified"`` to other entities. This can be used to
        avoid disclosing the specific version of the software.
        """
        return self._version

    @version.setter
    def version(self, value: typing.Optional[str]):
        if value is None:
            self._version = None
        else:
            self._version = str(value)

    @version.deleter
    def version(self):
        self._version = None

    @aioxmpp.service.iq_handler(aioxmpp.IQType.GET,
                                version_xso.Query)
    async def handle_query(self, iq: aioxmpp.IQ) -> version_xso.Query:
        if self._name is None:
            raise aioxmpp.errors.XMPPCancelError(
                aioxmpp.errors.ErrorCondition.SERVICE_UNAVAILABLE,
            )

        result = version_xso.Query()
        result.name = self._name
        result.os = self._os
        result.version = self._version or "unspecified"
        return result


async def query_version(stream: aioxmpp.stream.StanzaStream,
                        target: aioxmpp.JID) -> version_xso.Query:
    """
    Query the software version of an entity.

    :param stream: A stanza stream to send the query on.
    :type stream: :class:`aioxmpp.stream.StanzaStream`
    :param target: The address of the entity to query.
    :type target: :class:`aioxmpp.JID`
    :raises OSError: if a connection issue occurred before a reply was received
    :raises aioxmpp.errors.XMPPError: if an XMPP error was returned instead
        of a reply.
    :rtype: :class:`aioxmpp.version.xso.Query`
    :return: The response from the peer.

    The response is returned as :class:`~aioxmpp.version.xso.Query` object. The
    attributes hold the data returned by the peer. Each attribute may be
    :data:`None` if the peer chose to omit that information. In an extreme
    case, all attributes are :data:`None`.
    """

    return await stream.send(aioxmpp.IQ(
        type_=aioxmpp.IQType.GET,
        to=target,
        payload=version_xso.Query(),
    ))
