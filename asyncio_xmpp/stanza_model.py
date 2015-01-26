from . import stanza_types


class StanzaObject:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stanza_props = dict()


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

    def from_node(self, instance, el):
        self.__set__(instance, self._type.parse(el.text))

    def to_node(self, instance, el):
        el.text = self._type.format(self.__get__(instance, type(instance)))
