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
# General Public License for more details.
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

Shorthands
##########

.. function:: make_security_layer

   Alias of :func:`aioxmpp.security_layer.make`.

"""

from .version import version_info, __version__, version

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

from .errors import ( # NOQA
    XMPPAuthError,
    XMPPCancelError,
    XMPPContinueError,
    XMPPModifyError,
    XMPPWaitError,
)
from .node import PresenceManagedClient  # NOQA
from .stanza import Presence, IQ, Message  # NOQA
from .structs import (  # NOQA
    JID,
    PresenceState,
    MessageType,
    PresenceType,
    IQType,
    ErrorType,
)
from .security_layer import make as make_security_layer  # NOQA


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
