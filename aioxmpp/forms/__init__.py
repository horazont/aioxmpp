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

Attributes added to stanzas
===========================

:mod:`aioxmpp.forms` adds the following attributes to stanzas:

.. attribute:: aioxmpp.Message.xep0004_data

   A sequence of :class:`Data` instances. This is used for example by the
   :mod:`~.muc` implementation (:xep:`45`).

   .. versionadded:: 0.8


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

"""  # NOQA: E501


from . import xso  # NOQA: F401

from .xso import (  # NOQA: F401
    Data,
    DataType,
    Field,
    FieldType,
    Reported,
    Item,
)

from .fields import (  # NOQA: F401
    Boolean,
    ListSingle,
    ListMulti,
    JIDSingle,
    JIDMulti,
    TextSingle,
    TextMulti,
    TextPrivate,
)

from .form import (  # NOQA: F401
    Form,
)
