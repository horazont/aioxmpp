########################################################################
# File name: fields.py
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
import abc
import collections
import copy

import aioxmpp.xso as xso

from . import xso as forms_xso


descriptor_ns = "{jabber:x:data}field"


FIELD_DOCSTRING_TEMPLATE = """
``{field_type.value}`` field ``{var}``

{label}
"""


class BoundField(metaclass=abc.ABCMeta):
    """
    Abstract base class for objects returned by the field descriptors.

    :param field: field descriptor to bind
    :type field: :class:`AbstractField`
    :param instance: form instance to bind to
    :type instance: :class:`object`

    :class:`BoundField` instances represent the connection between the field
    descriptors present at a form *class* and the *instance* of that class.

    They store of course the value of the field for the specific instance, but
    also possible instance-specific overrides for the metadata attributes
    :attr:`desc`, :attr:`label` and :attr:`required` (and possibly
    :attr:`.BoundOptionsField.options`). By default, these attributes return
    the same value as set on the corresponding `field`, but the attributes can
    be set to different values, which only affects the single form instance.

    The use case is to fill these fields with the information obtained from a
    :class:`.Data` XSO when creating a form with :meth:`.Form.from_xso`: it
    allows the fields to behave exactly like the sender specified.

    Deep-copying a :class:`BoundField` deepcopies all attributes, except the
    :attr:`field` and :attr:`instance` attributes. See also :meth:`clone_for`
    for copying a bound field for a new `instance`.

    Subclass overview:

    .. autosummary::

       BoundSingleValueField
       BoundMultiValueField
       BoundSelectField
       BoundMultiSelectField

    Binding relationship:

    .. autoattribute:: field

    .. attribute:: instance

       The `instance` as passed to the constructor.

    Field metadata attributes:

    .. autoattribute:: desc

    .. autoattribute:: label

    .. autoattribute:: required

    Helper methods:

    .. automethod:: clone_for

    The following methods must be implemented by base classes.

    .. automethod:: load

    .. automethod:: render

    """

    def __init__(self, field, instance):
        super().__init__()
        self._field = field
        self.instance = instance

    @property
    def field(self):
        """
        The field which is bound to the :attr:`instance`.
        """
        return self._field

    def __repr__(self):
        return "<bound {!r} for {!r} at 0x{:x}>".format(
            self._field,
            self.instance,
            id(self),
        )

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        for k, v in self.__dict__.items():
            if k == "_field" or k == "instance":
                continue
            setattr(result, k, copy.deepcopy(v, memo))
        return result

    @property
    def desc(self):
        """
        .. seealso::

           :attr:`.Field.desc`
              for a full description of the ``desc`` semantics.
        """

        try:
            return self._desc
        except AttributeError:
            return self._field.desc

    @desc.setter
    def desc(self, value):
        self._desc = value

    @property
    def label(self):
        """
        .. seealso::

           :attr:`.Field.label`
              for a full description of the ``label`` semantics.
        """
        try:
            return self._label
        except AttributeError:
            return self._field.label

    @label.setter
    def label(self, value):
        self._label = value

    @property
    def required(self):
        """
        .. seealso::

           :attr:`.Field.required`
              for a full description of the ``required`` semantics.
        """
        try:
            return self._required
        except AttributeError:
            return self._field.required

    @required.setter
    def required(self, value):
        self._required = value

    def clone_for(self, other_instance, memo=None):
        """
        Clone this bound field for another instance, possibly during a
        :func:`~copy.deepcopy` operation.

        :param other_instance: Another form instance to which the newly created
                               bound field shall be bound.
        :type other_instance: :class:`object`
        :param memo: Optional deepcopy-memo (see :mod:`copy` for details)

        If this is called during a deepcopy operation, passing the `memo` helps
        preserving and preventing loops. This method is essentially a
        deepcopy-operation, with a modification of the :attr:`instance`
        afterwards.
        """

        if memo is None:
            result = copy.deepcopy(self)
        else:
            result = copy.deepcopy(self, memo)
        result.instance = other_instance
        return result

    @abc.abstractmethod
    def load(self, field_xso):
        """
        Load the field information from a data field.

        :param field_xso: XSO describing the field.
        :type field_xso: :class:`~.Field`

        This loads the current value, description, label and possibly options
        from the `field_xso`, shadowing the information from the declaration of
        the field on the class.

        This method is must be overridden and is thus marked abstract. However,
        when called from a subclass, it loads the :attr:`desc`, :attr:`label`
        and :attr:`required` from the given `field_xso`. Subclasses are
        supposed to implement a mechanism to load options and/or values from
        the `field_xso` and then call this implementation through
        :func:`super`.
        """
        if field_xso.desc:
            self._desc = field_xso.desc

        if field_xso.label:
            self._label = field_xso.label

        self._required = field_xso.required

    @abc.abstractmethod
    def render(self, *, use_local_metadata=True):
        """
        Return a :class:`~.Field` containing the values and metadata set in the
        field.

        :param use_local_metadata: if true, the description, label and required
                                   metadata can be sourced from the field
                                   descriptor associated with this bound field.
        :type use_local_metadata: :class:`bool`
        :return: A new :class:`~.Field` instance.

        The returned object uses the values accessible through this object;
        that means, any values set for e.g. :attr:`desc` take precedence over
        the values declared at the class level. If `use_local_metadata` is
        false, values declared at the class level are not used if no local
        values are declared. This is useful when generating a reply to a form
        received by a peer, as it avoids sending a modified form.

        This method is must be overridden and is thus marked abstract. However,
        when called from a subclass, it creates the :class:`~.Field` instance
        and initialises its :attr:`~.Field.var`, :attr:`~.Field.type_`,
        :attr:`~.Field.desc`, :attr:`~.Field.required` and
        :attr:`~.Field.label` attributes and returns the result. Subclasses are
        supposed to override this method, call the base implementation through
        :func:`super` to obtain the :class:`~.Field` instance and then fill in
        the values and/or options.
        """

        result = forms_xso.Field(
            var=self.field.var,
            type_=self.field.FIELD_TYPE,
        )

        if use_local_metadata:
            result.desc = self.desc
            result.label = self.label
            result.required = self.required
        else:
            try:
                result.desc = self._desc
            except AttributeError:
                pass

            try:
                result.label = self._label
            except AttributeError:
                pass

            try:
                result.required = self._required
            except AttributeError:
                pass

        return result


