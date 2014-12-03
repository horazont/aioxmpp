"""
:mod:`~asyncio_xmpp.plugins.xep0030` --- Support for Service Discovery
######################################################################

Discovery server
================

To automatically respond to service discovery requests and provide other
services with a way to announce their features, the :class:`Service` is used:

.. autoclass:: Service

Client utilities
================

Stanza elements
===============

.. autoclass:: InfoQuery
   :members:

.. autoclass:: Feature
   :members:

.. autoclass:: Identity
   :members:

.. autoclass:: ItemQuery
   :members:

.. autoclass:: Item
   :members:

"""

from asyncio_xmpp.utils import *

from .service import *
from .stanza import *
# from .client import *

def register(lookup):
    ns = lookup.get_namespace(namespaces.xep0030_disco_info)
    ns["query"] = InfoQuery
    ns["identity"] = Identity

    ns = lookup.get_namespace(namespaces.xep0030_disco_items)
    ns["query"] = ItemQuery
    ns["item"] = Item
