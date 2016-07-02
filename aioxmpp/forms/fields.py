import aioxmpp.xso as xso


class Field:
    def __init__(self, var,
                 type_=xso.String(),
                 validator=None,
                 default=None):
        super().__init__()
        self.var = var
        self.type_ = type_
        self.validator = validator
        self.default = default

    def __get__(self, instance, type_):
        if instance is None:
            return self

        try:
            return instance.__dict__[self]
        except KeyError:
            bound = BoundField(self)
            instance.__dict__[self] = bound
            return bound

    def __set__(self, instance, value):
        raise AttributeError("cannot write Field attributes directly")


class BoundField:
    def __init__(self, unbound_field):
        super().__init__()
        self.unbound_field = unbound_field
        self._data = unbound_field.default

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        coerced = self.unbound_field.type_.coerce(value)

        if    (self.unbound_field.validator is not None
               and not self.unbound_field.validator.validate(coerced)):
            raise ValueError("invalid value")

        self._data = coerced

    @data.deleter
    def data(self):
        self._data = self.unbound_field.default
