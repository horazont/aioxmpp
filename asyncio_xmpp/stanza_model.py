import copy
import inspect
import sys
import xml.sax.handler

from enum import Enum

from asyncio_xmpp.utils import etree

from . import stanza_types


def tag_to_str(tag):
    return "{{{:s}}}{:s}".format(*tag) if tag[0] else tag[1]


class UnknownChildPolicy(Enum):
    FAIL = 0
    DROP = 1


class UnknownAttrPolicy(Enum):
    FAIL = 0
    DROP = 1


class UnknownTopLevelTag(ValueError):
    def __init__(self, msg, ev_args):
        super().__init__(msg + ": {}".format((ev_args[0], ev_args[1])))
        self.ev_args = ev_args


class _PropBase:
    def __init__(self, default):
        super().__init__()
        self._default = default

    def __set__(self, instance, value):
        instance._stanza_props[self] = value

    def __get__(self, instance, cls):
        if instance is None:
            return self
        try:
            return instance._stanza_props[self]
        except KeyError as err:
            return self._default


class Text(_PropBase):
    def __init__(self,
                 type_=stanza_types.String(),
                 default=None):
        super().__init__(default)
        self._type = type_

    def from_value(self, instance, value):
        self.__set__(instance, self._type.parse(value))

    def to_node(self, instance, el):
        el.text = self._type.format(self.__get__(instance, type(instance)))


class Child(_PropBase):
    def __init__(self, classes, default=None):
        super().__init__(default)
        self._classes = tuple(classes)
        self._tag_map = {}
        for cls in self._classes:
            if cls.TAG in self._tag_map:
                raise ValueError("ambiguous children: {} and {} share the same "
                                 "TAG".format(
                                     self._tag_map[cls.TAG],
                                     cls))
            self._tag_map[cls.TAG] = cls

    def get_tag_map(self):
        return self._tag_map

    def from_events(self, instance, ev_args):
        cls = self._tag_map[ev_args[0], ev_args[1]]
        obj = (yield from cls.parse_events(ev_args))
        self.__set__(instance, obj)
        return obj

    def to_node(self, instance, parent):
        obj = self.__get__(instance, type(instance))
        obj.unparse_to_node(parent)


class Collector(_PropBase):
    def __init__(self):
        super().__init__(default=[])

    def __get__(self, instance, cls):
        if instance is None:
            return super().__get__(instance, cls)
        return instance._stanza_props.setdefault(self, [])

    def from_events(self, instance, ev_args):
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
        stack = [root_el]
        while stack:
            ev_type, *ev_args = yield
            if ev_type == "start":
                stack.append(make_from_args(ev_args, stack[-1]))
            elif ev_type == "text":
                curr = stack[-1]
                if curr.text is not None:
                    curr.text += ev_args[0]
                else:
                    curr.text = ev_args[0]
            elif ev_type == "end":
                stack.pop()
            else:
                raise ValueError(ev_type)

        self.__get__(instance, type(instance)).append(root_el)

    def to_node(self, instance, parent):
        for node in self.__get__(instance, type(instance)):
            parent.append(copy.copy(node))


class Attr(Text):
    def __init__(self, name, type_=stanza_types.String(), default=None):
        super().__init__(type_=type_, default=default)
        if isinstance(name, tuple):
            uri, localpart = name
        else:
            uri = None
            localpart = name
        self.name = uri, localpart

    def to_node(self, instance, parent):
        parent.set(
            tag_to_str(self.name),
            self._type.format(self.__get__(instance, type(instance))))


