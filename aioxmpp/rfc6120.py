########################################################################
# File name: rfc6120.py
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
:mod:`~aioxmpp.rfc6120` -- Stanza payloads for :rfc:`6120` implementation
#########################################################################

This module contains XSO-related classes for implementation of :rfc:`6120`.

.. autoclass:: BindFeature

.. autoclass:: Bind

.. autoclass:: Required

"""

from . import xso, stanza, nonza
from .utils import namespaces

namespaces.rfc6120_bind = "urn:ietf:params:xml:ns:xmpp-bind"


class Required(xso.XSO):
    """
    The XSO used for the :attr:`.BindFeature.required` attribute.
    """

    TAG = (namespaces.rfc6120_bind, "required")


@nonza.StreamFeatures.as_feature_class
class BindFeature(xso.XSO):
    """
    A stream feature for use with :class:`.nonza.StreamFeatures` which
    indicates that the server allows resource binding.

    .. attribute:: required

       This attribute is either an instance of :class:`Required` or
       :data:`None`. The former indicates that the server requires resource
       binding at this point in the stream negotiation; :data:`None` indicates
       that it is not required.

       User code should just test the boolean value of this attribute and not
       worry about the actual types involved.

    """
    TAG = (namespaces.rfc6120_bind, "bind")

    required = xso.Child([Required], required=False)


class Bind(xso.XSO):
    """
    The :class:`.IQ` payload for binding to a resource.

    .. attribute:: jid

       The server-supplied :class:`aioxmpp.JID`. This must not be set by
       client code.

    .. attribute:: resource

       The client-supplied, optional resource. If a client wishes to bind to a
       specific resource, it must tell the server that using this attribute.

    """

    TAG = (namespaces.rfc6120_bind, "bind")

    jid = xso.ChildText(
        (namespaces.rfc6120_bind, "jid"),
        type_=xso.JID(),
        default=None
    )
    resource = xso.ChildText(
        (namespaces.rfc6120_bind, "resource"),
        default=None
    )

    def __init__(self, jid=None, resource=None):
        super().__init__()
        self.jid = jid
        self.resource = resource


stanza.IQ.register_child(stanza.IQ.payload, Bind)
