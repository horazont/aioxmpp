########################################################################
# File name: model.py
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
:mod:`aioxmpp.xso.model` --- Declarative-style XSO definition
#############################################################

See :mod:`aioxmpp.xso` for documentation.
"""
import abc
import collections
import copy
import enum
import logging
import sys
import xml.sax.handler

import lxml.sax

import sortedcollections

import multidict  # get it from PyPI

from enum import Enum

from aioxmpp.utils import etree, namespaces

from . import query as xso_query
from . import types as xso_types
from . import tag_to_str, normalize_tag
from .. import structs


logger = logging.getLogger(__name__)


class UnknownChildPolicy(Enum):
    """
    Describe the event which shall take place whenever a child element is
    encountered for which no descriptor can be found to parse it.

    .. attribute:: FAIL

       Raise a :class:`ValueError`

    .. attribute:: DROP

       Drop and ignore the element and all of its children

    """

    FAIL = 0
    DROP = 1


class UnknownAttrPolicy(Enum):
    """
    Describe the event which shall take place whenever a XML attribute is
    encountered for which no descriptor can be found to parse it.

    .. attribute:: FAIL

       Raise a :class:`ValueError`

    .. attribute:: DROP

       Drop and ignore the attribute

    """
    FAIL = 0
    DROP = 1


class UnknownTextPolicy(Enum):
    """
    Describe the event which shall take place whenever XML character data is
    encountered on an object which does not support it.

    .. attribute:: FAIL

       Raise a :class:`ValueError`

    .. attribute:: DROP

       Drop and ignore the text

    """
    FAIL = 0
    DROP = 1


class ValidateMode(Enum):
    """
    Control which ways to set a value in a descriptor are passed through a
    validator.

    .. attribute:: FROM_RECV

       Values which are obtained from XML source are validated.

    .. attribute:: FROM_CODE

       Values which are set through attribute access are validated.

    .. attribute:: ALWAYS

       All values, whether set by attribute or obtained from XML source, are
       validated.

    """

    FROM_RECV = 1
    FROM_CODE = 2
    ALWAYS = 3

    @property
    def from_recv(self):
        return self.value & 1

    @property
    def from_code(self):
        return self.value & 2


class UnknownTopLevelTag(ValueError):
    """
    Subclass of :class:`ValueError`. `ev_args` must be the arguments of the
    ``"start"`` event and are stored as the :attr:`ev_args` attribute for
    inspection.

    .. attribute:: ev_args

       The `ev_args` passed to the constructor.

    """

    def __init__(self, msg, ev_args):
        super().__init__(msg + ": {}".format((ev_args[0], ev_args[1])))
        self.ev_args = ev_args


class XSOList(list):
    """
    A :class:`list` subclass; it provides the complete :class:`list` interface
    with the addition of the following methods:

    .. automethod:: filter

    .. automethod:: filtered

    In the future, methods to add indices to :class:`XSOList` instances may be
    added; right now, there is no need for the huge complexity which would
    arise from keeping the indices up-to-date with changes in the elements
    attributes.
    """

    def _filter_type(self, chained_results, type_):
        return (obj for obj in chained_results if isinstance(obj, type_))

    def _filter_lang(self, chained_results, lang):
        # first, filter on availability of the "lang" attribute
        result = [item
                  for item in chained_results
                  if hasattr(item, "lang") and item.lang is not None]

        # get a sorted list of all languages in the current result set
        languages = sorted(
            {item.lang for item in result}
        )

        if not languages:
            # no languages -> no results
            result = iter([])
        else:
            # lookup a matching language
            if isinstance(lang, structs.LanguageRange):
                lang = [lang]
            else:
                lang = list(lang)
            match = structs.lookup_language(languages, lang)
            # no language? fallback is using the first one
            if match is None:
                match = languages[0]
            result = (item for item in result if item.lang == match)

        return result

    def _filter_attrs(self, chained_results, attrs):
        result = chained_results
        for key, value in attrs.items():
            result = (item for item in result
                      if hasattr(item, key) and getattr(item, key) == value)
        return result

    def filter(self, *, type_=None, lang=None, attrs={}):
        """
        Return an iterable which produces a sequence of the elements inside
        this :class:`XSOList`, filtered by the criteria given as arguments. The
        function starts with a working sequence consisting of the whole list.

        If `type_` is not :data:`None`, elements which are not an instance of
        the given type are excluded from the working sequence.

        If `lang` is not :data:`None`, it must be either a
        :class:`~.structs.LanguageRange` or an iterable of language ranges. The
        set of languages present among the working sequence is determined and
        used for a call to
        :class:`~.structs.lookup_language`. If the lookup returns a language,
        all elements whose :attr:`lang` is different from that value are
        excluded from the working sequence.

        .. note::

           If an iterable of language ranges is given, it is evaluated into a
           list. This may be of concern if a huge iterable is about to be used
           for language ranges, but it is an requirement of the
           :class:`~.structs.lookup_language` function which is used under the
           hood.

        .. note::

           Filtering by language assumes that the elements have a
           :class:`~aioxmpp.xso.LangAttr` descriptor named ``lang``.

        If `attrs` is not empty, the filter iterates over each `key`-`value`
        pair. For each iteration, all elements which do not have an attribute
        of the name in `key` or where that attribute has a value not equal to
        `value` are excluded from the working sequence.

        In general, the iterable returned from :meth:`filter` can only be used
        once. It is dynamic in the sense that changes to elements which are in
        the list *behind* the last element returned from the iterator will
        still be picked up when the iterator is resumed.
        """
        result = self
        if type_ is not None:
            result = self._filter_type(result, type_)
        if lang is not None:
            result = self._filter_lang(result, lang)
        if attrs:
            result = self._filter_attrs(result, attrs)
        return result

    def filtered(self, *, type_=None, lang=None, attrs={}):
        """
        This method is a convencience wrapper around :meth:`filter` which
        evaluates the result into a list and returns that list.
        """
        return list(self.filter(type_=type_, lang=lang, attrs=attrs))


class PropBaseMeta(type):
    def __instancecheck__(self, instance):
        if (isinstance(instance, xso_query.BoundDescriptor) and
                super().__instancecheck__(instance.xq_descriptor)):
            return True
        return super().__instancecheck__(instance)


class _PropBase(metaclass=PropBaseMeta):
    class NO_DEFAULT:
        def __repr__(self):
            return "<no default>"

        def __bool__(self):
            raise TypeError("cannot convert {!r} to bool".format(self))

    NO_DEFAULT = NO_DEFAULT()

    class __INCOMPLETE:
        def __repr__(self):
            return "<incomplete value>"

        def __bool__(self):
            raise TypeError("cannot convert {!r} to bool".format(self))

    __INCOMPLETE = __INCOMPLETE()

    def __init__(self, default=NO_DEFAULT,
                 *,
                 validator=None,
                 validate=ValidateMode.FROM_RECV):
        super().__init__()
        self.default = default
        self.validate = validate
        self.validator = validator

    def _set(self, instance, value):
        instance._xso_contents[self] = value

    def __set__(self, instance, value):
        if (self.default != value and
                self.validate.from_code and
                self.validator and
                not self.validator.validate(value)):
            raise ValueError("invalid value")
        self._set(instance, value)

    def _set_from_code(self, instance, value):
        self.__set__(instance, value)

    def _set_from_recv(self, instance, value):
        if (self.default != value and
                self.validate.from_recv and
                self.validator and
                not self.validator.validate(value)):
            raise ValueError("invalid value")
        self._set(instance, value)

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetDescriptor,
            )
        try:
            value = instance._xso_contents[self]
        except KeyError:
            if self.default is self.NO_DEFAULT:
                raise AttributeError(
                    "attribute is unset ({} on instance of {})".format(
                        self, type_)
                ) from None
            return self.default
        if value is self.__INCOMPLETE:
            raise AttributeError(
                "attribute value is incomplete"
            )
        return value

    def mark_incomplete(self, instance):
        instance._xso_contents[self] = self.__INCOMPLETE

    def validate_contents(self, instance):
        try:
            self.__get__(instance, type(instance))
        except AttributeError as exc:
            raise ValueError(str(exc)) from None

    def to_node(self, instance, parent):
        handler = lxml.sax.ElementTreeContentHandler(
            makeelement=parent.makeelement)
        handler.startDocument()
        handler.startElementNS((None, "_"), None, {})
        self.to_sax(instance, handler)

        parent.extend(handler.etree.getroot())


class _TypedPropBase(_PropBase):
    def __init__(self, *,
                 type_=xso_types.String(),
                 erroneous_as_absent=False,
                 **kwargs):
        super().__init__(**kwargs)
        self.type_ = type_
        self.erroneous_as_absent = erroneous_as_absent

    def __set__(self, instance, value):
        if self.default is self.NO_DEFAULT or value != self.default:
            value = self.type_.coerce(value)
        super().__set__(instance, value)


class Text(_TypedPropBase):
    """
    Character data contents of an XSO.

    Note that this does not preserve the relative ordering of child elements
    and character data pieces. This is known and a WONTFIX, as it is not
    required in XMPP to keep that relative order: Elements either have
    character data *or* other elements as children.

    The `type_`, `validator`, `validate`, `default` and `erroneous_as_absent`
    arguments behave like in :class:`Attr`.

    .. automethod:: from_value

    .. automethod:: to_sax

    """

    def from_value(self, instance, value):
        """
        Convert the given value using the set `type_` and store it into
        `instance`’ attribute.
        """
        try:
            parsed = self.type_.parse(value)
        except (TypeError, ValueError):
            if self.erroneous_as_absent:
                return False
            raise
        self._set_from_recv(instance, parsed)
        return True

    def to_sax(self, instance, dest):
        """
        Assign the formatted value stored at `instance`’ attribute to the text
        of `el`.

        If the `value` is :data:`None`, no text is generated.
        """
        value = self.__get__(instance, type(instance))
        if value is None:
            return
        dest.characters(self.type_.format(value))


class _ChildPropBase(_PropBase):
    """
    This is a base class for descriptors related to child :class:`XSO`
    instances.

    It provides a few implementation parts shared between :class:`Child`,
    :class:`ChildList` and :class:`ChildMap`.
    """

    def __init__(self, classes, default=None):
        super().__init__(default)
        self._classes = set()
        self._tag_map = {}

        for cls in classes:
            self._register(cls)

    def _process(self, instance, ev_args, ctx):
        cls = self._tag_map[ev_args[0], ev_args[1]]
        return (yield from cls.parse_events(ev_args, ctx))

    def get_tag_map(self):
        """
        Return a dictionary mapping the tags of the supported classes to the
        classes themselves. Can be used to obtain a set of supported tags.
        """
        return self._tag_map

    def _register(self, cls):
        if cls.TAG in self._tag_map:
            raise ValueError("ambiguous children: {} and {} share the same "
                             "TAG".format(
                                 self._tag_map[cls.TAG],
                                 cls))
        self._tag_map[cls.TAG] = cls
        self._classes.add(cls)


class ChildValue(_ChildPropBase):
    """
    Child element parsed using an :term:`Element Type`.

    Descriptor represeting a child element as parsed using an element type.

    :param type_: The element type to use to parse the child element.
    :type type_: :class:`aioxmpp.xso.AbstractElementType`

    The descriptor value will be the unpacked child element value. Upon
    serialisation, the descriptor
    """

    def __init__(self, type_):
        super().__init__(type_.get_xso_types())
        self.type_ = type_

    def from_events(self, instance, ev_args, ctx):
        xso = (yield from super()._process(instance, ev_args, ctx))
        value = self.type_.unpack(xso)
        self._set_from_recv(instance, value)

    def to_sax(self, instance, dest):
        value = self.__get__(instance, type(instance))
        packed = self.type_.pack(value)
        packed.xso_serialise_to_sax(dest)


class Child(_ChildPropBase):
    """
    A single child element of any of the given XSO types.

    :param classes: XSO types to support in this attribute
    :type classes: iterable of :class:`aioxmpp.xso.XSO` subclasses
    :param required: If true, parsing fails if the element is missing.
    :type required: :class:`bool`
    :param strict: Enable strict type checking on assigned values.
    :type strict: :class:`bool`

    The tags among the `classes` must be unique, otherwise :class:`ValueError`
    is raised on construction.

    Instead of the `default` argument like supplied by :class:`Attr`,
    :class:`Child` only supports `required`: if `required` is a false value
    (the default), a missing child is tolerated and :data:`None` is a valid
    value for the described attribute. Otherwise, a missing matching child is
    an error and the attribute cannot be set to :data:`None`.

    If `strict` is true, only instances of the exact classes registered with
    the descriptor can be assigned to it. Subclasses of the registered classes
    also need to be registered explicitly to be allowed as types for values.

    This comes with a performance impact on every write to the descriptor, so
    it is disabled by default. It is recommended to enable this for descriptors
    where applications may register additional classes, to protect them from
    forgetting such a registration (which would cause issues with reception).

    If during parsing, more than one child element with a tag matching one of
    the :attr:`.XSO.TAG` values of the registered `classes` is encountered,
    it is unspecified which child is taken.

    .. automethod:: get_tag_map

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self, classes, required=False, strict=False):
        super().__init__(
            classes,
            default=_PropBase.NO_DEFAULT if required else None
        )
        self.__strict = strict

    @property
    def required(self):
        return self.default is _PropBase.NO_DEFAULT

    @property
    def strict(self):
        return self.__strict

    def __set__(self, instance, value):
        if value is None and self.required:
            raise ValueError("cannot set required member to None")
        if (self.__strict and
                value is not None and
                type(value) not in self._classes):
            raise TypeError("{!r} object is not a valid value".format(
                type(value)
            ))
        super().__set__(instance, value)

    def __delete__(self, instance):
        if self.required:
            raise AttributeError("cannot delete required member")
        try:
            del instance._xso_contents[self]
        except KeyError:
            pass

    def from_events(self, instance, ev_args, ctx):
        """
        Detect the object to instantiate from the arguments `ev_args` of the
        ``"start"`` event. The new object is stored at the corresponding
        descriptor attribute on `instance`.

        This method is suspendable.
        """
        obj = yield from self._process(instance, ev_args, ctx)
        self.__set__(instance, obj)
        return obj

    def validate_contents(self, instance):
        try:
            obj = self.__get__(instance, type(instance))
        except AttributeError:
            raise ValueError("missing required member")
        if obj is not None:
            obj.validate()

    def to_sax(self, instance, dest):
        """
        Take the object associated with this descriptor on `instance` and
        serialize it as child into the given :class:`lxml.etree.Element`
        `parent`.

        If the object is :data:`None`, no content is generated.
        """
        obj = self.__get__(instance, type(instance))
        if obj is None:
            return
        obj.xso_serialise_to_sax(dest)


