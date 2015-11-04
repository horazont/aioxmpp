"""
:mod:`~aioxmpp.structs` --- Simple data holders for common data types
#####################################################################

These classes provide a way to hold structured data which is commonly
encountered in the XMPP realm.

Jabber IDs
==========

.. autoclass:: JID(localpart, domain, resource)

Presence
========

.. autoclass:: PresenceState

Languages
=========

.. autoclass:: LanguageTag

.. autoclass:: LanguageRange

.. autoclass:: LanguageMap

Functions for working with language tags
----------------------------------------

.. autofunction:: basic_filter_languages

.. autofunction:: lookup_language

"""

import collections
import functools

from .stringprep import nodeprep, resourceprep, nameprep


class JID(collections.namedtuple("JID", ["localpart", "domain", "resource"])):
    """
    A Jabber ID (JID). To construct a JID, either use the actual constructor,
    or use the :meth:`fromstr` class method.

    .. automethod:: fromstr

    Information about a JID:

    .. attribute:: localpart

       The localpart, stringprep’d from the argument to the constructor.

    .. attribute:: domain

       The domain, stringprep’d from the argument to the constructor.

    .. attribute:: resource

       The resource, stringprep’d from the argument to the constructor.

    .. autoattribute:: is_bare

    .. autoattribute:: is_domain

    :class:`JID` objects are immutable. To obtain a JID object with a changed
    property, use one of the following methods:

    .. automethod:: bare

    .. automethod:: replace(*, [localpart], [domain], [resource])
    """

    __slots__ = []

    def __new__(cls, localpart, domain, resource):
        if localpart:
            localpart = nodeprep(localpart)
        if domain is not None:
            domain = nameprep(domain)
        if resource:
            resource = resourceprep(resource)

        if not domain:
            raise ValueError("domain must not be empty or None")
        if len(domain.encode("utf-8")) > 1023:
            raise ValueError("domain too long")
        if localpart is not None:
            if not localpart:
                raise ValueError("localpart must not be empty")
            if len(localpart.encode("utf-8")) > 1023:
                raise ValueError("localpart too long")
        if resource is not None:
            if not resource:
                raise ValueError("resource must not be empty")
            if len(resource.encode("utf-8")) > 1023:
                raise ValueError("resource too long")

        return super().__new__(cls, localpart, domain, resource)

    def replace(self, **kwargs):
        """
        Construct a new :class:`JID` object, using the values of the current
        JID. Use the arguments to override specific attributes on the new
        object.
        """

        new_kwargs = {}

        try:
            localpart = kwargs.pop("localpart")
        except KeyError:
            pass
        else:
            if localpart:
                localpart = nodeprep(localpart)
            new_kwargs["localpart"] = localpart

        try:
            domain = kwargs.pop("domain")
        except KeyError:
            pass
        else:
            if not domain:
                raise ValueError("domain must not be empty or None")
            new_kwargs["domain"] = nameprep(domain)

        try:
            resource = kwargs.pop("resource")
        except KeyError:
            pass
        else:
            if resource:
                resource = resourceprep(resource)
            new_kwargs["resource"] = resource

        if kwargs:
            raise TypeError("replace() got an unexpected keyword argument"
                            " {!r}".format(
                                next(iter(kwargs))))

        return super()._replace(**new_kwargs)

    def __str__(self):
        result = self.domain
        if self.localpart:
            result = self.localpart + "@" + result
        if self.resource:
            result += "/" + self.resource
        return result

    def bare(self):
        """
        Return the bare version of this JID as new :class:`JID` object.
        """
        return self.replace(resource=None)

    @property
    def is_bare(self):
        """
        :data:`True` if the JID is bare, i.e. has an empty :attr:`resource`
        part.
        """
        return not self.resource

    @property
    def is_domain(self):
        """
        :data:`True` if the JID is a domain, i.e. if both the :attr:`localpart`
        and the :attr:`resource` are empty.
        """
        return not self.resource and not self.localpart

    @classmethod
    def fromstr(cls, s):
        """
        Obtain a :class:`JID` object by parsing a JID from the given string
        `s`.
        """
        localpart, sep, domain = s.partition("@")
        if not sep:
            domain = localpart
            localpart = None

        domain, sep, resource = domain.partition("/")
        if not sep:
            resource = None
        return cls(localpart, domain, resource)


