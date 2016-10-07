import abc
import collections
import copy

import aioxmpp.xso as xso

from . import xso as forms_xso


descriptor_ns = "{jabber:x:data}field"


def descriptor_attr_name(descriptor):
    return "_descriptor_{:x}".format(id(descriptor))


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


class DescriptorClass(abc.ABCMeta):
    @classmethod
    def _merge_descriptors(mcls, dest_map, source):
        for key, (descriptor, from_class) in source:
            try:
                existing_descriptor, exists_at_class = dest_map[key]
            except KeyError:
                pass
            else:
                if descriptor is not existing_descriptor:
                    raise TypeError(
                        "descriptor with key {!r} already "
                        "declared at {}".format(
                            key,
                            exists_at_class,
                        )
                    )
                else:
                    continue

            dest_map[key] = descriptor, from_class

    @classmethod
    def _upcast_descriptor_map(mcls, descriptor_map, from_class):
        return {
            key: (descriptor, from_class)
            for key, descriptor in descriptor_map.items()
        }

    def __new__(mcls, name, bases, namespace, *, protect=True):
        descriptor_info = {}

        for base in bases:
            if not isinstance(base, DescriptorClass):
                continue

            base_descriptor_info = mcls._upcast_descriptor_map(
                base.DESCRIPTOR_MAP,
                "{}.{}".format(
                    base.__module__,
                    base.__qualname__,
                )
            )
            mcls._merge_descriptors(
                descriptor_info,
                base_descriptor_info.items(),
            )

        fqcn = "{}.{}".format(
            namespace["__module__"],
            namespace["__qualname__"],
        )

        descriptors = [
            (attribute_name, descriptor)
            for attribute_name, descriptor in namespace.items()
            if isinstance(descriptor, AbstractDescriptor)
        ]

        if any(descriptor.root_class is not None
               for _, descriptor in descriptors):
            raise ValueError(
                "descriptor cannot be used on multiple classes"
            )

        mcls._merge_descriptors(
            descriptor_info,
            (
                (key, (descriptor, fqcn))
                for _, descriptor in descriptors
                for key in descriptor.descriptor_keys()
            )
        )

        namespace["DESCRIPTOR_MAP"] = {
            key: descriptor
            for key, (descriptor, _) in descriptor_info.items()
        }
        namespace["DESCRIPTORS"] = set(namespace["DESCRIPTOR_MAP"].values())
        if "__slots__" not in namespace and protect:
            namespace["__slots__"] = ()

        result = super().__new__(mcls, name, bases, namespace)

        for attribute_name, descriptor in descriptors:
            descriptor.attribute_name = attribute_name
            descriptor.root_class = result

        return result

    def __init__(self, name, bases, namespace, *, protect=True):
        super().__init__(name, bases, namespace)

    def _is_descriptor_attribute(self, name):
        try:
            existing = getattr(self, name)
        except AttributeError:
            pass
        else:
            if isinstance(existing, AbstractDescriptor):
                return True
        return False

    def __setattr__(self, name, value):
        if self._is_descriptor_attribute(name):
            raise AttributeError("descriptor attributes cannot be set")

        if not isinstance(value, AbstractDescriptor):
            return super().__setattr__(name, value)

        if self.__subclasses__():
            raise TypeError("cannot add descriptors to classes with "
                            "subclasses")

        meta = type(self)
        descriptor_info = meta._upcast_descriptor_map(
            self.DESCRIPTOR_MAP,
            "{}.{}".format(self.__module__, self.__qualname__),
        )

        new_descriptor_info = [
            (key, (value, "<added via __setattr__>"))
            for key in value.descriptor_keys()
        ]

        # this would raise on conflict
        meta._merge_descriptors(
            descriptor_info,
            new_descriptor_info,
        )

        for key, (descriptor, _) in new_descriptor_info:
            self.DESCRIPTOR_MAP[key] = descriptor

        self.DESCRIPTORS.add(value)

        return super().__setattr__(name, value)

    def __delattr__(self, name):
        if self._is_descriptor_attribute(name):
            raise AttributeError("removal of descriptors is not allowed")

        return super().__delattr__(name)

    def _register_descriptor_keys(self, descriptor, keys):
        """
        Register the given descriptor keys for the given descriptor at the
        class.

        :param descriptor: The descriptor for which the `keys` shall be
                           registered.
        :type descriptor: :class:`AbstractDescriptor` instance
        :param keys: An iterable of descriptor keys
        :raises TypeError: if the specified keys are already handled by a
                           descriptor.
        :raises TypeError: if this class has subclasses or if it is not the
                           :attr:`~AbstractDescriptor.root_class`  of the given
                           descriptor.

        If the method raises, the caller must assume that registration was not
        successful.

        .. note::

           The intended audience for this method are developers of
           :class:`AbstractDescriptor` subclasses, which are generally only
           expected to live in the :mod:`aioxmpp` package.

           Thus, you should not expect this API to be stable. If you have a
           use-case for using this function outside of :mod:`aioxmpp`, please
           let me know through the usual issue reporting means.
        """

        if descriptor.root_class is not self or self.__subclasses__():
            raise TypeError(
                "descriptors cannot be modified on classes with subclasses"
            )

        meta = type(self)
        descriptor_info = meta._upcast_descriptor_map(
            self.DESCRIPTOR_MAP,
            "{}.{}".format(self.__module__, self.__qualname__),
        )

        # this would raise on conflict
        meta._merge_descriptors(
            descriptor_info,
            [
                (key, (descriptor, "<added via _register_descriptor_keys>"))
                for key in keys
            ]
        )

        for key in keys:
            self.DESCRIPTOR_MAP[key] = descriptor


