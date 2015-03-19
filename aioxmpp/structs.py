"""
:mod:`~aioxmpp.structs` --- Simple data holders for common data types
#####################################################################

These classes provide a way to hold structured data which is commonly
encountered in the XMPP realm.

.. autoclass:: JID(localpart, domain, resource)

.. autoclass:: PresenceState

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
        if not domain:
            raise ValueError("domain must not be empty or None")

        localpart = localpart or None
        resource = resource or None

        if localpart is not None:
            localpart = nodeprep(localpart)
        domain = nameprep(domain)
        if resource is not None:
            resource = resourceprep(resource)
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
        *s*.
        """
        localpart, sep, domain = s.partition("@")
        if not sep:
            domain = localpart
            localpart = None

        domain, _, resource = domain.partition("/")
        return cls(localpart, domain, resource)


@functools.total_ordering
class PresenceState:
    """
    Hold a presence state of an XMPP resource, as defined by the presence
    stanza semantics.

    *available* must be a boolean value, which defines whether the resource is
    available or not. If the resource is available, *show* may be set to one of
    ``"dnd"``, ``"xa"``, ``"away"``, :data:`None`, ``"chat"`` (it is a
    :class:`ValueError` to attempt to set *show* to a non-:data:`None` value if
    *available* is false).

    :class:`PresenceState` objects are ordered by their availability and by
    their show values. Non-availability sorts lower than availability, and for
    available presence states the order is in the order of valid values given
    for the *show* above.

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
        return (self.available == other.available and
                self.show == other.show)

    def __ne__(self, other):
        return not self == other

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
        :class:`~aioxmpp.stanza.Presence` *stanza_obj*. The
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

        If *strict* is :data:`True`, the value of *show* is strictly checked,
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