class ChildList(_ChildPropBase):
    """
    List of child elements of any of the given XSO classes.

    The :class:`ChildList` works like :class:`Child`, with two key differences:

    * multiple children which are matched by this descriptor get collected into
      an :class:`~aioxmpp.xso.model.XSOList`.
    * the default is fixed at an empty list.
    * `required` is not supported

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self, classes):
        super().__init__(classes)

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetSequenceDescriptor,
            )

        return instance._xso_contents.setdefault(self, XSOList())

    def _set(self, instance, value):
        if not isinstance(value, list):
            raise TypeError("expected list, but found {}".format(type(value)))
        return super()._set(instance, value)

    def from_events(self, instance, ev_args, ctx):
        """
        Like :meth:`.Child.from_events`, but instead of replacing the attribute
        value, the new object is appended to the list.
        """

        obj = yield from self._process(instance, ev_args, ctx)
        self.__get__(instance, type(instance)).append(obj)
        return obj

    def validate_contents(self, instance):
        for child in self.__get__(instance, type(instance)):
            child.validate()

    def to_sax(self, instance, dest):
        """
        Like :meth:`.Child.to_node`, but instead of serializing a single
        object, all objects in the list are serialized.
        """

        for obj in self.__get__(instance, type(instance)):
            obj.xso_serialise_to_sax(dest)


class Collector(_PropBase):
    """
    Catch-all descriptor collecting unhandled elements in an :mod:`lxml`
    element tree.

    When assigned to a class’ attribute, it collects all children which are not
    known to any other descriptor into an XML tree. The root node has the tag
    of the XSO class it pertains to.

    The default is fixed to the empty root node.

    .. versionchanged:: 0.10

       Before the subtrees were collected in a list. This was changed to an
       ElementTree to allow using XPath over all collected elements. Most code
       should not be affected by this, since the interface is very similar.
       Assignment is now forbidden. Use ``[:] =`` instead.

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self):
        super().__init__(default=[])

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetSequenceDescriptor,
            )

        try:
            return instance._xso_contents[self]
        except KeyError:
            res = etree.Element(tag_to_str(instance.TAG))
            instance._xso_contents[self] = res
            return res

    def _set(self, instance, value):
        raise AttributeError("Collector attribute cannot be assigned to")

    def from_events(self, instance, ev_args, ctx):
        """
        Collect the events and convert them to a single XML subtree, which then
        gets appended to the list at `instance`. `ev_args` must be the
        arguments of the ``"start"`` event of the new child.

        This method is suspendable.
        """

        # goal: collect all elements starting with the element for which we got
        # the start-ev_args in a lxml.etree.Element.

        def make_from_args(ev_args, parent):
            el = etree.SubElement(parent,
                                  tag_to_str((ev_args[0], ev_args[1])))
            for key, value in ev_args[2].items():
                el.set(tag_to_str(key), value)
            return el

        root_el = make_from_args(ev_args,
                                 self.__get__(instance, type(instance)))
        # create an element stack
        stack = [root_el]
        while stack:
            # we get send all sax-ish events until we return. we return when
            # the stack is empty, i.e. when our top element ended.
            ev_type, *ev_args = yield
            if ev_type == "start":
                # new element started, create and push to stack
                stack.append(make_from_args(ev_args, stack[-1]))
            elif ev_type == "text":
                # text for current element
                curr = stack[-1]
                if curr.text is not None:
                    curr.text += ev_args[0]
                else:
                    curr.text = ev_args[0]
            elif ev_type == "end":
                # element ended, remove from stack (it is already appended to
                # the current element)
                stack.pop()
            else:
                # not in coverage -- this is more like an assertion
                raise ValueError(ev_type)

    def to_sax(self, instance, dest):
        for node in self.__get__(instance, type(instance)):
            lxml.sax.saxify(node, _CollectorContentHandlerFilter(dest))


class Attr(Text):
    """
    A single XML attribute.

    :param tag: The tag identifying the attribute.
    :type tag: :class:`str` or :class:`tuple` of :term:`Namespace URI` and
        :term:`Local Name`.

    If the `tag` is a :class:`str`, it is converted using ``(None, tag)``,
    thus representing an unnamespaced attribute. Note that most attributes
    are unnamespaced; namespaced attributes always have a namespace prefix
    on them. Attributes without a namespace prefix, in XML, are unnamespaced
    (*not* part of the current prefixless namespace).

    .. note::

        The following arguments occur at several of the descriptor classes,
        and are all available at :class:`Attr`. Their semantics are identical
        on other classes, transferred to the respective use there.

        (For example, the :class:`ChildText` descriptor is obviously not
        working with attributes, so the phrase "if the attribute is absent"
        should be mentally translated to "if the child element is absent".)

    :param type_: A character data type to interpret the XML character data.
    :type type_: :class:`~.xso.AbstractCDataType`
    :param validator: Optional validator object
    :type validator: :class:`~.xso.AbstractValidator`
    :param validate: Control when the `validator` is enforced.
    :type validate: :class:`ValidateMode`
    :param default: The value which the attribute has if no value has been
        assigned.
    :param missing: Callback function to handle a missing attribute in the
        input.
    :type missing: :data:`None` or unary function
    :param erroneous_as_absent: Treat an erroneous value (= the `type_` raises
        :class:`ValueError` or :class:`TypeError` while parsing) as if the
        attribute was not present.
    :type erroneous_as_absent: :class:`bool`

    The `type_` must be a :term:`Character Data Type`, i.e. an instance of a
    subclass of :class:`AbstractCDataType`. By default, it is
    :class:`aioxmpp.xso.String`. The `type_` is used to parse the XML character
    data into python types as appropriate. Errors during this parsing count
    as parsing errors of the whole XSO (subtree), unless `erroneous_as_absent`
    is set to true. In that case, the attribute is simply treated as absent
    if parsing the value fails.

    If the XML attribute has no default assigned, the descriptor will appear
    to have the `default` value. If no `default` is given (the default) and
    an attempt is made to access the described attribute,
    :class:`AttributeError` is raised as you would expect from any normal
    attribute.

    If a `default` is given, the `default` is also returned after a `del`
    operation; otherwise, `del` behaves as for any normal attribute.

    Another peculiar property of the `default` is that it does not need to
    conform to the `validator` or `type_`. If the descriptor is set to the
    default value, it is *not* emitted on the output.

    In addition to the `default`, it is possible to inject attribute values
    at parse time using the `missing` callback. `missing` must be None or a
    function taking a single argument. If it is not None, it will be called
    with the parsing :class:`Context` as its only argument when a missing
    attribute is encountered. The return value, unless :data:`None`, is used
    as value for the descriptor. If the return value is :data:`None`, the
    attribute is treated like any normal missing attribute.

    It is possible to add validation to values received over the wire or
    assigned to the descriptor. The `validator` object controls *what*
    validation occurs and `validate` controls *when* validation occurs.

    `validate` must be a member of the :class:`ValidateMode` enumeration (see
    there for the semantics of the values). `validator` must be an object
    implementing the interface defined by :class:`AbstractValidator`.

    Note that validation is independent of the conversions applied by `type_`.
    Validation always happens on the parsed type and happens before
    serialisation. Thus, if `type_` is not :class:`aioxmpp.xso.String`, the
    validator will not receive a :class:`str` object to operate on.

    .. seealso::

       :class:`LangAttr`, which is a subclass of :class:`Attr` specialized for
       describing ``xml:lang`` attributes.

    .. note::

       The `default` argument does not need to comply with either `type_` or
       `validator`. This can be used to convey meaning with the absence of the
       attribute. Note that assigning the default value is not possible if it
       does not comply with `type_` or `validator` and the ``del`` operator
       must be used instead.

    .. automethod:: from_value

    .. automethod:: handle_missing

    .. automethod:: to_dict

    """

    def __init__(self, tag, *,
                 type_=xso_types.String(),
                 missing=None,
                 **kwargs):
        super().__init__(type_=type_, **kwargs)
        self.tag = normalize_tag(tag)
        self.missing = missing

    def __set__(self, instance, value):
        super().__set__(instance, value)

    def __delete__(self, instance):
        try:
            del instance._xso_contents[self]
        except KeyError:
            pass

    def handle_missing(self, instance, ctx):
        """
        Handle a missing attribute on `instance`. This is called whenever no
        value for the attribute is found during parsing. The call to
        :meth:`missing` is independent of the value of `required`.

        If the `missing` callback is not :data:`None`, it is called with the
        `instance` and the `ctx` as arguments. If the returned value is not
        :data:`None`, it is used as the value of the attribute (validation
        takes place as if the value had been set from the code, not as if the
        value had been received from XML) and the handler returns.

        If the `missing` callback is :data:`None` or returns :data:`None`, the
        handling continues as normal: if `required` is true, a
        :class:`ValueError` is raised.
        """
        if self.missing is not None:
            value = self.missing(instance, ctx)
            if value is not None:
                self._set_from_code(instance, value)
                return

        if self.default is _PropBase.NO_DEFAULT:
            raise ValueError("missing attribute {} on {}".format(
                tag_to_str(self.tag),
                tag_to_str(instance.TAG),
            ))

        # no need to set explicitly, it will be handled by _PropBase.__get__

    def validate_contents(self, instance):
        try:
            self.__get__(instance, type(instance))
        except AttributeError:
            raise ValueError("non-None value required for {}".format(
                tag_to_str(self.tag)
            )) from None

    def to_dict(self, instance, d):
        """
        Override the implementation from :class:`Text` by storing the formatted
        value in the XML attribute instead of the character data.

        If the value is :data:`None`, no element is generated.
        """

        value = self.__get__(instance, type(instance))
        if value == self.default:
            return

        d[self.tag] = self.type_.format(value)


