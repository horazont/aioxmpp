########################################################################
# File name: xso.py
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
import collections
import enum

import aioxmpp
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0004_data = "jabber:x:data"


class Value(xso.XSO):
    TAG = (namespaces.xep0004_data, "value")

    value = xso.Text(default="")


class ValueElement(xso.AbstractElementType):
    def unpack(self, item):
        return item.value

    def pack(self, value):
        v = Value()
        v.value = value
        return v

    def get_xso_types(self):
        return [Value]


class Option(xso.XSO):
    TAG = (namespaces.xep0004_data, "option")

    label = xso.Attr(
        tag="label",
        default=None,
    )

    value = xso.ChildText(
        (namespaces.xep0004_data, "value"),
        default=None,
    )

    def validate(self):
        if self.value is None:
            raise ValueError("option is missing a value")


class OptionElement(xso.AbstractElementType):
    def unpack(self, item):
        return (item.value, item.label)

    def pack(self, value):
        value, label = value
        o = Option()
        o.value = value
        o.label = label
        return o

    def get_xso_types(self):
        return [Option]


class FieldType(enum.Enum):
    """
    Enumeration containing the field types defined in :xep:`4`.

    .. seealso::

       :attr:`Field.values`
          for important information regarding typing, restrictions, validation
          and constraints of values in that attribute.

    Each type has the following attributes and methods:

    .. automethod:: allow_upcast

    .. autoattribute:: has_options

    .. autoattribute:: is_multivalued

    Quotations in the following attribute descriptions are from said XEP.

    .. attribute:: BOOLEAN

       The ``"boolean"`` field:

          The field enables an entity to gather or provide an either-or choice
          between two options. The default value is "false".

       The :attr:`Field.values` sequence should contain zero or one elements.
       If it contains an element, it must be ``"0"``, ``"1"``, ``"false"``, or
       ``"true"``, in accordance with the XML Schema documents.

    .. attribute:: FIXED

       The ``"fixed"`` field:

          The field is intended for data description (e.g., human-readable text
          such as "section" headers) rather than data gathering or provision.
          The <value/> child SHOULD NOT contain newlines (the ``\\n`` and
          ``\\r`` characters); instead an application SHOULD generate multiple
          fixed fields, each with one <value/> child.

       As such, the :attr:`Field.values` sequence should contain exactly one
       element. :attr:`Field.desc`, :attr:`Field.label`, :attr:`Field.options`
       and :attr:`Field.var` should be set to :data:`None` or empty containers.

    .. attribute:: HIDDEN

       The ``"hidden"`` field:

          The field is not shown to the form-submitting entity, but instead is
          returned with the form. The form-submitting entity SHOULD NOT modify
          the value of a hidden field, but MAY do so if such behavior is
          defined for the "using protocol".

       This type is commonly used for the ``var="FORM_TYPE"`` field, as
       specified in :xep:`68`.

    .. attribute:: JID_MULTI

       The ``"jid-multi"`` field:

          The field enables an entity to gather or provide multiple Jabber IDs.
          Each provided JID SHOULD be unique (as determined by comparison that
          includes application of the Nodeprep, Nameprep, and Resourceprep
          profiles of Stringprep as specified in XMPP Core), and duplicate JIDs
          MUST be ignored.

       As such, the :attr:`Field.values` sequence should contain zero or more
       strings representing Jabber IDs. :attr:`Field.options` should be empty.

    .. attribute:: JID_SINGLE

       The ``"jid-single"`` field:

          The field enables an entity to gather or provide a single Jabber ID.

       As such, the :attr:`Field.values` sequence should contain zero or one
       string representing a Jabber ID. :attr:`Field.options` should be empty.

    .. attribute:: LIST_MULTI

       The ``"list-multi"`` field:

          The field enables an entity to gather or provide one or more options
          from among many. A form-submitting entity chooses one or more items
          from among the options presented by the form-processing entity and
          MUST NOT insert new options. The form-submitting entity MUST NOT
          modify the order of items as received from the form-processing
          entity, since the order of items MAY be significant.

       Thus, :attr:`Field.values` should contain a subset of the keys of the
       :class:`Field.options` dictionary.

    .. attribute:: LIST_SINGLE

       The ``"list-single"`` field:

          The field enables an entity to gather or provide one option from
          among many. A form-submitting entity chooses one item from among the
          options presented by the form-processing entity and MUST NOT insert
          new options.

       Thus, :attr:`Field.values` should contain a zero or one of the keys of
       the :class:`Field.options` dictionary.

    .. attribute:: TEXT_MULTI

       The ``"text-multi"`` field:

          The field enables an entity to gather or provide multiple lines of
          text.

       Each string in the :attr:`Field.values` attribute should be a single
       line of text. Newlines are not allowed in data forms fields (due to the
       ambiguity between ``\\r`` and ``\\n`` and combinations thereof), which
       is why the text is split on the line endings.

    .. attribute:: TEXT_PRIVATE

       The ``"text-private"`` field:

          The field enables an entity to gather or provide a single line or
          word of text, which shall be obscured in an interface (e.g., with
          multiple instances of the asterisk character).

       The :attr:`Field.values` attribute should contain zero or one string
       without any newlines.

    .. attribute:: TEXT_SINGLE

       The ``"text-single"`` field:

          The field enables an entity to gather or provide a single line or
          word of text, which may be shown in an interface. This field type is
          the default and MUST be assumed if a form-submitting entity receives
          a field type it does not understand.

       The :attr:`Field.values` attribute should contain zero or one string
       without any newlines.

    """

    FIXED = "fixed"
    HIDDEN = "hidden"
    BOOLEAN = "boolean"
    TEXT_SINGLE = "text-single"
    TEXT_MULTI = "text-multi"
    TEXT_PRIVATE = "text-private"
    LIST_SINGLE = "list-single"
    LIST_MULTI = "list-multi"
    JID_SINGLE = "jid-single"
    JID_MULTI = "jid-multi"

    @property
    def has_options(self):
        """
        true for the ``list-`` field types, false otherwise.
        """
        return self.value.startswith("list-")

    @property
    def is_multivalued(self):
        """
        true for the ``-multi`` field types, false otherwise.
        """
        return self.value.endswith("-multi")

    def allow_upcast(self, to):
        """
        Return true if the field type may be upcast to the other field type
        `to`.

        This relation specifies when it is safe to transfer data from this
        field type to the given other field type `to`.

        This is the case if any of the following holds true:

        * `to` is equal to this type
        * this type is :attr:`TEXT_SINGLE` and `to` is :attr:`TEXT_PRIVATE`
        """

        if self == to:
            return True
        if self == FieldType.TEXT_SINGLE and to == FieldType.TEXT_PRIVATE:
            return True
        return False