@functools.total_ordering
class PresenceState:
    """
    Hold a presence state of an XMPP resource, as defined by the presence
    stanza semantics.

    `available` must be a boolean value, which defines whether the resource is
    available or not. If the resource is available, `show` may be set to one of
    ``"dnd"``, ``"xa"``, ``"away"``, :data:`None`, ``"chat"`` (it is a
    :class:`ValueError` to attempt to set `show` to a non-:data:`None` value if
    `available` is false).

    :class:`PresenceState` objects are ordered by their availability and by
    their show values. Non-availability sorts lower than availability, and for
    available presence states the order is in the order of valid values given
    for the `show` above.

    .. attribute:: available

       As per the argument to the constructor, converted to a :class:`bool`.

    .. attribute:: show

       As per the argument to the constructor.

    .. automethod:: apply_to_stanza

    .. automethod:: from_stanza

    :class:`PresenceState` objects are immutable.

    """

    SHOW_VALUES = ["dnd", "xa", "away", None, "chat"]
    SHOW_VALUE_WEIGHT = {
        value: i
        for i, value in enumerate(SHOW_VALUES)
    }

    __slots__ = ["_available", "_show"]

    def __init__(self, available=False, show=None):
        super().__init__()
        if not available and show:
            raise ValueError("Unavailable state cannot have show value")
        if show not in PresenceState.SHOW_VALUES:
            raise ValueError("Not a valid show value")
        self._available = bool(available)
        self._show = show

    @property
    def available(self):
        return self._available

    @property
    def show(self):
        return self._show

    def __lt__(self, other):
        my_key = (self.available,
                  PresenceState.SHOW_VALUE_WEIGHT[self.show])
        other_key = (other.available,
                     PresenceState.SHOW_VALUE_WEIGHT[other.show])
        return my_key < other_key

    def __eq__(self, other):
        try:
            return (self.available == other.available and
                    self.show == other.show)
        except AttributeError:
            return NotImplemented

    def __repr__(self):
        more = ""
        if self.available:
            if self.show:
                more = " available show={!r}".format(self.show)
            else:
                more = " available"
        return "<PresenceState{}>".format(more)

    def apply_to_stanza(self, stanza_obj):
        """
        Apply the properties of this :class:`PresenceState` to a
        :class:`~aioxmpp.stanza.Presence` `stanza_obj`. The
        :attr:`~aioxmpp.stanza.Presence.type_` and
        :attr:`~aioxmpp.stanza.Presence.show` attributes of the object will be
        modified to fit the values in this object.
        """

        if self.available:
            stanza_obj.type_ = None
        else:
            stanza_obj.type_ = "unavailable"
        stanza_obj.show = self.show

    @classmethod
    def from_stanza(cls, stanza_obj, strict=False):
        """
        Create and return a new :class:`PresenceState` object which inherits
        the presence state as advertised in the given
        :class:`~aioxmpp.stanza.Presence` stanza.

        If `strict` is :data:`True`, the value of `show` is strictly checked,
        that is, it is required to be :data:`None` if the stanza indicates an
        unavailable state.

        The default is not to check this.
        """

        if stanza_obj.type_ != "unavailable" and stanza_obj.type_ is not None:
            raise ValueError("presence state stanza required")
        available = not stanza_obj.type_
        if not strict:
            show = stanza_obj.show if available else None
        else:
            show = stanza_obj.show
        return cls(available=available, show=show)


