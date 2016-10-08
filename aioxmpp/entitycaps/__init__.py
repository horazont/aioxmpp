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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.entitycaps` --- Entity Capabilities support (:xep:`0115`)
########################################################################

This module provides support for :xep:`XEP-0115 (Entity Capabilities) <0115>`. To use it,
summon the :class:`Service` on a :class:`~.AbstractClient`. See the service
documentation for more information.

.. versionadded:: 0.5

Service
=======

.. autoclass:: Service

.. autoclass:: Cache

.. currentmodule:: aioxmpp.entitycaps.xso

:mod:`.entitycaps.xso` --- Presence payload
===========================================

The submodule :mod:`aioxmpp.entitycaps.xso` contains the
:class:`~aioxmpp.xso.XSO` subclasses which describe the presence payload used
by the implementation.

In general, you will not need to use these classes directly, nor encounter
them, as the service filters them off the presence stanzas. If the filter is
not loaded, the :class:`Caps` instance is available at
:attr:`.Presence.xep0115_caps`.

.. autoclass:: Caps


"""

from .service import Service, Cache  # NOQA
from . import xso  # NOQA