class BoundSingleValueField(BoundField):
    """
    A bound field which has only a single value at any time. Only the first
    value is parsed when loading data from a :class:`~.Field` XSO. When writing
    data to a :class:`~.Field` XSO, :data:`None` is treated as the absence of
    any value; every other value is serialised through the
    :attr:`~.AbstractField.type_` of the field.

    .. seealso::

       :class:`BoundField`
          for a description of the arguments.

    This bound field is used by :class:`TextSingle`, :class:`TextPrivate` and
    :class:`JIDSingle`.

    .. autoattribute:: value
    """

    @property
    def value(self):
        """
        The current value of the field. If no value is set when this attribute
        is accessed for reading, the :meth:`default` of the field is invoked
        and the result is set and returned as value.

        Only values which pass through :meth:`~.AbstractCDataType.coerce` of
        the :attr:`~.AbstractField.type_` of the field can be set. To
        revert the :attr:`value` to its default, use the ``del`` operator.
        """
        try:
            return self._value
        except AttributeError:
            # call through to field
            self._value = self._field.default()
            return self._value

    @value.setter
    def value(self, value):
        self._value = self._field.type_.coerce(value)

    @value.deleter
    def value(self):
        try:
            del self._value
        except AttributeError:
            pass

    def load(self, field_xso):
        try:
            value = field_xso.values[0]
        except IndexError:
            value = self._field.default()
        else:
            value = self._field.type_.parse(value)

        self._value = value

        super().load(field_xso)

    def render(self, **kwargs):
        result = super().render(**kwargs)

        try:
            value = self._value
        except AttributeError:
            value = self._field.default()

        if value is None:
            return result

        result.values[:] = [
            self.field.type_.format(value)
        ]

        return result


class BoundMultiValueField(BoundField):
    """
    A bound field which can have multiple values.

    .. seealso::

       :class:`BoundField`
          for a description of the arguments.

    This bound field is used by :class:`TextMulti` and :class:`JIDMulti`.

    .. autoattribute:: value
    """

    @property
    def value(self):
        """
        A tuple of values. This attribute can be set with any iterable; the
        iterable is then evaluated into a tuple and stored at the bound field.

        Whenever values are written to this attribute, they are passed through
        the :meth:`~.AbstractCDataType.coerce` method of the
        :attr:`~.AbstractField.type_` of the field. To revert the
        :attr:`value` to its default, use the ``del`` operator.
        """
        try:
            return self._value
        except AttributeError:
            self.value = self._field.default()
            return self._value

    @value.setter
    def value(self, values):
        coerce = self._field.type_.coerce
        self._value = tuple(
            coerce(v)
            for v in values
        )

    @value.deleter
    def value(self):
        try:
            del self._value
        except AttributeError:
            pass

    def load(self, field_xso):
        self._value = tuple(
            self._field.type_.parse(v)
            for v in field_xso.values
        )

        super().load(field_xso)

    def render(self, **kwargs):
        result = super().render(**kwargs)
        result.values[:] = (
            self.field.type_.format(v)
            for v in self._value
        )
        return result


