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

.. versionadded:: 0.7

   Even though the :mod:`aioxmpp.forms` module existed pre-0.7, it has not been
   documented and was thus not part of the public API.

.. note::

   The authors are not entirely happy with the API at some points.
   Specifically, at some places where mutable data structures are used, the
   mutation of these data structures may have unexpected side effects. This may
   be rectified in a future release by replacing these data structures with
   their appropriate immutable equivalents.

   These locations are marked accordingly.

.. _api-aioxmpp.forms-declarative-style:

Declarative-style Forms
=======================

Base class
----------

.. autoclass:: Form

Fields
------

Text fields
~~~~~~~~~~~

.. autoclass:: TextSingle(var, type_=xso.String(), *[, default=None][, required=False][, desc=None][, label=None])

.. autoclass:: TextPrivate(var, type_=xso.String(), *[, default=None][, required=False][, desc=None][, label=None])

.. autoclass:: TextMulti(var, type_=xso.String(), *[, default=()][, required=False][, desc=None][, label=None])

JID fields
~~~~~~~~~~

.. autoclass:: JIDSingle(var, *[, default=None][, required=False][, desc=None][, label=None])

.. autoclass:: JIDMulti(var, *[, default=()][, required=False][, desc=None][, label=None])

Selection fields
~~~~~~~~~~~~~~~~

.. autoclass:: ListSingle(var, type_=xso.String(), *[, default=None][, options=[]][, required=False][, desc=None][, label=None])

.. autoclass:: ListMulti(var, type_=xso.String(), *[, default=frozenset()][, options=[]][, required=False][, desc=None][, label=None])

Other fields
~~~~~~~~~~~~

.. autoclass:: Boolean(var, *[, default=False][, required=False][, desc=None][, label=None])

Abstract base classes
~~~~~~~~~~~~~~~~~~~~~

.. currentmodule:: aioxmpp.forms.fields

.. autoclass:: AbstractField

.. autoclass:: AbstractChoiceField(var, type_=xso.String(), *[, options=[]][, required=False][, desc=None][, label=None])

.. currentmodule:: aioxmpp.forms

.. _api-aioxmpp.forms-bound-fields:

Bound fields
============

Bound fields are objects which are returned when the descriptor attribute is
accessed on a form instance. It holds the value of the field, as well as
overrides for the default (specified on the descriptors themselves) values for
certain attributes (such as :attr:`~.AbstractField.desc`).

For the different field types, there are different classes of bound fields,
which are documented below.

.. currentmodule:: aioxmpp.forms.fields

.. autoclass:: BoundField

.. autoclass:: BoundSingleValueField

.. autoclass:: BoundMultiValueField

.. autoclass:: BoundOptionsField

.. autoclass:: BoundSelectField

.. autoclass:: BoundMultiSelectField

.. currentmodule:: aioxmpp.forms

XSOs
====

.. autoclass:: Data

.. autoclass:: DataType

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
    DataType,
    Field,
    FieldType,
    Reported,
    Item,
)

from .fields import (  # NOQA
    Boolean,
    ListSingle,
    ListMulti,
    JIDSingle,
    JIDMulti,
    TextSingle,
    TextMulti,
    TextPrivate,
)

from .form import (  # NOQA
    Form,
)
