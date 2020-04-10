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
:mod:`~aioxmpp.pubsub` --- Publish-Subscribe support (:xep:`0060`)
##################################################################

This subpackage provides client-side support for :xep:`0060` publish-subscribe
services.

.. versionadded:: 0.6

Using Publish-Subscribe
=======================

To start using PubSub services in your application, you have to load the
:class:`.PubSubClient` into the client, using :meth:`~.node.Client.summon`.

.. currentmodule:: aioxmpp

.. autoclass:: PubSubClient

.. currentmodule:: aioxmpp.pubsub

.. class:: Service

   Alias of :class:`.PubSubClient`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

.. currentmodule:: aioxmpp.pubsub.xso

XSOs
====

Registering payloads
--------------------

PubSub payloads are must be registered at several places, so there is a
short-hand function to handle that:

.. autofunction:: as_payload_class

Features
--------

.. autoclass:: Feature

Generic namespace
-----------------

The top-level XSO is :class:`Request`. Below that, several different XSOs are
allowed, which are listed below the documentation of :class:`Request` in
alphabetical order.

.. autoclass:: Request

.. autoclass:: Affiliation

.. autoclass:: Affiliations

.. autoclass:: Configure

.. autoclass:: Create

.. autoclass:: Default

.. autoclass:: Item

.. autoclass:: Items

.. autoclass:: Options

.. autoclass:: Publish

.. autoclass:: Retract

.. autoclass:: Subscribe

.. autoclass:: SubscribeOptions

.. autoclass:: Subscription

.. autoclass:: Subscriptions

.. autoclass:: Unsubscribe

Owner namespace
---------------

The top-level XSO is :class:`OwnerRequest`. Below that, several different XSOs
are allowed, which are listed below the documentation of :class:`OwnerRequest`
in alphabetical order.

.. autoclass:: OwnerRequest

.. autoclass:: OwnerAffiliation

.. autoclass:: OwnerAffiliations

.. autoclass:: OwnerConfigure

.. autoclass:: OwnerDefault

.. autoclass:: OwnerDelete

.. autoclass:: OwnerPurge

.. autoclass:: OwnerRedirect

.. autoclass:: OwnerSubscription

.. autoclass:: OwnerSubscriptions

Application-condition error XSOs
--------------------------------

Application-condition XSOs for use in
:attr:`.stanza.Error.application_condition` are also defined for the error
conditions specified by :xep:`0060`. They are listed in alphabetical order
below:

.. autoclass:: ClosedNode()

.. autoclass:: ConfigurationRequired()

.. autoclass:: InvalidJID()

.. autoclass:: InvalidOptions()

.. autoclass:: InvalidPayload()

.. autoclass:: InvalidSubID()

.. autoclass:: ItemForbidden()

.. autoclass:: ItemRequired()

.. autoclass:: JIDRequired()

.. autoclass:: MaxItemsExceeded()

.. autoclass:: MaxNodesExceeded()

.. autoclass:: NodeIDRequired()

.. autoclass:: NotInRosterGroup()

.. autoclass:: NotSubscribed()

.. autoclass:: PayloadTooBig()

.. autoclass:: PayloadRequired()

.. autoclass:: PendingSubscription()

.. autoclass:: PresenceSubscriptionRequired()

.. autoclass:: SubIDRequired()

.. autoclass:: TooManySubscriptions()

.. autoclass:: Unsupported()


Forms
-----

.. currentmodule:: aioxmpp.pubsub

.. autoclass:: NodeConfigForm


"""

from .service import PubSubClient  # NOQA: F401
from .xso import NodeConfigForm  # NOQA: F401
Service = PubSubClient
