"""
:mod:`aioxmpp.stanza_types` --- Types specifications for use with :mod:`~aioxmpp.stanza_model`
########################################################################################################

This module provides classes whose objects can be used as types and validators
in :mod:`~aioxmpp.stanza_model`.

Types
=====

Types are used to convert strings obtained from XML character data or attribute
contents to python types. They are valid values for *type_* arguments e.g. for
:class:`~aioxmpp.stanza_model.Attr`.

The basic type interface
------------------------

.. autoclass:: AbstractType

Implementations
---------------

.. autoclass:: String

.. autoclass:: Integer

.. autoclass:: Bool

.. autoclass:: DateTime

.. autoclass:: Base64Binary

.. autoclass:: HexBinary

.. autoclass:: JID

Validators
==========

Validators validate the python values after they have been parsed from
XML-sourced strings or even when being assigned to a descriptor attribute
(depending on the choice in the *validate* argument).

They can be useful both for defending and rejecting incorrect input and to avoid
producing incorrect output.

The basic validator interface
-----------------------------

.. autoclass:: AbstractValidator

Implementations
---------------

.. autoclass:: RestrictToSet

.. autoclass:: Nmtoken

"""

import abc
import base64
import binascii
import unicodedata
import re

import pytz

from datetime import datetime, timedelta

from . import jid


class AbstractType(metaclass=abc.ABCMeta):
    """
    This is the interface all types must implement.

    .. automethod:: parse

    .. automethod:: format
    """

    @abc.abstractmethod
    def parse(self, v):
        """
        Convert the given string *v* into a value of the appropriate type this
        class implements and return the result.

        If conversion fails, :class:`ValueError` is raised.
        """

    def format(self, v):
        """
        Convert the value *v* of the type this class implements to a str.

        This conversion does not fail.
        """
        return str(v)


class String(AbstractType):
    """
    Interpret the input value as string. The identity operation: the value is
    returned unmodified.
    """

    def parse(self, v):
        return v


class Integer(AbstractType):
    """
    Parse the value as base-10 integer and return the result as :class:`int`.
    """

    def parse(self, v):
        return int(v)


class Float(AbstractType):
    """
    Parse the value as decimal float and return the result as :class:`float`.
    """

    def parse(self, v):
        return float(v)


class Bool(AbstractType):
    """
    Parse the value as boolean:

    * ``"true"`` and ``"1"`` are taken as :data:`True`,
    * ``"false"`` and ``"0"`` are taken as :data:`False`,
    * everything else results in a :class:`ValueError` exception.

    """

    def parse(self, v):
        v = v.strip()
        if v in ["true", "1"]:
            return True
        elif v in ["false", "0"]:
            return False
        else:
            raise ValueError("not a boolean value")

    def format(self, v):
        if v:
            return "true"
        else:
            return "false"


class DateTime(AbstractType):
    """
    Parse the value as ISO datetime, possibly including microseconds and
    timezone information.

    Timezones are handled as constant offsets from UTC, and are converted to UTC
    before the :class:`~datetime.datetime` object is returned (which is
    correctly tagged with UTC tzinfo). Values without timezone specification are
    not tagged.

    This class makes use of :mod:`pytz`.
    """

    tzextract = re.compile("((Z)|([+-][0-9]{2}):([0-9]{2}))$")

    def parse(self, v):
        v = v.strip()
        m = self.tzextract.search(v)
        if m:
            _, utc, hour_offset, minute_offset = m.groups()
            if utc:
                hour_offset = 0
                minute_offset = 0
            else:
                hour_offset = int(hour_offset)
                minute_offset = int(minute_offset)
            tzinfo = pytz.utc
            offset = timedelta(minutes=minute_offset+60*hour_offset)
            v = v[:m.start()]
        else:
            tzinfo = None
            offset = timedelta(0)

        try:
            dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")

        return dt.replace(tzinfo=tzinfo) - offset

    def format(self, v):
        if v.tzinfo:
            v = pytz.utc.normalize(v)
        result = v.strftime("%Y-%m-%dT%H:%M:%S")
        if v.microsecond:
            result += ".{:06d}".format(v.microsecond).rstrip("0")
        if v.tzinfo:
            result += "Z"
        return result


class Base64Binary(AbstractType):
    """
    Parse the value as base64 and return the :class:`bytes` object obtained from
    decoding.
    """

    def parse(self, v):
        return base64.b64decode(v)

    def format(self, v):
        return base64.b64encode(v).decode("ascii")


class HexBinary(AbstractType):
    """
    Parse the value as hexadecimal blob and return the :class:`bytes` object
    obtained from decoding.
    """

    def parse(self, v):
        return binascii.a2b_hex(v)

    def format(self, v):
        return binascii.b2a_hex(v).decode("ascii")


class JID(AbstractType):
    """
    Parse the value as Jabber ID using :meth:`~aioxmpp.jid.JID.fromstr` and
    return the :class:`aioxmpp.jid.JID` object.
    """

    def parse(self, v):
        return jid.JID.fromstr(v)


class AbstractValidator(metaclass=abc.ABCMeta):
    """
    This is the interface all validators must implement. In addition, a
    validators documentation should clearly state on which types it operates.

    .. automethod:: validate
    """

    @abc.abstractmethod
    def validate(self, value):
        """
        Return :data:`True` if the *value* adheres to the restrictions imposed
        by this validator and :data:`False` otherwise.
        """


class RestrictToSet(AbstractValidator):
    """
    Restrict the possible values to the values from *values*. Operates on any
    types.
    """

    def __init__(self, values):
        self.values = frozenset(values)

    def validate(self, value):
        return value in self.values


class Nmtoken(AbstractValidator):
    """
    Restrict the possible strings to the NMTOKEN specification of XML Schema
    Definitions. The validator only works with strings.

    .. warning::

       This validator is probably incorrect. It is a good first line of defense
       to avoid creating obvious incorrect output and should not be used as
       input validator.

       It most likely falsely rejects valid values and may let through invalid
       values.

    """

    VALID_CATS = {
        "Ll", "Lu", "Lo", "Lt", "Nl",  # Name start
        "Mc", "Me", "Mn", "Lm", "Nd",  # Name without name start
    }
    ADDITIONAL = frozenset(":_.-\u06dd\u06de\u06df\u00b7\u0387\u212e")
    UCD = unicodedata.ucd_3_2_0

    @classmethod
    def _validate_chr(cls, c):
        if c in cls.ADDITIONAL:
            return True
        if 0xf900 < ord(c) < 0xfffe:
            return False
        if 0x20dd <= ord(c) <= 0x20e0:
            return False
        if cls.UCD.category(c) not in cls.VALID_CATS:
            return False
        return True

    def validate(self, value):
        return all(map(self._validate_chr, value))