class BoundOptionsField(BoundField):
    """
    This is an intermediate base class used to implement bound fields for
    fields which have options from which one or more values must be chosen.

    .. seealso::

       :class:`BoundField`
          for a description of the arguments.

    When the field is loaded from a :class:`~.Field` XSO, the options are also
    loaded from there and thus shadow the options defined at the `field`. This
    may come to a surprise of code expecting a specific set of options.

    Subclass overview:

    .. autosummary::

       BoundSelectField
       BoundMultiSelectField

    .. autoattribute:: options
    """

    @property
    def options(self):
        """
        This is a :class:`collections.OrderedDict` which maps option keys to
        their labels. The keys are used as the values of the field; the labels
        are human-readable text for display.

        This attribute can be written with any object which is compatible with
        the dict-constructor. The order is preserved if a sequence of key-value
        pairs is used.

        When writing the attribute, the keys are checked against the
        :meth:`~.AbstractCDataType.coerce` method of the
        :attr:`~.AbstractField.type_` of the field. To make the :attr:`options`
        attribute identical to the :attr:`~.AbstractField.options` attribute,
        use the ``del`` operator.

        .. warning::

           This attribute is mutable, however, mutating it directly may have
           unexpected side effects:

           * If the attribute has not been set before, you will actually be
             mutating the :class:`~.AbstractChoiceField.options` attributes
             value.

             This may be changed in the future by copying more eagerly.

           * The type checking cannot take place when keys are added by direct
             mutation of the dictionary. This means that errors will be delayed
             until the actual serialisation of the data form, which may be a
             confusing thing to debug.

           Relying on the above behaviour or any other behaviour induced by
           directly mutating the value returned by this attribute is **not
           recommended**. Changes to this behaviour are *not* considered
           breaking changes and will be done without the usual deprecation.
        """
        try:
            return self._options
        except AttributeError:
            return self.field.options

    @options.setter
    def options(self, value):
        iterator = (value.items()
                    if isinstance(value, collections.abc.Mapping)
                    else value)
        self._options = collections.OrderedDict(
            (self.field.type_.coerce(k), v)
            for k, v in iterator
        )

    @options.deleter
    def options(self):
        try:
            del self._options
        except AttributeError:
            pass

    def load(self, field_xso):
        self._options = collections.OrderedDict(
            field_xso.options
        )
        super().load(field_xso)

    def render(self, **kwargs):
        format_ = self._field.type_.format
        field_xso = super().render(**kwargs)
        field_xso.options.update(
            (format_(k), v)
            for k, v in self.options.items()
        )
        return field_xso


class BoundSelectField(BoundOptionsField):
    """
    Bound field carrying one value out of a set of options.

    .. seealso::

       :class:`BoundField`
          for a description of the arguments.
       :attr:`BoundOptionsField.options`
          for semantics and behaviour of the ``options`` attribute

    .. autoattribute:: value

    """

    @property
    def value(self):
        """
        The current value of the field. If no value is set when this attribute
        is accessed for reading, the :meth:`default` of the field is invoked
        and the result is set and returned as value.

        Only values contained in the :attr:`~.BoundOptionsField.options` can be
        set, other values are rejected with a :class:`ValueError`. To revert
        the value to the default value specified in the descriptor, use the
        ``del`` operator.
        """
        try:
            return self._value
        except AttributeError:
            self._value = self.field.default()
            return self._value

    @value.setter
    def value(self, value):
        options = self.options
        if value not in options:
            raise ValueError("{!r} not in field options: {!r}".format(
                value,
                tuple(options.keys()),
            ))

        self._value = value

    @value.deleter
    def value(self):
        try:
            del self._value
        except AttributeError:
            pass

    def load(self, field_xso):
        try:
            value = field_xso.values[0]
        except IndexError:
            try:
                del self._value
            except AttributeError:
                pass
        else:
            self._value = self.field.type_.parse(value)

        super().load(field_xso)

    def render(self, **kwargs):
        format_ = self._field.type_.format
        field_xso = super().render(**kwargs)
        value = self.value
        if value is not None:
            field_xso.values[:] = [format_(value)]
        return field_xso


