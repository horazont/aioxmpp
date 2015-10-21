import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0004_data = "jabber:x:data"


class Value(xso.AbstractTextChild):
    TAG = (namespaces.xep0004_data, "value")


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

    values = xso.ChildList([Value])

    options = xso.ChildList([Option])

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
    )

    label = xso.Attr(
        (None, "label"),
        default=None
    )

    def __init__(self):
        super().__init__()
        self.type_ = "text-single"

    def validate(self):
        super().validate()

        if self.type_ != "fixed" and not self.var:
            raise ValueError("missing attribute var")

        if not self.type_.startswith("list-") and self.options:
            raise ValueError("unexpected option on non-list field")

        if not self.type_.endswith("-multi") and len(self.values) > 1:
            raise ValueError("too many values on non-multi field")

        labels_list = [opt.label for opt in self.options]
        labels_set = set(labels_list)

        if len(labels_list) != len(labels_set):
            raise ValueError("duplicate option label")

        values_list = [opt.value for opt in self.options]
        values_set = set(values_list)

        if len(values_list) != len(values_set):
            raise ValueError("duplicate option label")


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

        if self.type_ == "result":
            self._validate_result()
