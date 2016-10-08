#!/usr/bin/python3
import argparse
import io
import sys

import aioxmpp.xml
import aioxmpp.xso
import aioxmpp.forms
import aioxmpp.forms.xso as forms_xso

from aioxmpp.utils import namespaces


class FormType(aioxmpp.xso.XSO):
    TAG = namespaces.xep0004_data, "form_type"

    fields = aioxmpp.xso.ChildList([forms_xso.Field])

    name = aioxmpp.xso.ChildText(
        (namespaces.xep0004_data, "name"),
    )


CLASS_MAP = {
    forms_xso.FieldType.LIST_SINGLE: aioxmpp.forms.ListSingle,
    forms_xso.FieldType.LIST_MULTI: aioxmpp.forms.ListMulti,

    forms_xso.FieldType.TEXT_SINGLE: aioxmpp.forms.TextSingle,
    forms_xso.FieldType.TEXT_MULTI: aioxmpp.forms.TextMulti,
    forms_xso.FieldType.TEXT_PRIVATE: aioxmpp.forms.TextPrivate,

    forms_xso.FieldType.JID_SINGLE: aioxmpp.forms.JIDSingle,
    forms_xso.FieldType.JID_MULTI: aioxmpp.forms.JIDMulti,

    forms_xso.FieldType.BOOLEAN: aioxmpp.forms.Boolean,
}


def sanitize_field_name(var):
    lhs, sep, rhs = var.rpartition("#")
    if rhs:
        var = rhs
    else:
        var = lhs

    return var.translate(str.maketrans(
        "-:/ ",
        "____",
    ))


def get_field_fqcn(class_):
    return ".".join(["aioxmpp.forms", class_.__qualname__])


def load_definition(infile):
    indata = infile.read()

    # this is nasty
    indata = indata.replace(
        b"<form_type>",
        "<form_type xmlns='{}'>".format(
            namespaces.xep0004_data
        ).encode("utf-8"),
        1
    )

    defn = aioxmpp.xml.read_single_xso(
        io.BytesIO(indata),
        FormType
    )

    return defn


def generate_class(defn, outfile, strip_prefix):
    print("class Form(aioxmpp.forms.Form):", file=outfile)
    print("    FORM_TYPE = {!r}".format(defn.name), file=outfile)
    print(file=outfile)

    for field in defn.fields:
        field_name = sanitize_field_name(field.var)
        if field_name.startswith(strip_prefix):
            field_name = field_name[len(strip_prefix):]
        fqcn = get_field_fqcn(CLASS_MAP[field.type_])

        print(
            "    {name} = {type_}(".format(
                name=field_name,
                type_=fqcn,
            ),
            file=outfile,
        )
        print(
            "        var={var!r},".format(
                var=field.var,
            ),
            file=outfile,
        )

        if field.label:
            print(
                "        label={label!r}".format(
                    label=field.label,
                ),
                file=outfile,
            )

        if field.desc:
            print(
                "        desc={label!r}".format(
                    desc=field.desc,
                ),
                file=outfile,
            )

        print("    )", file=outfile)
        print(file=outfile)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--strip-prefix",
        default="",
    )
    parser.add_argument(
        "infile",
        type=argparse.FileType("rb"),
    )

    args = parser.parse_args()

    with args.infile as f:
        defn = load_definition(f)

    generate_class(
        defn,
        sys.stdout,
        args.strip_prefix,
    )


if __name__ == "__main__":
    main()