class AbstractField(AbstractDescriptor):
    def __init__(self, var, *, required=False, desc=None, label=None):
        super().__init__()
        self._var = var
        self.required = required
        self.desc = desc
        self.label = label

    def descriptor_keys(self):
        yield descriptor_ns, self._var

    @property
    def desc(self):
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
        return self._var

    @abc.abstractmethod
    def default(self):
        pass

    @abc.abstractmethod
    def create_bound(self, for_instance):
        pass

    def make_bound(self, for_instance):
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


class BoundField(metaclass=abc.ABCMeta):
    def __init__(self, field, instance):
        super().__init__()
        self._field = field
        self.instance = instance

    @property
    def field(self):
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
        try:
            return self._desc
        except AttributeError:
            return self._field.desc

    @desc.setter
    def desc(self, value):
        self._desc = value

    @property
    def label(self):
        try:
            return self._label
        except AttributeError:
            return self._field.label

    @label.setter
    def label(self, value):
        self._label = value

    @property
    def required(self):
        try:
            return self._required
        except AttributeError:
            return self._field.required

    @required.setter
    def required(self, value):
        self._required = value

    def clone_for(self, other_instance, memo=None):
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

        This method is must be overriden and is thus marked abstract. However,
        when called from a subclass, it loads the :attr:`desc`, :attr:`label`
        and :attr:`required` from the given `field_xso`. Subclasses are
        supposed to implement a mechansim to load options and/or values from
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

        This method is must be overriden and is thus marked abstract. However,
        when called from a subclass, it creates the :class:`~.Field` instance
        and initialies its :attr:`~.Field.var`, :attr:`~.Field.type_`,
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
    @property
    def value(self):
        try:
            return self._value
        except AttributeError:
            # call through to field
            self._value = self._field.default()
            return self._value

    @value.setter
    def value(self, value):
        self._value = self._field.type_.coerce(value)

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
        result.values[:] = [
            self.field.type_.format(self._value)
        ]

        return result


class BoundMultiValueField(BoundField):
    @property
    def value(self):
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
    @property
    def options(self):
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
    @property
    def value(self):
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
    @property
    def value(self):
        try:
            return self._value
        except AttributeError:
            self._value = self.field.default()
            return self._value

    @value.setter
    def value(self, values):
        new_values = frozenset(values)
        options = set(self.options.keys())
        invalid = new_values - options
        try:
            raise ValueError(
                "{!r} not in field options: {!r}".format(
                    next(iter(invalid)),
                    tuple(self.options.keys())
                )
            )
        except StopIteration:  # invalid is empty -> all valid
            pass

        self._value = new_values

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