class BoundMultiSelectField(BoundOptionsField):
    """
    Bound field carrying a subset of values out of a set of options.

    .. seealso::

       :class:`BoundField`
          for a description of the arguments.
       :attr:`BoundOptionsField.options`
          for semantics and behaviour of the ``options`` attribute

    .. autoattribute:: value
    """

    @property
    def value(self):
        """
        A :class:`frozenset` whose elements are a subset of the keys of the
        :attr:`~.BoundOptionsField.options` mapping.

        This value can be written with any iterable; the iterable is then
        evaluated into a :class:`frozenset`. If it contains any value not
        contained in the set of keys of options, the attribute is not written
        and :class:`ValueError` is raised.

        To revert the value to the default specified by the field descriptor,
        use the ``del`` operator.
        """
        try:
            return self._value
        except AttributeError:
            self.value = self.field.default()
            return self._value

    @value.setter
    def value(self, values):
        new_values = frozenset(values)
        options = set(self.options.keys())
        invalid = new_values - options
        if invalid:
            raise ValueError(
                "{!r} not in field options: {!r}".format(
                    next(iter(invalid)),
                    tuple(self.options.keys())
                )
            )

        self._value = new_values

    @value.deleter
    def value(self):
        try:
            del self._value
        except AttributeError:
            pass

    def load(self, field_xso):
        self._value = frozenset(
            self.field.type_.parse(value)
            for value in field_xso.values
        )
        super().load(field_xso)

    def render(self, **kwargs):
        format_ = self.field.type_.format

        result = super().render(**kwargs)
        result.values[:] = [
            format_(value)
            for value in self.value
        ]
        return result


class AbstractDescriptor(metaclass=abc.ABCMeta):
    attribute_name = None
    root_class = None

    @abc.abstractmethod
    def descriptor_keys(self):
        """
        Return an iterator with the descriptor keys for this descriptor. The
        keys will be added to the :attr:`DescriptorClass.DESCRIPTOR_KEYS`
        mapping, pointing to the descriptor.

        Duplicate keys will lead to a :class:`TypeError` being raised during
        declaration of the class.
        """


