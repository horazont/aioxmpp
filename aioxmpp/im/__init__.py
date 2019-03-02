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
:mod:`~aioxmpp.im` --- Instant Messaging Utilities and Services
###############################################################

This subpackage provides tools for Instant Messaging applications based on
XMPP. The tools are meant to be useful for both user-facing as well as
automated IM applications.

.. warning::

    :mod:`aioxmpp.im` is highly experimental, even more than :mod:`aioxmpp` by
    itself is. This is not a threat, this is a chance. Please play with the
    API, try to build an application around it, and let us know how it feels!
    This is your chance to work with us on the API.

    On the other hand, yes, there is a risk that we’ll restructure the API
    massively in the next release, even though it works quite well for our
    applications currently.


Terminology
===========

This is a short overview of the terminology. The full definitions can be found
in the glossary and are linked.

:term:`Conversation`
   Communication context for two or more parties.
:term:`Conversation Member`
   An entity taking part in a :term:`Conversation`.
:term:`Conversation Implementation`
   A :term:`Service` which provides means to create and manage specific
   :class:`~.AbstractConversation` subclasses.
:term:`Service Member`
   A :term:`Conversation Member` which represents the service over which the
   conversation is run inside the conversation.

.. module:: aioxmpp.im.p2p

:mod:`.im.p2p` --- One-on-one conversations
===========================================

.. autoclass:: Service

.. autoclass:: Conversation

.. autoclass:: Member

.. currentmodule:: aioxmpp.im

:mod:`aioxmpp.muc` --- Multi-User-Chats (:xep:`45`)
===================================================

.. seealso::

    :mod:`aioxmpp.muc`
      has a :term:`Conversation Implementation` for MUCs.

Core Services
=============

.. autoclass:: ConversationService


Enumerations
============

.. autoclass:: ConversationState

.. autoclass:: ConversationFeature

.. autoclass:: InviteMode

Abstract base classes
=====================

.. module:: aioxmpp.im.conversation

.. currentmodule:: aioxmpp.im.conversation

Conversations
-------------

.. autoclass:: AbstractConversation

.. autoclass:: AbstractConversationMember


Conversation Service
--------------------

.. autoclass:: AbstractConversationService

"""

from .conversation import (  # NOQA: F401
    ConversationState,
    ConversationFeature,
    InviteMode,
)
from .service import (  # NOQA: F401
    ConversationService,
)