class StanzaClass(type):
    def __new__(mcls, name, bases, namespace):
        text_property = None
        child_map = {}
        child_props = set()
        attr_map = {}
        collector_property = None

        for name, obj in namespace.items():
            if isinstance(obj, Attr):
                attr_map[obj.name] = obj
            elif isinstance(obj, Text):
                if text_property is not None:
                    raise TypeError("multiple Text properties on stanza class")
                text_property = obj
            elif isinstance(obj, Child):
                for key in obj.get_tag_map().keys():
                    if key in child_map:
                        raise TypeError("ambiguous Child properties: {} and {}"
                                        " both use the same tag".format(
                                            child_map[key],
                                            obj))
                    child_map[key] = obj
                child_props.add(obj)
            elif isinstance(obj, Collector):
                if collector_property is not None:
                    raise TypeError("multiple Collector properties on stanza "
                                    "class")
                collector_property = obj

        namespace["TEXT_PROPERTY"] = text_property
        namespace["CHILD_MAP"] = child_map
        namespace["CHILD_PROPS"] = frozenset(child_props)
        namespace["ATTR_MAP"] = attr_map
        namespace["COLLECTOR_PROPERTY"] = collector_property
        namespace.setdefault("UNKNOWN_CHILD_POLICY",
                             UnknownChildPolicy.FAIL)
        namespace.setdefault("UNKNOWN_ATTR_POLICY",
                             UnknownAttrPolicy.FAIL)

        try:
            tag = namespace["TAG"]
        except KeyError:
            pass
        else:
            if isinstance(tag, tuple):
                try:
                    uri, localname = tag
                except ValueError:
                    raise TypeError("TAG attribute has incorrect type") \
                        from None
            else:
                namespace["TAG"] = (None, tag)

        return super().__new__(mcls, name, bases, namespace)

    def parse_events(cls, ev_args):
        obj = cls()
        attrs = ev_args[2]
        for key, value in attrs.items():
            try:
                prop = cls.ATTR_MAP[key]
            except KeyError:
                if cls.UNKNOWN_ATTR_POLICY == UnknownAttrPolicy.DROP:
                    continue
                else:
                    raise ValueError("unexpected attribute {!r} on {}".format(
                        key,
                        (ev_args[0], ev_args[1])
                    )) from None
            prop.from_value(obj, value)

        collected_text = []
        while True:
            ev_type, *ev_args = yield
            if ev_type == "end":
                break
            elif ev_type == "text":
                collected_text.append(ev_args[0])
            elif ev_type == "start":
                try:
                    handler = cls.CHILD_MAP[ev_args[0], ev_args[1]]
                except KeyError:
                    if cls.COLLECTOR_PROPERTY:
                        handler = cls.COLLECTOR_PROPERTY
                    elif cls.UNKNOWN_CHILD_POLICY == UnknownChildPolicy.DROP:
                        yield from drop_handler(ev_args)
                        continue
                    else:
                        raise ValueError("unexpected child TAG: {}".format(
                            (ev_args[0], ev_args[1]))) from None
                yield from handler.from_events(obj, ev_args)

        if collected_text:
            if cls.TEXT_PROPERTY:
                cls.TEXT_PROPERTY.from_value(obj, "".join(collected_text))
            else:
                raise ValueError("unexpected text")

        return obj


class StanzaObject(metaclass=StanzaClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stanza_props = dict()

    def unparse_to_node(self, parent):
        cls = type(self)
        el = etree.SubElement(
            parent,
            tag_to_str(self.TAG)
        )
        for prop in cls.ATTR_MAP.values():
            prop.to_node(self, el)
        if cls.TEXT_PROPERTY:
            cls.TEXT_PROPERTY.to_node(self, el)
        for prop in cls.CHILD_PROPS:
            prop.to_node(self, el)
        return el


class SAXDriver(xml.sax.handler.ContentHandler):
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

    def startElementNS(self, name, qname, attributes):
        uri, localname = name
        self._send(("start", uri, localname, dict(attributes)))

    def characters(self, data):
        self._send(("text", data))

    def endElementNS(self, name, qname):
        self._send(("end",))

    def close(self):
        if self._dest is not None:
            self._dest.close()
            self._dest = None


def stanza_parser(stanza_classes):
    ev_type, *ev_args = yield
    for cls in stanza_classes:
        if cls.TAG == (ev_args[0], ev_args[1]):
            cls_to_use = cls
            break
    else:
        raise UnknownTopLevelTag(
            "unhandled top-level element",
            ev_args)

    generator = cls_to_use.parse_events(ev_args)
    return (yield from generator)


def drop_handler(ev_args):
    depth = 1
    while depth:
        ev = yield
        if ev[0] == "start":
            depth += 1
        elif ev[0] == "end":
            depth -= 1
