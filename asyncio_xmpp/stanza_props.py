"""
:mod:`stanza_props` --- Descriptors (properties) for use with stanzas
#####################################################################


"""
import abc

from . import jid
from .utils import *

__all__ = [
    "StringType",
    "JIDType",
    "EnumType",
    "BoolType",
    "xmlattr",
    "xmltext",
    "xmlchildtext",
]

class StanzaMeta(type):
    def __new__(mcls, name, bases, namespace):
        for name, obj in namespace.items():
            if isinstance(obj, xmlprop):
                obj._bind_to_name(namespace, name)
        cls = type.__new__(mcls, name, bases, namespace)
        return cls


class PropertyType:
    """
    .. attribute:: strict

       A boolean attribute dictating whether validation on reads is strict. The
       value of this is controlled by the value passed to the constructor.

    """

    def __init__(self, *, strict=False):
        self.strict = strict

    @abc.abstractmethod
    def _get(self, value, default):
        """
        The default implementation raises a :class:`ValueError` if the value is
        missing and returns :data:`None` otherwise. It can be used in constructs
        like the following::

            def get(self, value, default):
                super().get(value, default)
                # do the real validation here, raise ValueError on errors

        Subclasses must implement their validation in this method, except if
        they want to change the general behaviour of the descriptor (see
        :meth:`get`).
        """

        if value is None:
            raise ValueError("Value is not present")

    def get(self, value, default):
        """
        Validate the *value* against the type and return either the value or the
        default or raise a :class:`ValueError` exception (the latter is only
        allowed if :attr:`strict` has been set to :data:`True`).

        This calls :meth:`_get` and catches any :class:`ValueError` exceptions
        if :attr:`strict` is true and lets them propagate if :attr:`strict` is
        false.
        """
        try:
            return self._get(value, default)
        except ValueError:
            if self.strict:
                raise
            return default

    @abc.abstractmethod
    def set(self, value):
        """
        Validate the *value*. Return the actual string value which will be
        written to the data structure or the *default* or raise a
        :class:`ValueError`. Raising the exception is the preferred way of
        signalling an error in this method, independent from the state of the
        :attr:`strict` attribute.
        """

class StringType(PropertyType):
    def _get(self, value, default):
        super()._get(value, default)
        return value

    def set(self, value):
        if not isinstance(value, str):
            raise ValueError("Attribute values must be strings")
        return value

class JIDType(PropertyType):
    def _get(self, value, default):
        super()._get(value, default)
        return jid.JID.fromstr(value)

    def set(self, value):
        return str(value)

class EnumType(PropertyType):
    def __init__(self, options, **kwargs):
        super().__init__(**kwargs)
        self._options = frozenset(options)

    def _check(self, value):
        if value in self._options:
            return value
        raise ValueError("Value must be any of {}".format(
            ", ".join(self._options)))

    def _get(self, value, default):
        return self._check(value)

    def set(self, value):
        if value is None:
            raise ValueError("Value must not be None (use del to delete "
                             "an attribute)")
        return self._check(value)

class BoolType(PropertyType):
    _TRUE_VALUES = ["true", "1"]
    _FALSE_VALUES = ["false", "0"]

    def _get(self, value, default):
        value = value.strip().lower()
        if value in self._TRUE_VALUES:
            return True
        if value in self._FALSE_VALUES:
            return False
        raise ValueError("Not a boolean value: {}".format(value))

    def set(self, value):
        if value:
            return self._TRUE_VALUES[0]
        else:
            return self._FALSE_VALUES[0]

class xmlprop:
    def __init__(self, *, default=None):
        self._default = default

    def _bind_to_name(self, namespace, name):
        """
        Called by the :class:`StanzaMeta` metaclass with the *name* the
        descriptor was assigned to.
        """

class xmlattr(xmlprop):
    def __init__(self, type_=None, *, name=None, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._type = type_ or StringType()

    def _bind_to_name(self, namespace, name):
        if self._name is None:
            self._name = name

    def __get__(self, instance, type_):
        if instance is None:
            return self

        try:
            return self._type.get(instance.get(self._name), self._default)
        except ValueError as err:
            raise AttributeError(
                "XML attribute @{} value is invalid: {}".format(
                    self._name, err))

    def __set__(self, instance, value):
        instance.set(self._name, self._type.set(value))

    def __delete__(self, instance):
        try:
            del instance.attrib[self._name]
        except KeyError:
            pass

class xmltext(xmlprop):
    def __init__(self, type_=None, **kwargs):
        super().__init__(**kwargs)
        self._type = type_ or StringType()

    def __get__(self, instance, type_):
        if instance is None:
            return self

        try:
            return self._type.get(instance.text, self._default)
        except ValueError as err:
            raise AttributeError(
                "XML character data is invalid: {}".format(
                    self._name, err))

    def __set__(self, instance, value):
        instance.text = self._type.set(value)

    def __delete__(self, instance):
        instance.text = None


class xmlchildtext(xmltext):
    def __init__(self, type_=None, *, tag=None, hard_delete=True, **kwargs):
        super().__init__(**kwargs)
        self._tag = tag
        self._type = type_ or StringType()
        self._hard_delete = hard_delete

    def _bind_to_name(self, namespace, name):
        if self._tag is not None:
            return
        try:
            ns, _ = split_tag(namespace["TAG"])
        except KeyError:
            raise ValueError("xmlchildtext must be passed a tag if the parent"
                             " object does not have a TAG attribute.")
        self._tag = "{{{}}}{}".format(ns, name)

    def __get__(self, instance, type_):
        if instance is None:
            return self

        node = instance.find(self._tag)
        if node is None:
            value = None
        else:
            value = node.text
        return self._type.get(value, self._default)

    def __set__(self, instance, value):
        node = instance.find(self._tag)
        if node is None:
            node = etree.SubElement(instance, self._tag)
        return super().__set__(node, value)

    def __delete__(self, instance):
        node = instance.find(self._tag)
        if node is None:
            return
        if self._hard_delete:
            instance.remove(node)
        else:
            super().__delete__(node)
