"""
:mod:`~aioxmpp.forms` --- Data Forms support (:xep:`4`)
#######################################################

This subpackage contains tools to deal with :xep:`4` Data Forms. Data Forms is
a pervasive and highly flexible protocol used in XMPP. It allows for
machine-readable (and processable) forms as well as tables of data. This
flexibility comes unfortunately at the price of complexity. This subpackage
attempts to take some of the load of processing Data Forms off the application
developer.

Cheat Sheet:

* The :class:`Form` class exists for use cases where automated processing of
  Data Forms is supposed to happen. The
  :ref:`api-aioxmpp.forms-declarative-style` allow convenient access to and
  manipulation of form data from within code.

* Direct use of the :class:`Data` XSO is advisable if you want to present forms
  or data to sentient beings: even though :class:`Form` is more convenient for
  machine-to-machine use, using the :class:`Data` sent by the peer easily
  allows showing the user *all* fields supported by the peer.

* For machine-processed tables, there is no tooling (yet).

.. _api-aioxmpp.forms-declarative-style:

Declarative-style Forms
=======================

Base class
----------

.. autoclass:: Form

Fields
------

.. autoclass:: InputLine(var, type_=xso.String(), *[, default=None][, required=False][, desc=None][, label=None])

.. autoclass:: InputJID(var, type_=xso.JID(), *[, default=None][, required=False][, desc=None][, label=None])

XSOs
====

.. autoclass:: Data

.. autoclass:: Field

.. autoclass:: FieldType

Report and table support
------------------------

.. autoclass:: Reported

.. autoclass:: Item

"""


from . import xso

from .xso import (  # NOQA
    Data,
    Field,
    FieldType,
    Reported,
    Item,
)

from .form import (  # NOQA
    Form,
    Boolean,
    ListSingle,
    ListMulti,
    JIDSingle,
    JIDMulti,
    TextSingle,
    TextMulti,
    TextPrivate,
)
