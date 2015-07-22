"""
:mod:`aioxmpp.xso.model` --- Declarative-style XSO definition
#############################################################

See :mod:`aioxmpp.xso` for documentation.
"""
import collections
import sys
import xml.sax.handler

import lxml.sax

import orderedset  # get it from PyPI

from enum import Enum

from aioxmpp.utils import etree, namespaces

from . import types as xso_types
from . import tag_to_str, normalize_tag
from .. import structs


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
        result = [item for item in chained_results if hasattr(item, "lang")]

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
        fucntion starts with a working sequence consisting of the whole list.

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


class _PropBase:
    def __init__(self, default,
                 *,
                 validator=None,
                 validate=ValidateMode.FROM_RECV):
        super().__init__()
        self.default = default
        self.validate = validate
        self.validator = validator

    def _set(self, instance, value):
        instance._stanza_props[self] = value

    def __set__(self, instance, value):
        if     (self.validate.from_code and
                self.validator and
                not self.validator.validate(value)):
            raise ValueError("invalid value")
        self._set(instance, value)

    def _set_from_code(self, instance, value):
        self.__set__(instance, value)

    def _set_from_recv(self, instance, value):
        if     (self.validate.from_recv and
                self.validator and
                not self.validator.validate(value)):
            raise ValueError("invalid value")
        self._set(instance, value)

    def __get__(self, instance, cls):
        if instance is None:
            return self
        try:
            return instance._stanza_props[self]
        except KeyError:
            return self.default

    def validate_contents(self, instance):
        pass

    def to_node(self, instance, parent):
        handler = lxml.sax.ElementTreeContentHandler(
            makeelement=parent.makeelement)
        handler.startDocument()
        handler.startElementNS((None, "_"), None, {})
        self.to_sax(instance, handler)

        parent.extend(handler.etree.getroot())


class _TypedPropBase(_PropBase):
    def __init__(self, default,
                 *,
                 type_=xso_types.String(),
                 **kwargs):
        super().__init__(default, **kwargs)
        self.type_ = type_

    def __set__(self, instance, value):
        if value is not None:
            value = self.type_.coerce(value)
        super().__set__(instance, value)


class Text(_TypedPropBase):
    """
    When assigned to a class’ attribute, it collects all character data of the
    XML element.

    Note that this destroys the relative ordering of child elements and
    character data pieces. This is known and a WONTFIX, as it is not required
    in XMPP to keep that relative order: Elements either have character data
    *or* other elements as children.

    The `type_`, `validator`, `validate` and `default` arguments behave like in
    :class:`Attr`.

    .. automethod:: from_value

    .. automethod:: to_sax

    """

    def __init__(self,
                 default=None,
                 **kwargs):
        super().__init__(default, **kwargs)

    def from_value(self, instance, value):
        """
        Convert the given value using the set `type_` and store it into
        `instance`’ attribute.
        """
        self._set_from_recv(instance, self.type_.parse(value))

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


