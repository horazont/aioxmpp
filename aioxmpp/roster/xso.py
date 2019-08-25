########################################################################
# File name: xso.py
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
import aioxmpp.stanza as stanza
import aioxmpp.nonza as nonza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.rfc6121_roster = "jabber:iq:roster"
namespaces.rfc6121_roster_versioning = "urn:xmpp:features:rosterver"


class Group(xso.XSO):
    """
    A group declaration for a contact in a roster.

    .. attribute:: name

       The name of the group.

    """
    TAG = (namespaces.rfc6121_roster, "group")

    name = xso.Text(default=None)

    def __init__(self, *, name=None):
        super().__init__()
        self.name = name


class Item(xso.XSO):
    """
    A contact item in a roster.

    .. attribute:: jid

       The bare :class:`~aioxmpp.JID` of the contact.

    .. attribute:: name

       The optional display name of the contact.

    .. attribute:: groups

       A :class:`~aioxmpp.xso.model.XSOList` of :class:`Group` instances which
       describe the roster groups in which the contact is.

    The following attributes represent the subscription status of the
    contact. A client **must not** set these attributes when sending roster
    items to the server. To change subscription status, use presence stanzas of
    the respective type. The only exception is a :attr:`subscription` value of
    ``"remove"``, which is used to remove an entry from the roster.

    .. attribute:: subscription

       Primary subscription status, one of ``"none"`` (the default), ``"to"``,
       ``"from"`` and ``"both"``.

       In addition, :attr:`subscription` can be set to ``"remove"`` to remove
       an item from the roster during a roster set. Removing an entry from the
       roster will also cancel any presence subscriptions from and to that
       entries entity.

    .. attribute:: approved

       Whether the subscription has been pre-approved by the owning entity.

    .. attribute:: ask

       Subscription sub-states, one of ``"subscribe"`` and :data:`None`.

    .. note::

       Do not confuse this class with :class:`~aioxmpp.roster.Item`.

    """

    TAG = (namespaces.rfc6121_roster, "item")

    approved = xso.Attr(
        "approved",
        type_=xso.Bool(),
        default=False,
    )

    ask = xso.Attr(
        "ask",
        validator=xso.RestrictToSet({
            None,
            "subscribe",
        }),
        validate=xso.ValidateMode.ALWAYS,
        default=None,
    )

    jid = xso.Attr(
        "jid",
        type_=xso.JID(),
    )

    name = xso.Attr(
        "name",
        default=None,
    )

    subscription = xso.Attr(
        "subscription",
        validator=xso.RestrictToSet({
            "none",
            "to",
            "from",
            "both",
            "remove",
        }),
        validate=xso.ValidateMode.ALWAYS,
        default="none",
    )

    groups = xso.ChildList([Group])

    def __init__(self, jid, *,
                 name=None,
                 groups=(),
                 subscription="none",
                 approved=False,
                 ask=None):
        super().__init__()
        if jid is not None:
            self.jid = jid
        self.name = name
        self.groups.extend(groups)
        self.subscription = subscription
        self.approved = approved
        self.ask = ask


@stanza.IQ.as_payload_class
class Query(xso.XSO):
    """
    A query which fetches data from the roster or sends new items to the
    roster.

    .. attribute:: ver

       The version of the roster, if any. See the RFC for the detailed
       semantics.

    .. attribute:: items

       The items in the roster query.

    """
    TAG = (namespaces.rfc6121_roster, "query")

    ver = xso.Attr(
        "ver",
        default=None
    )

    items = xso.ChildList([Item])

    def __init__(self, *, ver=None, items=()):
        super().__init__()
        self.ver = ver
        self.items.extend(items)


@nonza.StreamFeatures.as_feature_class
class RosterVersioningFeature(xso.XSO):
    """
    Roster versioning feature.

    .. seealso::

       :class:`aioxmpp.nonza.StreamFeatures`

    """
    TAG = (namespaces.rfc6121_roster_versioning, "ver")
