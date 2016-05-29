"""
:mod:`~aioxmpp.shim` --- Stanza Headers and Internet Metadata (:xep:`0131`)
###########################################################################

This module provides support for :xep:`131` stanza headers. The following
attributes are added by this module to the existing stanza classes:

.. attribute:: aioxmpp.stanza.Message.xep0131_headers

   A :class:`xso.Headers` instance or :data:`None`. Represents the SHIM headers of
   the stanza.

.. attribute:: aioxmpp.stanza.Presence.xep0131_headers

   A :class:`xso.Headers` instance or :data:`None`. Represents the SHIM headers of
   the stanza.

The attributes are available as soon as :mod:`aioxmpp.shim` is loaded.

.. autoclass:: Service

.. currentmodule:: aioxmpp.shim.xso

.. autoclass:: Headers

"""
from . import xso

from .service import (
    Service,
)
