########################################################################
# File name: rfc3921.py
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
:mod:`~aioxmpp.rfc3921` --- XSOs for legacy protocol parts
##########################################################

This module was introduced to ensure compatibility with legacy XMPP servers
(such as ejabberd).

.. autoclass:: Session

.. autoclass:: SessionFeature

"""

from . import stanza, nonza, xso

from .utils import namespaces


namespaces.rfc3921_session = "urn:ietf:params:xml:ns:xmpp-session"


@stanza.IQ.as_payload_class
class Session(xso.XSO):
    """
    IQ payload to establish a legacy XMPP session.

    .. versionadded:: 0.4
    """

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP
    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    TAG = (namespaces.rfc3921_session, "session")


@nonza.StreamFeatures.as_feature_class
class SessionFeature(xso.XSO):
    """
    Stream feature which the server uses to announce that it supports legacy
    XMPP sessions.

    .. versionadded:: 0.4
    """

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP
    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    TAG = (namespaces.rfc3921_session, "session")

    optional = xso.ChildFlag(
        (namespaces.rfc3921_session, "optional")
    )
