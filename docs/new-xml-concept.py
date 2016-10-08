########################################################################
# File name: new-xml-concept.py
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
New XML concept
===============

The idea is to have stanza classes describe what their contents shall be and how
these are serialized/deserialized to/from XML.

.. class:: StanzaModel.Attr(name=<autodected>,
                            type_=StanzaModel.String,
                            required=False,
                            restrict=None,
                            default=None)

   *required* must be either a :data:`bool` or a callable taking one
   argument. If it is a callable, during validation, it is passed the instance
   which is currently being validated. The instance has been fully populated at
   that time, but not yet validated. The callable shall return a boolean value
   indicating whether the attribute is required or not.

   *type_* must be a :class:`StanzaModel.Type`. It is used to parse the string
   contents of the attribute and convert it to a python type. To impose
   additional restrictions on the type, use the *restrict* argument.

   *restrict* must be a :class:`StanzaModel.Restriction` or :data:`None`, which
   is used to *validate* the value extracted using the *type_* object. Passing
   :data:`None` indicates that all values which are accepted by the *type_* are
   valid.

   *default* is used if the attribute is absent and *required* evaluates to
   :data:`False`. *default* is not checked against either the *type_* or the
   *restrict* objects.

.. class:: StanzaModel.Child(match="*",
                             n=1,
                             required=False)

   *required* works as in :class:`StanzaModel.Attr`.

   *n* must be either a positive integer (indicating the exact amount of
   elements which may occur) or a tuple of two positive integers. If it is a
   tuple, the first value may also be ``0`` and the second value may be
   :data:`None`, in which case no upper bound is specified.

   *match* must be either a string expression which can be used with
   :meth:`lxml.etree._Element.iterchildren` or a :class:`StanzaObject`
   class. In the latter case, the :attr:`StanzaObject.TAG` attribute is used as
   a matcher. It restricts the set of elements to be considered for this
   attribute.

   If *n* is a tuple or not equal to ``1``, the elements are stored in a
   list. Otherwise, the element must be accessible directly.

.. class:: StanzaModel.Text(type_=StanzaModel.String,
                            required=False,
                            restrict=None,
                            default=None)

   All arguments work like those applying to :class:`StanzaModel.Attr`.

.. note::

   Mixing :class:`StanzaModel.Text` and :class:`StanzaModel.Child` descriptors
   on the same :class:`StanzaObject` won’t end well. The semantics of
   :class:`StanzaModel.Text` is undefined in that case.

"""

class IQ(metaclass=StanzaObject):
    TAG = "{jabber:client}iq"

    type_ = xml_attr(
        name="type",
        type_=StanzaModel.enum("set", "get", "error", "result"),
        required=True
    )

    data = xml_child(
        match="*",
        n=1,
        required=lambda instance: instance.type_ in {"set", "get"}
    )