class LangAttr(Attr):
    """
    Special handler for the ``xml:lang`` attribute.

    An attribute representing the ``xml:lang`` attribute, including inheritance
    semantics.

    This is a subclass of :class:`Attr` which takes care of inheriting the
    ``xml:lang`` value of the parent. The `tag` is set to the
    ``(namespaces.xml, "lang")`` value to match ``xml:lang`` attributes.
    `type_` is a :class:`xso.LanguageTag` instance and `missing` is set to
    :func:`lang_attr`.

    Note that :class:`LangAttr` overrides `default` to be :data:`None` by
    default.
    """

    def __init__(self, default=None, **kwargs):
        super().__init__(
            (namespaces.xml, "lang"),
            default=default,
            type_=xso_types.LanguageTag(),
            missing=lang_attr
        )


class ChildText(_TypedPropBase):
    """
    Character data of a single child element matching the given tag.

    When assigned to a class’ attribute, it binds that attribute to the XML
    character data of a child element with the given `tag`. `tag` must be a
    valid input to :func:`normalize_tag`.

    :param child_policy: The policy to apply when children are found in the
        child element whose text this descriptor represents.
    :type child_policy: :class:`UnknownChildPolicy`
    :param attr_policy: The policy to apply when attributes are found at the
        child element whose text this descriptor represents.
    :type attr_policy: :class:`UnknownAttrPolicy`

    The `type_`, `validate`, `validator`, `default` and `erroneous_as_absent`
    arguments behave like in :class:`Attr`.

    `declare_prefix` works as for :class:`ChildTag`.

    `child_policy` and `attr_policy` describe how the parser behaves when an
    unknown child or attribute (respectively) is encountered on the child
    element whose text this descriptor represents. See
    :class:`UnknownChildPolicy` and :class:`UnknownAttrPolicy` for the possible
    behaviours.

    .. automethod:: get_tag_map

    .. automethod:: from_events

    .. automethod:: to_sax

    """

    def __init__(self, tag,
                 *,
                 child_policy=UnknownChildPolicy.FAIL,
                 attr_policy=UnknownAttrPolicy.FAIL,
                 declare_prefix=False,
                 **kwargs):
        super().__init__(**kwargs)
        self.tag = normalize_tag(tag)
        self.child_policy = child_policy
        self.attr_policy = attr_policy
        self.declare_prefix = declare_prefix

    def get_tag_map(self):
        """
        Return an iterable yielding :attr:`tag`.

        This is for compatibility with the :class:`Child` interface.
        """
        return {self.tag}

    def from_events(self, instance, ev_args, ctx):
        """
        Starting with the element to which the start event information in
        `ev_args` belongs, parse text data. If any children are encountered,
        :attr:`child_policy` is enforced (see
        :class:`UnknownChildPolicy`). Likewise, if the start event contains
        attributes, :attr:`attr_policy` is enforced
        (c.f. :class:`UnknownAttrPolicy`).

        The extracted text is passed through :attr:`type_` and
        :attr:`validator` and if it passes, stored in the attribute on the
        `instance` with which the property is associated.

        This method is suspendable.
        """

        # goal: take all text inside the child element and collect it as
        # attribute value

        attrs = ev_args[2]
        if attrs and self.attr_policy == UnknownAttrPolicy.FAIL:
            raise ValueError("unexpected attribute (at text only node)")
        parts = []
        while True:
            ev_type, *ev_args = yield
            if ev_type == "text":
                # collect ALL TEH TEXT!
                parts.append(ev_args[0])
            elif ev_type == "start":
                # ok, a child inside the child was found, we look at our policy
                # to see what to do
                yield from enforce_unknown_child_policy(
                    self.child_policy,
                    ev_args)
            elif ev_type == "end":
                # end of our element, return
                break

        joined = "".join(parts)
        try:
            parsed = self.type_.parse(joined)
        except (ValueError, TypeError):
            if self.erroneous_as_absent:
                return
            raise
        self._set_from_recv(instance, parsed)

    def to_sax(self, instance, dest):
        """
        Create a child node at `parent` with the tag :attr:`tag`. Set the text
        contents to the value of the attribute which this descriptor represents
        at `instance`.

        If the value is :data:`None`, no element is generated.
        """

        value = self.__get__(instance, type(instance))
        if value == self.default:
            return

        if self.declare_prefix is not False and self.tag[0]:
            dest.startPrefixMapping(self.declare_prefix, self.tag[0])
        dest.startElementNS(self.tag, None, {})
        try:
            dest.characters(self.type_.format(value))
        finally:
            dest.endElementNS(self.tag, None)
            if self.declare_prefix is not False and self.tag[0]:
                dest.endPrefixMapping(self.declare_prefix)


class ChildMap(_ChildPropBase):
    """
    Dictionary holding child elements of one or more XSO classes.

    The :class:`ChildMap` class works like :class:`ChildList`, but instead of
    storing the child objects in a list, they are stored in a map which
    contains an :class:`~aioxmpp.xso.model.XSOList` of objects for each tag.

    `key` may be callable. If it is given, it is used while parsing to
    determine the dictionary key under which a newly parsed XSO will be
    put. For that, the `key` callable is called with the newly parsed XSO as
    the only argument and is expected to return the key.

    .. automethod:: from_events

    .. automethod:: to_sax

    The following utility function is useful when filling data into descriptors
    using this class:

    .. automethod:: fill_into_dict

    """

    def __init__(self, classes, *, key=None):
        super().__init__(classes)
        self.key = key or (lambda obj: obj.TAG)

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetMappingDescriptor,
            )

        return instance._xso_contents.setdefault(
            self,
            collections.defaultdict(XSOList)
        )

    def __set__(self, instance, value):
        raise AttributeError("ChildMap attribute cannot be assigned to")

    def _set(self, instance, value):
        if not isinstance(value, dict):
            raise TypeError("expected dict, but found {}".format(type(value)))
        return super()._set(instance, value)

    def fill_into_dict(self, items, dest):
        """
        Take an iterable of `items` and group it into the given `dest` dict,
        using the :attr:`key` function.

        The `dest` dict must either already contain the keys which are
        generated by the :attr:`key` function for the items in `items`, or must
        default them suitably. The values of the affected keys must be
        sequences or objects with an :meth:`append` method which does what you
        want it to do.
        """
        for item in items:
            dest[self.key(item)].append(item)

    def from_events(self, instance, ev_args, ctx):
        """
        Like :meth:`.ChildList.from_events`, but the object is appended to the
        list associated with its tag in the dict.
        """

        tag = ev_args[0], ev_args[1]
        cls = self._tag_map[tag]
        obj = yield from cls.parse_events(ev_args, ctx)
        mapping = self.__get__(instance, type(instance))
        mapping[self.key(obj)].append(obj)

    def validate_contents(self, instance):
        mapping = self.__get__(instance, type(instance))
        for objects in mapping.values():
            for obj in objects:
                obj.validate()

    def to_sax(self, instance, dest):
        """
        Serialize all objects in the dict associated with the descriptor at
        `instance` to the given `parent`.

        The order of elements within a tag is preserved; the order of the tags
        relative to each other is undefined.
        """

        for items in self.__get__(instance, type(instance)).values():
            for obj in items:
                obj.xso_serialise_to_sax(dest)


class ChildLangMap(ChildMap):
    """
    Shorthand for a dictionary of child elements keyed by the language
    attribute.

    The :class:`ChildLangMap` class is a specialized version of the
    :class:`ChildMap`, which uses a `key` function to group the children by
    their XML language tag.

    It is expected that the language tag is available as ``lang`` attribute on
    the objects stored in this map.
    """

    @staticmethod
    def _lang_key(obj):
        return obj.lang

    def __init__(self, classes, **kwargs):
        super().__init__(classes, key=self._lang_key, **kwargs)


