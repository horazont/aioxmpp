import collections
import functools

from .stringprep import nodeprep, resourceprep, nameprep


class JID(collections.namedtuple("JID", ["localpart", "domain", "resource"])):
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
        try:
            localpart = kwargs["localpart"]
        except KeyError:
            pass
        else:
            if localpart:
                kwargs["localpart"] = nodeprep(localpart)

        try:
            domain = kwargs["domain"]
        except KeyError:
            pass
        else:
            if not domain:
                raise ValueError("domain must not be empty or None")
            kwargs["domain"] = nameprep(domain)

        try:
            resource = kwargs["resource"]
        except KeyError:
            pass
        else:
            if resource:
                kwargs["resource"] = resourceprep(resource)

        return super()._replace(**kwargs)

    def __str__(self):
        result = self.domain
        if self.localpart:
            result = self.localpart + "@" + result
        if self.resource:
            result += "/" + self.resource
        return result

    @property
    def bare(self):
        return self.replace(resource=None)

    @property
    def is_bare(self):
        return not self.resource

    @property
    def is_domain(self):
        return not self.resource and not self.localpart

    @classmethod
    def fromstr(cls, s):
        localpart, sep, domain = s.partition("@")
        if not sep:
            domain = localpart
            localpart = None

        domain, _, resource = domain.partition("/")
        return cls(localpart, domain, resource)


@functools.total_ordering
class PresenceState:
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
        self._available = available
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
        if self.available:
            stanza_obj.type_ = None
        else:
            stanza_obj.type_ = "unavailable"
        stanza_obj.show = self.show

    @classmethod
    def from_stanza(cls, stanza_obj, strict=False):
        if stanza_obj.type_ != "unavailable" and stanza_obj.type_ is not None:
            raise ValueError("presence state stanza required")
        available = not stanza_obj.type_
        if not strict:
            show = stanza_obj.show if available else None
        else:
            show = stanza_obj.show
        return cls(available=available, show=show)