class Field(xso.XSO):
    """
    Represent a single field in a Data Form.

    :param type_: Field type, must be one of the valid field types specified in
                  :xep:`4`.
    :type type_: :class:`FieldType`
    :param options: A mapping of values to labels defining the options in a
                    ``list-*`` field.
    :type options: :class:`dict` mapping :class:`str` to :class:`str`
    :param values: A sequence of values currently given for the field. Having
                   more than one value is only valid in ``*-multi`` fields.
    :type values: :class:`list` of :class:`str`
    :param desc: Description which can be shown in a tool-tip or similar,
                 without newlines.
    :type desc: :class:`str` or :data:`None`
    :param label: Human-readable label to be shown next to the field input
    :type label: :class:`str` or :data:`None`
    :param required: Flag to indicate that the field is required
    :type required: :class:`bool`
    :param var: "ID" identifying the field uniquely inside the form. Only
                required for fields carrying a meaning (thus, not for
                ``fixed``).
    :type var: :class:`str` or :data:`None`

    The semantics of a :class:`Field` are different depending on where it
    occurs: in a :class:`Data`, it is a form field to be filled in, in a
    :class:`Item` it is a cell of a row and in a :class:`Reported` it
    represents a column header.

    .. attribute:: required

       A boolean flag indicating whether the field is required.

       If true, the XML serialisation will contain the corresponding
       ``<required/>`` tag.

    .. attribute:: desc

       Single line of description for the field. This attribute represents the
       ``<desc/>`` element from :xep:`4`.

    .. attribute:: values

       A sequence of strings representing the ``<value/>`` elements of the
       field, one string for each value.

       .. note::

          Since the requirements on the sequence of strings in :attr:`values`
          change depending on the :attr:`type_` attribute, validation and type
          conversion on assignment is very lax. The attribute accepts all
          sequences of strings, even if the field is for example a
          :attr:`FieldType.BOOLEAN` field, which allows for at most one string
          of a well-defined format (see the documentation there for the
          details).

          This makes it easy to inadvertendly generate invalid forms, which is
          why you should be using :class:`Form` subclasses when accessing forms
          from within normal code and some other, generic mechanism taking care
          of these details when showing forms in a UI framework to users. Note
          that devising such a mechanism is out of scope for :mod:`aioxmpp`, as
          every UI framework has different requirements.

    .. attribute:: options

       A dictionary mapping values to human-readable labels, representing the
       ``<option/>`` elements of the field.

    .. attribute:: var

       The uniquely identifying string of the (valued, that is,
       non-:attr:`FieldType.FIXED` field). Represents the ``var`` attribute of
       the field.

    .. attribute:: type_

       The type of the field. The :attr:`type_` must be a :class:`FieldType`
       enumeration value and determines restrictions and constraints on other
       attributes. See the :class:`FieldType` enumeration and :xep:`4` for
       details.

    .. attribute:: label

       The human-readable label for the field, representing the ``label``
       attribute of the field. May be :data:`None` if the label is omitted.

    """

    TAG = (namespaces.xep0004_data, "field")

    required = xso.ChildFlag(
        (namespaces.xep0004_data, "required"),
    )

    desc = xso.ChildText(
        (namespaces.xep0004_data, "desc"),
        default=None
    )

    values = xso.ChildValueList(
        type_=ValueElement()
    )

    options = xso.ChildValueMap(
        type_=OptionElement(),
        mapping_type=collections.OrderedDict,
    )

    var = xso.Attr(
        (None, "var"),
        default=None
    )

    type_ = xso.Attr(
        (None, "type"),
        type_=xso.EnumCDataType(
            FieldType,
        ),
        default=None,
    )

    label = xso.Attr(
        (None, "label"),
        default=None
    )

    def __init__(self, *,
                 type_=FieldType.TEXT_SINGLE,
                 options={},
                 values=[],
                 desc=None,
                 label=None,
                 required=False,
                 var=None):
        super().__init__()
        self.type_ = type_
        self.options.update(options)
        self.values[:] = values
        self.desc = desc
        self.label = label
        self.required = required
        self.var = var

    def validate(self):
        super().validate()

        if self.type_ != FieldType.FIXED and not self.var:
            raise ValueError("missing attribute var")

        if self.type_ is not None:
            if not self.type_.has_options and self.options:
                raise ValueError("unexpected option on non-list field")

            if not self.type_.is_multivalued and len(self.values) > 1:
                raise ValueError("too many values on non-multi field")

        values_list = [opt for opt in self.options.values() if opt is not None]
        values_set = set(values_list)

        if len(values_list) != len(values_set):
            raise ValueError("duplicate option label in {}".format(
                values_list
            ))