class ChildTag(_PropBase):
    """
    Tag of a single child element with one of the given tags.

    :param tags: The tags to match on.
    :type tags: iterable of valid arguments to :func:`normalize_tags` or
        a :class:`enum.Enum` subclass
    :param text_policy: Determine how text content on the child elements is
        handled.
    :type text_policy: :class:`UnknownTextPolicy`
    :param child_policy: Determine how elements nested in the child elements
        are handled.
    :type child_policy: :class:`UnknownChildPolicy`
    :param attr_policy: Determine how attributes on the child elements are
        handled.
    :type attr_policy: :class:`UnknownAttrPolicy`
    :param allow_none: If true, :data:`None` is used as the default if no
        child matching the tags is found and represents the absence of the
        child for serialisation.
    :type allow_none: :class:`bool`
    :param declare_prefix: Which namespace prefix, if any, to declare on the
        child element for its namespace.
    :type declare_prefix: :data:`False`, :data:`None` or :class:`str`

    When assigned to a class’ attribute, this descriptor represents the
    presence or absence of a single child with a tag from a given set of valid
    tags.

    `tags` must be an iterable of valid arguments to
    :func:`normalize_tag` or an :class:`enum.Enum` whose values are
    valid arguments to :func:`normalize_tag`. If :func:`normalize_tag`
    returns a false value (such as :data:`None`) as `namespace_uri`,
    it is replaced with `default_ns` (defaulting to :data:`None`,
    which makes this sentence a no-op). This allows a benefit to
    readability if you have many tags which share the same namespace.
    This is, however, not allowed for tags given as enumeration.

    `text_policy`, `child_policy` and `attr_policy` describe the behaviour if
    the child element unexpectedly has text, children or attributes,
    respectively. The default for each is to fail with a :class:`ValueError`.

    If `allow_none` is :data:`True`, assignment of :data:`None` to the
    attribute to which this descriptor belongs is allowed and represents the
    absence of the child element.

    If `declare_prefix` is not :data:`False` (note that :data:`None` is a
    valid, non-:data:`False` value in this context!), the namespace is
    explicitly declared using the given prefix when serializing to SAX.

    .. automethod:: from_events

    .. automethod:: to_sax

    """

    class ConvertEnum:

        def __init__(self, enum_=None):
            self._enum = enum_

        def parse(self, v):
            return self._enum(normalize_tag(v))

        def format(self, v):
            return tag_to_str(v.value)

    class ConvertTag:

        def parse(self, v):
            return normalize_tag(v)

        def format(self, v):
            return tag_to_str(v)

    def __init__(self, tags, *,
                 default_ns=None,
                 text_policy=UnknownTextPolicy.FAIL,
                 child_policy=UnknownChildPolicy.FAIL,
                 attr_policy=UnknownAttrPolicy.FAIL,
                 allow_none=False,
                 declare_prefix=False):

        def normalize_tags(tags):
            return {
                (ns or default_ns, localname)
                for ns, localname in map(normalize_tag, tags)
            }

        if isinstance(tags, type(enum.Enum)):
            self._converter = self.ConvertEnum(tags)
            values = list(tags)
            tags = normalize_tags([tag.value for tag in tags])
        else:
            self._converter = self.ConvertTag()
            tags = normalize_tags(tags)
            values = tags

        super().__init__(
            default=None if allow_none else _PropBase.NO_DEFAULT,
            validator=xso_types.RestrictToSet(values),
            validate=ValidateMode.ALWAYS)

        self.child_map = tags
        self.text_policy = text_policy
        self.attr_policy = attr_policy
        self.child_policy = child_policy
        self.declare_prefix = declare_prefix

    @property
    def allow_none(self):
        return self.default is not _PropBase.NO_DEFAULT

    def get_tag_map(self):
        return self.child_map

    def from_events(self, instance, ev_args, ctx):
        attrs = ev_args[2]
        if attrs and self.attr_policy == UnknownAttrPolicy.FAIL:
            raise ValueError("unexpected attributes")
        tag = ev_args[0], ev_args[1]
        while True:
            ev_type, *ev_args = yield
            if ev_type == "text":
                if self.text_policy == UnknownTextPolicy.FAIL:
                    raise ValueError("unexpected text")
            elif ev_type == "start":
                yield from enforce_unknown_child_policy(
                    self.child_policy,
                    ev_args)
            elif ev_type == "end":
                break
        self._set_from_recv(instance, self._converter.parse(tag))

    def to_sax(self, instance, dest):
        value = self.__get__(instance, type(instance))
        if value is None:
            return

        value = normalize_tag(self._converter.format(value))

        if self.declare_prefix is not False and value[0]:
            dest.startPrefixMapping(self.declare_prefix, value[0])
        dest.startElementNS(value, None, {})
        dest.endElementNS(value, None)
        if self.declare_prefix is not False and value[0]:
            dest.endPrefixMapping(self.declare_prefix)


class ChildFlag(_PropBase):
    """
    Presence of a child element with the given tag, as boolean.

    :param tag: The tag of the child element to use as flag.
    :type tag: :class:`str` or :class:`tuple`
    :param text_policy: Determine how text content on the child elements is
        handled.
    :type text_policy: :class:`UnknownTextPolicy`
    :param child_policy: Determine how elements nested in the child elements
        are handled.
    :type child_policy: :class:`UnknownChildPolicy`
    :param attr_policy: Determine how attributes on the child elements are
        handled.
    :type attr_policy: :class:`UnknownAttrPolicy`
    :type declare_prefix: :data:`False`, :data:`None` or :class:`str`

    When used as a :class:`XSO` descriptor, it represents the presence or
    absence of a single child with the given `tag`. The presence or absence is
    represented by the values :data:`True` and :data:`False` respectively.

    `tag` must be a valid tag.

    The default value for attributes using this descriptor is :data:`False`.

    `text_policy`, `child_policy` and `attr_policy` describe the behaviour if
    the child element unexpectedly has text, children or attributes,
    respectively. The default for each is to fail with a :class:`ValueError`.

    If `declare_prefix` is not :data:`False` (note that :data:`None` is a
    valid, non-:data:`False` value in this context!), the namespace is
    explicitly declared using the given prefix when serializing to SAX.
    """

    def __init__(self, tag,
                 text_policy=UnknownTextPolicy.FAIL,
                 child_policy=UnknownChildPolicy.FAIL,
                 attr_policy=UnknownAttrPolicy.FAIL,
                 declare_prefix=False):
        super().__init__(
            default=False,
        )
        self.tag = normalize_tag(tag)
        self.text_policy = text_policy
        self.attr_policy = attr_policy
        self.child_policy = child_policy
        self.declare_prefix = declare_prefix

    def get_tag_map(self):
        return {self.tag}

    def from_events(self, instance, ev_args, ctx):
        attrs = ev_args[2]
        if attrs and self.attr_policy == UnknownAttrPolicy.FAIL:
            raise ValueError("unexpected attributes")
        while True:
            ev_type, *ev_args = yield
            if ev_type == "text":
                if self.text_policy == UnknownTextPolicy.FAIL:
                    raise ValueError("unexpected text")
            elif ev_type == "start":
                yield from enforce_unknown_child_policy(
                    self.child_policy,
                    ev_args)
            elif ev_type == "end":
                break
        self._set_from_recv(instance, True)

    def to_sax(self, instance, dest):
        value = self.__get__(instance, type(instance))
        if not value:
            return

        if self.declare_prefix is not False and self.tag[0]:
            dest.startPrefixMapping(self.declare_prefix, self.tag[0])
        dest.startElementNS(self.tag, None, {})
        dest.endElementNS(self.tag, None)
        if self.declare_prefix is not False and self.tag[0]:
            dest.endPrefixMapping(self.declare_prefix)


class ChildValueList(_ChildPropBase):
    """
    List of child elements parsed using the given :term:`Element Type`.

    :param type_: Type describing the subtree to convert to python values.
    :type type_: :class:`~.xso.AbstractElementType`
    :param container_type: Type of the container to use.
    :type container_type: Subclass of :class:`~collections.abc.MutableSequence`
        or :class:`~collections.abc.MutableSet`

    This descriptor parses the XSO classes advertised by the `type_` (via
    :meth:`~.AbstractElementType.get_xso_types`) and exposes the unpacked
    values in a container.

    The optional `container_type` argument must, if given, be a callable which
    returns a mutable container supporting either :meth:`add` or :meth:`append`
    of the values used with the `type_` and iteration. It will be used instead
    of :class:`list` to create the values for the descriptor.

    .. versionadded:: 0.5
    """

    def __init__(self, type_, *, container_type=list):
        super().__init__(type_.get_xso_types())
        self.type_ = type_
        self.container_type = container_type
        try:
            self._add = container_type.append
        except AttributeError:
            self._add = container_type.add

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetSequenceDescriptor,
                expr_kwargs={"sequence_factory": self.container_type},
            )

        try:
            return instance._xso_contents[self]
        except KeyError:
            result = self.container_type()
            instance._xso_contents[self] = result
            return result

    def __set__(self, instance, value):
        raise AttributeError("child value list not writable")

    def from_events(self, instance, ev_args, ctx):
        obj = yield from self._process(instance, ev_args, ctx)
        value = self.type_.unpack(obj)
        self._add(self.__get__(instance, type(instance)), value)

    def to_sax(self, instance, dest):
        for value in self.__get__(instance, type(instance)):
            self.type_.pack(value).xso_serialise_to_sax(dest)


class ChildValueMap(_ChildPropBase):
    """
    Dictiorary of child elements parsed using the given :term:`Element Type`.

    :param type_: Type describing the subtree to convert to pairs of key and
        value.
    :type type_: :class:`~.xso.AbstractElementType`
    :param mapping_type: Type of the mapping to use.
    :type mapping_type: Subclass of :class:`~collections.abc.MutableMapping`

    This works very similar to :class:`ChildValueList`, but instead of a
    mutable sequence, the value of the descriptor is a mutable mapping.

    The `type_` must return key-value pairs from
    :meth:`.xso.AbstractElementType.unpack` and must accept such key-value
    pairs in :meth:`.xso.AbstractElementType.pack`.

    The optional `mapping_type` argument must, if given, be a callable which
    returns a :class:`collections.abc.MutableMapping` supporting the keys and
    values used by the `type_`. It will be used instead of :class:`dict` to
    create the values for the descriptor. A possible use-case is using
    :class:`.structs.LanguageMap` together with :class:`~.xso.TextChildMap`.

    .. seealso::

       :class:`ChildTextMap` for a specialised version to deal with
       :class:`AbstractTextChild` subclasses.

    .. versionadded:: 0.5
    """

    def __init__(self, type_, *, mapping_type=dict):
        super().__init__(type_.get_xso_types())
        self.type_ = type_
        self.mapping_type = mapping_type

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetMappingDescriptor,
                expr_kwargs={"mapping_factory": self.mapping_type}
            )

        try:
            return instance._xso_contents[self]
        except KeyError:
            result = self.mapping_type()
            instance._xso_contents[self] = result
            return result

    def __set__(self, instance, value):
        raise AttributeError("child value map not writable")

    def to_sax(self, instance, dest):
        for item in self.__get__(instance, type(instance)).items():
            self.type_.pack(item).xso_serialise_to_sax(dest)

    def from_events(self, instance, ev_args, ctx):
        obj = yield from self._process(instance, ev_args, ctx)
        key, value = self.type_.unpack(obj)
        self.__get__(instance, type(instance))[key] = value