class Child(_PropBase):
    """
    When assigned to a class’ attribute, it collects any child which matches
    any :attr:`XSO.TAG` of the given `classes`.

    The tags among the `classes` must be unique, otherwise :class:`ValueError`
    is raised on construction.

    The `default` argument behaves like in :class:`Attr`. Validators are not
    supported.

    .. automethod:: get_tag_map

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self, classes, default=None):
        super().__init__(default)
        self._classes = tuple(classes)
        self._tag_map = {}
        for cls in self._classes:
            self._register(cls)

    def get_tag_map(self):
        """
        Return a dictionary mapping the tags of the supported classes to the
        classes themselves. Can be used to obtain a set of supported tags.
        """
        return self._tag_map

    def _process(self, instance, ev_args, ctx):
        cls = self._tag_map[ev_args[0], ev_args[1]]
        return (yield from cls.parse_events(ev_args, ctx))

    def from_events(self, instance, ev_args, ctx):
        """
        Detect the object to instanciate from the arguments `ev_args` of the
        ``"start"`` event. The new object is stored at the corresponding
        descriptor attribute on `instance`.

        This method is suspendable.
        """
        obj = yield from self._process(instance, ev_args, ctx)
        self.__set__(instance, obj)
        return obj

    def validate_contents(self, instance):
        obj = self.__get__(instance, type(instance))
        if obj is None:
            return
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
        obj.unparse_to_sax(dest)

    def _register(self, cls):
        if cls.TAG in self._tag_map:
            raise ValueError("ambiguous children: {} and {} share the same "
                             "TAG".format(
                                 self._tag_map[cls.TAG],
                                 cls))
        self._tag_map[cls.TAG] = cls


class ChildList(Child):
    """
    The :class:`ChildList` works like :class:`Child`, with two key differences:

    * multiple children which are matched by this descriptor get collected into
      an :class:`~aioxmpp.xso.model.XSOList`.
    * the default is fixed at an empty list.

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self, classes):
        super().__init__(classes)

    def __get__(self, instance, cls):
        if instance is None:
            return super().__get__(instance, cls)
        return instance._stanza_props.setdefault(self, XSOList())

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
            obj.unparse_to_sax(dest)


class Collector(_PropBase):
    """
    When assigned to a class’ attribute, it collects all children which are not
    known to any other descriptor into a list of XML subtrees.

    The default is fixed at an empty list.

    .. automethod:: from_events

    .. automethod:: to_sax
    """

    def __init__(self):
        super().__init__(default=[])

    def __get__(self, instance, cls):
        if instance is None:
            return super().__get__(instance, cls)
        return instance._stanza_props.setdefault(self, [])

    def _set(self, instance, value):
        if not isinstance(value, list):
            raise TypeError("expected list, but found {}".format(type(value)))
        return super()._set(instance, value)

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
            if parent is not None:
                el = etree.SubElement(parent,
                                      tag_to_str((ev_args[0], ev_args[1])))
            else:
                el = etree.Element(tag_to_str((ev_args[0], ev_args[1])))
            for key, value in ev_args[2].items():
                el.set(tag_to_str(key), value)
            return el

        root_el = make_from_args(ev_args, None)
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

        self.__get__(instance, type(instance)).append(root_el)

    def to_sax(self, instance, dest):
        for node in self.__get__(instance, type(instance)):
            lxml.sax.saxify(node, dest)


class Attr(Text):
    """
    When assigned to a class’ attribute, it binds that attribute to the XML
    attribute with the given `tag`. `tag` must be a valid input to
    :func:`normalize_tag`.

    The following arguments occur at several of the descriptor classes, and are
    all available at :class:`Attr`.

    :param type_: An object which fulfills the type interface proposed by
                  :class:`~.xso.AbstractType`. Usually, this is defaulted
                  to a :class:`~aioxmpp.xso.String` instance.
    :param validator: An object which has a :meth:`validate` method. That
                      method receives a value which was either assigned to the
                      property (depending on the `validate` argument) or parsed
                      from XML (after it passed through `type_`).
    :param validate: A value from the :class:`ValidateMode` enum, which defines
                     which values have to pass through the validator. At some
                     points it makes sense to only validate outgoing values,
                     but be liberal with incoming values. This defaults to
                     :attr:`ValidateMode.FROM_RECV`.
    :param default: The value which the attribute has if no value has been
                    assigned. This defaults to :data:`None`.
    :param required: Whether the absence of data for this object during parsing
                     is a fatal error. This defaults to :data:`False`.
    :param missing: A callable which takes a :class:`Context` instance. It is
                    called whenever the attribute is missing (independent from
                    the fact whether it is required or not). The callable shall
                    return a not-:data:`None` value for the attribute to
                    use. If the value is :data:`None`, the usual handling of
                    missing attributes takes place.

    .. seealso::

       :class:`LangAttr`, which is a subclass of :class:`Attr` specialized for
       describing ``xml:lang`` attributes.

    .. automethod:: from_value

    .. automethod:: handle_missing

    .. automethod:: to_dict

    """

    def __init__(self, tag,
                 type_=xso_types.String(),
                 default=None,
                 required=False,
                 missing=None,
                 **kwargs):
        super().__init__(type_=type_, default=default, **kwargs)
        self.tag = normalize_tag(tag)
        self.required = required
        self.missing = missing

    def __set__(self, instance, value):
        if self.required and value == self.default:
            raise AttributeError("cannot set required attribute to default")
        super().__set__(instance, value)

    def __delete__(self, instance):
        if self.required:
            raise AttributeError("cannot delete required attribute")
        try:
            del instance._stanza_props[self]
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

        if self.required:
            raise ValueError("missing attribute {} on {}".format(
                tag_to_str(self.tag),
                tag_to_str(instance.TAG),
            ))

    def validate_contents(self, instance):
        if self.required:
            value = self.__get__(instance, type(instance))
            if value == self.default:
                raise ValueError("non-default value required for {}".format(
                    tag_to_str(self.tag)
                ))

    def to_dict(self, instance, d):
        """
        Override the implementation from :class:`Text` by storing the formatted
        value in the XML attribute instead of the character data.

        If the value is :data:`None`, no element is generated.
        """

        value = self.__get__(instance, type(instance))
        if value is None:
            return

        d[self.tag] = self.type_.format(value)


