import abc
import copy

import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

from . import xso as form_xso


descriptor_ns = "{jabber:x:data}field"


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
    def __init__(self, *, required=False, desc=None, label=None):
        super().__init__()
        self.required = required
        self.desc = desc
        self.label = label

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

    def render_into(self, instance, field_xso):
        if self.required:
            field_xso.required = (namespaces.xep0004_data, "required")
        else:
            field_xso.required = None
        field_xso.desc = self.desc
        field_xso.label = self.label


class InputLine(AbstractField):
    def __init__(self, var, type_=xso.String(), *,
                 default=None,
                 **kwargs):
        super().__init__(**kwargs)
        self._var = var
        self._type = type_
        self.default = default

    def descriptor_keys(self):
        yield descriptor_ns, self._var

    @property
    def var(self):
        return self._var

    @property
    def type_(self):
        return self._type

    def load(self, instance, field_xso):
        if field_xso.values:
            instance._descriptor_data[self] = self._type.parse(
                field_xso.values[0]
            )
        else:
            instance._descriptor_data[self] = self.default

    def render_into(self, instance, field_xso):
        value = instance._descriptor_data.get(self, self.default)
        field_xso.type_ = "text-single"
        field_xso.var = self._var
        field_xso.values[:] = [self._type.format(value)]
        super().render_into(instance, field_xso)

    def __get__(self, instance, type_):
        if instance is None:
            return self
        return instance._descriptor_data[self]

    def __set__(self, instance, value):
        value = self._type.coerce(value)
        formatted = self._type.format(value)
        if any(ch == "\r" or ch == "\n" for ch in formatted):
            raise ValueError("newlines not allowed in input line")
        instance._descriptor_data[self] = value


class InputJID(InputLine):
    def __init__(self, var, **kwargs):
        super().__init__(var, type_=xso.JID(), **kwargs)

    def render_into(self, instance, field_xso):
        super().render_into(instance, field_xso)
        field_xso.type_ = "jid-single"


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
            descriptor = self.DESCRIPTOR_MAP[key]
            descriptor.load(f, field)

        f._recv_xso = xso

        return f


class Form(metaclass=FormClass):
    """
    A form template for :xep:`0004` data forms.

    Fields are declared using the different field descriptors available in this
    module:

    .. autosummary::

       InputLine
       InputJID

    .. FIXME: add more

    A form template can be instantiated by two different means:

    1. the :meth:`from_xso` method can be called on a :class:`.xso.Data`
       instance to fill in the template with the data from the XSO.

    2. the constructor can be called.

    With the first method, labels, descriptions, options and values are taken
    from the XSO. The descriptors declared on the form merely act as a
    convenient way to access the fields in the XSO.

    If a field is missing from the XSO, its descriptor still works as if the
    form had been constructed using its constructor. It will not be emitted
    when re-serialising the form or asking the form for its fields through the
    introspection methods, to avoid confusing the sender of the form (by adding
    fields they did not ask for) or the user (by showing fields the originator
    of the form does not understand).

    If the XSO has more fields than the form template, these fields are
    re-emitted and also listed when the form is asked for its fields, but the
    field cannot be accessed using an attribute.

    For details on the field semantics and restrictions with respect to field
    declaration and inheritance, check out the documentation of the meta class
    :class:`FormClass` used by :class:`Form`.
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
            k: copy.deepcopy(v, memo)
            for k, v in self._descriptor_data.items()
        }
        return result

    def render_reply(self):
        data = copy.copy(self._recv_xso)
        data.fields = list(self._recv_xso.fields)

        for i, field_xso in enumerate(data.fields):
            if field_xso.var is None:
                continue
            if field_xso.var == "FORM_TYPE":
                continue
            key = descriptor_ns, field_xso.var
            descriptor = self.DESCRIPTOR_MAP[key]
            new_field_xso = copy.deepcopy(field_xso)
            descriptor.render_into(self, new_field_xso)
            data.fields[i] = new_field_xso

        return data

    def render_request(self):
        data = form_xso.Data()

        try:
            layout = self.LAYOUT
        except AttributeError:
            layout = list(self.DESCRIPTORS)

        for item in layout:
            field_xso = form_xso.Field()
            if isinstance(item, str):
                field_xso.type_ = "fixed"
                field_xso.values[:] = [item]
            else:
                item.render_into(self, field_xso)
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
