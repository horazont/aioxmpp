import collections
import functools

_PresenceState = collections.namedtuple(
    "PresenceState",
    ["available", "show"])

@functools.total_ordering
class PresenceState(_PresenceState):
    SHOW_VALUES = ["dnd", "xa", "away", None, "chat"]
    SHOW_VALUE_WEIGHT = {
        value: i
        for i, value in enumerate(SHOW_VALUES)
    }

    def __new__(cls, available=False, show=None):
        if show not in cls.SHOW_VALUES:
            raise ValueError("Invalid value for <show/>: {!r}".format(
                show))
        if not available and show:
            raise ValueError("Unavailable state cannot have show value")
        return _PresenceState.__new__(cls, bool(available), show)

    def __lt__(self, other):
        my_key = (self.available, self.SHOW_VALUE_WEIGHT[self.show])
        other_key = (other.available, other.SHOW_VALUE_WEIGHT[other.show])
        return my_key < other_key

    def to_stanza(self, presence_factory):
        stanza = presence_factory(
            type_=None if self.available else "unavailable")
        if self.show is not None:
            stanza.show = self.show
        return stanza

    def __repr__(self):
        s = "<PresenceState available={!r}".format(self.available)
        if self.available and self.show:
            s += " show={!r}".format(self.show)
        return s+">"

    def __bool__(self):
        return self.available
