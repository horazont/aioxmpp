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
:mod:`~aioxmpp.xso` --- Working with XML stream contents
########################################################

This subpackage deals with **X**\\ ML **S**\\ tream **O**\\ bjects. XSOs can be
stanzas, but in general any XML.

The facilities in this subpackage are supposed to help developers of XEP
plugins, as well as the main development of :mod:`aioxmpp`. The subpackage
is split in two parts, :mod:`aioxmpp.xso.model`, which provides facilities to
allow declarative-style parsing and un-parsing of XML subtrees into XSOs and
the :mod:`aioxmpp.xso.types` module, which provides classes which implement
validators and type parsers for content represented as strings in XML.


Introduction
============

.. seealso::

    For a more in-depth introduction into :mod:`aioxmpp.xso`, please refer to
    the :ref:`ug-introduction-to-xso` chapter in the user guide. This document
    here is a reference manual.

The :mod:`aioxmpp.xso` subpackage provides declarative-style parsing of XML
document fragments. The declarations are similar to what you might know from
declarative Object-Relational-Mappers such as :mod:`sqlalchemy`. Due to the
different data model of XML and relational databases, they are not identical
of course.

An abstract class describing the common properties of an XMPP stanza might
look like this:

.. code:: python

    class Stanza(xso.XSO):
        from_ = xso.Attr(tag="from", type_=xso.JID(), default=None)
        to = xso.Attr(tag="to", type_=xso.JID(), default=None)
        lang = xso.LangAttr(tag=(namespaces.xml, "lang"))


Instances of classes deriving from :class:`aioxmpp.xso.XSO` are called XML
stream objects, or XSOs for short. Each XSO maps to an XML element node.

The declaration of an XSO class typically has one or more
:term:`descriptors <descriptor>` describing the mapping of XML child nodes of
the element. XML nodes which can be mapped include attributes, text and
elements (processing instructions and comments are not supported; CDATA
sections are treated like text).


XSO-specific Terminology
========================

Definition of an XSO
--------------------

An XSO is an object whose class inherits from
:class:`aioxmpp.xso.XSO`.

A word on tags
--------------

Tags, as used by etree, are used throughout this module. Note that we are
representing tags as tuples of ``(namespace_uri, localname)``, where
``namespace_uri`` may be :data:`None`.

.. seealso::

   The functions :func:`normalize_tag` and :func:`tag_to_str` are useful to
   convert from and to ElementTree compatible strings.


XML stream events
-----------------

XSOs are parsed using SAX-like events. This allows them to be built one-by-one
in memory (and discarded) even while the XML stream is in progress.

The XSO module uses a subset of the original SAX event list, and it uses a
custom format. The reason for that is that instead of using an interface with
methods, the parsing parts are implemented using suspendable functions (see
below).


Suspendable functions
---------------------

This module uses suspendable functions, implemented as generators, at several
points. These may also be called coroutines, but have nothing to do with
coroutines as used by :mod:`asyncio`, which is why we will call them
suspendable functions here.

Suspendable functions possibly take arguments and then operate on input which
is fed to them in a push-manner step by step (using the
:meth:`~types.GeneratorType.send` method). The main usage in this module is to
process XML stream events: The SAX events are processed step-by-step by the functions,
and when the event is fully processed, it suspends itself (using ``yield``)
until the next event is sent into it.

General functions
=================

.. autofunction:: normalize_tag

.. autofunction:: tag_to_str

.. module:: aioxmpp.xso.model

.. currentmodule:: aioxmpp.xso

Object declaration with :mod:`aioxmpp.xso.model`
================================================

This module provides facilities to create classes which map to full XML stream
subtrees (for example stanzas including payload).

To create such a class, derive from :class:`XSO` and provide attributes
using the :class:`Attr`, :class:`Text`, :class:`Child` and :class:`ChildList`
descriptors.

Descriptors for XML-sourced attributes
--------------------------------------

.. autosummary::

    Attr
    LangAttr
    Text
    Child
    ChildTag
    ChildFlag
    ChildText
    ChildTextMap
    ChildValue
    ChildList
    ChildMap
    ChildLangMap
    ChildValueList
    ChildValueMap
    ChildValueMultiMap
    Collector

The following descriptors can be used to load XSO attributes from XML. There
are two fundamentally different descriptor types: *scalar* and *non-scalar*
(e.g. list) descriptors. Assignment to the descriptor attribute is
strictly type-checked for *scalar* descriptors.