class AbstractField(AbstractDescriptor):
    """
    Abstract base class to implement field descriptor classes.

    :param var: The field ``var`` attribute this descriptor is supposed to
                represent.
    :type var: :class:`str`
    :param type_: The type of the data, defaults to :class:`~.xso.String`.
    :type type_: :class:`~.xso.AbstractCDataType`
    :param required: Flag to indicate that the field is required.
    :type required: :class:`bool`
    :param desc: Description text for the field, e.g. for tool-tips.
    :type desc: :class:`str`, without newlines
    :param label: Short, human-readable label for the field
    :type label: :class:`str`

    The arguments are used to initialise the respective attributes. Details on
    the semantics can be found in the respective documentation pieces below.

    .. autoattribute:: desc

    .. attribute:: label

       Represents the label flag as specified per :xep:`4`.

       The value of this attribute is used when forms are generated locally.
       When forms are received from remote peers and :class:`~.Form` instances
       are constructed from that data, this attribute is not used when
       rendering a reply or when the value is accessed through the bound field.

        .. seealso::

           :attr:`~.Field.label`
              for details on the semantics of this attribute

    .. attribute:: required

       Represents the required flag as specified per :xep:`4`.

       The value of this attribute is used when forms are generated locally.
       When forms are received from remote peers and :class:`~.Form` instances
       are constructed from that data, this attribute is not used when
       rendering a reply or when the value is accessed through the bound field.

        .. seealso::

           :attr:`~.Field.required`
              for details on the semantics of this attribute

    .. autoattribute:: var

    .. automethod:: create_bound

    .. automethod:: default

    .. automethod:: make_bound
    """

    def __init__(self, var, type_, *, required=False, desc=None, label=None):
        super().__init__()
        self._var = var
        self.required = required
        self.desc = desc
        self.label = label
        self._type = type_
        self.__doc__ = FIELD_DOCSTRING_TEMPLATE.format(
            field_type=self.FIELD_TYPE,
            var=self.var,
            desc=self.desc,
            label=self.label,
        )

    def descriptor_keys(self):
        yield descriptor_ns, self._var

    @property
    def type_(self):
        """
        :class:`.AbstractCDataType` instance used to parse, validate and
        format the value(s) of this field.

        The type of a field cannot be changed after its initialisation.
        """
        return self._type

    @property
    def desc(self):
        """
        Represents the description as specified per :xep:`4`.

        The value of this attribute is used when forms are generated locally.
        When forms are received from remote peers and :class:`~.Form` instances
        are constructed from that data, this attribute is not used when
        rendering a reply or when the value is accessed through the bound
        field.

        .. seealso::

           :attr:`~.Field.desc`
              for details on the semantics of this attribute
        """

        return self._desc

    @desc.setter
    def desc(self, value):
        if value is not None and any(ch == "\r" or ch == "\n" for ch in value):
            raise ValueError("desc must not contain newlines")
        self._desc = value

    @desc.deleter
    def desc(self):
        self._desc = None

    @property
    def var(self):
        """
        Represents the field ID as specified per :xep:`4`.

        The value of this attribute is used to match fields when instantiating
        :class:`~.Form` classes from :class:`~.Data` XSOs.

        .. seealso::

           :attr:`~.Field.var`
              for details on the semantics of this attribute
        """
        return self._var

    @abc.abstractmethod
    def default(self):
        """
        Create and return a default value for this field.

        This must be implemented by subclasses.
        """

    @abc.abstractmethod
    def create_bound(self, for_instance):
        """
        Create a :ref:`bound field class <api-aioxmpp.forms-bound-fields>`
        instance for this field for the given form object and return it.

        :param for_instance: The form instance to which the bound field should
                             be bound.

        This method must be re-implemented by subclasses.

        .. seealso::

           :meth:`make_bound`
              creates (using this method) or returns an existing bound field
              for a given form instance.

        """

    def make_bound(self, for_instance):
        """
        Create a new :ref:`bound field class <api-aioxmpp.forms-bound-fields>`
        or return an existing one for the given form object.

        :param for_instance: The form instance to which the bound field should
                             be bound.

        If no bound field can be found on the given `for_instance` for this
        field, a new one is created using :meth:`create_bound`, stored at the
        instance and returned. Otherwise, the existing instance is returned.

        .. seealso::

           :meth:`create_bound`
              creates a new bound field for the given form instance (without
              storing it anywhere).
        """

        try:
            return for_instance._descriptor_data[self]
        except KeyError:
            bound = self.create_bound(for_instance)
            for_instance._descriptor_data[self] = bound
            return bound

    def __get__(self, instance, type_):
        if instance is None:
            return self
        return self.make_bound(instance)


class TextSingle(AbstractField):
    """
    Represent a ``"text-single"`` input with the given `var`.

    :param default: A default value to initialise the field.

    .. seealso::

       :class:`~.fields.BoundSingleValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """
    FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE

    def __init__(self, var, type_=xso.String(), *,
                 default=None,
                 **kwargs):
        super().__init__(var, type_, **kwargs)
        self._default = default

    def default(self):
        return self._default

    def create_bound(self, for_instance):
        return BoundSingleValueField(
            self,
            for_instance,
        )


class JIDSingle(AbstractField):
    """
    Represent a ``"jid-single"`` input with the given `var`.

    :param default: A default value to initialise the field.

    .. seealso::

       :class:`~.fields.BoundSingleValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `required`, `desc` and
          `label` arguments.

    """
    FIELD_TYPE = forms_xso.FieldType.JID_SINGLE

    def __init__(self, var, *, default=None, **kwargs):
        super().__init__(var, type_=xso.JID(), **kwargs)
        self._default = default

    def default(self):
        return self._default

    def create_bound(self, for_instance):
        return BoundSingleValueField(
            self,
            for_instance,
        )


