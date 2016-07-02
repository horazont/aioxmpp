"""
:mod:`~aioxmpp.roster` --- :rfc:`6121` roster implementation
############################################################

This subpackage provides a :class:`aioxmpp.service.Service` to interact with
:rfc:`6121` rosters.

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
"""

from .service import Service, Item  # NOQA
