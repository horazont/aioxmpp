#!/usr/bin/python3
########################################################################
# File name: form_type_to_code.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################
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


def simplify_text(s):
    return " ".join(s.split())


def generate_class(defn, outfile, strip_prefix):
    def prep_field_name(name):
        name = sanitize_field_name(name)
        if name.startswith(strip_prefix):
            name = name[len(strip_prefix):]
        return name

    field_data = [
        (prep_field_name(field.var), field)
        for field in defn.fields
    ]

    print("class Form(aioxmpp.forms.Form):", file=outfile)
    print("    \"\"\"")
    print("    Declaration of the form with type ``{}``".format(defn.name))
    print()
    for field_name, _ in field_data:
        print("    .. autoattribute:: {}".format(
            field_name
        ))
        print()
    print("    \"\"\"")
    print()
    print("    FORM_TYPE = {!r}".format(defn.name), file=outfile)
    print(file=outfile)

    for field_name, field in field_data:
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
                    label=simplify_text(field.label),
                ),
                file=outfile,
            )

        if field.desc:
            print(
                "        desc={desc!r}".format(
                    desc=simplify_text(field.desc),
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
