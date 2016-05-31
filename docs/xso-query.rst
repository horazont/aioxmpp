"""
XSO Query Language
##################

Motivation
==========

In several situations, we want to have the ability to register callbacks for
only a subset of events. These events can generally be filtered with a
predicate.

It is inconvenient to write a filter function for each possible required
situation; even filter function templates get cumbersome at some point.

Syntax Draft
============

This is largely inspired by the syntax and semantics commonly found in ORMs. We
will have a less powerful expression language I’m afraid, but let’s see what we
can do::

  Message.from_ == "fnord",
  pubsub_xso.Event @ Message.xep0060_event,
  pubsub_xso.EventItems @ pubsub_xso.Event.payload,
  pubsub_xso.EventItems.node == "foo",

The ``@`` operator extracts an object of the LHS class from the descriptor on
the RHS. In subsequent statements, references to descriptors on that class refer
to the object extracted on the most recent extract having the class on the LHS.

The other operators work as normal.

Alternative::

  Message.from_ == "fnord",
  (Message.xep0060_event / pubsub_xso.Event.payload / pubsub_xso.EventItems.node
      == "foo"),

The difficulty with this implementation is that we need a way to recover the
class to which the descriptor is bound from the descriptor. This requires either
a complete rewrite of the XSO module or a proxy which is returned when accessing
the descriptor via the class.

The proxy essentially breaks the isinstance checks we have throughout the test
code. The same would happen with a re-write though.

Specification
=============


``<expr> / <class>``
   Return all instances of `class` from the result set of `expr`

``<expr> / <descriptor bound to class>``
   Return the union of the values of `descriptor` on all `class` instances
   found in the result set of `expr`.

``<expr> / <unbound descriptor>`` (undetermined)
   Return the union of the values of `descriptor` on all instances in the
   result set of `expr` whose class has the `descriptor`.

   Whether this semantic will be implemented is not determined yet.

``<expr ending on descriptor>[constant]``
   If `descriptor` is a mapping, return the union of the values with key
   `constant` from the maps in `expr`.

``<expr>[integer constant]``
   Return the n-th element from the result set of expr

``<expr>[where(subexpr)]``
   Filter the result set of `expr`, excluding all elements where `subexpr` does
   not evaluate to a true value.

Note that in the query language, ``[]`` binds less strong than ``/``. To
implement this, we will have to do some magic, but it should be implementable.

"""
