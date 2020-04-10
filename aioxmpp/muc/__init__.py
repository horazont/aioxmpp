########################################################################
# File name: __init__.py
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
:mod:`~aioxmpp.muc` --- Multi-User-Chat support (:xep:`45`)
###########################################################

This subpackage provides client-side support for :xep:`0045`.

.. versionadded:: 0.5

.. versionchanged:: 0.9

    Nearly the whole public interface of this module has been re-written in
    0.9 to make it coherent with the Modern IM interface defined by
    :class:`aioxmpp.im`.

Using Multi-User-Chats
======================

To start using MUCs in your application, you have to load the :class:`Service`
into the client, using :meth:`~.node.Client.summon`.

.. currentmodule:: aioxmpp

.. autoclass:: MUCClient

.. currentmodule:: aioxmpp.muc

.. class:: Service

   Alias of :class:`.MUCClient`.

   .. deprecated:: 0.8

      The alias will be removed in 1.0.

The service returns :class:`Room` objects which are used to track joined MUCs:

.. autoclass:: Room

.. autoclass:: RoomState

.. autoclass:: LeaveMode

Inside rooms, there are occupants:

.. autoclass:: Occupant

.. autoclass:: ServiceMember

Timeout controls / :xep:`0410` (MUC Self-Ping) support
------------------------------------------------------

.. versionadded:: 0.11

    :xep:`410` support and aliveness detection.

Motivation
^^^^^^^^^^

In XMPP, multi-user chat services may reside on a server different than the
one the user is at. This may either be due to the service running on a remote
domain, or due to the service being connected via the network to the users
server as component (see e.g. :xep:`114`).

When the connection between the MUC service and the user’s server is broken
when stanzas need to be delivered, stanzas can be lost. This can lead to the
MUC getting "out of sync", in the sense that different participants have
different views of what happens and who even is in the MUC; this uncertainty
can go as far as a client assuming that they’re still joined, while they were
long removed from the MUC.

These types of breakages are hard to detect, unless the user tries to send a
message through the MUC (in which case the lack of reflection or an error reply
will give a clue that something is wrong). In the worst case, with an always-on
client, it may appear that the MUC has been silent for days, while in fact
everyone has been chatting away happily.

Solution
^^^^^^^^

The underlying problem (networks get split) cannot be solved. While Stream
Management on the s2s links could mitigate the issue to some extent, there will
always be limits and circumstances at play which can still cause the
out-of-sync situation.

While loss of messages can be compensated for by fetching the messages from the
archive (doing this automatically on an interruption is out of scope for
aioxmpp), there is no way for an application to detect that the client has been
removed from the MUC except by explicitly pinging or sending messages.

To codify the complex rules which are needed to silently (i.e. invisible to
other participants) check whether a client is still joined, :xep:`410` was
written. It specifies the use of :xep:`199` pings through the MUC to the
clients occupant (i.e. pinging oneself). MUC services explicitly reject the
ping request if the sending client is not an occupant.

.. _api-aioxmpp.muc-self-ping-logic:

Self-Ping Implementation and Logic
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :xep:`410` implementation in aioxmpp is controlled with several attributes
and lines of defense. In the first line of defense, there is a
:class:`~aioxmpp.utils.AlivenessMonitor` instance (this class is also used to
manage pinging the main XML stream). It is configured through
:attr:`aioxmpp.muc.Room.muc_soft_timeout` and
:attr:`~aioxmpp.muc.Room.muc_hard_timeout`.

The two timers run concurrently. When the soft timeout expires, the pinger (see
below) task is started. When the hard timeout expires, the MUC is marked stale
(this means, the :meth:`~aioxmpp.muc.Room.on_muc_stale` event fires). The
timers for both timeouts are reset whenever a presence or message stanza is
received from the MUC, preventing unnecessary pinging.

The pinger task emits pings in a defined interval
(:attr:`~aioxmpp.muc.Room.muc_ping_interval`). The pings have a timeout of
:attr:`~aioxmpp.muc.Room.muc_ping_timeout`. If a ping is replied to, the result
is interpreted according to :xep:`410`. If the result is positive (= user
still joined), the soft and hard timeout timers mentioned above are reset
(the pinger, thus, ideally prevents the hard timeout from being triggered if
the connection to the MUC is fine after the soft timeout expired). If the
result is inconclusive, pinging continues. If the result is negative (= user
is not joined anymore), the MUC room is marked as exited (with the reason
:attr:`~aioxmpp.muc.LeaveMode.DISCONNECTED`), except if it is set to
autorejoin, in which case a re-join (just as if the XML stream had been
disconnected) is attempted.

The default timeouts are set reasonably high to work reliably even on mobile
links.

.. warning::

    Please see the notes on :attr:`~aioxmpp.muc.Room.muc_ping_timeout`
    when changing the value of :attr:`~aioxmpp.muc.Room.muc_ping_timeout` or
    :attr:`~aioxmpp.muc.Room.muc_ping_interval`.

Forms
=====

.. autoclass:: ConfigurationForm
   :members:

.. autoclass:: InfoForm
    :members:

.. autoclass:: VoiceRequestForm
    :members:

XSOs
====

.. autoclass:: StatusCode

.. currentmodule:: aioxmpp.muc.xso

Attributes added to existing XSOs
---------------------------------

.. attribute:: aioxmpp.Message.xep0045_muc

    A :class:`GenericExt` object or :data:`None`.

.. attribute:: aioxmpp.Message.xep0045_muc_user

    A :class:`UserExt` object or :data:`None`.

.. attribute:: aioxmpp.Presence.xep0045_muc

    A :class:`GenericExt` object or :data:`None`.

.. attribute:: aioxmpp.Presence.xep0045_muc_user

    A :class:`UserExt` object or :data:`None`.

.. attribute:: aioxmpp.Message.xep0249_direct_invite

    A :class:`DirectInvite` object or :data:`None`.

Generic namespace
-----------------

.. autoclass:: GenericExt

.. autoclass:: History

User namespace
--------------

.. autoclass:: UserExt

.. autoclass:: Status

.. autoclass:: DestroyNotification

.. autoclass:: Decline

.. autoclass:: Invite

.. autoclass:: UserItem

.. autoclass:: UserActor

.. autoclass:: Continue

Admin namespace
---------------

.. autoclass:: AdminQuery

.. autoclass:: AdminItem

.. autoclass:: AdminActor

Owner namespace
---------------

.. autoclass:: OwnerQuery

.. autoclass:: DestroyRequest

:xep:`249` Direct Invitations
-----------------------------

.. autoclass:: DirectInvite

"""
from .service import (  # NOQA: F401
    MUCClient,
    Occupant,
    Room,
    LeaveMode,
    RoomState,
    ServiceMember,
)
from . import xso  # NOQA: F401
from .xso import (  # NOQA: F401
    ConfigurationForm,
    InfoForm,
    VoiceRequestForm,
    StatusCode,
)
Service = MUCClient  # NOQA
