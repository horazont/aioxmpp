import multidict

import aioxmpp.stanza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0131_shim = "http://jabber.org/protocol/shim"


class Header(xso.XSO):
    TAG = (namespaces.xep0131_shim, "header")

    name = xso.Attr(
        "name",
    )

    value = xso.Text()

    def __init__(self, name, value):
        super().__init__()
        self.name = name
        self.value = value


class HeaderType(xso.AbstractType):
    def get_formatted_type(self):
        return Header

    def parse(self, v):
        return v.name, v.value

    def format(self, v):
        name, value = v
        return Header(
            name,
            value,
        )


class Headers(xso.XSO):
    """
    Represent stanza headers. The headers are accessible at the :attr:`headers`
    attribute.

    .. attribute:: headers

       A :class:`multidict.CIMultiDict` which provides access to the headers.
       The keys are the header names and the values are the values of the
       header. Both must be strings.

    .. seealso::

       :attr:`.stanza.Message.xep0131_headers`
          SHIM headers for :class:`~.stanza.Message` stanzas

       :attr:`.stanza.Presence.xep0131_headers`
          SHIM headers for :class:`~.stanza.Presence` stanzas
    """

    TAG = (namespaces.xep0131_shim, "header")

    headers = xso.ChildValueMultiMap(
        HeaderType(),
        mapping_type=multidict.CIMultiDict,
    )


aioxmpp.stanza.Message.xep0131_headers = xso.Child([
    Headers,
])

aioxmpp.stanza.Presence.xep0131_headers = xso.Child([
    Headers,
])
