########################################################################
# File name: types.py
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
:mod:`aioxmpp.xso.types` --- Types specifications for use with :mod:`aioxmpp.xso.model`
#######################################################################################

See :mod:`aioxmpp.xso` for documentation.

"""  # NOQA: E501

import abc
import array
import base64
import binascii
import decimal
import ipaddress
import json
import numbers
import re
import unicodedata
import warnings

import pytz

from datetime import datetime, timedelta, date, time

from .. import structs, i18n


class Unknown:
    """
    A wrapper for an unknown enumeration value.

    :param value: The raw value of the "enumeration" "member".
    :type value: arbitrary

    Instances of this class may be emitted from and accepted by
    :class:`EnumCDataType` and :class:`EnumElementType`, see the documentation
    there for details.

    :class:`Unknown` instances compare equal when they hold an equal value.
    :class:`Unknown` objects are hashable if their values are hashable. The
    value they refer to cannot be changed during the lifetime of an
    :class:`Unknown` object.
    """

    def __init__(self, value):
        super().__init__()
        self.__value = value

    @property
    def value(self):
        return self.__value

    def __hash__(self):
        return hash(self.__value)

    def __eq__(self, other):
        try:
            return self.__value == other.__value
        except AttributeError:
            return NotImplemented

    def __repr__(self):
        return "<Unknown: {!r}>".format(
            self.__value
        )


class AbstractCDataType(metaclass=abc.ABCMeta):
    """
    Subclasses of this class describe character data types.

    They are used to convert python values from (:meth:`parse`) and to
    (:meth:`format`) XML character data as well as enforce basic type
    restrictions (:meth:`coerce`) when values are assigned to descriptors
    using this type.

    This type can be used by the character data descriptors, like :class:`Attr`
    and :class:`Text`.

    .. automethod:: coerce

    .. automethod:: parse

    .. automethod:: format
    """

    def coerce(self, v):
        """
        Force the given value `v` to be of the type represented by this
        :class:`AbstractCDataType`.

        :meth:`coerce` is called when user code assigns values to descriptors
        which use the type; it is notably not called when values are extracted
        from SAX events, as these go through :meth:`parse` and that is expected
        to return correctly typed values.

        If `v` cannot be sensibly coerced, :class:`TypeError` is raised (in
        some rare occasions, :class:`ValueError` may be ok too).

        Return a coerced version of `v` or `v` itself if it matches the
        required type.

        .. note::

           For the sake of usability, coercion should only take place rarely;
           in most of the cases, throwing :class:`TypeError` is the preferred
           method.

           Otherwise, a user might be surprised why the :class:`int` they
           assigned to an attribute suddenly became a :class:`str`.

        """
        return v

    @abc.abstractmethod
    def parse(self, v):
        """
        Convert the given string `v` into a value of the appropriate type this
        class implements and return the result.

        If conversion fails, :class:`ValueError` is raised.

        The result of :meth:`parse` must pass through :meth:`coerce` unchanged.
        """

    def format(self, v):
        """
        Convert the value `v` of the type this class implements to a str.

        This conversion does not fail.

        The returned value can be passed to :meth:`parse` to obtain `v`.
        """
        return str(v)


class AbstractElementType(metaclass=abc.ABCMeta):
    """
    Subclasses of this class describe XML subtree types.

    They are used to convert python values from (:meth:`unpack`) and to
    (:meth:`pack`) XML subtrees represented as :class:`XSO` instances as well
    as enforce basic type restrictions (:meth:`coerce`) when values are
    assigned to descriptors using this type.

    This type can be used by the element descriptors, like
    :class:`ChildValueList` and :class:`ChildValueMap`.

    .. automethod:: get_xso_types

    .. automethod:: coerce

    .. automethod:: unpack

    .. automethod:: pack
    """

    @abc.abstractmethod
    def get_xso_types(self):
        """
        Return the :class:`XSO` subclasses supported by this type.

        :rtype: :class:`~collections.Iterable` of :class:`XMLStreamClass`
        :return: The :class:`XSO` subclasses which can be passed to
            :meth:`unpack`.
        """

    @abc.abstractmethod
    def unpack(self, obj):
        """
        Convert a :class:`XSO` instance to another object, usually a scalar
        value or a tuple.

        :param obj: The object to unpack.
        :type obj: One of the types returned by :meth:`get_xso_types`.
        :raises ValueError: if the conversaion fails.
        :return: The unpacked value.

        Think of unpack like a high-level :func:`struct.unpack`: it converts
        wire-format data (XML subtrees represented as :class:`XSO` instances)
        to python values.
        """

    @abc.abstractmethod
    def pack(self, v):
        """
        Convert the value `v` of the type this class implements to an
        :class:`XSO` instance.

        :param v: Value to pack
        :type v: as returned by :meth:`unpack`
        :rtype: One of the types returned by :meth:`get_xso_types`.
        :return: The packed value.

        The returned value can be passed through :meth:`unpack` to obtain a
        value equal to `v`.

        Think of pack like a high-level :func:`struct.pack`: it converts
        python values to wire-format (XML subtrees represented as :class:`XSO`
        instances).
        """

    def coerce(self, v):
        """
        Force the given value `v` to be compatible to :meth:`pack`.

        :meth:`coerce` is called when user code assigns
        values to descriptors which use the type; it is notably not called when
        values are extracted from SAX events, as these go through
        :meth:`unpack` and that is expected to return correctly typed values.

        If `v` cannot be sensibly coerced, :class:`TypeError` is raised (in
        some rare occasions, :class:`ValueError` may be ok too).

        Return a coerced version of `v` or `v` itself if it matches the
        required type.

        .. note::

           For the sake of usability, coercion should only take place rarely;
           in most of the cases, throwing :class:`TypeError` is the preferred
           method.

           Otherwise, a user might be surprised why the :class:`int` they
           assigned to an attribute suddenly became a :class:`str`.

        """
        return v


class String(AbstractCDataType):
    """
    String :term:`Character Data Type`, optionally with string preparation.

    Optionally, a stringprep function `prepfunc` can be applied on the
    string. A stringprep function must take the string and prepare it
    accordingly; if it is invalid input, it must raise
    :class:`ValueError`. Otherwise, it shall return the prepared string.

    If no `prepfunc` is given, this type is the identity operation.
    """

    def __init__(self, prepfunc=None):
        super().__init__()
        self.prepfunc = prepfunc

    def coerce(self, v):
        if not isinstance(v, str):
            raise TypeError("must be a str object")
        if self.prepfunc is not None:
            return self.prepfunc(v)
        return v

    def parse(self, v):
        if self.prepfunc is not None:
            return self.prepfunc(v)
        return v


class Integer(AbstractCDataType):
    """
    Integer :term:`Character Data Type`, to the base 10.
    """

    def coerce(self, v):
        if not isinstance(v, numbers.Integral):
            raise TypeError("must be integral number")
        return int(v)

    def parse(self, v):
        return int(v)


class Float(AbstractCDataType):
    """
    Floating point or decimal :term:`Character Data Type`.
    """

    def coerce(self, v):
        if not isinstance(v, (numbers.Real, decimal.Decimal)):
            raise TypeError("must be real number")
        return float(v)

    def parse(self, v):
        return float(v)


class Bool(AbstractCDataType):
    """
    XML boolean :term:`Character Data Type`.

    Parse the value as boolean:

    * ``"true"`` and ``"1"`` are taken as :data:`True`,
    * ``"false"`` and ``"0"`` are taken as :data:`False`,
    * everything else results in a :class:`ValueError` exception.

    """

    def coerce(self, v):
        return bool(v)

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


class DateTime(AbstractCDataType):
    """
    ISO datetime :term:`Character Data Type`.

    Parse the value as ISO datetime, possibly including microseconds and
    timezone information.

    Timezones are handled as constant offsets from UTC, and are converted to
    UTC before the :class:`~datetime.datetime` object is returned (which is
    correctly tagged with UTC tzinfo). Values without timezone specification
    are not tagged.

    If `legacy` is true, the formatted dates use the legacy date/time format
    (``CCYYMMDDThh:mm:ss``), as used for example in :xep:`0082` or :xep:`0009`
    (whereas in the latter it is not legacy, but defined by XML RPC). In any
    case, parsing of the legacy format is transparently supported. Timestamps
    in the legacy format are assumed to be in UTC, and datetime objects are
    converted to UTC before emitting the legacy format. The timezone designator
    is never emitted with the legacy format, and ignored if given.

    This class makes use of :mod:`pytz`.

    .. versionadded:: 0.5

       The `legacy` argument was added.

    """

    tzextract = re.compile("((Z)|([+-][0-9]{2}):([0-9]{2}))$")

    def __init__(self, *, legacy=False):
        super().__init__()
        self.legacy = legacy

    def coerce(self, v):
        if not isinstance(v, datetime):
            raise TypeError("must be a datetime object")
        return v

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
            offset = timedelta(minutes=minute_offset + 60 * hour_offset)
            v = v[:m.start()]
        else:
            tzinfo = None
            offset = timedelta(0)

        try:
            dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            try:
                dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                dt = datetime.strptime(v, "%Y%m%dT%H:%M:%S")
                tzinfo = pytz.utc
                offset = timedelta(0)

        return dt.replace(tzinfo=tzinfo) - offset

    def format(self, v):
        if v.tzinfo:
            v = pytz.utc.normalize(v)
        if self.legacy:
            return v.strftime("%Y%m%dT%H:%M:%S")

        result = v.strftime("%Y-%m-%dT%H:%M:%S")
        if v.microsecond:
            result += ".{:06d}".format(v.microsecond).rstrip("0")
        if v.tzinfo:
            result += "Z"
        return result


class Date(AbstractCDataType):
    """
    ISO date :term:`Character Data Type`.

    Implement the Date type from :xep:`0082`.

    Values must have the :class:`date` type, :class:`datetime` is forbidden to
    avoid silent loss of information.

    .. versionadded:: 0.5
    """

    def parse(self, s):
        return datetime.strptime(s, "%Y-%m-%d").date()

    def coerce(self, v):
        if not isinstance(v, date) or isinstance(v, datetime):
            raise TypeError("must be a date object")
        return v


class Time(AbstractCDataType):
    """
    ISO time :term:`Character Data Type`.

    Implement the Time type from :xep:`0082`.

    Values must have the :class:`time` type, :class:`datetime` is forbidden to
    avoid silent loss of information. Assignment of :class:`time` values in
    time zones which are not UTC is not allowed either. The reason is that the
    translation to UTC on formatting is not properly defined without an
    accompanying date (think daylight saving time transitions, redefinitions of
    time zones, …).

    .. versionadded:: 0.5
    """

    def parse(self, v):
        v = v.strip()
        m = DateTime.tzextract.search(v)
        if m:
            _, utc, hour_offset, minute_offset = m.groups()
            if utc:
                hour_offset = 0
                minute_offset = 0
            else:
                hour_offset = int(hour_offset)
                minute_offset = int(minute_offset)
            tzinfo = pytz.utc
            offset = timedelta(minutes=minute_offset + 60 * hour_offset)
            v = v[:m.start()]
        else:
            tzinfo = None
            offset = timedelta(0)

        try:
            dt = datetime.strptime(v, "%H:%M:%S.%f")
        except ValueError:
            dt = datetime.strptime(v, "%H:%M:%S")

        return (dt.replace(tzinfo=tzinfo) - offset).timetz()

    def format(self, v):
        if v.tzinfo:
            v = pytz.utc.normalize(v)

        result = v.strftime("%H:%M:%S")
        if v.microsecond:
            result += ".{:06d}".format(v.microsecond).rstrip("0")
        if v.tzinfo:
            result += "Z"
        return result

    def coerce(self, t):
        if not isinstance(t, time):
            raise TypeError("must be a time object")
        if t.tzinfo is None:
            return t
        if t.tzinfo == pytz.utc:
            return t
        raise ValueError("time must have UTC timezone or none at all")


class _BinaryType(AbstractCDataType):
    """
    Implements pointful coercion for binary types.
    """

    def coerce(self, v):
        if isinstance(v, bytes):
            return v
        elif isinstance(v, (bytearray, array.array)):
            return bytes(v)
        raise TypeError("must be convertible to bytes")


class Base64Binary(_BinaryType):
    """
    :term:`Character Data Type` for :class:`bytes` encoded as base64.

    Parse the value as base64 and return the :class:`bytes` object obtained
    from decoding.

    If `empty_as_equal` is :data:`True`, an empty value is represented using a
    single equal sign. This is used in the SASL protocol.
    """

    def __init__(self, *, empty_as_equal=False):
        super().__init__()
        self._empty_as_equal = empty_as_equal

    def parse(self, v):
        return base64.b64decode(v)

    def format(self, v):
        if self._empty_as_equal and not v:
            return "="
        return base64.b64encode(v).decode("ascii")


class HexBinary(_BinaryType):
    """
    :term:`Character Data Type` for :class:`bytes` encoded as hexadecimal.

    Parse the value as hexadecimal blob and return the :class:`bytes` object
    obtained from decoding.
    """

    def parse(self, v):
        return binascii.a2b_hex(v)

    def format(self, v):
        return binascii.b2a_hex(v).decode("ascii")


class JID(AbstractCDataType):
    """
    :term:`Character Data Type` for :class:`aioxmpp.JID` objects.

    Parse the value as Jabber ID using :meth:`~aioxmpp.JID.fromstr` and
    return the :class:`aioxmpp.JID` object.

    `strict` is passed to :meth:`~aioxmpp.JID.fromstr` and defaults to
    false. See the :meth:`~aioxmpp.JID.fromstr` method for a rationale
    and consider that :meth:`parse` is only called for input coming from the
    outside.
    """

    def __init__(self, *, strict=False):
        super().__init__()
        self.strict = strict

    def coerce(self, v):
        if not isinstance(v, structs.JID):
            raise TypeError("{} object {!r} is not a JID".format(
                type(v), v))

        return v

    def parse(self, v):
        return structs.JID.fromstr(v, strict=self.strict)


class ConnectionLocation(AbstractCDataType):
    """
    :term:`Character Data Type` for a hostname-port pair.

    Parse the value as a host-port pair, as for example used for Stream
    Management reconnection location advisories.
    """

    def coerce(self, v):
        if not isinstance(v, tuple):
            raise TypeError("2-tuple required for ConnectionLocation")
        if len(v) != 2:
            raise TypeError("2-tuple required for ConnectionLocation")

        addr, port = v

        if not isinstance(port, numbers.Integral):
            raise TypeError("port number must be integral number")
        port = int(port)

        if not (0 <= port <= 65535):
            raise ValueError("port number {} out of range".format(port))

        try:
            addr = ipaddress.IPv4Address(addr)
        except ValueError:
            try:
                addr = ipaddress.IPv6Address(addr)
            except ValueError:
                pass

        return (addr, port)

    def parse(self, v):
        v = v.strip()

        if v.endswith("]"):
            # IPv6 address without port number
            if not v.startswith("["):
                raise ValueError(
                    "IPv6 address must be encapsulated in square brackets"
                )
            return self.coerce((
                ipaddress.IPv6Address(v[1:-1]),
                5222
            ))

        addr, sep, port = v.rpartition(":")
        if sep:
            port = int(port)
        else:
            # with rpartition, the stuff is on the RHS when the separator was
            # not found
            addr = port
            port = 5222

        if addr.startswith("[") and addr.endswith("]"):
            addr = ipaddress.IPv6Address(addr[1:-1])
        elif ":" in addr:
            raise ValueError(
                "IPv6 address must be encapsulated in square brackets"
            )

        try:
            addr = ipaddress.IPv4Address(addr)
        except ValueError:
            pass

        return self.coerce((addr, port))

    def format(self, v):
        if isinstance(v[0], ipaddress.IPv6Address):
            return "[{}]:{}".format(*v)
        return ":".join(map(str, v))


class LanguageTag(AbstractCDataType):
    """
    :term:`Character Data Type` for language tags.

    Parses the value as Language Tag using
    :meth:`~.structs.LanguageTag.fromstr`.

    Type coercion requires that any value assigned to a descriptor using this
    type is an instance of :class:`~.structs.LanguageTag`.
    """

    def parse(self, v):
        return structs.LanguageTag.fromstr(v)

    def coerce(self, v):
        if not isinstance(v, structs.LanguageTag):
            raise TypeError("{!r} is not a LanguageTag", v)
        return v


class JSON(AbstractCDataType):
    """
    :term:`Character Data Type` for JSON formatted data.

    .. versionadded:: 0.11

    Upon deserialisation, character data is parsed as JSON using :mod:`json`.
    On serialisation, the value is serialised as JSON. This implies that the
    data must be JSON serialisable, but there is no check for that in
    :meth:`coerce`, as this check would be (a) expensive to do for nested data
    structures and (b) impossible to do for mutable data structures.

    Example:

    .. code-block:: python

        class JSONContainer(aioxmpp.xso.XSO):
            TAG = ("urn:xmpp:json:0", "json")

            data = aioxmpp.xso.Text(
                type_=aioxmpp.xso.JSON()
            )

    """

    def parse(self, v):
        return json.loads(v)

    def format(self, v):
        return json.dumps(v)

    def coerce(self, v):
        return v


class TextChildMap(AbstractElementType):
    """
    A type for use with :class:`.xso.ChildValueMap` and descendants of
    :class:`.xso.AbstractTextChild`.

    This type performs the packing and unpacking of language-text-pairs to and
    from the `xso_type`. `xso_type` must have an interface compatible with
    :class:`.xso.AbstractTextChild`, which means that it must have the language
    and text at :attr:`~.xso.AbstractTextChild.lang` and
    :attr:`~.xso.AbstractTextChild.text`, respectively and support the
    same-named keyword arguments for those attributes at the constructor.

    For an example see the source of :class:`aioxmpp.Message`.

    .. versionadded:: 0.5
    """

    def __init__(self, xso_type):
        super().__init__()
        self.xso_type = xso_type

    def get_xso_types(self):
        return [self.xso_type]

    def unpack(self, obj):
        return obj.lang, obj.text

    def pack(self, item):
        lang, text = item
        xso = self.xso_type(text=text, lang=lang)
        return xso


class EnumCDataType(AbstractCDataType):
    """
    Use an :class:`enum.Enum` as type for an XSO descriptor.

    :param enum_class: The :class:`~enum.Enum` to use as type.
    :param nested_type: A type which can handle the values of the enumeration
        members.
    :type nested_type: :class:`AbstractCDataType`
    :param allow_coerce: Allow coercion of different types to enumeration
                         values.
    :type allow_coerce: :class:`bool`
    :param deprecate_coerce: Emit :class:`DeprecationWarning` when coercion
                             occurs. Requires (but does not imply)
                             `allow_coerce`.
    :type deprecate_coerce: :class:`int` or :class:`bool`
    :param allow_unknown: If true, unknown values are converted to
                          :class:`Unknown` instances when parsing values from
                          the XML stream.
    :type allow_unknown: :class:`bool`
    :param accept_unknown: If true, :class:`Unknown` instances are passed
                           through :meth:`coerce` and can thus be assigned to
                           descriptors using this type.
    :type accept_unknown: :class:`bool`
    :param pass_unknown: If true, unknown values are accepted unmodified (both
        on the receiving and on the sending side). It is useful for some
        :class:`enum.IntEnum` use cases.
    :type pass_unknown: :class:`bool`

    A descriptor using this type will accept elements from the given
    `enum_class` as values. Upon serialisiation, the :attr:`value` of the
    enumeration element is taken and formatted through the given `nested_type`.

    Normally, :meth:`coerce` will raise :class:`TypeError` for any value which
    is not an instance of `enum_class`. However, if `allow_coerce` is true, the
    value is passed to the `enum_class` constructor and the result is returned;
    the :class:`ValueError` raised from the `enum_class` constructor if an
    invalid value is passed propagates unmodified.

    .. note::

       When using `allow_coerce`, keep in mind that this may have surprising
       effects for users. Coercion means that the value assigned to an
       attribute and the value subsequently read from that attribute may not
       be the same; this may be very surprising to users::

         class E(enum.Enum):
             X = "foo"

         class SomeXSO(xso.XSO):
             attr = xso.Attr("foo", xso.EnumCDataType(E, allow_coerce=True))

         x = SomeXSO()
         x.attr = "foo"
         assert x.attr == "foo"  # assertion fails!

    To allow coercion transitionally while moving from e.g. string-based values
    to a proper enum, `deprecate_coerce` can be used. In that case, a
    :class:`DeprecationWarning` (see :mod:`warnings`) is emitted when coercion
    takes place, to warn users about future removal of the coercion capability.
    If `deprecate_coerce` is an integer, it is used as the stacklevel argument
    for the :func:`warnings.warn` call. If it is :data:`True`, the stacklevel
    is 4, which leads to the warning pointing to a descriptor assignment when
    used with XSO descriptors.

    Handling of :class:`Unknown` values: Using `allow_unknown` and
    `accept_unknown` is advisable to stay compatible with future protocols,
    which is why both are enabled by default. Considering that constructing an
    :class:`Unknown` value needs to be done explicitly in code, it is unlikely
    that a user will *accidentally* assign an unspecified value to a descriptor
    using this type with `accept_unknown`.

    `pass_unknown` requires `allow_unknown` and `accept_unknown`. When set to
    true, values which are not a member of `enum_class` are used without
    modification (but they are validated against the `nested_type`). This
    applies to both the sending and the receiving side. The intended use case
    is with :class:`enum.IntEnum` classes. If a :class:`Unknown` value is
    passed, it is unwrapped and treated as if the original value had been
    passed.

    Example::

      class SomeEnum(enum.Enum):
          X = 1
          Y = 2
          Z = 3

      class SomeXSO(xso.XSO):
          attr = xso.Attr(
              "foo",
              type_=xso.EnumCDataType(
                  SomeEnum,
                  # have to use integer, because the value of e.g. SomeEnum.X
                  # is integer!
                  xso.Integer()
              ),
          )

    .. versionchanged:: 0.10

        Support for `pass_unknown` was added.
    """

    def __init__(self, enum_class, nested_type=String(), *,
                 allow_coerce=False,
                 deprecate_coerce=False,
                 allow_unknown=True,
                 accept_unknown=True,
                 pass_unknown=False):
        if pass_unknown and (not allow_unknown or not accept_unknown):
            raise ValueError(
                "pass_unknown requires allow_unknown and accept_unknown"
            )

        super().__init__()
        self.nested_type = nested_type
        self.enum_class = enum_class
        self.allow_coerce = allow_coerce
        self.deprecate_coerce = deprecate_coerce
        self.accept_unknown = accept_unknown
        self.allow_unknown = allow_unknown
        self.pass_unknown = pass_unknown

    def coerce(self, value):
        if (not self.pass_unknown and self.accept_unknown and
                isinstance(value, Unknown)):
            return value

        if isinstance(value, self.enum_class):
            return value

        if self.allow_coerce:
            if self.deprecate_coerce:
                stacklevel = (4 if self.deprecate_coerce is True
                              else self.deprecate_coerce)
                warnings.warn(
                    "assignment of non-enum values to this descriptor is"
                    " deprecated",
                    DeprecationWarning,
                    stacklevel=stacklevel,
                )

            value = self.nested_type.coerce(value)
            try:
                return self.enum_class(value)
            except ValueError:
                if self.pass_unknown:
                    return value
                raise

        if self.pass_unknown:
            value = self.nested_type.coerce(value)
            return value

        raise TypeError("not a valid {} value: {!r}".format(
            self.enum_class,
            value,
        ))

    def parse(self, s):
        parsed = self.nested_type.parse(s)
        try:
            return self.enum_class(parsed)
        except ValueError:
            if self.pass_unknown:
                return parsed
            if self.allow_unknown:
                return Unknown(parsed)
            raise

    def format(self, v):
        if self.pass_unknown and not isinstance(v, self.enum_class):
            return self.nested_type.format(v)
        return self.nested_type.format(v.value)


class EnumElementType(AbstractElementType):
    """
    Use an :class:`enum.Enum` as type for an XSO descriptor.

    :param enum_class: The :class:`~enum.Enum` to use as type.
    :param nested_type: Type which describes the value type of the
        `enum_class`.
    :type nested_type: :class:`AbstractElementType`
    :param allow_coerce: Allow coercion of different types to enumeration
                         values.
    :type allow_coerce: :class:`bool`
    :param deprecate_coerce: Emit :class:`DeprecationWarning` when coercion
                             occurs. Requires (but does not imply)
                             `allow_coerce`.
    :type deprecate_coerce: :class:`int` or :class:`bool`
    :param allow_unknown: If true, unknown values are converted to
                          :class:`Unknown` instances when parsing values from
                          the XML stream.
    :type allow_unknown: :class:`bool`
    :param accept_unknown: If true, :class:`Unknown` instances are passed
                           through :meth:`coerce` and can thus be assigned to
                           descriptors using this type.
    :type allow_unknown: :class:`bool`

    A descriptor using this type will accept elements from the given
    `enum_class` as values. Upon serialisiation, the :attr:`value` of the
    enumeration element is taken and packed through the given `nested_type`.

    Normally, :meth:`coerce` will raise :class:`TypeError` for any value which
    is not an instance of `enum_class`. However, if `allow_coerce` is true, the
    value is passed to the `enum_class` constructor and the result is returned;
    the :class:`ValueError` raised from the `enum_class` constructor if an
    invalid value is passed propagates unmodified.

    .. seealso::

        :class:`EnumCDataType`
            for a detailed discussion on the implications of coercion.

    Handling of :class:`Unknown` values: Using `allow_unknown` and
    `accept_unknown` is advisable to stay compatible with future protocols,
    which is why both are enabled by default. Considering that constructing an
    :class:`Unknown` value needs to be done explicitly in code, it is unlikely
    that a user will *accidentally* assign an unspecified value to a descriptor
    using this type with `accept_unknown`.
    """

    def __init__(self, enum_class, nested_type, *,
                 allow_coerce=False,
                 deprecate_coerce=False,
                 allow_unknown=True,
                 accept_unknown=True):
        super().__init__()
        self.nested_type = nested_type
        self.enum_class = enum_class
        self.allow_coerce = allow_coerce
        self.deprecate_coerce = deprecate_coerce
        self.accept_unknown = accept_unknown
        self.allow_unknown = allow_unknown

    def get_xso_types(self):
        return self.nested_type.get_xso_types()

    def coerce(self, value):
        if self.accept_unknown and isinstance(value, Unknown):
            return value
        if self.allow_coerce:
            if self.deprecate_coerce:
                if isinstance(value, self.enum_class):
                    return value
                stacklevel = (4 if self.deprecate_coerce is True
                              else self.deprecate_coerce)
                warnings.warn(
                    "assignment of non-enum values to this descriptor is"
                    " deprecated",
                    DeprecationWarning,
                    stacklevel=stacklevel,
                )
            return self.enum_class(value)
        if isinstance(value, self.enum_class):
            return value
        raise TypeError("not a valid {} value: {!r}".format(
            self.enum_class,
            value,
        ))

    def unpack(self, s):
        parsed = self.nested_type.unpack(s)
        try:
            return self.enum_class(parsed)
        except ValueError:
            if self.allow_unknown:
                return Unknown(parsed)
            raise

    def pack(self, v):
        return self.nested_type.pack(v.value)


class AbstractValidator(metaclass=abc.ABCMeta):
    """
    This is the interface all validators must implement. In addition, a
    validators documentation should clearly state on which types it operates.

    .. automethod:: validate

    .. automethod:: validate_detailed
    """

    def validate(self, value):
        """
        Return :data:`True` if the `value` adheres to the restrictions imposed
        by this validator and :data:`False` otherwise.

        By default, this method calls :meth:`validate_detailed` and returns
        :data:`True` if :meth:`validate_detailed` returned an empty result.
        """
        return not self.validate_detailed(value)

    @abc.abstractmethod
    def validate_detailed(self, value):
        """
        Return an empty list if the `value` adheres to the restrictions imposed
        by this validator.

        If the value does not comply, return a list of
        :class:`~aioxmpp.errors.UserValueError` instances which each represent
        a condition which was violated in a human-readable way.
        """


class RestrictToSet(AbstractValidator):
    """
    Restrict the possible values to the values from `values`. Operates on any
    types.
    """

    def __init__(self, values):
        self.values = frozenset(values)

    def validate_detailed(self, value):
        from ..errors import UserValueError
        if value not in self.values:
            return [
                UserValueError(i18n._("{} is not an allowed value"),
                               value)
            ]
        return []


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

    def validate_detailed(self, value):
        from ..errors import UserValueError
        if not all(map(self._validate_chr, value)):
            return [
                UserValueError(i18n._("{} is not a valid NMTOKEN"),
                               value)
            ]
        return []


class IsInstance(AbstractValidator):
    """
    This validator checks that the value is an instance of any of the classes
    given in `valid_classes`.

    `valid_classes` is *not* copied into the :class:`IsInstance` instance, but
    instead shared; it can be mutated after the construction of
    :class:`IsInstance` to allow addition and removal of classes.
    """

    def __init__(self, valid_classes):
        self.classes = valid_classes

    def validate_detailed(self, v):
        from ..errors import UserValueError
        if not isinstance(v, tuple(self.classes)):
            return [
                UserValueError(
                    i18n._("{} is of incorrect type (must be one of {})"),
                    v,
                    ", ".join(type_.__name__
                              for type_ in self.classes)
                )
            ]
        return []


class NumericRange(AbstractValidator):
    """
    To be used with orderable types, such as :class:`.DateTime` or
    :class:`.Integer`.

    The value is enforced to be within *[min, max]* (this is the interval from
    `min_` to `max_`, including both ends).

    Setting `min_` or `max_` to :data:`None` disables enforcement of that end
    of the interval. A common use is ``NumericRange(min_=1)`` in conjunction
    with :class:`.Integer` to enforce the use of positive integers.

    .. versionadded:: 0.6

    """

    def __init__(self, min_=None, max_=None):
        super().__init__()
        self.min_ = min_
        self.max_ = max_

    def validate_detailed(self, v):
        from ..errors import UserValueError
        if self.min_ is None:
            if self.max_ is None:
                return []
            if not v <= self.max_:
                return [
                    UserValueError(
                        i18n._("{} is too large (max is {})"),
                        v,
                        self.max_
                    )
                ]
        elif self.max_ is None:
            if not self.min_ <= v:
                return [
                    UserValueError(
                        i18n._("{} is too small (min is {})"),
                        v,
                        self.max_
                    )
                ]
        elif not self.min_ <= v <= self.max_:
            return [
                UserValueError(
                    i18n._("{} is out of bounds ({}..{})"),
                    v,
                    self.min_,
                    self.max_
                )
            ]
        return []


_Undefined = object()


def EnumType(enum_class, nested_type=_Undefined, **kwargs):
    """
    Create and return a :class:`EnumCDataType` or :class:`EnumElementType`,
    depending on the type of `nested_type`.

    If `nested_type` is a :class:`AbstractCDataType` or omitted, a
    :class:`EnumCDataType` is constructed. Otherwise, :class:`EnumElementType`
    is used.

    The arguments are forwarded to the respective class’ constructor.

    .. versionadded:: 0.10

    .. deprecated:: 0.10

        This function was introduced to ease the transition in 0.10 from
        a unified :class:`EnumType` to split :class:`EnumCDataType` and
        :class:`EnumElementType`.

        It will be removed in 1.0.
    """

    if nested_type is _Undefined:
        return EnumCDataType(enum_class, **kwargs)
    if isinstance(nested_type, AbstractCDataType):
        return EnumCDataType(enum_class, nested_type, **kwargs)
    else:
        return EnumElementType(enum_class, nested_type, **kwargs)
