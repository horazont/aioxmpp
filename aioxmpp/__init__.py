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
Version information
###################

There are two ways to obtain the imported version of the :mod:`aioxmpp`
package:

.. autodata:: __version__

.. data:: version

   Alias of :data:`__version__`.

.. autodata:: version_info

.. _api-aioxmpp-services:

Overview of Services
####################

.. autosummary::
    :nosignatures:

    aioxmpp.AdHocClient
    aioxmpp.AvatarService
    aioxmpp.BlockingClient
    aioxmpp.BookmarkClient
    aioxmpp.CarbonsClient
    aioxmpp.DiscoClient
    aioxmpp.DiscoServer
    aioxmpp.EntityCapsService
    aioxmpp.MUCClient
    aioxmpp.PingService
    aioxmpp.PresenceClient
    aioxmpp.PresenceServer
    aioxmpp.PEPClient
    aioxmpp.RosterClient
    aioxmpp.VersionServer

Shorthands
##########

.. function:: make_security_layer

   Alias of :func:`aioxmpp.security_layer.make`.

"""
from ._version import version_info, __version__, version  # NOQA: F401

#: The imported :mod:`aioxmpp` version as a tuple.
#:
#: The components of the tuple are, in order: `major version`, `minor version`,
#: `patch level`, and `pre-release identifier`.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
version_info = version_info

#: The imported :mod:`aioxmpp` version as a string.
#:
#: The version number is dot-separated; in pre-release or development versions,
#: the version number is followed by a hypen-separated pre-release identifier.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
__version__ = __version__

# XXX: ^ this is a hack to make Sphinx find the docs. We could also be using
# .. data instead of .. autodata, but that has the downside that the actual
# version number isn’t printed in the docs (without additional maintenance
# cost).

import asyncio  # NOQA
# Adds fallback if asyncio version does not provide an ensure_future function.
if not hasattr(asyncio, "ensure_future"):
    asyncio.ensure_future = getattr(asyncio, "async")

from .errors import (  # NOQA
    XMPPAuthError,
    XMPPCancelError,
    XMPPContinueError,
    XMPPModifyError,
    XMPPWaitError,
    ErrorCondition,
)
from .stanza import Presence, IQ, Message  # NOQA: F401
from .structs import (  # NOQA: F401
    JID,
    PresenceShow,
    PresenceState,
    MessageType,
    PresenceType,
    IQType,
    ErrorType,
    jid_escape,
    jid_unescape,
)
from .security_layer import make as make_security_layer  # NOQA: F401
from .node import Client, PresenceManagedClient  # NOQA: F401

# services
from .presence import PresenceClient, PresenceServer  # NOQA: F401
from .roster import RosterClient  # NOQA: F401
from .disco import DiscoServer, DiscoClient  # NOQA: F401
from .entitycaps import EntityCapsService  # NOQA: F401
from .muc import MUCClient  # NOQA: F401
from .pubsub import PubSubClient  # NOQA: F401
from .shim import SHIMService  # NOQA: F401
from .adhoc import AdHocClient, AdHocServer  # NOQA: F401
from .avatar import AvatarService  # NOQA: F401
from .blocking import BlockingClient  # NOQA: F401
from .carbons import CarbonsClient  # NOQA: F401
from .ping import PingService  # NOQA: F401
from .pep import PEPClient  # NOQA: F401
from .bookmarks import BookmarkClient  # NOQA: F401
from .version import VersionServer  # NOQA: F401
from .mdr import DeliveryReceiptsService  # NOQA: F401

from . import httpupload  # NOQA: F401


def set_strict_mode():
    from .stanza import Error
    from .stream import StanzaStream
    from . import structs
    Message.type_.type_.allow_coerce = False
    IQ.type_.type_.allow_coerce = False
    Error.type_.type_.allow_coerce = False
    Presence.type_.type_.allow_coerce = False
    StanzaStream._ALLOW_ENUM_COERCION = False
    structs._USE_COMPAT_ENUM = False