class AbstractItem(xso.XSO):
    fields = xso.ChildList([Field])


class Item(AbstractItem):
    """
    A single row in a report :class:`Data` object.

    .. attribute:: fields

       A sequence of :class:`Field` objects representing the cells of the row.
    """

    TAG = (namespaces.xep0004_data, "item")


class Reported(AbstractItem):
    """
    The table heading of a report :class:`Data` object.

    .. attribute:: fields

       A sequence of :class:`Field` objects representing the columns of the
       report or table.

    """

    TAG = (namespaces.xep0004_data, "reported")


class Instructions(xso.XSO):
    TAG = (namespaces.xep0004_data, "instructions")

    value = xso.Text(default="")


class InstructionsElement(xso.AbstractElementType):
    def unpack(self, item):
        return item.value

    def pack(self, value):
        v = Instructions()
        v.value = value
        return v

    def get_xso_types(self):
        return [Instructions]


class DataType(enum.Enum):
    """
    Enumeration containing the :class:`Data` types defined in :xep:`4`.

    Quotations in the following attribute descriptions are from :xep:`4`.

    .. attribute:: FORM

       The ``"form"`` type:

         The form-processing entity is asking the form-submitting entity to
         complete a form.

    .. attribute:: SUBMIT

       The ``"submit"`` type:

         The form-submitting entity is submitting data to the form-processing
         entity. The submission MAY include fields that were not provided in
         the empty form, but the form-processing entity MUST ignore any fields
         that it does not understand.

    .. attribute:: CANCEL

       The ``"cancel"`` type:

         The form-submitting entity has cancelled submission of data to the
         form-processing entity.

    .. attribute:: RESULT

       The ``"result"`` type:

         The form-processing entity is returning data (e.g., search results) to
         the form-submitting entity, or the data is a generic data set.
    """
    FORM = "form"
    SUBMIT = "submit"
    RESULT = "result"
    CANCEL = "cancel"


