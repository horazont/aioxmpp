########################################################################
# File name: form.py
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
import copy

from . import xso as forms_xso
from . import fields as fields


def descriptor_attr_name(descriptor):
    return "_descriptor_{:x}".format(id(descriptor))


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
            if isinstance(descriptor, fields.AbstractDescriptor)
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
            if isinstance(existing, fields.AbstractDescriptor):
                return True
        return False

    def __setattr__(self, name, value):
        if self._is_descriptor_attribute(name):
            raise AttributeError("descriptor attributes cannot be set")

        if not isinstance(value, fields.AbstractDescriptor):
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


class FormClass(DescriptorClass):
    def from_xso(self, xso):
        """
        Construct and return an instance from the given `xso`.

        .. note::

           This is a static method (classmethod), even though sphinx does not
           document it as such.

        :param xso: A :xep:`4` data form
        :type xso: :class:`~.Data`
        :raises ValueError: if the ``FORM_TYPE`` mismatches
        :raises ValueError: if field types mismatch
        :return: newly created instance of this class

        The fields from the given `xso` are matched against the fields on the
        form. Any matching field loads its data from the `xso` field. Fields
        which occur on the form template but not in the `xso` are skipped.
        Fields which occur in the `xso` but not on the form template are also
        skipped (but are re-emitted when the form is rendered as reply, see
        :meth:`~.Form.render_reply`).

        If the form template has a ``FORM_TYPE`` attribute and the incoming
        `xso` also has a ``FORM_TYPE`` field, a mismatch between the two values
        leads to a :class:`ValueError`.

        The field types of matching fields are checked. If the field type on
        the incoming XSO may not be upcast to the field type declared on the
        form (see :meth:`~.FieldType.allow_upcast`), a :class:`ValueError` is
        raised.

        If the :attr:`~.Data.type_` does not indicate an actual form (but
        rather a cancellation request or tabular result), :class:`ValueError`
        is raised.
        """

        my_form_type = getattr(self, "FORM_TYPE", None)

        f = self()
        for field in xso.fields:
            if field.var == "FORM_TYPE":
                if (my_form_type is not None and
                        field.type_ == forms_xso.FieldType.HIDDEN and
                        field.values):
                    if my_form_type != field.values[0]:
                        raise ValueError(
                            "mismatching FORM_TYPE ({!r} != {!r})".format(
                                field.values[0],
                                my_form_type,
                            )
                        )
                continue
            if field.var is None:
                continue

            key = fields.descriptor_ns, field.var
            try:
                descriptor = self.DESCRIPTOR_MAP[key]
            except KeyError:
                continue

            if (field.type_ is not None and not
                    field.type_.allow_upcast(descriptor.FIELD_TYPE)):
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

       TextSingle
       TextMulti
       TextPrivate
       JIDSingle
       JIDMulti
       ListSingle
       ListMulti
       Boolean

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
        Create a :class:`~.Data` object equal to the object from which the from
        was created through :meth:`from_xso`, except that the values of the
        fields are exchanged with the values set on the form.

        Fields which have no corresponding form descriptor are left untouched.
        Fields which are accessible through form descriptors, but are not in
        the original :class:`~.Data` are not included in the output.

        This method only works on forms created through :meth:`from_xso`.

        The resulting :class:`~.Data` instance has the :attr:`~.Data.type_` set
        to :attr:`~.DataType.SUBMIT`.
        """

        data = copy.copy(self._recv_xso)
        data.type_ = forms_xso.DataType.SUBMIT
        data.fields = list(self._recv_xso.fields)

        for i, field_xso in enumerate(data.fields):
            if field_xso.var is None:
                continue
            if field_xso.var == "FORM_TYPE":
                continue
            key = fields.descriptor_ns, field_xso.var
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

        my_form_type = getattr(self, "FORM_TYPE", None)
        if my_form_type is not None:
            field_xso = forms_xso.Field()
            field_xso.var = "FORM_TYPE"
            field_xso.type_ = forms_xso.FieldType.HIDDEN
            field_xso.values[:] = [my_form_type]
            data.fields.append(field_xso)

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
