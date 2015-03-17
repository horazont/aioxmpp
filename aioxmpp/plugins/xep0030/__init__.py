"""
:mod:`~aioxmpp.plugins.xep0030` --- Support for Service Discovery
######################################################################

Discovery server
================

To automatically respond to service discovery requests and provide other
services with a way to announce their features, the :class:`DiscoInfoService` is
used:

.. note::

   The ``disco#items`` query is not supported yet. The complexity (tree-like
   structures) requires further thought on how to split the responsiblities and
   who distributes the queries in which way.

.. autoclass:: DiscoInfoService

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

from aioxmpp.utils import *

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