class ChildValueMultiMap(_ChildPropBase):
    """
    Multi-dict of child elements parsed using the given :term:`Element Type`.

    :param type_: Type describing the subtree to convert to pairs of key and
        value.
    :type type_: :class:`~.xso.AbstractElementType`

    This is very similar to :class:`ChildValueMap`, but it uses a
    :class:`multidict.MultiDict` as storage. Interface-compatible classes can
    be substituted by passing them to `mapping_type`. Candidate for that are
    :class:`multidict.CIMultiDict`.

    .. note::

        :class:`multidict.MultiDict` (even the non-case-insensitve version)
        requires that the keys are strings, so there is only limited use in
        the context of :mod:`aioxmpp`.

    .. versionadded:: 0.6
    """

    def __init__(self, type_, *, mapping_type=multidict.MultiDict):
        super().__init__(type_.get_xso_types())
        self.type_ = type_
        self.mapping_type = mapping_type

    def __get__(self, instance, type_):
        if instance is None:
            return xso_query.BoundDescriptor(
                type_,
                self,
                xso_query.GetMappingDescriptor,
                expr_kwargs={"mapping_factory": self.mapping_type},
            )

        try:
            return instance._xso_contents[self]
        except KeyError:
            result = self.mapping_type()
            instance._xso_contents[self] = result
            return result

    def __set__(self, instance, value):
        raise AttributeError("child value multi map not writable")

    def to_sax(self, instance, dest):
        for key, value in self.__get__(instance, type(instance)).items():
            self.type_.pack((key, value)).xso_serialise_to_sax(dest)

    def from_events(self, instance, ev_args, ctx):
        obj = yield from self._process(instance, ev_args, ctx)
        key, value = self.type_.unpack(obj)
        self.__get__(instance, type(instance)).add(key, value)


class ChildTextMap(ChildValueMap):
    """
    Dictionary of character data in child elements keyed by the language
    attribute.

    A specialised version of :class:`ChildValueMap` which uses
    :class:`TextChildMap` together with :class:`.structs.LanguageMap` to
    convert the :class:`AbstractTextChild` subclass `xso_type` to and from
    a language-text mapping.

    If instead of an :class:`XSO` a tag is passed (that is, a valid
    argument to :func:`normalize_tag`) an :class:`AbstractTextChild`
    instance is created on demand.

    For an example, see :class:`.Message`.
    """

    def __init__(self, xso_type):
        if not isinstance(xso_type, XMLStreamClass):
            tag = normalize_tag(xso_type)

            xso_type = type(
                "TextChild" + tag[1],
                (AbstractTextChild,),
                {"TAG": tag},
            )

        super().__init__(
            xso_types.TextChildMap(xso_type),
            mapping_type=structs.LanguageMap
        )


def _mark_attributes_incomplete(attrs, obj):
    for attr in attrs:
        attr.mark_incomplete(obj)


class XMLStreamClass(xso_query.Class, abc.ABCMeta):
    """
    This metaclass is used to implement the fancy features of :class:`.XSO`
    classes and instances. Its documentation details on some of the
    restrictions and features of XML Stream Classes.

    .. note::

       There should be no need to use this metaclass directly when implementing
       your own XSO classes. Instead, derive from :class:`~.xso.XSO`.

    The following restrictions apply when a class uses the
    :class:`XMLStreamClass` metaclass:

    1. At no point in the inheritance tree there must exist more than one
       distinct :class:`~.xso.Text` descriptor. It is possible to inherit two
       identical text descriptors from several base classes though.

    2. The above applies equivalently for :class:`~.xso.Collector`
       descriptors.

    3. At no point in the inheritance tree there must exist more than one
       :class:`~.xso.Attr` descriptor which handles a given attribute tag. Like
       with :class:`~.xso.Text`, it is allowed that the same
       :class:`~.xso.Attr` descriptor is inherited through multiple paths from
       parent classes.

    4. The above applies likewise for element tags and :class:`~.xso.Child` (or
       similar) descriptors.

    Objects of this metaclass (i.e. classes) have some useful attributes. The
    following attributes are gathered from the namespace of the class, by
    collecting the different XSO-related descriptors:

    .. attribute:: TEXT_PROPERTY

       The :class:`~.xso.Text` descriptor object associated with this
       class. This is :data:`None` if no attribute using that descriptor is
       declared on the class.

    .. attribute:: COLLECTOR_PROPERTY

       The :class:`~.xso.Collector` descriptor object associated with this
       class. This is :data:`None` if no attribute using that descriptor is
       declared on the class.

    .. attribute:: ATTR_MAP

       A dictionary mapping attribute tags to the :class:`~.xso.Attr`
       descriptor objects for these attributes.

    .. attribute:: CHILD_MAP

       A dictionary mapping element tags to the :class:`~.xso.Child` (or
       similar) descriptor objects which accept these child elements.

    .. attribute:: CHILD_PROPS

       A set of all :class:`~.xso.Child` (or :class:`~.xso.ChildList`)
       descriptor objects of this class.

    .. attribute:: DECLARE_NS

       A dictionary which defines the namespace mappings which shall be
       declared when serializing this element. It must map namespace prefixes
       (such as :data:`None` or ``"foo"``) to namespace URIs.

       For maximum compatibility with legacy XMPP implementations (I’m looking
       at you, ejabberd!), :attr:`DECLARE_NS` is set by this metaclass unless
       it is provided explicitly when declaring the class:

       * If no :attr:`TAG` is set, :attr:`DECLARE_NS` is also not set. The
         attribute does not exist on the class in that case, unless it is
         inherited from a base class.

       * If :attr:`TAG` is set and at least one base class has a
         :attr:`DECLARE_NS`, :attr:`DECLARE_NS` is not auto generated, so that
         inheritance can take place.

       * If :attr:`TAG` is set and has a namespace (and no base class has a
         :attr:`DECLARE_NS`), :attr:`DECLARE_NS` is set to
         ``{ None: namespace }``, where ``namespace`` is the namespace of the
         :attr:`TAG`.

       * If :attr:`TAG` is set and does not have a namespace,
         :attr:`DECLARE_NS` is set to the empty dict. This should not occur
         outside testing, and support for tags without namespace might be
         removed in future versions.

       .. warning::

          It is discouraged to use namespace prefixes of the format
          ``"ns{:d}".format(n)``, for any given number `n`. These prefixes are
          reserved for ad-hoc namespace declarations, and attempting to use
          them may have unwanted side-effects.

       .. versionchanged:: 0.4

          The automatic generation of the :attr:`DECLARE_NS` attribute was
          added in 0.4.

    .. attribute:: __slots__

       The metaclass automatically sets this attribute to the empty tuple,
       unless a different value is set in the class or `protect` is passed as
       false to the metaclass.

       Thus, to disable the automatic setting of :attr:`__slots__`, inherit for
       example like this::

         class MyXSO(xso.XSO, protect=False):
             pass

       The rationale for this is that attributes on XSO instances are magic.
       Having a typo in an attribute may fail non-obviously, if it causes an
       entirely different semantic to be invoked at the peer (for example the
       :attr:`.Message.type_` attribute).

       Setting :attr:`__slots__` to empty by default prevents assigning any
       attribute not bound to an descriptor.

       .. seealso::

          :ref:`slots`
             The official Python documentation describes the semantics of the
             :attr:`__slots__` attribute in more detail.

       :class:`~.xso.XSO` automatically sets a sensible :attr:`__slots__`
       (including ``__weakref__``, but not ``__dict__``).

       .. versionadded:: 0.6

       .. note::

          If you need to stay compatible with versions before 0.6 *and* have
          arbitrary attributes writable, the correct way of doing things is to
          explicitly set :attr:`__slots__` to ``("__dict__",)`` in your class.
          You cannot use `protect` because it is not known in pre-0.6 versions.

    .. note::

       :class:`~.xso.XSO` defines defaults for more attributes which also
       must be present on objects which are used as XSOs.

    When inheriting from :class:`XMLStreamClass` objects, the properties are
    merged sensibly.

    Rebinding attributes of :class:`XMLStreamClass` instances (i.e. classes
    using this metaclass) is somewhat restricted. The following rules cannot be
    broken, attempting to do so will result in :class:`TypeError` being raised
    when setting the attribute:

    1. Existing descriptors for XSO purposes (such as :class:`.xso.Attr`)
       cannot be removed (either by assigning a new value to the name they are
       bound to or deleting the name).

    2. New descriptors can only be added if they do not violate the rules
       stated at the beginning of the :class:`XMLStreamClass` documentation.

    3. New descriptors can only be added if no subclasses exist (see
       :meth:`.xso.XSO.register_child` for reasons why).

    """

    def __new__(mcls, name, bases, namespace, protect=True):
        text_property = None
        child_map = {}
        child_props = sortedcollections.OrderedSet()
        attr_map = {}
        collector_property = None

        for base in reversed(bases):
            if not isinstance(base, XMLStreamClass):
                continue

            if base.TEXT_PROPERTY is not None:
                if (text_property is not None and
                        base.TEXT_PROPERTY.xq_descriptor is not text_property):
                    raise TypeError("multiple text properties in inheritance")
                text_property = base.TEXT_PROPERTY.xq_descriptor

            for key, prop in base.CHILD_MAP.items():
                try:
                    existing = child_map[key]
                except KeyError:
                    child_map[key] = prop
                else:
                    if existing is not prop:
                        raise TypeError("ambiguous Child properties inherited")

            child_props |= base.CHILD_PROPS

            for key, prop in base.ATTR_MAP.items():
                try:
                    existing = attr_map[key]
                except KeyError:
                    attr_map[key] = prop
                else:
                    if existing is not prop:
                        raise TypeError("ambiguous Attr properties inherited")

            if base.COLLECTOR_PROPERTY is not None:
                if (collector_property is not None and
                        base.COLLECTOR_PROPERTY.xq_descriptor is not
                        collector_property):
                    raise TypeError("multiple collector properties in "
                                    "inheritance")
                collector_property = base.COLLECTOR_PROPERTY.xq_descriptor

        for attrname, obj in namespace.items():
            if isinstance(obj, Attr):
                if obj.tag in attr_map:
                    raise TypeError("ambiguous Attr properties")
                attr_map[obj.tag] = obj
            elif isinstance(obj, Text):
                if text_property is not None:
                    raise TypeError("multiple Text properties on XSO class")
                text_property = obj
            elif isinstance(obj, (_ChildPropBase, ChildText, ChildTag,
                                  ChildFlag)):
                for key in obj.get_tag_map():
                    if key in child_map:
                        raise TypeError("ambiguous Child properties: {} and {}"
                                        " both use the same tag".format(
                                            child_map[key],
                                            obj))
                    child_map[key] = obj
                child_props.add(obj)
            elif isinstance(obj, Collector):
                if collector_property is not None:
                    raise TypeError("multiple Collector properties on XSO "
                                    "class")
                collector_property = obj

        namespace["TEXT_PROPERTY"] = text_property
        namespace["CHILD_MAP"] = child_map
        namespace["CHILD_PROPS"] = child_props
        namespace["ATTR_MAP"] = attr_map
        namespace["COLLECTOR_PROPERTY"] = collector_property

        try:
            tag = namespace["TAG"]
        except KeyError:
            tag = None
        else:
            try:
                namespace["TAG"] = tag = normalize_tag(tag)
            except ValueError:
                raise TypeError("TAG attribute has incorrect format")

        if (tag is not None and
                "DECLARE_NS" not in namespace and
                not any(hasattr(base, "DECLARE_NS") for base in bases)):
            if tag[0] is None:
                namespace["DECLARE_NS"] = {}
            else:
                namespace["DECLARE_NS"] = {
                    None: tag[0]
                }

        if protect:
            namespace.setdefault("__slots__", ())

        return super().__new__(mcls, name, bases, namespace)

    def __init__(cls, name, bases, namespace, protect=True):
        super().__init__(name, bases, namespace)

    def __setattr__(cls, name, value):
        try:
            existing = getattr(cls, name).xq_descriptor
        except AttributeError:
            pass
        else:
            if isinstance(existing, _PropBase):
                raise AttributeError("cannot rebind XSO descriptors")

        if isinstance(value, _PropBase) and cls.__subclasses__():
            raise TypeError("adding descriptors is forbidden on classes with"
                            " subclasses (subclasses: {})".format(
                                ", ".join(map(str, cls.__subclasses__()))
                            ))

        if isinstance(value, Attr):
            if value.tag in cls.ATTR_MAP:
                raise TypeError("ambiguous Attr properties")
            cls.ATTR_MAP[value.tag] = value

        elif isinstance(value, Text):
            if cls.TEXT_PROPERTY is not None:
                raise TypeError("multiple Text properties on XSO class")
            super().__setattr__("TEXT_PROPERTY", value)

        elif isinstance(value, (_ChildPropBase, ChildText, ChildTag,
                                ChildFlag)):
            updates = {}
            for key in value.get_tag_map():
                if key in cls.CHILD_MAP:
                    raise TypeError("ambiguous Child properties: {} and {} "
                                    "both use the same tag".format(
                                        cls.CHILD_MAP[key],
                                        value))
                updates[key] = value
            cls.CHILD_MAP.update(updates)
            cls.CHILD_PROPS.add(value)

        elif isinstance(value, Collector):
            if cls.COLLECTOR_PROPERTY is not None:
                raise TypeError("multiple Collector properties on XSO class")
            super().__setattr__("COLLECTOR_PROPERTY", value)

        super().__setattr__(name, value)

    def __delattr__(cls, name):
        try:
            existing = getattr(cls, name).xq_descriptor
        except AttributeError:
            pass
        else:
            if isinstance(existing, _PropBase):
                raise AttributeError("cannot unbind XSO descriptors")

        super().__delattr__(name)

    def __prepare__(name, bases, **kwargs):
        return collections.OrderedDict()

    def parse_events(cls, ev_args, parent_ctx):
        """
        Create an instance of this class, using the events sent into this
        function. `ev_args` must be the event arguments of the ``"start"``
        event.

        .. seealso::

           You probably should not call this method directly, but instead use
           :class:`XSOParser` with a :class:`SAXDriver`.

        .. note::

           While this method creates an instance of the class, ``__init__`` is
           not called. See the documentation of :meth:`.xso.XSO` for details.

        This method is suspendable.
        """
        with parent_ctx as ctx:
            obj = cls.__new__(cls)
            attrs = ev_args[2]
            attr_map = cls.ATTR_MAP.copy()
            for key, value in attrs.items():
                try:
                    prop = attr_map.pop(key)
                except KeyError:
                    if cls.UNKNOWN_ATTR_POLICY == UnknownAttrPolicy.DROP:
                        continue
                    else:
                        raise ValueError(
                            "unexpected attribute {!r} on {}".format(
                                key,
                                tag_to_str((ev_args[0], ev_args[1]))
                            )) from None
                try:
                    if not prop.from_value(obj, value):
                        # assignment failed due to recoverable error, treat as
                        # absent
                        attr_map[key] = prop
                except Exception:
                    prop.mark_incomplete(obj)
                    _mark_attributes_incomplete(attr_map.values(), obj)
                    logger.debug("while parsing XSO %s (%r)", cls,
                                 value,
                                 exc_info=True)
                    # true means suppress
                    if not obj.xso_error_handler(
                            prop,
                            value,
                            sys.exc_info()):
                        raise

            for key, prop in attr_map.items():
                try:
                    prop.handle_missing(obj, ctx)
                except Exception:
                    logger.debug("while parsing XSO %s", cls,
                                 exc_info=True)
                    # true means suppress
                    if not obj.xso_error_handler(
                            prop,
                            None,
                            sys.exc_info()):
                        raise

            try:
                prop = cls.ATTR_MAP[namespaces.xml, "lang"]
            except KeyError:
                pass
            else:
                lang = prop.__get__(obj, cls)
                if lang is not None:
                    ctx.lang = lang

            collected_text = []
            while True:
                ev_type, *ev_args = yield
                if ev_type == "end":
                    break
                elif ev_type == "text":
                    if not cls.TEXT_PROPERTY:
                        if ev_args[0].strip():
                            # true means suppress
                            if not obj.xso_error_handler(
                                    None,
                                    ev_args[0],
                                    None):
                                raise ValueError("unexpected text")
                    else:
                        collected_text.append(ev_args[0])
                elif ev_type == "start":
                    try:
                        handler = cls.CHILD_MAP[ev_args[0], ev_args[1]]
                    except KeyError:
                        if cls.COLLECTOR_PROPERTY:
                            handler = cls.COLLECTOR_PROPERTY.xq_descriptor
                        else:
                            yield from enforce_unknown_child_policy(
                                cls.UNKNOWN_CHILD_POLICY,
                                ev_args,
                                obj.xso_error_handler)
                            continue
                    try:
                        yield from guard(
                            handler.from_events(obj, ev_args, ctx),
                            ev_args
                        )
                    except Exception:
                        logger.debug("while parsing XSO %s", type(obj),
                                     exc_info=True)
                        # true means suppress
                        if not obj.xso_error_handler(
                                handler,
                                ev_args,
                                sys.exc_info()):
                            raise

            if collected_text:
                collected_text = "".join(collected_text)
                try:
                    cls.TEXT_PROPERTY.xq_descriptor.from_value(
                        obj,
                        collected_text
                    )
                except Exception:
                    logger.debug("while parsing XSO", exc_info=True)
                    # true means suppress
                    if not obj.xso_error_handler(
                            cls.TEXT_PROPERTY.xq_descriptor,
                            collected_text,
                            sys.exc_info()):
                        raise

        obj.validate()

        obj.xso_after_load()

        return obj

    def register_child(cls, prop, child_cls):
        """
        Register a new :class:`XMLStreamClass` instance `child_cls` for a given
        :class:`Child` descriptor `prop`.

        .. warning::

           This method cannot be used after a class has been derived from this
           class. This is for consistency: the method modifies the bookkeeping
           attributes of the class. There would be two ways to deal with the
           situation:

           1. Updating all the attributes at all the subclasses and re-evaluate
              the constraints of inheritance. This is simply not implemented,
              although it would be the preferred way.

           2. Only update the bookkeeping attributes on *this* class, hiding
              the change from any existing subclasses. New subclasses would
              pick the change up, however, which is inconsistent. This is the
              way which was previously documented here and is not supported
              anymore.

           Obviously, (2) is bad, which is why it is not supported anymore. (1)
           might be supported at some point in the future.

           Attempting to use :meth:`register_child` on a class which already
           has subclasses results in a :class:`TypeError`.

        Note that *first* using :meth:`register_child` and only *then* deriving
        clasess is a valid use: it will still lead to a consistent inheritance
        hierarchy and is a convenient way to break reference cycles (e.g. if an
        XSO may be its own child).
        """
        if cls.__subclasses__():
            raise TypeError(
                "register_child is forbidden on classes with subclasses"
                " (subclasses: {})".format(
                    ", ".join(map(str, cls.__subclasses__()))
                ))

        if child_cls.TAG in cls.CHILD_MAP:
            raise ValueError("ambiguous Child")

        prop.xq_descriptor._register(child_cls)
        cls.CHILD_MAP[child_cls.TAG] = prop.xq_descriptor


