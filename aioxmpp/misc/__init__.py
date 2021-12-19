########################################################################
# File name: __init__.py
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
:mod:`~aioxmpp.misc` -- Miscellaneous XSOs
##########################################

This subpackage bundles XSO definitions for several XEPs. They do not get their
own subpackage because they often only define one or two XSOs without any logic
involved. The XSOs are often intended for re-use by other protocols.


Out of Band Data (:xep:`66`)
============================

.. autoclass:: OOBExtension

.. attribute:: aioxmpp.Message.xep0066_oob


Delayed Delivery (:xep:`203`)
=============================

.. autoclass:: Delay()

.. attribute:: aioxmpp.Message.xep0203_delay

   A :class:`Delay` instance which indicates that the message has been
   delivered with delay.


Stanza Forwarding (:xep:`297`)
==============================

.. autoclass:: Forwarded()


Last Message Correction (:xep:`308`)
====================================

.. autoclass:: Replace()

.. attribute:: aioxmpp.Message.xep308_replace

    A :class:`Replace` instance which indicates that the message is supposed
    to replcae another message.


Chat Markers (:xep:`333`)
=========================

.. autoclass:: ReceivedMarker

.. autoclass:: DisplayedMarker

.. autoclass:: AcknowledgedMarker

.. attribute:: aioxmpp.Message.xep0333_marker


JSON Containers (:xep:`335`)
============================

:xep:`335` defines a standard way to transport JSON data in XMPP. The
:class:`JSONContainer` is an XSO class which represents the ``<json/>`` element
specified in :xep:`335`.

:mod:`aioxmpp` also provides an :class:`~aioxmpp.xso.AbstractElementType`
called :class:`JSONContainerType` which can be used to extract JSON data from
an element using the :class:`JSONContainer` format.

.. autoclass:: JSONContainer

.. autoclass:: JSONContainerType


Unique and Stable Stanza IDs (:xep:`359`)
=========================================

:xep:`359` defines a way to attach additional IDs to a stanza, allowing
entities on the path from the sender to the recipient to signal under which ID
they know a specific stanza. This is most notably used by MAM (:xep:`313`).

.. autoclass:: StanzaID(*[, id_][, by])

.. autoclass:: OriginID()

.. attribute:: aioxmpp.Message.xep0359_stanza_ids

    This is a mapping which associates the `by` value of a stanza ID with the
    list of IDs (as strings or :data:`None` if the attribute was not set)
    assigned by that entity. Normally, there should only ever be a single ID
    assigned, but misbehaving parties on the path could inject IDs for other
    entities.

    To allow code handling the ID selection deterministically in such cases,
    all IDs are exposed.

.. attribute:: aioxmpp.Message.xep0359_origin_id

    The :class:`OriginID` object, if any.


Pre-Authenticated Roster Subcription (:xep:`379`)
=================================================

.. autoclass:: Preauth

.. attribute:: aioxmpp.Presence.xep0379_preauth

   The pre-auth element associate with a subscription request.


Current Jabber OpenPGP Usage (:xep:`27`)
========================================

.. autoclass:: OpenPGPEncrypted

.. autoclass:: OpenPGPSigned

.. attribute:: aioxmpp.Message.xep0027_encrypted

    Instance of :class:`OpenPGPEncrypted`, if present.

    .. note::

        :xep:`27` does not specify the signing of messages.

.. attribute:: aioxmpp.Presence.xep0027_signed

    Instance of :class:`OpenPGPSigned`, if present.

"""

from .delay import Delay  # NOQA: F401
from .lmc import Replace  # NOQA: F401
from .forwarding import Forwarded  # NOQA: F401
from .oob import OOBExtension  # NOQA: F401
from .markers import (  # NOQA: F401
    ReceivedMarker,
    DisplayedMarker,
    AcknowledgedMarker,
)
from .json import JSONContainer, JSONContainerType  # NOQA: F401
from .pars import Preauth  # NOQA: F401
from .openpgp_legacy import (
    OpenPGPEncrypted,
    OpenPGPSigned,
)
from .stanzaid import (  # NOQA: F401
    StanzaID,
    OriginID,
)
