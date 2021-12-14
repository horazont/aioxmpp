########################################################################
# File name: stringprep.py
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
Stringprep support
##################

This module implements the Nodeprep (`RFC 6122`_) and Resourceprep
(`RFC 6122`_) stringprep profiles.

.. autofunction:: nodeprep

.. autofunction:: resourceprep

.. autofunction:: nameprep

.. _RFC 3454: https://tools.ietf.org/html/rfc3454
.. _RFC 6122: https://tools.ietf.org/html/rfc6122

"""

import stringprep

from unicodedata import ucd_3_2_0 as unicodedata

_nodeprep_prohibited = frozenset("\"&'/:<>@")


def is_RandALCat(c):
    return unicodedata.bidirectional(c) in ("R", "AL")


def is_LCat(c):
    return unicodedata.bidirectional(c) == "L"


def check_against_tables(chars, tables):
    """
    Perform a check against the table predicates in `tables`. `tables` must be
    a reusable iterable containing characteristic functions of character sets,
    that is, functions which return :data:`True` if the character is in the
    table.

    The function returns the first character occurring in any of the tables or
    :data:`None` if no character matches.
    """

    for c in chars:
        if any(in_table(c) for in_table in tables):
            return c

    return None


def do_normalization(chars):
    """
    Perform the stringprep normalization. Operates in-place on a list of
    unicode characters provided in `chars`.
    """
    chars[:] = list(unicodedata.normalize("NFKC", "".join(chars)))


def check_bidi(chars):
    """
    Check proper bidirectionality as per stringprep. Operates on a list of
    unicode characters provided in `chars`.
    """

    # the empty string is valid, as it cannot violate the RandALCat constraints
    if not chars:
        return

    # first_is_RorAL = unicodedata.bidirectional(chars[0]) in {"R", "AL"}
    # if first_is_RorAL:

    has_RandALCat = any(is_RandALCat(c) for c in chars)
    if not has_RandALCat:
        return

    has_LCat = any(is_LCat(c) for c in chars)
    if has_LCat:
        raise ValueError("L and R/AL characters must not occur in the same"
                         " string")

    if not is_RandALCat(chars[0]) or not is_RandALCat(chars[-1]):
        raise ValueError("R/AL string must start and end with R/AL character.")


def check_prohibited_output(chars, bad_tables):
    """
    Check against prohibited output, by checking whether any of the characters
    from `chars` are in any of the `bad_tables`.

    Operates in-place on a list of code points from `chars`.
    """
    violator = check_against_tables(chars, bad_tables)
    if violator is not None:
        raise ValueError("Input contains invalid unicode codepoint: "
                         "U+{:04x}".format(ord(violator)))


def check_unassigned(chars, bad_tables):
    """
    Check that `chars` does not contain any unassigned code points as per
    the given list of `bad_tables`.

    Operates on a list of unicode code points provided in `chars`.
    """
    bad_tables = (
        stringprep.in_table_a1,)

    violator = check_against_tables(chars, bad_tables)
    if violator is not None:
        raise ValueError("Input contains unassigned code point: "
                         "U+{:04x}".format(ord(violator)))


def _nodeprep_do_mapping(chars):
    i = 0
    while i < len(chars):
        c = chars[i]
        if stringprep.in_table_b1(c):
            del chars[i]
        else:
            replacement = stringprep.map_table_b2(c)
            if replacement != c:
                chars[i:(i + 1)] = list(replacement)
            i += len(replacement)


def nodeprep(string, allow_unassigned=False):
    """
    Process the given `string` using the Nodeprep (`RFC 6122`_) profile. In the
    error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError` is
    raised.
    """

    chars = list(string)
    _nodeprep_do_mapping(chars)
    do_normalization(chars)
    check_prohibited_output(
        chars,
        (
            stringprep.in_table_c11,
            stringprep.in_table_c12,
            stringprep.in_table_c21,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
            lambda x: x in _nodeprep_prohibited
        ))
    check_bidi(chars)

    if not allow_unassigned:
        check_unassigned(
            chars,
            (
                stringprep.in_table_a1,
            )
        )

    return "".join(chars)


def _resourceprep_do_mapping(chars):
    i = 0
    while i < len(chars):
        c = chars[i]
        if stringprep.in_table_b1(c):
            del chars[i]
            continue
        i += 1


def resourceprep(string, allow_unassigned=False):
    """
    Process the given `string` using the Resourceprep (`RFC 6122`_) profile. In
    the error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError`
    is raised.
    """

    chars = list(string)
    _resourceprep_do_mapping(chars)
    do_normalization(chars)
    check_prohibited_output(
        chars,
        (
            stringprep.in_table_c12,
            stringprep.in_table_c21,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
        ))
    check_bidi(chars)

    if not allow_unassigned:
        check_unassigned(
            chars,
            (
                stringprep.in_table_a1,
            )
        )

    return "".join(chars)


def nameprep(string, allow_unassigned=False):
    """
    Process the given `string` using the Nameprep (`RFC 3491`_) profile. In the
    error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError` is
    raised.
    """

    chars = list(string)
    _nodeprep_do_mapping(chars)
    do_normalization(chars)
    check_prohibited_output(
        chars,
        (
            stringprep.in_table_c12,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
        ))
    check_bidi(chars)

    if not allow_unassigned:
        check_unassigned(
            chars,
            (
                stringprep.in_table_a1,
            )
        )

    return "".join(chars)
