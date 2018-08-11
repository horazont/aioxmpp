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
import collections.abc
import enum

import aioxmpp.stanza
import aioxmpp.forms
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0050_commands = "http://jabber.org/protocol/commands"


class NoteType(enum.Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class ActionType(enum.Enum):
    NEXT = "next"
    EXECUTE = "execute"
    PREV = "prev"
    CANCEL = "cancel"
    COMPLETE = "complete"


class CommandStatus(enum.Enum):
    """
    Describes the status a command execution is in.

    .. attribute:: EXECUTING

       The command is being executed.

    .. attribute:: COMPLETED

       The command has been completed.

    .. attribute:: CANCELED

       The command has been canceled.
    """

    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELED = "canceled"


class Note(xso.XSO):
    TAG = (namespaces.xep0050_commands, "note")

    body = xso.Text(
        default=None,
    )

    type_ = xso.Attr(
        "type",
        type_=xso.EnumCDataType(
            NoteType,
        ),
        default=NoteType.INFO,
    )

    def __init__(self, type_, body):
        super().__init__()
        self.type_ = type_
        self.body = body


class Actions(xso.XSO):
    TAG = (namespaces.xep0050_commands, "actions")

    next_is_allowed = xso.ChildFlag(
        (namespaces.xep0050_commands, "next"),
    )

    prev_is_allowed = xso.ChildFlag(
        (namespaces.xep0050_commands, "prev"),
    )

    complete_is_allowed = xso.ChildFlag(
        (namespaces.xep0050_commands, "complete"),
    )

    execute = xso.Attr(
        "execute",
        type_=xso.EnumCDataType(ActionType),
        validator=xso.RestrictToSet({
            ActionType.NEXT,
            ActionType.PREV,
            ActionType.COMPLETE,
        }),
        default=None,
    )

    @property
    def allowed_actions(self):
        result = [ActionType.EXECUTE, ActionType.CANCEL]
        if self.prev_is_allowed:
            result.append(ActionType.PREV)
        if self.next_is_allowed:
            result.append(ActionType.NEXT)
        if self.complete_is_allowed:
            result.append(ActionType.COMPLETE)
        return frozenset(result)

    @allowed_actions.setter
    def allowed_actions(self, values):
        values = frozenset(values)
        if ActionType.EXECUTE not in values:
            raise ValueError("EXECUTE must always be allowed")
        if ActionType.CANCEL not in values:
            raise ValueError("CANCEL must always be allowed")
        self.prev_is_allowed = ActionType.PREV in values
        self.next_is_allowed = ActionType.NEXT in values
        self.complete_is_allowed = ActionType.COMPLETE in values


@aioxmpp.IQ.as_payload_class
class Command(xso.XSO):
    TAG = (namespaces.xep0050_commands, "command")

    actions = xso.Child([Actions])

    notes = xso.ChildList([Note])

    action = xso.Attr(
        "action",
        type_=xso.EnumCDataType(ActionType),
        default=ActionType.EXECUTE,
    )

    status = xso.Attr(
        "status",
        type_=xso.EnumCDataType(CommandStatus),
        default=None,
    )

    sessionid = xso.Attr(
        "sessionid",
        default=None,
    )

    node = xso.Attr(
        "node",
    )

    payload = xso.ChildList([
        aioxmpp.forms.Data,
    ])

    def __init__(self, node, *,
                 action=ActionType.EXECUTE,
                 status=None,
                 sessionid=None,
                 payload=[],
                 notes=[],
                 actions=None):
        super().__init__()
        self.node = node
        self.action = action
        self.status = status
        self.sessionid = sessionid
        if not isinstance(payload, collections.abc.Iterable):
            self.payload[:] = [payload]
        else:
            self.payload[:] = payload
        self.notes[:] = notes
        self.actions = actions

    @property
    def first_payload(self):
        try:
            return self.payload[0]
        except IndexError:
            return


MalformedAction = aioxmpp.stanza.make_application_error(
    "MalformedAction",
    (namespaces.xep0050_commands, "malformed-action"),
)

BadAction = aioxmpp.stanza.make_application_error(
    "BadAction",
    (namespaces.xep0050_commands, "bad-action"),
)

BadLocale = aioxmpp.stanza.make_application_error(
    "BadLocale",
    (namespaces.xep0050_commands, "bad-locale"),
)

BadPayload = aioxmpp.stanza.make_application_error(
    "BadPayload",
    (namespaces.xep0050_commands, "bad-payload"),
)

BadSessionID = aioxmpp.stanza.make_application_error(
    "BadSessionID",
    (namespaces.xep0050_commands, "bad-sessionid"),
)

SessionExpired = aioxmpp.stanza.make_application_error(
    "SessionExpired",
    (namespaces.xep0050_commands, "session-expired"),
)