class Data(AbstractItem):
    """
    A :xep:`4` ``x`` element, that is, a Data Form.

    :param type_: Initial value for the :attr:`type_` attribute.

    .. attribute:: type_

       The ``type`` attribute of the form, represented by one of the members of
       the :class:`DataType` enumeration.

    .. attribute:: title

       The (optional) title of the form. Either a :class:`str` or :data:`None`.

    .. attribute:: instructions

       A sequence of strings which represent the instructions elements on the
       form.

    .. attribute:: fields

       If the :class:`Data` is a form, this is a sequence of :class:`Field`
       elements which represent the fields to be filled in.

       This does not make sense on :attr:`.DataType.RESULT` typed objects.

    .. attribute:: items

       If the :class:`Data` is a table, this is a sequence of :class:`Item`
       instances which represent the table rows.

       This only makes sense on :attr:`.DataType.RESULT` typed objects.

    .. attribute:: reported

       If the :class:`Data` is a table, this is a :class:`Reported` object
       representing the table header.

       This only makes sense on :attr:`.DataType.RESULT` typed objects.

    .. automethod:: get_form_type
    """

    TAG = (namespaces.xep0004_data, "x")

    type_ = xso.Attr(
        "type",
        type_=xso.EnumCDataType(DataType)
    )

    title = xso.ChildText(
        (namespaces.xep0004_data, "title"),
        default=None,
    )

    instructions = xso.ChildValueList(
        type_=InstructionsElement()
    )

    items = xso.ChildList([Item])

    reported = xso.Child([Reported], required=False)

    def __init__(self, type_):
        super().__init__()
        self.type_ = type_

    def _validate_result(self):
        if self.fields:
            raise ValueError("field in report result")

        fieldvars = {field.var for field in self.reported.fields}

        if not fieldvars:
            raise ValueError("empty report header")

        for item in self.items:
            itemvars = {field.var for field in item.fields}
            if itemvars != fieldvars:
                raise ValueError("field mismatch between row and header")

    def validate(self):
        super().validate()

        if (self.type_ != DataType.RESULT and
                (self.reported is not None or self.items)):
            raise ValueError("report in non-result")

        if (self.type_ == DataType.RESULT and
                (self.reported is not None or self.items)):
            self._validate_result()

    def get_form_type(self):
        """
        Extract the ``FORM_TYPE`` from the fields.

        :return: ``FORM_TYPE`` value or :data:`None`
        :rtype: :class:`str` or :data:`None`

        Return :data:`None` if no well-formed ``FORM_TYPE`` field is found in
        the list of fields.

        .. versionadded:: 0.8
        """

        for field in self.fields:
            if field.var == "FORM_TYPE" and field.type_ == FieldType.HIDDEN:
                if len(field.values) != 1:
                    return None
                return field.values[0]


aioxmpp.Message.xep0004_data = xso.ChildList([Data])
