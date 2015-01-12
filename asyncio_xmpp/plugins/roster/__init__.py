"""
:mod:`~asyncio_xmpp.plugins.roster` --- Roster and presence support
###################################################################

The roster support of asyncio_xmpp is only client side. That is, the module does
directly provide code to serve a roster to others. The presence support includes
both receiving as well as generating presence and managing subscription
requests.

Note that subscription requests are handled through :class:`RosterClient`,
although technically transmitted using ``presence`` stanzas. The rationale is
that these requests are part of modifying and managing a roster, and a client
which needs to work with these most likely also needs to work with the roster in
general.

On the other hand, generic presence reception is managed by
:class:`PresenceClient`. Presence is not neccessarily bound to the roster
(such as directed presence), which is why it is split into a separate class.

Roster client
=============

Receiving and using the roster
------------------------------

For accessing the roster, a :class:`RosterClient` is needed. It provides the
user with :class:`RosterItemInfo` objects for all JIDs in the roster, as well as
many types of callbacks for different events related to the roster.

.. autoclass:: RosterClient
   :members:

.. autoclass:: RosterItemInfo
   :members:

Modifying the roster
--------------------

To make roster changes as robost as possible, they are represented in a
version-control-style diff. Each change is not represented by the final new
attributes of the roster item, but instead by the changes which need to be
applied to the item.

This allows that roster changes are rebased on changes received from the remote
server before the changes can be applied. For example, when a disconnect happens
after the user has requested a roster item change through
:meth:`~RosterClient.submit_change` or :meth:`~RosterClient.submit_changeset`,
the changes can be rebased and reapplied onto the initial roster received after
the reconnect.

.. autoclass:: RosterItemChange
   :members:

.. autofunction:: compress_changeset


Presence client
===============

.. autoclass:: PresenceClient

"""

import asyncio_xmpp.xml
from asyncio_xmpp.utils import *

from .stanza import *
from .client import *

def register(lookup):
    ns = lookup.get_namespace(namespaces.roster)
    ns["query"] = Query
    ns["item"] = Item
    ns["group"] = Group

register(asyncio_xmpp.xml.lookup)