# I know it makes only partially sense to have a separate metasubclass for
# this, but I like how :meth:`parse_events` is *not* accessible from
# instances.
class CapturingXMLStreamClass(XMLStreamClass):
    """
    This is a subclass of :meth:`XMLStreamClass`. It overrides the
    :meth:`parse_events` to capture the incoming events, including the initial
    event.

    .. see::

       :class:`CapturingXSO`

    .. automethod:: parse_events
    """

    def parse_events(cls, ev_args, parent_ctx):
        """
        Capture the events sent to :meth:`.XSO.parse_events`,
        including the initial `ev_args` to a list and call
        :meth:`_set_captured_events` on the result of
        :meth:`.XSO.parse_events`.

        Like the method it overrides, :meth:`parse_events` is suspendable.
        """

        dest = [("start", )+tuple(ev_args)]
        result = yield from capture_events(
            super().parse_events(ev_args, parent_ctx),
            dest
        )
        result._set_captured_events(dest)

        return result


class XSO(metaclass=XMLStreamClass):
    """
    XSO is short for **X**\\ ML **S**\\ tream **O**\\ bject and means an object
    which represents a subtree of an XML stream. These objects can also be
    created and validated on-the-fly from SAX-like events using
    :class:`XSOParser`.

    The constructor does not require any arguments and forwards them directly
    the next class in the resolution order. Note that during deserialization,
    ``__init__`` is not called. It is assumed that all data is loaded from the
    XML stream and thus no initialization is required.

    This is beneficial to applications, as it allows them to define mandatory
    arguments for ``__init__``. This would not be possible if ``__init__`` was
    called during deserialization. A way to execute code after successful
    deserialization is provided through :meth:`xso_after_load`.

    :class:`XSO` objects support copying. Like with deserialisation,
    ``__init__`` is not called during copy. The default implementation only
    copies the XSO descriptors’ values (with deepcopy, they are copied
    deeply). If you have more attributes to copy, you need to override
    ``__copy__`` and ``__deepcopy__`` methods.

    .. versionchanged:: 0.4

       Copy and deepcopy support has been added. Previously, copy copied not
       enough data, while deepcopy copied too much data (including descriptor
       objects).

    To declare an XSO, inherit from :class:`XSO` and provide
    the following attributes on your class:

    * A ``TAG`` attribute, which is a tuple ``(namespace_uri, localname)``
      representing the tag of the XML element you want to match.
    * An arbitrary number of :class:`Text`, :class:`Collector`, :class:`Child`,
      :class:`ChildList` and :class:`Attr`-based attributes.

    .. seealso::

       :class:`.xso.model.XMLStreamClass`
          is the metaclass of :class:`XSO`. The documentation of the metaclass
          holds valuable information with respect to modifying :class:`XSO`
          *classes* and subclassing.

    .. note::

       Attributes whose name starts with ``xso_`` or ``_xso_`` are reserved for
       use by the :mod:`aioxmpp.xso` implementation. Do not use these in your
       code if you can possibly avoid it.

    :class:`XSO` subclasses automatically declare a
    :attr:`~.xso.model.XMLStreamClass.__slots__` attribute which does not
    include the ``__dict__`` value. This effectively prevents any attributes
    not declared on the class as descriptors from being written. The rationale
    is detailed on in the linked documentation. To prevent this from happening
    in your subclass, inherit with `protect` set to false::

      class MyXSO(xso.XSO, protect=False):
          pass

    .. versionadded:: 0.6

       The handling of the :attr:`~.xso.model.XMLStreamClass.__slots__`
       attribute was added.

    To further influence the parsing behaviour of a class, two attributes are
    provided which give policies for unexpected elements in the XML tree:

    .. attribute:: UNKNOWN_CHILD_POLICY
       :annotation: = UnknownChildPolicy.DROP

       A value from the :class:`UnknownChildPolicy` enum which defines the
       behaviour if a child is encountered for which no matching attribute is
       found.

       Note that this policy has no effect if a :class:`Collector` descriptor
       is present, as it takes all children for which no other descriptor
       exists, thus all children are known.

    .. attribute:: UNKNOWN_ATTR_POLICY
       :annotation: = UnknownAttrPolicy.DROP

       A value from the :class:`UnknownAttrPolicy` enum which defines the
       behaviour if an attribute is encountered for which no matching
       descriptor is found.

    Example::

        class Body(aioxmpp.xso.XSO):
            TAG = ("jabber:client", "body")

            text = aioxmpp.xso.Text()

        class Message(aioxmpp.xso.XSO):
            TAG = ("jabber:client", "message")
            UNKNOWN_CHILD_POLICY = aioxmpp.xso.UnknownChildPolicy.DROP

            type_ = aioxmpp.xso.Attr(tag="type")
            from_ = aioxmpp.xso.Attr(tag="from")
            to = aioxmpp.xso.Attr(tag="to")
            id_ = aioxmpp.xso.Attr(tag="id")

            body = aioxmpp.xso.Child([Body])

    Beyond the validation of the individual descriptor values, it is possible
    to implement more complex validation steps by overriding the
    :meth:`validate` method:

    .. automethod:: validate

    The following methods are available on instances of :class:`XSO`:

    .. automethod:: xso_serialise_to_sax

    The following **class methods** are provided by the metaclass:

    .. automethod:: parse_events(ev_args)

    .. automethod:: register_child(prop, child_cls)

    To customize behaviour of deserialization, these methods are provided which
    can be re-implemented by subclasses:

    .. automethod:: xso_after_load

    .. automethod:: xso_error_handler

    """
    UNKNOWN_CHILD_POLICY = UnknownChildPolicy.DROP
    UNKNOWN_ATTR_POLICY = UnknownAttrPolicy.DROP

    __slots__ = ("_xso_contents", "__weakref__")

    def __new__(cls, *args, **kwargs):
        # XXX: is it always correct to omit the arguments here?
        # the semantics of the __new__ arguments are odd to say the least
        result = super().__new__(cls)
        result._xso_contents = dict()
        return result

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __copy__(self):
        result = type(self).__new__(type(self))
        result._xso_contents.update(self._xso_contents)
        return result

    def __deepcopy__(self, memo):
        result = type(self).__new__(type(self))
        result._xso_contents = {
            k: copy.deepcopy(v, memo)
            for k, v in self._xso_contents.items()
        }
        return result

    def validate(self):
        """
        Validate the objects structure beyond the values of individual fields
        (which have their own validators).

        This first calls :meth:`_PropBase.validate_contents` recursively on the
        values of all child descriptors. These may raise (or re-raise) errors
        which occur during validation of the child elements.

        To implement your own validation logic in a subclass of :class:`XSO`,
        override this method and call it via :func:`super` before doing your
        own validation.

        Validate is called by the parsing stack after an object has been fully
        deserialized from the SAX event stream. If the deserialization fails
        due to invalid values of descriptors or due to validation failures in
        child objects, this method is obviously not called.
        """

        for descriptor in self.CHILD_PROPS:
            descriptor.validate_contents(self)

    def xso_after_load(self):
        """
        After an object has been successfully deserialized, this method is
        called. Note that ``__init__`` is never called on objects during
        deserialization.
        """

    def xso_error_handler(self, descriptor, ev_args, exc_info):
        """
        This method is called whenever an error occurs while parsing.

        If an exception is raised by the parsing function of a descriptor
        attribute, such as :class:`Attr`, the `descriptor` is passed as first
        argument, the `exc_info` tuple as third argument and the arguments
        which led to the descriptor being invoked as second argument.

        If an unknown child is encountered and the :attr:`UNKNOWN_CHILD_POLICY`
        is set to :attr:`UnknownChildPolicy.FAIL`, `descriptor` and `exc_info`
        are passed as :data:`None` and `ev_args` are the arguments to the
        ``"start"`` event of the child (i.e. a triple
        ``(namespace_uri, localname, attributes)``).

        If the error handler wishes to suppress the exception, it must return a
        true value. Otherwise, the exception is propagated (or a new exception
        is raised, if the error was not caused by an exception). The error
        handler may also raise its own exception.

        .. warning::

           Suppressing exceptions can cause invalid input to reside in the
           object or the object in general being in a state which violates the
           schema.

           For example, suppressing exceptions about missing attributes will
           cause the attribute to remain uninitialized (i.e. left at its
           :attr:`default` value).

        Even if the error handler suppresses an exception caused by a broken
        child, that child will not be added to the object.
        """

    def xso_serialise_to_sax(self, dest):
        """
        Serialise the XSO to a SAX handler.

        :param dest: SAX handler to send the events to

        .. versionchanged:: 0.11

            The method was renamed from unparse_to_sax to
            xso_serialise_to_sax.
        """
        # XXX: if anyone has an idea on how to optimize this, this is a hotspot
        # when serialising XML
        # things which do not suffice or even change anything:
        # 1. pull things in local variables
        # 2. get rid of the try/finally, even without any replacement
        cls = type(self)
        attrib = {}
        for prop in cls.ATTR_MAP.values():
            prop.to_dict(self, attrib)
        if cls.DECLARE_NS:
            for prefix, uri in cls.DECLARE_NS.items():
                dest.startPrefixMapping(prefix, uri)
        dest.startElementNS(self.TAG, None, attrib)
        try:
            if cls.TEXT_PROPERTY:
                cls.TEXT_PROPERTY.to_sax(self, dest)
            for prop in cls.CHILD_PROPS:
                prop.to_sax(self, dest)
            if cls.COLLECTOR_PROPERTY:
                cls.COLLECTOR_PROPERTY.to_sax(self, dest)
        finally:
            dest.endElementNS(self.TAG, None)
            if cls.DECLARE_NS:
                for prefix, uri in cls.DECLARE_NS.items():
                    dest.endPrefixMapping(prefix)

    def unparse_to_node(self, parent):
        handler = lxml.sax.ElementTreeContentHandler(
            makeelement=parent.makeelement)
        handler.startDocument()
        handler.startElementNS((None, "root"), None)
        self.xso_serialise_to_sax(handler)
        handler.endElementNS((None, "root"), None)
        handler.endDocument()

        parent.extend(handler.etree.getroot())