class Boolean(AbstractField):
    """
    Represent a ``"boolean"`` input with the given `var`.

    :param default: A default value to initialise the field.

    .. seealso::

       :class:`~.fields.BoundSingleValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.BOOLEAN

    def __init__(self, var, *, default=False, **kwargs):
        super().__init__(var, xso.Bool(), **kwargs)
        self._default = default

    def default(self):
        return self._default

    def create_bound(self, for_instance):
        return BoundSingleValueField(
            self,
            for_instance,
        )


class TextPrivate(TextSingle):
    """
    Represent a ``"text-private"`` input with the given `var`.

    :param default: A default value to initialise the field.

    .. seealso::

       :class:`~.fields.BoundSingleValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.TEXT_PRIVATE


class TextMulti(AbstractField):
    """
    Represent a ``"text-multi"`` input with the given `var`.

    :param default: A default value to initialise the field.
    :type default: :class:`tuple`

    .. seealso::

       :class:`~.fields.BoundMultiValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.TEXT_MULTI

    def __init__(self, var, type_=xso.String(), *,
                 default=(), **kwargs):
        super().__init__(var, type_, **kwargs)
        self._default = default

    def create_bound(self, for_instance):
        return BoundMultiValueField(self, for_instance)

    def default(self):
        return self._default


class JIDMulti(AbstractField):
    """
    Represent a ``"jid-multi"`` input with the given `var`.

    :param default: A default value to initialise the field.
    :type default: :class:`tuple`

    .. seealso::

       :class:`~.fields.BoundMultiValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.JID_MULTI

    def __init__(self, var, *, default=(), **kwargs):
        super().__init__(var, xso.JID(), **kwargs)
        self._default = default

    def create_bound(self, for_instance):
        return BoundMultiValueField(self, for_instance)

    def default(self):
        return self._default


class AbstractChoiceField(AbstractField):
    """
    Abstract base class to implement field descriptor classes using options.

    :param type_: Type used for the option keys.
    :type type_: :class:`~.xso.AbstractCDataType`
    :param options: A sequence of key-value pairs or a mapping object
                    representing the options available.
    :type options: sequence of pairs or mapping

    The keys of the `options` mapping (or the first elements in the pairs in
    the sequence of pairs) must be compatible with `type_`, in the sense that
    must pass through :meth:`~.xso.AbstractCDataType.coerce` (this is enforced
    when the field is instantiated).

    Fields using this base class:

    .. autosummary::

       aioxmpp.forms.ListSingle
       aioxmpp.forms.ListMulti

    .. seealso::

       :class:`~.fields.BoundOptionsField`
          is an abstract base class to implement :ref:`bound field classes
          <api-aioxmpp.forms-bound-fields>` for fields inheriting from this
          class.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `required`, `desc` and `label`
          arguments.

    """

    def __init__(self, var, *,
                 type_=xso.String(),
                 options=[],
                 **kwargs):
        super().__init__(var, type_, **kwargs)
        iterator = (options.items()
                    if isinstance(options, collections.abc.Mapping)
                    else options)
        self.options = collections.OrderedDict(
            (type_.coerce(k), v)
            for k, v in iterator
        )
        self._type = type_

    @property
    def type_(self):
        return self._type


class ListSingle(AbstractChoiceField):
    """
    Represent a ``"list-single"`` input with the given `var`.

    :param default: A default value to initialise the field. This must be a
                    member of the `options`.

    .. seealso::

       :class:`~.fields.BoundMultiValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractChoiceField`
          for documentation on the `options` argument.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.LIST_SINGLE

    def __init__(self, var, *, default=None, **kwargs):
        super().__init__(var, **kwargs)
        if default is not None and default not in self.options:
            raise ValueError("invalid default: not in options")
        self._default = default

    def create_bound(self, for_instance):
        return BoundSelectField(self, for_instance)

    def default(self):
        return self._default


class ListMulti(AbstractChoiceField):
    """
    Represent a ``"list-multi"`` input with the given `var`.

    :param default: An iterable of `options` keys
    :type default: iterable

    `default` is evaluated into a :class:`frozenset` and all elements must be
    keys of the `options` mapping argument.

    .. seealso::

       :class:`~.fields.BoundMultiValueField`
          is the :ref:`bound field class <api-aioxmpp.forms-bound-fields>` used
          by fields of this type.

       :class:`~.fields.AbstractChoiceField`
          for documentation on the `options` argument.

       :class:`~.fields.AbstractField`
          for documentation on the `var`, `type_`, `required`, `desc` and
          `label` arguments.

    """

    FIELD_TYPE = forms_xso.FieldType.LIST_MULTI

    def __init__(self, var, *, default=frozenset(), **kwargs):
        super().__init__(var, **kwargs)
        self._default = frozenset(default)
        if any(value not in self.options for value in self._default):
            raise ValueError(
                "invalid default: not in options"
            )

    def create_bound(self, for_instance):
        return BoundMultiSelectField(self, for_instance)

    def default(self):
        return self._default
