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
:attr:`.stanza.Presence.xep0115_caps`.

.. autoclass:: Caps


"""

from .service import Service, Cache  # NOQA
from . import xso  # NOQA