class CapturingXSO(XSO, metaclass=CapturingXMLStreamClass):
    """
    The following **class methods** is provided by the metaclass (which is not
    publicly available, but a subclass of :class:`~.XMLStreamClass`):

    .. automethod:: parse_events

    The :meth:`_set_captured_events` method can be overridden by subclasses to
    make use of the captured events:

    .. automethod:: _set_captured_events

    An example use case for this class is :class:`.disco.InfoQuery`, combined
    with :mod:`aioxmpp.entitycaps`. We want to be able to store hashes and the
    generating XML data for use with future versions, including XML data which
    cannot be parsed by an XSO in the current process (for example, due to an
    unknown namespace or a plugin which is available but not loaded). With the
    captured events, it is possible to re-create XML semantically equivalent to
    the XML originally received.

    .. versionadded:: 0.5
    """

    @abc.abstractmethod
    def _set_captured_events(self, events):
        """
        This method is called by :meth:`parse_events` after parsing the
        object. `events` is the list of event tuples which this object was
        deserialised from.

        Subclasses must override this method.
        """


class SAXDriver(xml.sax.handler.ContentHandler):
    """
    This is a :class:`xml.sax.handler.ContentHandler` subclass which *only*
    supports namespace-conforming SAX event sources.

    `dest_generator_factory` must be a function which returns a new suspendable
    method supporting the interface of :class:`XSOParser`. The SAX events are
    converted to an internal event format and sent to the suspendable function
    in order.

    `on_emit` may be a callable. Whenever a suspendable function returned by
    `dest_generator_factory` returns, with the return value as sole argument.

    When you are done with a :class:`SAXDriver`, you should call :meth:`close`
    to clean up internal parser state.

    .. automethod:: close
    """

    def __init__(self, dest_generator_factory, on_emit=None):
        self._on_emit = on_emit
        self._dest_factory = dest_generator_factory
        self._dest = None

    def _emit(self, value):
        if self._on_emit:
            self._on_emit(value)

    def _send(self, value):
        if self._dest is None:
            self._dest = self._dest_factory()
            self._dest.send(None)
        try:
            self._dest.send(value)
        except StopIteration as err:
            self._emit(err.value)
            self._dest = None
        except:  # NOQA
            self._dest = None
            raise

    def startElementNS(self, name, qname, attributes):
        uri, localname = name
        self._send(("start", uri, localname, dict(attributes)))

    def characters(self, data):
        self._send(("text", data))

    def endElementNS(self, name, qname):
        self._send(("end",))

    def close(self):
        """
        Clean up all internal state.
        """
        if self._dest is not None:
            self._dest.close()
            self._dest = None


class Context:
    def __init__(self):
        super().__init__()
        self.lang = None

    def __enter__(self):
        new_ctx = Context()
        new_ctx.__dict__ = self.__dict__.copy()
        return new_ctx

    def __exit__(self, *args):
        pass


