import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0004_data = "jabber:x:data"


class Value(xso.XSO):
    TAG = (namespaces.xep0004_data, "value")

    value = xso.Text(default="")


class ValueElement(xso.AbstractType):
    def parse(self, item):
        return item.value

    def format(self, value):
        v = Value()
        v.value = value
        return v

    def get_formatted_type(self):
        return Value


class Option(xso.XSO):
    TAG = (namespaces.xep0004_data, "option")

    label = xso.Attr(
        tag="label",
        default=None,
    )

    value = xso.ChildText(
        (namespaces.xep0004_data, "value"),
        default=None,
    )

    def validate(self):
        if self.value is None:
            raise ValueError("option is missing a value")


class OptionElement(xso.AbstractType):
    def parse(self, item):
        return (item.value, item.label)

    def format(self, value):
        value, label = value
        o = Option()
        o.value = value
        o.label = label
        return o

    def get_formatted_type(self):
        return Option


class Field(xso.XSO):
    TAG = (namespaces.xep0004_data, "field")

    required = xso.ChildTag(
        tags=[
            (namespaces.xep0004_data, "required"),
        ],
        allow_none=True)

    desc = xso.ChildText(
        (namespaces.xep0004_data, "desc"),
        default=None
    )

    values = xso.ChildValueList(
        type_=ValueElement()
    )

    options = xso.ChildValueMap(
        type_=OptionElement()
    )

    var = xso.Attr(
        (None, "var"),
        default=None
    )

    type_ = xso.Attr(
        (None, "type"),
        validator=xso.RestrictToSet([
            "boolean",
            "fixed",
            "hidden",
            "jid-multi",
            "jid-single",
            "list-multi",
            "list-single",
            "text-multi",
            "text-private",
            "text-single",
        ]),
        default="text-single"
    )

    label = xso.Attr(
        (None, "label"),
        default=None
    )

    def __init__(self, *,
                 type_="text-single",
                 options={},
                 values=[],
                 desc=None,
                 label=None,
                 required=False,
                 var=None):
        super().__init__()
        self.type_ = type_
        self.options.update(options)
        self.values[:] = values
        self.desc = desc
        self.label = label
        if required:
            self.required = (namespaces.xep0004_data, "required")
        self.var = var

    def validate(self):
        super().validate()

        if self.type_ != "fixed" and not self.var:
            raise ValueError("missing attribute var")

        if not self.type_.startswith("list-") and self.options:
            raise ValueError("unexpected option on non-list field")

        if not self.type_.endswith("-multi") and len(self.values) > 1:
            raise ValueError("too many values on non-multi field")

        values_list = [opt for opt in self.options.values()]
        values_set = set(values_list)

        if len(values_list) != len(values_set):
            raise ValueError("duplicate option value")


class AbstractItem(xso.XSO):
    fields = xso.ChildList([Field])


class Item(AbstractItem):
    TAG = (namespaces.xep0004_data, "item")


class Reported(AbstractItem):
    TAG = (namespaces.xep0004_data, "reported")


class Title(xso.AbstractTextChild):
    TAG = (namespaces.xep0004_data, "title")


class Instructions(xso.AbstractTextChild):
    TAG = (namespaces.xep0004_data, "instructions")


class Data(AbstractItem):
    TAG = (namespaces.xep0004_data, "x")

    type_ = xso.Attr(
        "type",
        validator=xso.RestrictToSet({
            "form",
            "submit",
            "cancel",
            "result",
        }),
        validate=xso.ValidateMode.ALWAYS,
    )

    title = xso.ChildList([Title])

    instructions = xso.ChildList([Instructions])

    items = xso.ChildList([Item])

    reported = xso.Child([Reported], required=False)

    def _validate_result(self):
        if self.fields:
            raise ValueError("field in report result")

        fieldvars = {field.var for field in self.reported.fields}

        if not fieldvars:
            raise ValueError("empty report header")

        for item in self.items:
            itemvars = {field.var for field in item.fields}
            if itemvars != fieldvars:
                raise ValueError("field mismatch between row and header")

    def validate(self):
        super().validate()

        if     (self.type_ != "result" and
                (self.reported is not None or self.items)):
            raise ValueError("report in non-result")

        if     (self.type_ == "result" and
                (self.reported is not None or self.items)):
            self._validate_result()