class LangAttr(Attr):
    """
    The :class:`LangAttr` is identical to :class:`Attr`, except that the
    `type_`, `tag` and `missing` arguments are already bound. The `tag` is set
    to the ``(namespaces.xml, "lang")`` value to match ``xml:lang``
    attributes. `type_` is a :class:`xso.LanguageTag` instance and `missing` is
    set to :func:`lang_attr`.
    """

    def __init__(self, **kwargs):
        super().__init__(
            (namespaces.xml, "lang"),
            type_=xso_types.LanguageTag(),
            missing=lang_attr
        )


class ChildText(_TypedPropBase):
    """
    When assigned to a class’ attribute, it binds that attribute to the XML
    character data of a child element with the given `tag`. `tag` must be a
    valid input to :func:`normalize_tag`.

    The `type_`, `validate`, `validator` and `default` arguments behave like in
    :class:`Attr`.

    `child_policy` is applied when :meth:`from_events` encounters an element in
    the child element of which it is supposed to extract text. Likewise,
    `attr_policy` is applied if an attribute is encountered on the element.

    `declare_prefix` works as for :class:`ChildTag`.

    .. automethod:: get_tag_map

    .. automethod:: from_events

    .. automethod:: to_sax

    """

    def __init__(self, tag,
                 *,
                 default=None,
                 child_policy=UnknownChildPolicy.FAIL,
                 attr_policy=UnknownAttrPolicy.FAIL,
                 declare_prefix=False,
                 **kwargs):
        super().__init__(default=default, **kwargs)
        self.tag = normalize_tag(tag)
        self.default = default
        self.child_policy = child_policy
        self.attr_policy = attr_policy
        self.declare_prefix = declare_prefix

    def get_tag_map(self):
        """
        Return an iterable yielding :attr:`tag`.

        This is for compatiblity with the :class:`Child` interface.
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

        self._set_from_recv(instance, self.type_.parse("".join(parts)))

    def to_sax(self, instance, dest):
        """
        Create a child node at `parent` with the tag :attr:`tag`. Set the text
        contents to the value of the attribute which this descriptor represents
        at `instance`.

        If the value is :data:`None`, no element is generated.
        """

        value = self.__get__(instance, type(instance))
        if value is None:
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


class ChildMap(Child):
    """
    The :class:`ChildMap` class works like :class:`ChildList`, but instead of
    storing the child objects in a list, they are stored in a map which
    contains an :class:`~aioxmpp.xso.model.XSOList` of objects for each tag.

    `key` may be callable. If it is given, it is used while parsing to
    determine the dictionary key under which a newly parsed XSO will be
    put. For that, the `key` callable is called with the newly parsed XSO as
    the only argument and is expected to return the key.

    .. automethod:: from_events

    .. automethod:: to_sax

    """

    def __init__(self, classes, *, key=None, **kwargs):
        super().__init__(classes, **kwargs)
        self.key = key or (lambda obj: obj.TAG)

    def __get__(self, instance, cls):
        if instance is None:
            return super().__get__(instance, cls)
        return instance._stanza_props.setdefault(
            self,
            collections.defaultdict(XSOList))

    def __set__(self, instance, value):
        raise AttributeError("ChildMap attribute cannot be assigned to")

    def _set(self, instance, value):
        if not isinstance(value, dict):
            raise TypeError("expected dict, but found {}".format(type(value)))
        return super()._set(instance, value)

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
                obj.unparse_to_sax(dest)


class ChildLangMap(ChildMap):
    """
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
    When assigned to a class’ attribute, this descriptor represents the
    presence or absence of a single child with a tag from a given set of valid
    tags.

    `tags` must be an iterable of valid arguments to :func:`normalize_tag`. If
    :func:`normalize_tag` returns a false value (such as :data:`None`) as
    `namespace_uri`, it is replaced with `default_ns` (defaulting to
    :data:`None`, which makes this sentence a no-op). This allows a benefit to
    readability if you have many tags which share the same namespace.

    `text_policy`, `child_policy` and `attr_policy` describe the behaviour if
    the child element unexpectedly has text, children or attributes,
    respectively. The default for each is to fail with a :class:`ValueError`.

    If `allow_none` is :data:`True`, assignment of :data:`None` to the
    attribute to which this descriptor belongs is allowed and represents the
    absence of the child element.

    If `declare_prefix` is not :data:`False` (note that :data:`None` is a
    valid, non-:data:`False` value in this context!), the namespace is
    explicitly declared using the given prefix when serializing to SAX.

    `default` works as for :class:`Attr`.

    .. automethod:: from_events

    .. automethod:: to_sax

    """

    class ElementTreeTag(xso_types.AbstractType):
        """
        Parse an element-tree-format tag to a tuple-format tag. This type
        operates on strings and should not be used in general.
        """

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
                 default=None,
                 declare_prefix=False):
        tags = {
            (ns or default_ns, localname)
            for ns, localname in map(normalize_tag, tags)
        }
        if allow_none:
            tags.add(None)
        super().__init__(
            default=default,
            validator=xso_types.RestrictToSet(tags),
            validate=ValidateMode.ALWAYS)
        self.type_ = self.ElementTreeTag()
        self.text_policy = text_policy
        self.attr_policy = attr_policy
        self.child_policy = child_policy
        self.declare_prefix = declare_prefix

    def get_tag_map(self):
        return self.validator.values

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
        self._set_from_recv(instance, tag)

    def to_sax(self, instance, dest):
        value = self.__get__(instance, type(instance))
        if value is None:
            return

        if self.declare_prefix is not False and value[0]:
            dest.startPrefixMapping(self.declare_prefix, value[0])
        dest.startElementNS(value, None, {})
        dest.endElementNS(value, None)
        if self.declare_prefix is not False and value[0]:
            dest.endPrefixMapping(self.declare_prefix)


class XMLStreamClass(type):
    """
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

    def __new__(mcls, name, bases, namespace):
        text_property = None
        child_map = {}
        child_props = orderedset.OrderedSet()
        attr_map = {}
        collector_property = None

        for base in reversed(bases):
            if not isinstance(base, XMLStreamClass):
                continue

            if base.TEXT_PROPERTY is not None:
                if     (text_property is not None and
                        base.TEXT_PROPERTY is not text_property):
                    raise TypeError("multiple text properties in inheritance")
                text_property = base.TEXT_PROPERTY

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
                if     (collector_property is not None and
                        base.COLLECTOR_PROPERTY is not collector_property):
                    raise TypeError("multiple collector properties in "
                                    "inheritance")
                collector_property = base.COLLECTOR_PROPERTY

        for attrname, obj in namespace.items():
            if isinstance(obj, Attr):
                if obj.tag in attr_map:
                    raise TypeError("ambiguous Attr properties")
                attr_map[obj.tag] = obj
            elif isinstance(obj, Text):
                if text_property is not None:
                    raise TypeError("multiple Text properties on XSO class")
                text_property = obj
            elif isinstance(obj, (Child, ChildText, ChildTag)):
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
            pass
        else:
            try:
                namespace["TAG"] = normalize_tag(tag)
            except ValueError:
                raise TypeError("TAG attribute has incorrect format")

        return super().__new__(mcls, name, bases, namespace)

    def __setattr__(cls, name, value):
        try:
            existing = getattr(cls, name)
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

        elif isinstance(value, (Child, ChildText, ChildTag)):
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
            existing = getattr(cls, name)
        except AttributeError:
            pass
        else:
            if isinstance(existing, _PropBase):
                raise AttributeError("cannot unbind XSO descriptors")

        super().__delattr__(name)

    def __prepare__(name, bases):
        return collections.OrderedDict()

    def parse_events(cls, ev_args, parent_ctx):
        """
        Create an instance of this class, using the events sent into this
        function. `ev_args` must be the event arguments of the ``"start"``
        event.

        .. seealso::

           You probably should not call this method directly, but instead use
           :class:`XSOParser` with a :class:`SAXDriver`.

        This method is suspendable.
        """
        with parent_ctx as ctx:
            obj = cls()
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
                    prop.from_value(obj, value)
                except:
                    obj.xso_error_handler(
                        prop,
                        value,
                        sys.exc_info())
                    raise

            for key, prop in attr_map.items():
                try:
                    prop.handle_missing(obj, ctx)
                except:
                    obj.xso_error_handler(
                        prop,
                        None,
                        sys.exc_info()
                    )
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
                            raise ValueError("unexpected text")
                    else:
                        collected_text.append(ev_args[0])
                elif ev_type == "start":
                    try:
                        handler = cls.CHILD_MAP[ev_args[0], ev_args[1]]
                    except KeyError:
                        if cls.COLLECTOR_PROPERTY:
                            handler = cls.COLLECTOR_PROPERTY
                        else:
                            yield from enforce_unknown_child_policy(
                                cls.UNKNOWN_CHILD_POLICY,
                                ev_args,
                                obj.xso_error_handler)
                            continue
                    try:
                        yield from handler.from_events(obj, ev_args, ctx)
                    except:
                        obj.xso_error_handler(
                            handler,
                            ev_args,
                            sys.exc_info())
                        raise

            if collected_text:
                collected_text = "".join(collected_text)
                try:
                    cls.TEXT_PROPERTY.from_value(obj, collected_text)
                except:
                    obj.xso_error_handler(
                        cls.TEXT_PROPERTY,
                        collected_text,
                        sys.exc_info())
                    raise

        obj.validate()

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

        prop._register(child_cls)
        cls.CHILD_MAP[child_cls.TAG] = prop