class XSOParser:
    """
    A generic XSO parser which supports a dynamic set of XSOs to
    parse. :class:`XSOParser` objects are callable and they are suspendable
    methods (i.e. calling a :class:`XSOParser` returns a generator which parses
    stanzas from sax-ish events. Use with :class:`SAXDriver`).

    Example use::

        # let Message be a XSO class, like in the XSO example
        result = None
        def catch_result(value):
            global result
            result = value

        parser = aioxmpp.xso.XSOParser()
        parser.add_class(Message, catch_result)
        sd = aioxmpp.xso.SAXDriver(parser)
        lxml.sax.saxify(lxml.etree.fromstring(
            "<jc:message id='foo' from='bar' to='baz' type='chat' "
            "xmlns:jc='jabber:client'/>"
        ), sd)


    The following methods can be used to dynamically add and remove top-level
    :class:`XSO` classes.

    .. automethod:: add_class

    .. automethod:: remove_class

    .. automethod:: get_tag_map

    """

    def __init__(self):
        self._class_map = {}
        self._tag_map = {}
        self._ctx = Context()

    @property
    def lang(self):
        return self._ctx.lang

    @lang.setter
    def lang(self, value):
        self._ctx.lang = value

    def add_class(self, cls, callback):
        """
        Add a class `cls` for parsing as root level element. When an object of
        `cls` type has been completely parsed, `callback` is called with the
        object as argument.
        """
        if cls.TAG in self._tag_map:
            raise ValueError(
                "duplicate tag: {!r} is already handled by {}".format(
                    cls.TAG,
                    self._tag_map[cls.TAG]))
        self._class_map[cls] = callback
        self._tag_map[cls.TAG] = (cls, callback)

    def get_tag_map(self):
        """
        Return the internal mapping which maps tags to tuples of ``(cls,
        callback)``.

        .. warning::

           The results of modifying this dict are undefined. Make a copy if you
           need to modify the result of this function.

        """
        return self._tag_map

    def get_class_map(self):
        """
        Return the internal mapping which maps classes to the associated
        callbacks.

        .. warning::

           The results of modifying this dict are undefined. Make a copy if you
           need to modify the result of this function.

        """
        return self._class_map

    def remove_class(self, cls):
        """
        Remove a XSO class `cls` from parsing. This method raises
        :class:`KeyError` with the classes :attr:`TAG` attribute as argument if
        removing fails because the class is not registered.
        """
        del self._tag_map[cls.TAG]
        del self._class_map[cls]

    def __call__(self):
        while True:
            ev_type, *ev_args = yield
            if ev_type == "text" and not ev_args[0].strip():
                continue

            tag = ev_args[0], ev_args[1]
            try:
                cls, cb = self._tag_map[tag]
            except KeyError:
                raise UnknownTopLevelTag(
                    "unhandled top-level element",
                    ev_args)
            cb((yield from cls.parse_events(ev_args, self._ctx)))


def drop_handler(ev_args):
    depth = 1
    while depth:
        ev = yield
        if ev[0] == "start":
            depth += 1
        elif ev[0] == "end":
            depth -= 1


def enforce_unknown_child_policy(policy, ev_args, error_handler=None):
    if policy == UnknownChildPolicy.DROP:
        yield from drop_handler(ev_args)
    else:
        if error_handler is not None:
            if error_handler(None, ev_args, None):
                yield from drop_handler(ev_args)
                return
        raise ValueError("unexpected child")


def guard(dest, ev_args):
    depth = 1
    try:
        next(dest)
        while True:
            ev = yield
            if ev[0] == "start":
                depth += 1
            elif ev[0] == "end":
                depth -= 1
            try:
                dest.send(ev)
            except StopIteration as exc:
                return exc.value
    finally:
        while depth > 0:
            ev_type, *_ = yield
            if ev_type == "end":
                depth -= 1
            elif ev_type == "start":
                depth += 1


def lang_attr(instance, ctx):
    """
    A `missing` handler for :class:`Attr` descriptors. If any parent object has
    a ``xml:lang`` attribute set, its value is used.

    Pass as `missing` argument to :class:`Attr` constructors to use this
    behaviour for a given attribute.
    """
    return ctx.lang


def capture_events(receiver, dest):
    """
    Capture all events sent to `receiver` in the sequence `dest`. This is a
    generator, and it is best used with ``yield from``. The observable effect
    of using this generator with ``yield from`` is identical to the effect of
    using `receiver` with ``yield from`` directly (including the return value),
    but in addition, the values which are *sent* to the receiver are captured
    in `dest`.

    If `receiver` raises an exception or the generator is closed prematurely
    using its :meth:`close`, `dest` is cleared.

    This is used to implement :class:`CapturingXSO`. See the documentation
    there for use cases.

    .. versionadded:: 0.5
    """
    # the following code is a copy of the formal definition of `yield from`
    # in PEP 380, with modifications to capture the value sent during yield
    _i = iter(receiver)
    try:
        _y = next(_i)
    except StopIteration as _e:
        return _e.value

    try:
        while True:
            try:
                _s = yield _y
            except GeneratorExit as _e:
                try:
                    _m = _i.close
                except AttributeError:
                    pass
                else:
                    _m()
                    raise _e
            except BaseException as _e:
                _x = sys.exc_info()
                try:
                    _m = _i.throw
                except AttributeError:
                    raise _e
                else:
                    try:
                        _y = _m(*_x)
                    except StopIteration as _e:
                        _r = _e.value
                        break
            else:
                dest.append(_s)
                try:
                    if _s is None:
                        _y = next(_i)
                    else:
                        _y = _i.send(_s)
                except StopIteration as _e:
                    _r = _e.value
                    break
    except:  # NOQA
        dest.clear()
        raise
    return _r


def events_to_sax(events, dest):
    """
    Convert an iterable `events` of XSO events to SAX events by calling the
    matching SAX methods on `dest`
    """
    name_stack = []

    for ev_type, *ev_args in events:
        if ev_type == "start":
            name = (ev_args[0], ev_args[1])
            dest.startElementNS(name, None, ev_args[2])
            name_stack.append(name)
        elif ev_type == "end":
            name = name_stack.pop()
            dest.endElementNS(name, None)
        elif ev_type == "text":
            dest.characters(ev_args[0])


class _CollectorContentHandlerFilter(xml.sax.handler.ContentHandler):
    def __init__(self, receiver):
        super().__init__()
        self.__receiver = receiver

    def setDocumentLocator(self, locator):
        self.__receiver.setDocumentLocator(locator)

    def startElement(self, name, attrs):
        self.__receiver.startElement(name, attrs)

    def endElement(self, name):
        self.__receiver.endElement(name)

    def startElementNS(self, name, qname, attrs):
        self.__receiver.startElementNS(name, qname, attrs)

    def endElementNS(self, name, qname):
        self.__receiver.endElementNS(name, qname)

    def characters(self, content):
        self.__receiver.characters(content)

    def ignorableWhitespace(self, content):
        self.__receiver.ignorableWhitespace(content)

    def processingInstruction(self, target, data):
        self.__receiver.processingInstruction(target, data)

    def skippedEntity(self, name):
        self.__receiver.skippedEntity(name)


class XSOEnumMixin:
    """
    Mix-in to create enumerations of XSOs.

    .. versionadded:: 0.10

    The enumeration member values must be pairs of ``namespace``, ``localpart``
    strings. Each enumeration member is equipped with an :attr:`xso_class`
    attribute at definition time.

    .. automethod:: to_xso

    .. autoattribute:: enum_member

    .. attribute:: xso_class

        A :class:`aioxmpp.xso.XSO` *subclass* which has the enumeration members
        value as :attr:`~.XSO.TAG`. So the subclass matches elements which have
        the qualified tag in the enumeration member value.

        The class does not have any XSO descriptors assigned. They can be added
        after class definition.

        .. attribute:: enum_member

            The enumeration member to which the :attr:`xso_class` belongs.

            This allows to use XSOs and enumeration members more
            interchangeably; see :attr:`enum_member` for details.

        .. method:: to_xso

            Return the XSO itself.

            This allows to use XSOs and enumeration members more
            interchangeably; see :meth:`to_xso` for details.

    Example usage::

        class TagEnum(aioxmpp.xso.XSOEnumMixin, enum.Enum):
            X = ("uri:foo", "x")
            Y = ("uri:foo", "y")

        TagEnum.X.xso_class.enabled = aioxmpp.xso.Attr(
            "enabled",
            type_=aioxmpp.xso.Bool()
        )

    The :class:`TagEnum` members then have a :attr:`xso_class` attribute which
    is a *subclass* of :class:`~aioxmpp.xso.XSO` (**not** an instance of a
    subclass of :class:`~aioxmpp.xso.XSO`).

    The :attr:`xso_class` for :attr:`TagEnum.X` also supports the ``enabled``
    attribute (due to it being monkey-patched onto it), while the
    :attr:`xso_class` for :attr:`TagEnum.Y` does not. Thus, monkey-patching
    can be used to customize the individual XSO classes of the members.

    To use such an enum on a descriptor, the following syntax can be used::

        class Element(aioxmpp.xso.XSO):
            TAG = ("uri:foo", "parent")

            child = aioxmpp.xso.Child([
                member.xso_class
                for member in TagEnum
            ])
    """

    def __init__(self, namespace, localname):
        super().__init__()
        self.xso_class = self._create_class()

    def _create_name(self):
        return "".join(map(str.title, self.name.split("_")))

    def _create_class(self):
        def to_xso(self):
            return self

        return XMLStreamClass(
            self._create_name(),
            (XSO,),
            {
                "TAG": self.value,
                "__qualname__": "{}.{}.xso_class".format(
                    type(self).__qualname__,
                    self.name,
                ),
                "enum_member": self,
                "to_xso": to_xso,
            },
        )

    @property
    def enum_member(self):
        """
        The object (enum member) itself.

        This property exists to make it easier to use the XSO objects and the
        enumeration members interchangeably. The XSO objects also have the
        :attr:`enum_member` property to obtain the enumeration member to which
        they belong. Code which is only interested in the enumeration member
        can thus access the :attr:`enum_member` attribute to "coerce" both
        (enumeration members and instances of their XSO classes) into
        enumeration members.
        """
        return self

    def to_xso(self):
        """
        A new instance of the :attr:`xso_class`.

        This method exists to make it easier to use the XSO objects and the
        enumeration members interchangeably. The XSO objects also have the
        :meth:`to_xso` method which just returns the XSO unmodified.

        Code which needs an XSO, but does not care about the data, can thus use
        the :meth:`to_xso` method to "coerce" either (enumeration members and
        instances of their XSO classes) into XSOs.
        """
        return self.xso_class()


class AbstractTextChild(XSO):
    """
    One of the recurring patterns when using :mod:`xso` is the use of a XSO
    subclass to represent an XML node which has only character data and an
    ``xml:lang`` attribute.

    The `text` and `lang` arguments to the constructor can be used to
    initialize the attributes.

    This class provides exactly that. It inherits from :class:`XSO`.

    .. attribute:: lang

       The ``xml:lang`` of the node, as :class:`~.structs.LanguageTag`.

    .. attribute:: text

       The textual content of the node (XML character data).

    Example use as base class::

      class Subject(xso.AbstractTextChild):
          TAG = (namespaces.client, "subject")

    The full example can also be found in the source code of
    :class:`.stanza.Subject`.

    """

    lang = LangAttr()
    text = Text(default=None)

    def __init__(self, text=None, lang=None):
        super().__init__()
        self.text = text
        self.lang = lang

    def __eq__(self, other):
        try:
            other_key = (other.lang, other.text)
        except AttributeError:
            return NotImplemented
        return (self.lang, self.text) == other_key
