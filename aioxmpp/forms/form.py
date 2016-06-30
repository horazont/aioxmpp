import abc

import aioxmpp.xso as xso


class InputLine:
    def __init__(self, var, type_=xso.String()):
        super().__init__()
        self._var = var
        self._type = type_

    @property
    def var(self):
        return self._var

    @property
    def type_(self):
        return self._type

    def __get__(self, instance, type_):
        if instance is None:
            return self
        return self._type.parse(instance._field_data[self.var])

    def __set__(self, instance, value):
        value = self._type.format(self._type.coerce(value))
        if "\r" in value or "\n" in value:
            raise ValueError("newlines not allowed in input line")
        instance._field_data[self.var] = value


class InputJID(InputLine):
    def __init__(self, var):
        super().__init__(var, type_=xso.JID())


class FormClass(abc.ABCMeta):
    def __new__(mcls, name, bases, namespace):
        namespace["FIELD_DESCRIPTORS"] = False
        namespace["FIELDS"] = False
        return super().__new__(mcls, name, bases, namespace)


class Form:
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


# class MUCConfigureForm(forms.Form):
#     FORM_TYPE = "http://jabber.org/protocol/muc#roomconfig"

#     name = forms.TextLine(
#         "muc#roomconfig_roomname",
#         label="fnord",
#         desc="""some
#         multi
#         line
#         text""",
#     )

#     LAYOUT = [
#         "heading",
#         """
#         multi-line stuff gets broken down automatically.

#         each paragraph becomes a "fixed" field. {jid} is replaced by
#         _layout_form on request.
#         """,
#         name,  # adding fields inline
#     ]

#     def layout_form(self, localizer, translators):
#         return super()._layout_form(
#             localizer,
#             translators,
#             kwargs={
#                 "jid": "bar",
#             },
#         )


# how I want it to be

# class MUCConfigureForm(forms.Form):
#     FORM_TYPE = "http://jabber.org/protocol/muc#roomconfig"

#     name = forms.TextLine(
#         "muc#roomconfig_roomname",
#         label="fnord",
#         desc="""some
#         multi
#         line
#         text""",
#     )

#     _ = forms.Fixed("foo")

#     description = forms.TextLine(
#         "muc#roomconfig_roomdesc"
#     )

#     public_logging = forms.Boolean(
#         "muc#roomconfig_enablelogging"
#     )


#     def received_fields(self):
#         """
#         Return an iterable of the field XSOs, in the order they were sent by
#         the peer.
#         """

#     def render(self):
#         """
#         Return an iterable of descriptors, strings and/or XSOs. Strings are
#         converted to ``"fixed"`` fields, XSOs must be Fields. The descriptors
#         are converted to their corresponding XSOs.
#         """