Scalar descriptors
^^^^^^^^^^^^^^^^^^

Many of the arguments and attributes used for the scalar descriptors are
similar. They are described in detail on the :class:`Attr` class and not
repeated that detailed on the other classes. Refer to the documentation of the
:class:`Attr` class in those cases.

.. autoclass:: Attr(name, *[, type_=xso.String()][, validator=None][, validate=ValidateMode.FROM_RECV][, missing=None][, default][, erroneous_as_absent=False])

.. autoclass:: LangAttr(*[, validator=None][, validate=ValidateMode.FROM_RECV][, default=None])

.. autoclass:: Child(classes, *[, required=False][, strict=False])

.. autoclass:: ChildTag(tags, *[, text_policy=UnknownTextPolicy.FAIL][, child_policy=UnknownChildPolicy.FAIL][, attr_policy=UnknownAttrPolicy.FAIL][, default_ns=None][, allow_none=False])

.. autoclass:: ChildFlag(tag, *[, text_policy=UnknownTextPolicy.FAIL][, child_policy=UnknownChildPolicy.FAIL][, attr_policy=UnknownAttrPolicy.FAIL])

.. autoclass:: ChildText(tag, *[, child_policy=UnknownChildPolicy.FAIL][, attr_policy=UnknownAttrPolicy.FAIL][, type_=xso.String()][, validator=None][, validate=ValidateMode.FROM_RECV][, default][, erroneous_as_absent=False])

.. autoclass:: ChildValue(type_)

.. autoclass:: Text(*[, type_=xso.String()][, validator=None][, validate=ValidateMode.FROM_RECV][, default][, erroneous_as_absent=False])

Non-scalar descriptors
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: ChildList(classes)

.. autoclass:: ChildMap(classes[, key=None])

.. autoclass:: ChildLangMap(classes)

.. autoclass:: ChildValueList(type_)

.. autoclass:: ChildValueMap(type_, *, mapping_type=dict)

.. autoclass:: ChildValueMultiMap(type_, *, mapping_type=multidict.MultiDict)

.. autoclass:: ChildTextMap(xso_type)

.. autoclass:: Collector()

Container for child lists
^^^^^^^^^^^^^^^^^^^^^^^^^

The child lists in :class:`ChildList`, :class:`ChildMap` and
:class:`ChildLangMap` descriptors use a specialized list-subclass which
provides advanced capabilities for filtering :class:`XSO` objects.

.. currentmodule:: aioxmpp.xso.model

.. autoclass:: XSOList

.. currentmodule:: aioxmpp.xso


Parsing XSOs
------------

To parse XSOs, an asynchronous approach which uses SAX-like events is
followed. For this, the suspendable functions explained earlier are used. The
main class to parse a XSO from events is :class:`XSOParser`. To drive
that suspendable callable from SAX events, use a :class:`SAXDriver`.

.. autoclass:: XSOParser

.. autoclass:: SAXDriver

Base and meta class
-------------------

The :class:`XSO` base class makes use of the :class:`model.XMLStreamClass`
metaclass and provides implementations for utility methods. For an object to
work with this module, it must derive from :class:`XSO` or provide an
identical interface.

.. autoclass:: XSO()

.. autoclass:: CapturingXSO()

The metaclass takes care of collecting the special descriptors in attributes
where they can be used by the SAX event interpreter to fill the class with
data. It also provides a class method for late registration of child classes.

.. currentmodule:: aioxmpp.xso.model

.. autoclass:: XMLStreamClass

.. currentmodule:: aioxmpp.xso

To create an enumeration of XSO classes, the following mixin can be used:

.. autoclass:: XSOEnumMixin

Functions, enumerations and exceptions
--------------------------------------

The values of the following enumerations are used on "magic" attributes of
:class:`XMLStreamClass` instances (i.e. classes).

.. autoclass:: UnknownChildPolicy

.. autoclass:: UnknownAttrPolicy

.. autoclass:: UnknownTextPolicy

.. autoclass:: ValidateMode

The following exceptions are generated at some places in this module:

.. autoclass:: UnknownTopLevelTag

The following special value is used to indicate that no default is used with a
descriptor:

.. data:: NO_DEFAULT

   This is a special value which is used to indicate that no defaulting should
   take place. It can be passed to the `default` arguments of descriptors, and
   usually is the default value of these arguments.

   It compares unequal to everything but itself, does not support ordering,
   conversion to bool, float or integer.