class XSO(metaclass=XMLStreamClass):
    """
    XSO is short for **X**\ ML **S**\ tream **O**\ bject and means an object
    which represents a subtree of an XML stream. These objects can also be
    created and validated on-the-fly from SAX-like events using
    :class:`XSOParser`. The constructor does not require any arguments and
    forwards them directly the next class in the resolution order.

    To declare an XSO, inherit from :class:`XSO` and provide
    the following attributes on your class:

    * A ``TAG`` attribute, which is a tuple ``(namespace_uri, localname)``
      representing the tag of the XML element you want to match.
    * An arbitrary number of :class:`Text`, :class:`Collector`, :class:`Child`,
      :class:`ChildList` and :class:`Attr`-based attributes.

    .. seealso::

       The documentation of :class:`.xso.model.XMLStreamClass` holds valuable
       information with respect to subclassing and modifying :class:`XSO`
       subclasses, as well as restrictions on the use of the said attribute
       descriptors.

    To further influence the parsing behaviour of a class, two attributes are
    provided which give policies for unexpected elements in the XML tree:

    .. attribute:: UNKNOWN_CHILD_POLICY = UnknownChildPolicy.FAIL

       A value from the :class:`UnknownChildPolicy` enum which defines the
       behaviour if a child is encountered for which no matching attribute is
       found.

       Note that this policy has no effect if a :class:`Collector` descriptor
       is present, as it takes all children for which no other descriptor
       exists, thus all children are known.

    .. attribute:: UNKNOWN_ATTR_POLICY = UnknownAttrPolicy.FAIL

       A value from the :class:`UnknownAttrPolicy` enum which defines the
       behaviour if an attribute is encountered for which no matching
       descriptor is found.

    .. attribute:: DECLARE_NS = None

       Either a dictionary which defines the namespace mappings which shall be
       declared when serializing this element or :data:`None`. If it is a
       dictionary, it must map namespace prefixes (such as :data:`None` or
       ``"foo"``) to namespace URIs.

       .. warning::

          It is discouraged to use namespace prefixes of the format
          ``"ns{:d}".format(n)``, for any given number `n`. These prefixes are
          reserved for ad-hoc namespace declarations, and attempting to use
          them may have unwanted side-effects.

    Example::

        class Body(aioxmpp.xso.XSO):
            TAG = ("jabber:client", "body")

            text = aioxmpp.xso.Text()

        class Message(aioxmpp.xso.XSO):
            TAG = ("jabber:client", "message")
            UNKNOWN_CHILD_POLICY = aioxmpp.xso.UnknownChildPolicy.DROP

            type_ = aioxmpp.xso.Attr(tag="type", required=True)
            from_ = aioxmpp.xso.Attr(tag="from", required=True)
            to = aioxmpp.xso.Attr(tag="to")
            id_ = aioxmpp.xso.Attr(tag="id")

            body = aioxmpp.xso.Child([Body])

    Beyond the validation of the individual descriptor values, it is possible
    to implement more complex validation steps by overriding the
    :meth:`validate` method:

    .. automethod:: validate

    The following methods are available on instances of :class:`XSO`:

    .. automethod:: unparse_to_sax

    The following **class methods** are provided by the metaclass:

    .. automethod:: parse_events(ev_args)

    .. automethod:: register_child(prop, child_cls)

    """
    UNKNOWN_CHILD_POLICY = UnknownChildPolicy.FAIL
    UNKNOWN_ATTR_POLICY = UnknownAttrPolicy.FAIL
    DECLARE_NS = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stanza_props = dict()

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
        """
        pass

    def unparse_to_sax(self, dest):
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
        self.unparse_to_sax(handler)
        handler.endElementNS((None, "root"), None)
        handler.endDocument()

        parent.extend(handler.etree.getroot())


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
        except:
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
            nonlocal result
            result = value

        parser = aioxmpp.xso.XSOParser()
        parser.add_class(Message, catch_result)
        sd = aioxmpp.xso.SAXDriver(parser)
        lxml.sax.saxify(lmxl.etree.fromstring(
            "<message id='foo' from='bar' type='chat' />"
        ))


    The following methods can be used to dynamically add and remove top-level
    :class:`XSO` classes.

    .. automethod:: add_class

    .. automethod:: remove_class

    .. automethod:: get_tag_map

    """

    def __init__(self):
        self._class_map = {}
        self._tag_map = {}

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
        ctx = Context()
        while True:
            ev_type, *ev_args = yield
            tag = ev_args[0], ev_args[1]
            try:
                cls, cb = self._tag_map[tag]
            except KeyError:
                raise UnknownTopLevelTag(
                    "unhandled top-level element",
                    ev_args)
            cb((yield from cls.parse_events(ev_args, ctx)))


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
        if error_handler:
            error_handler(None, ev_args, None)
        raise ValueError("unexpected child")


def lang_attr(instance, ctx):
    """
    A `missing` handler for :class:`Attr` descriptors. If any parent object has
    a ``xml:lang`` attribute set, its value is used.

    Pass as `missing` argument to :class:`Attr` constructors to use this
    behaviour for a given attribute.
    """
    return ctx.lang
