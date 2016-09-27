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

.. class:: IQ

   Alias of :class:`aioxmpp.stanza.IQ`.

.. class:: JID

   Alias of :class:`aioxmpp.structs.JID`.

.. function:: make_security_lader

   Alias of :func:`aioxmpp.security_layer.make`.

.. class:: Message

   Alias of :class:`aioxmpp.stanza.Message`.

.. class:: Presence

   Alias of :class:`aioxmpp.stanza.Presence`.

.. class:: PresenceManagedClient

   Alias of :class:`aioxmpp.node.PresenceManagedClient`.

.. class:: PresenceState

   Alias of :class:`aioxmpp.structs.PresenceState`.

.. class:: XMPPAuthError

   Alias of :class:`aioxmpp.errors.XMPPAuthError`.

.. class:: XMPPCancelError

   Alias of :class:`aioxmpp.errors.XMPPCancelError`.

.. class:: XMPPContinueError

   Alias of :class:`aioxmpp.errors.XMPPContinueError`.

.. class:: XMPPModifyError

   Alias of :class:`aioxmpp.errors.XMPPModifyError`.

.. class:: XMPPWaitError

   Alias of :class:`aioxmpp.errors.XMPPWaitError`.

"""

#: The imported :mod:`aioxmpp` version as a tuple.
#:
#: The components of the tuple are, in order: `major version`, `minor version`,
#: `patch level`, and `pre-release identifier`.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
version_info = (0, 7, 0, "a0")

#: The imported :mod:`aioxmpp` version as a string.
#:
#: The version number is dot-separated; in pre-release or development versions,
#: the version number is followed by a hypen-separated pre-release identifier.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
__version__ = ".".join(map(str, version_info[:3])) + ("-"+version_info[3] if
                                                      version_info[3] else "")

version = __version__


from .errors import ( # NOQA
    XMPPAuthError,
    XMPPCancelError,
    XMPPContinueError,
    XMPPModifyError,
    XMPPWaitError,
)
from .node import PresenceManagedClient  # NOQA
from .stanza import Presence, IQ, Message  # NOQA
from .structs import JID, PresenceState  # NOQA
from .security_layer import make as make_security_layer  # NOQA


def set_strict_mode():
    from .stanza import Error
    Message.type_.type_.allow_coerce = False
    IQ.type_.type_.allow_coerce = False
    Error.type_.type_.allow_coerce = False
    Presence.type_.type_.allow_coerce = False