.. autofunction:: capture_events

.. autofunction:: events_to_sax

Handlers for missing attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: lang_attr

.. module:: aioxmpp.xso.types

.. currentmodule:: aioxmpp.xso

Types and validators from :mod:`~aioxmpp.xso.types`
===================================================

This module provides classes whose objects can be used as types and validators
in :mod:`~aioxmpp.xso.model`.

Character Data types
--------------------

.. autosummary::

    String
    Float
    Integer
    Bool
    DateTime
    Date
    Time
    Base64Binary
    HexBinary
    JID
    ConnectionLocation
    LanguageTag
    JSON
    EnumCDataType

These types describe character data, i.e. text in XML. Thus, they can be used
with :class:`Attr`, :class:`Text` and similar descriptors. They are used to
deserialise XML character data to python values, such as integers or dates and
vice versa. These types inherit from :class:`AbstractCDataType`.

.. autoclass:: String

.. autoclass:: Float

.. autoclass:: Integer

.. autoclass:: Bool

.. autoclass:: DateTime

.. autoclass:: Date

.. autoclass:: Time

.. autoclass:: Base64Binary

.. autoclass:: HexBinary

.. autoclass:: JID

.. autoclass:: ConnectionLocation

.. autoclass:: LanguageTag

.. autoclass:: JSON

.. autoclass:: EnumCDataType(enum_class, nested_type=xso.String(), *, allow_coerce=False, deprecate_coerce=False, allow_unknown=True, accept_unknown=True)

.. autofunction:: EnumType(enum_class[, nested_type], *, allow_coerce=False, deprecate_coerce=False, allow_unknown=True, accept_unknown=True)

.. autoclass:: Unknown

Element types
-------------

.. autosummary::

    EnumElementType
    TextChildMap

These types describe structured XML data, i.e. subtrees. Thus, they can be used
with the :class:`ChildValueList` and :class:`ChildValueMap` family of
descriptors (which represent XSOs as python values). These types inherit from
:class:`AbstractElementType`.

.. autoclass:: EnumElementType

.. autoclass:: TextChildMap

Defining custom types
---------------------

.. autoclass:: AbstractCDataType

.. autoclass:: AbstractElementType

Validators
----------

Validators validate the python values after they have been parsed from
XML-sourced strings or even when being assigned to a descriptor attribute
(depending on the choice in the `validate` argument).

They can be useful both for defending and rejecting incorrect input and to
avoid producing incorrect output.

The basic validator interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: AbstractValidator

Implementations
^^^^^^^^^^^^^^^

.. autoclass:: RestrictToSet

.. autoclass:: Nmtoken

.. autoclass:: IsInstance

.. autoclass:: NumericRange

.. module:: aioxmpp.xso.query

.. currentmodule:: aioxmpp.xso

Querying data from XSOs
=======================

With XML, we have XPath as query language to retrieve data from XML trees. With
XSOs, we have :mod:`aioxmpp.xso.query`, even though it’s not as powerful as
XPath.

Syntactically, it’s oriented on XPath. Consider the following XSO classes:

.. code-block:: python

    class FooXSO(xso.XSO):
        TAG = (None, "foo")

        attr = xso.Attr(
            "attr"
        )


    class BarXSO(xso.XSO):
        TAG = (None, "bar")

        child = xso.Child([
            FooXSO,
        ])


    class BazXSO(FooXSO):
        TAG = (None, "baz")

        attr2 = xso.Attr(
            "attr2"
        )


    class RootXSO(xso.XSO):
        TAG = (None, "root")

        children = xso.ChildList([
            FooXSO,
            BarXSO,
        ])

        attr = xso.Attr(
            "attr"
        )


To perform a query, we first need to set up a
:class:`.query.EvaluationContext`:

.. code-block:: python

   root_xso = # a RootXSO instance
   ec = xso.query.EvaluationContext()
   ec.set_toplevel_object(root_xso)

Using the context, we can now execute queries:

.. code-block:: python

   # to find all FooXSO children of the RootXSO
   ec.eval(RootXSO.children / FooXSO)

   # to find all BarXSO children of the RootXSO
   ec.eval(RootXSO.children / BarXSO)

   # to find all FooXSO children of the RootXSO, where FooXSO.attr
   # is set
   ec.eval(RootXSO.children / FooXSO[where(FooXSO.attr)])

   # to find all FooXSO children of the RootXSO, where FooXSO.attr
   # is *not* set
   ec.eval(RootXSO.children / FooXSO[where(not FooXSO.attr)])

   # to find all FooXSO children of the RootXSO, where FooXSO.attr
   # is set to "foobar"
   ec.eval(RootXSO.children / FooXSO[where(FooXSO.attr == "foobar")])

   # to test whether there is a FooXSO which has attr set to
   # "foobar"
   ec.eval(RootXSO.children / FooXSO.attr == "foobar")

   # to find the first three FooXSO children where attr is set
   ec.eval(RootXSO.children / FooXSO[where(FooXSO.attr)][:3])

The following operators are available in the :mod:`aioxmpp.xso` namespace:

.. autoclass:: where

.. autofunction:: not_

The following need to be explicitly sourced from :mod:`aioxmpp.xso.query`, as
they are rarely used directly in user code.

.. currentmodule:: aioxmpp.xso.query

.. autoclass:: EvaluationContext()

.. note::

   The implementation details of the query language are documented in the
   source. They are not useful unless you want to implement custom query
   operators, which is not possible without modifying the
   :mod:`aioxmpp.xso.query` source anyways.

.. currentmodule:: aioxmpp.xso

Predefined XSO base classes
===========================

Some patterns reoccur when using this subpackage. For these, base classes are
provided which facilitate the use.

.. autoclass:: AbstractTextChild


"""  # NOQA: E501


def tag_to_str(tag):
    """
    `tag` must be a tuple ``(namespace_uri, localname)``. Return a tag string
    conforming to the ElementTree specification. Example::

         tag_to_str(("jabber:client", "iq")) == "{jabber:client}iq"
    """
    return "{{{:s}}}{:s}".format(*tag) if tag[0] else tag[1]


def normalize_tag(tag):
    """
    Normalize an XML element tree `tag` into the tuple format. The following
    input formats are accepted:

    * ElementTree namespaced string, e.g. ``{uri:bar}foo``
    * Unnamespaced tags, e.g. ``foo``
    * Two-tuples consisting of `namespace_uri` and `localpart`; `namespace_uri`
      may be :data:`None` if the tag is supposed to be namespaceless. Otherwise
      it must be, like `localpart`, a :class:`str`.

    Return a two-tuple consisting the ``(namespace_uri, localpart)`` format.
    """
    if isinstance(tag, str):
        namespace_uri, sep, localname = tag.partition("}")
        if sep:
            if not namespace_uri.startswith("{"):
                raise ValueError("not a valid etree-format tag")
            namespace_uri = namespace_uri[1:]
        else:
            localname = namespace_uri
            namespace_uri = None
        return (namespace_uri, localname)
    elif len(tag) != 2:
        raise ValueError("not a valid tuple-format tag")
    else:
        if any(part is not None and not isinstance(part, str) for part in tag):
            raise TypeError("tuple-format tags must only contain str and None")
        if tag[1] is None:
            raise ValueError("tuple-format localname must not be None")
    return tag


from .types import (  # NOQA: F401
    Unknown,
    AbstractCDataType,
    AbstractElementType,
    String,
    Integer,
    Float,
    Bool,
    DateTime,
    Date,
    Time,
    Base64Binary,
    HexBinary,
    JID,
    ConnectionLocation,
    LanguageTag,
    JSON,
    TextChildMap,
    EnumType,
    EnumCDataType,
    EnumElementType,
    AbstractValidator,
    RestrictToSet,
    Nmtoken,
    IsInstance,
    NumericRange,
)

from .model import (  # NOQA: F401
    UnknownChildPolicy,
    UnknownAttrPolicy,
    UnknownTextPolicy,
    ValidateMode,
    UnknownTopLevelTag,
    Attr,
    LangAttr,
    ChildValue,
    Child,
    ChildFlag,
    ChildList,
    ChildLangMap,
    ChildMap,
    ChildTag,
    ChildText,
    Collector,
    Text,
    ChildValueList,
    ChildValueMap,
    ChildValueMultiMap,
    ChildTextMap,
    XSOParser,
    SAXDriver,
    XSO,
    XSOEnumMixin,
    CapturingXSO,
    lang_attr,
    capture_events,
    events_to_sax,
    AbstractTextChild,
)


from .model import _PropBase  # NOQA: E402
NO_DEFAULT = _PropBase.NO_DEFAULT
del _PropBase


from .query import (  # NOQA: F401
    where,
    not_,
)