class TextSingle(AbstractField):
    """
    Represent a ``"text-single"`` input with the given `var`.

    :param var: The var attribute of the Data Form field.
    :type var: :class:`str`
    :param type_: The type of the data, defaults to :class:`~.xso.String`.
    :type type_: :class:`~.xso.AbstractType`
    :param default: A default value to initialise the field.
    :param required: Flag to indicate that the field is required.
    :type required: :class:`bool`
    :param desc: Description text for the field, e.g. for tool-tips.
    :type desc: :class:`str`, without newlines
    :param label: Short, human-readable label for the field
    :type label: :class:`str`

    The arguments `required`, `desc` and `label` are only used when generating
    locally; they are ignored when parsing forms from :class:`Data` objects.

    `var` is used to match the field with the corresponding :class:`Field`
    object in the :class:`Data`. A `var` must be unique within a :class:`Form`.

    `type_` is used to :meth:`~.xso.AbstractType.parse` the value from received
    :class:`Field` objects and :meth:`~.xso.AbstractType.format` the value when
    generating :class:`Field` objects to send a form.
    """
    FIELD_TYPE = forms_xso.FieldType.TEXT_SINGLE

    def __init__(self, var, type_=xso.String(), *,
                 default=None,
                 **kwargs):
        super().__init__(var, **kwargs)
        self._type = type_
        self._default = default

    def default(self):
        return self._default

    @property
    def type_(self):
        return self._type

    def create_bound(self, for_instance):
        return BoundSingleValueField(
            self,
            for_instance,
        )


class JIDSingle(TextSingle):
    """
    Represent a ``"jid-single"`` input with the given `var`.

    The arguments have identical semantics to those to :class:`InputLine`, see
    the documentation there for details. The only exception is `type_`, which
    defaults to :class:`~.xso.JID` instead of :class:`~.xso.String`.
    """
    FIELD_TYPE = forms_xso.FieldType.JID_SINGLE

    def __init__(self, var, type_=xso.JID(), **kwargs):
        super().__init__(var, type_=type_, **kwargs)


class TextPrivate(TextSingle):
    FIELD_TYPE = forms_xso.FieldType.TEXT_PRIVATE


class Boolean(TextSingle):
    FIELD_TYPE = forms_xso.FieldType.BOOLEAN

    def __init__(self, var, type_=xso.Bool(), *, default=False, **kwargs):
        super().__init__(var, type_=type_, default=default, **kwargs)


class TextMulti(AbstractField):
    FIELD_TYPE = forms_xso.FieldType.TEXT_MULTI

    def __init__(self, var, type_=xso.String(), *,
                 default=(), **kwargs):
        super().__init__(var, **kwargs)
        self._type = type_
        self._default = default

    @property
    def type_(self):
        return self._type

    def create_bound(self, for_instance):
        return BoundMultiValueField(self, for_instance)

    def default(self):
        return self._default


class JIDMulti(TextMulti):
    FIELD_TYPE = forms_xso.FieldType.JID_MULTI

    def __init__(self, var, type_=xso.JID(), **kwargs):
        super().__init__(var, type_=type_, **kwargs)


class AbstractChoiceField(AbstractField):
    def __init__(self, var, *,
                 type_=xso.String(),
                 options=[],
                 **kwargs):
        super().__init__(var, **kwargs)
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
    FIELD_TYPE = forms_xso.FieldType.LIST_MULTI

    def __init__(self, var, *, default=frozenset(), **kwargs):
        super().__init__(var, **kwargs)
        if any(value not in self.options for value in default):
            raise ValueError(
                "invalid default: not in options"
            )
        self._default = frozenset(default)

    def create_bound(self, for_instance):
        return BoundMultiSelectField(self, for_instance)

    def default(self):
        return self._default


class FormClass(DescriptorClass):
    def from_xso(self, xso):
        """
        Construct and return an instance from the given `xso`.
        """

        f = self()
        for field in xso.fields:
            if field.var == "FORM_TYPE":
                continue
            if field.var is None:
                continue

            key = descriptor_ns, field.var
            try:
                descriptor = self.DESCRIPTOR_MAP[key]
            except KeyError:
                continue

            if not field.type_.allow_upcast(descriptor.FIELD_TYPE):
                raise ValueError(
                    "mismatching type ({!r} != {!r}) on field var={!r}".format(
                        field.type_,
                        descriptor.FIELD_TYPE,
                        field.var,
                    )
                )

            data = descriptor.__get__(f, self)
            data.load(field)

        f._recv_xso = xso

        return f


