"""
:mod:`~aioxmpp.disco` --- Service discovery support (XEP-0030)
##############################################################

This module provides support for
`XEP-0030 (Service Discovery)
<https://xmpp.org/extensions/xep-0030.html>`_. For this, it provides a
:class:`~aioxmpp.service.Service` subclass which can be loaded into a client
using :meth:`.AbstractClient.summon`.

Service
=======

.. autoclass:: Service

Entity information
------------------

.. autoclass:: Node

.. autoclass:: StaticNode

.. module:: aioxmpp.disco.xso

.. currentmodule:: aioxmpp.disco.xso

:mod:`.disco.xso` --- IQ payloads
=================================

The submodule :mod:`aioxmpp.disco.xso` contains the :class:`~aioxmpp.xso.XSO`
classes which describe the IQ payloads used by this subpackage.

You will encounter some of these in return values, but there should never be a
need to construct them by yourself; the :class:`~aioxmpp.disco.Service` handles
it all.

Information queries
-------------------

.. autoclass:: InfoQuery(*[, identities][, features][, node])

.. autoclass:: Feature(*[, var])

.. autoclass:: Identity(*[, category][, type_][, name][, lang])

Item queries
------------

.. autoclass:: ItemsQuery(*[, node][, items])

.. autoclass:: Item(*[, jid][, name][, node])

.. currentmodule:: aioxmpp.disco

"""

from . import xso  # NOQA
from .service import Service, Node, StaticNode  # NOQA
