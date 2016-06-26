"""
:mod:`~aioxmpp.pubsub` --- Publish-Subscribe support (:xep:`0060`)
##################################################################

This subpackage provides client-side support for :xep:`0060` publish-subscribe
services.

.. versionadded:: 0.6

Using Publish-Subscribe
=======================

To start using PubSub services in your application, you have to load the
:class:`Service` into the client, using :meth:`~.node.AbstractClient.summon`.

.. autoclass:: Service

.. currentmodule:: aioxmpp.pubsub.xso

XSOs
====

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


"""

from .service import Service