class Form(metaclass=FormClass):
    """
    A form template for :xep:`0004` Data Forms.

    Fields are declared using the different field descriptors available in this
    module:

    .. autosummary::

       InputLine
       InputJID

    A form template can be instantiated by two different means:

    1. the :meth:`from_xso` method can be called on a :class:`.xso.Data`
       instance to fill in the template with the data from the XSO.

    2. the constructor can be called.

    With the first method, labels, descriptions, options and values are taken
    from the XSO. The descriptors declared on the form merely act as a
    convenient way to access the fields in the XSO.

    If a field is missing from the XSO, its descriptor still works as if the
    form had been constructed using its constructor. It will not be emitted
    when re-serialising the form for a response using :meth:`render_reply`.

    If the XSO has more fields than the form template, these fields are
    re-emitted when the form is serialised using :meth:`render_reply`.

    .. attribute:: LAYOUT

       A mixed list of descriptors and strings to determine form layout as
       generated by :meth:`render_request`. The semantics are the following:

       * each :class:`str` is converted to a ``"fixed"`` field without ``var``
         attribute in the output.
       * each :class:`AbstractField` descriptor is rendered to its
         corresponding :class:`Field` XSO.

       The elements of :attr:`LAYOUT` are processed in-order. This attribute is
       optional and can be set on either the :class:`Form` or a specific
       instance. If it is absent, it is treated as if it were set to
       ``list(self.DESCRIPTORS)``.

    .. automethod:: from_xso

    .. automethod:: render_reply

    .. automethod:: render_request
    """

    __slots__ = ("_descriptor_data", "_recv_xso")

    def __new__(cls, *args, **kwargs):
        result = super().__new__(cls)
        result._descriptor_data = {}
        result._recv_xso = None
        return result

    def __copy__(self):
        result = type(self).__new__(type(self))
        result._descriptor_data.update(self._descriptor_data)
        return result

    def __deepcopy__(self, memo):
        result = type(self).__new__(type(self))
        result._descriptor_data = {
            k: v.clone_for(self, memo=memo)
            for k, v in self._descriptor_data.items()
        }
        return result

    def render_reply(self):
        """
        Create a :class:`Data` object equal to the object from which the from
        was created through :meth:`from_xso`, except that the values of the
        fields are exchanged with the values set on the form.

        Fields which have no corresponding form descriptor are left untouched.
        Fields which are accessible through form descriptors, but are not in
        the original :class:`Data` are not included in the output.

        This method only works on forms created through :meth:`from_xso`.
        """

        data = copy.copy(self._recv_xso)
        data.fields = list(self._recv_xso.fields)

        for i, field_xso in enumerate(data.fields):
            if field_xso.var is None:
                continue
            if field_xso.var == "FORM_TYPE":
                continue
            key = descriptor_ns, field_xso.var
            try:
                descriptor = self.DESCRIPTOR_MAP[key]
            except KeyError:
                continue

            bound_field = descriptor.__get__(self, type(self))
            data.fields[i] = bound_field.render(
                use_local_metadata=False
            )

        return data

    def render_request(self):
        """
        Create a :class:`Data` object containing all fields known to the
        :class:`Form`. If the :class:`Form` has a :attr:`LAYOUT` attribute, it
        is used during generation.
        """

        data = forms_xso.Data(type_=forms_xso.DataType.FORM)

        try:
            layout = self.LAYOUT
        except AttributeError:
            layout = list(self.DESCRIPTORS)

        for item in layout:
            if isinstance(item, str):
                field_xso = forms_xso.Field()
                field_xso.type_ = forms_xso.FieldType.FIXED
                field_xso.values[:] = [item]
            else:
                field_xso = item.__get__(
                    self, type(self)
                ).render()
            data.fields.append(field_xso)

        return data

    def _layout(self, usecase):
        """
        Return an iterable of form members which are used to lay out the form.

        :param usecase: Configure the use case of the layout. This either
                        indicates transmitting the form to a peer as
                        *response*, as *initial form*, or as *error form*, or
                        *showing* the form to a local user.

        Each element in the iterable must be one of the following:

        * A string; gets converted to a ``"fixed"`` form field.
        * A field XSO; gets used verbatimly
        * A descriptor; gets converted to a field XSO
        """