@functools.total_ordering
class LanguageTag:
    """
    Implementation of a language tag. This may be a fully RFC5646 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.

    :class:`LanguageTag` instances compare and hash case-insensitively.

    .. automethod:: fromstr

    .. autoattribute:: match_str

    .. autoattribute:: print_str

    """

    __slots__ = ("_tag",)

    def __init__(self, *, tag=None):
        if not tag:
            raise ValueError("tag cannot be empty")

        self._tag = tag

    @property
    def match_str(self):
        """
        The string which is used for matching two lanugage tags. This is the
        lower-cased version of the :attr:`print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self):
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s):
        """
        Create a language tag from the given string `s`.

        .. note::

           This is a stub implementation which merely refers to the given
           string as the :attr:`print_str` and derives the :attr:`match_str`
           from that.

        """
        return cls(tag=s)

    def __str__(self):
        return self.print_str

    def __eq__(self, other):
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __lt__(self, other):
        return self.match_str < other.match_str

    def __le__(self, other):
        return self.match_str <= other.match_str

    def __hash__(self):
        return hash(self.match_str)

    def __repr__(self):
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__,
            type(self).__qualname__,
            str(self))


class LanguageRange:
    """
    Implementation of a language range. This may be a fully RFC4647 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.

    :class:`LanguageRange` instances compare and hash case-insensitively.

    .. automethod:: fromstr

    .. automethod:: strip_rightmost

    .. autoattribute:: match_str

    .. autoattribute:: print_str

    """

    __slots__ = ("_tag",)

    def __init__(self, *, tag=None):
        if not tag:
            raise ValueError("range cannot be empty")

        self._tag = tag

    @property
    def match_str(self):
        """
        The string which is used for matching two lanugage tags. This is the
        lower-cased version of the :attr:`print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self):
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s):
        """
        Create a language tag from the given string `s`.

        .. note::

           This is a stub implementation which merely refers to the given
           string as the :attr:`print_str` and derives the :attr:`match_str`
           from that.

        """
        if s == "*":
            return cls.WILDCARD

        return cls(tag=s)

    def __str__(self):
        return self.print_str

    def __eq__(self, other):
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.match_str)

    def __repr__(self):
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__,
            type(self).__qualname__,
            str(self))

    def strip_rightmost(self):
        """
        Strip the rightmost part of the language range. If the new rightmost
        part is a singleton or ``x`` (i.e. starts an extension or private use
        part), it is also stripped.

        Return the newly created :class:`LanguageRange`.
        """

        parts = self.print_str.split("-")
        parts.pop()
        if parts and len(parts[-1]) == 1:
            parts.pop()
        return type(self).fromstr("-".join(parts))

LanguageRange.WILDCARD = LanguageRange(tag="*")


def basic_filter_languages(languages, ranges):
    """
    Filter languages using the string-based basic filter algorithm described in
    RFC4647.

    `languages` must be a sequence of :class:`LanguageTag` instances which are
    to be filtered.

    `ranges` must be an iterable which represent the basic language ranges to
    filter with, in priority order. The language ranges must be given as
    :class:`LanguageRange` objects.

    Return an iterator of languages which matched any of the `ranges`. The
    sequence produced by the iterator is in match order and duplicate-free. The
    first range to match a language yields the language into the iterator, no
    other range can yield that language afterwards.
    """

    if LanguageRange.WILDCARD in ranges:
        yield from languages
        return

    found = set()

    for language_range in ranges:
        range_str = language_range.match_str
        for language in languages:
            if language in found:
                continue

            match_str = language.match_str
            if match_str == range_str:
                yield language
                found.add(language)
                continue

            if len(range_str) < len(match_str):
                if     (match_str[:len(range_str)] == range_str and
                        match_str[len(range_str)] == "-"):
                    yield language
                    found.add(language)
                    continue


def lookup_language(languages, ranges):
    """
    Look up a single language in the sequence `languages` using the lookup
    mechansim described in RFC4647. If no match is found, :data:`None` is
    returned. Otherwise, the first matching language is returned.

    `languages` must be a sequence of :class:`LanguageTag` objects, while
    `ranges` must be an iterable of :class:`LanguageRange` objects.
    """

    for language_range in ranges:
        while True:
            try:
                return next(iter(basic_filter_languages(
                    languages,
                    [language_range])))
            except StopIteration:
                pass

            try:
                language_range = language_range.strip_rightmost()
            except ValueError:
                break


class LanguageMap(dict):
    """
    A :class:`dict` subclass specialized for holding :class:`LanugageTag`
    instances as keys.

    In addition to the interface provided by :class:`dict`, instances of this
    class also have the following method:

    .. automethod:: lookup
    """

    def lookup(self, language_ranges):
        """
        Perform an RFC4647 language range lookup on the keys in the
        dictionary. `language_ranges` must be a sequence of
        :class:`LanguageRange` instances.

        Return the entry in the dictionary with a key as produced by
        `lookup_language`. If `lookup_language` does not find a match and the
        mapping contains an entry with key :data:`None`, that entry is
        returned, otherwise :class:`KeyError` is raised.
        """
        keys = list(self.keys())
        try:
            keys.remove(None)
        except ValueError:
            pass
        keys.sort()
        key = lookup_language(keys, language_ranges)
        return self[key]
