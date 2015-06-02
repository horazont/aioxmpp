"""
:mod:`aioxmpp.xso.types` --- Types specifications for use with :mod:`aioxmpp.xso.model`
#######################################################################################

See :mod:`aioxmpp.xso` for documentation.

"""

import abc
import array
import base64
import binascii
import decimal
import ipaddress
import numbers
import unicodedata
import re

import pytz

from datetime import datetime, timedelta

from .. import structs


class AbstractType(metaclass=abc.ABCMeta):
    """
    This is the interface all types must implement.

    .. automethod:: check

    .. automethod:: parse

    .. automethod:: format
    """

    def coerce(self, v):
        """
        Force the given value *v* to be of the type represented by this
        :class:`AbstractType`. :meth:`check` is called when user code assigns
        values to descriptors which use the type; it is notably not called when
        values are extracted from SAX events, as these go through :meth:`parse`
        and that is expected to return correctly typed values.

        If *v* cannot be sensibly coerced, :class:`TypeError` is raised (in
        some rare occasions, :class:`ValueError` may be ok too).

        Return a coerced version of *v* or *v* itself if it matches the
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
        Convert the given string *v* into a value of the appropriate type this
        class implements and return the result.

        If conversion fails, :class:`ValueError` is raised.

        The result of :meth:`parse` must pass through :meth:`check`.
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

    def coerce(self, v):
        if not isinstance(v, str):
            raise TypeError("must be a str object")
        return v

    def parse(self, v):
        return v


class Integer(AbstractType):
    """
    Parse the value as base-10 integer and return the result as :class:`int`.
    """

    def coerce(self, v):
        if not isinstance(v, numbers.Integral):
            raise TypeError("must be integral number")
        return int(v)

    def parse(self, v):
        return int(v)


class Float(AbstractType):
    """
    Parse the value as decimal float and return the result as :class:`float`.
    """

    def coerce(self, v):
        if not isinstance(v, (numbers.Real, decimal.Decimal)):
            raise TypeError("must be real number")
        return float(v)

    def parse(self, v):
        return float(v)


class Bool(AbstractType):
    """
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


class DateTime(AbstractType):
    """
    Parse the value as ISO datetime, possibly including microseconds and
    timezone information.

    Timezones are handled as constant offsets from UTC, and are converted to
    UTC before the :class:`~datetime.datetime` object is returned (which is
    correctly tagged with UTC tzinfo). Values without timezone specification
    are not tagged.

    This class makes use of :mod:`pytz`.
    """

    tzextract = re.compile("((Z)|([+-][0-9]{2}):([0-9]{2}))$")

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


class _BinaryType(AbstractType):
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
    Parse the value as base64 and return the :class:`bytes` object obtained
    from decoding.

    If *empty_as_equal* is :data:`True`, an empty value is represented using a
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
    Parse the value as hexadecimal blob and return the :class:`bytes` object
    obtained from decoding.
    """

    def parse(self, v):
        return binascii.a2b_hex(v)

    def format(self, v):
        return binascii.b2a_hex(v).decode("ascii")


class JID(AbstractType):
    """
    Parse the value as Jabber ID using :meth:`~aioxmpp.structs.JID.fromstr` and
    return the :class:`aioxmpp.structs.JID` object.
    """

    def coerce(self, v):
        if not isinstance(v, structs.JID):
            raise TypeError("{} object {!r} is not a JID".format(
                type(v), v))

        return v

    def parse(self, v):
        return structs.JID.fromstr(v)


class ConnectionLocation(AbstractType):
    """
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
        addr, _, port = v.rpartition(":")
        if not _:
            raise ValueError("missing colon in connection location")
        port = int(port)

        if addr.startswith("[") and addr.endswith("]"):
            addr = ipaddress.IPv6Address(addr[1:-1])

        try:
            addr = ipaddress.IPv4Address(addr)
        except ValueError:
            pass

        return self.coerce((addr, port))

    def format(self, v):
        if isinstance(v[0], ipaddress.IPv6Address):
            return "[{}]:{}".format(*v)
        return ":".join(map(str, v))


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
