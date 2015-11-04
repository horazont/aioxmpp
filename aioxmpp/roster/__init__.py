"""
:mod:`~aioxmpp.roster` --- RFC 6121 roster implementation
#########################################################

This subpackage provides a :class:`aioxmpp.service.Service` to interact with
`RFC 6121`_ rosters.

.. autoclass:: Service

.. autoclass:: Item

.. module:: aioxmpp.roster.xso

.. currentmodule:: aioxmpp.roster.xso

:mod:`.roster.xso` --- IQ payloads and stream feature
=====================================================

The submodule :mod:`aioxmpp.roster.xso` contains the :class:`~aioxmpp.xso.XSO`
classes which describe the IQ payloads used by this subpackage.

.. autoclass:: Query

.. autoclass:: Item

.. autoclass:: Group

The stream feature which is used by servers to announce support for roster
versioning:

.. autoclass:: RosterVersioningFeature()

.. _RFC 6121: https://tools.ietf.org/html/rfc6121
"""

from .service import Service, Item  # NOQA
