########################################################################
# File name: utils.py
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
from abc import ABCMeta, abstractproperty

from . import xso as chatstates_xso


class ChatStateStrategy(metaclass=ABCMeta):

    @abstractproperty
    def sending(self):
        """
        Return whether to send chat state notifications.
        """
        raise NotImplementedError  # pragma: no cover

    def reset(self):
        """
        Reset the strategy (called after a reconnect).
        """
        pass

    def no_reply(self):
        """
        Called when the replies did not include a chat state.
        """
        pass


class DoNotEmit(ChatStateStrategy):
    """
    Chat state strategy: Do not emit chat state notifications.
    """

    @property
    def sending(self):
        return False


class DiscoverSupport(ChatStateStrategy):
    """
    Chat state strategy: Discover support for chat state notifications
    as per section 5.1 of :xep:`0085`.
    """
    def __init__(self):
        self.state = True

    def reset(self):
        self.state = True

    def no_reply(self):
        self.state = False

    @property
    def sending(self):
        return self.state


class AlwaysEmit(ChatStateStrategy):
    """
    Chat state strategy: Always emit chat state notifications.
    """

    @property
    def sending(self):
        return True


class ChatStateManager:
    """
    Manage the state of our chat state.

    :param strategy: the strategy used to decide whether to send
                     notifications (defaults to :class:`DiscoverSupport`)
    :type strategy: a subclass of :class:`ChatStateStrategy`
    """

    def __init__(self, strategy=None):
        self._state = chatstates_xso.ChatState.ACTIVE
        if strategy is None:
            strategy = DiscoverSupport()
        self._strategy = strategy

    @property
    def sending(self):
        """
        Returns whether to send chat state notifications.
        """
        return self._strategy.sending

    def handle(self, state):
        """
        Handle a state update.

        :param state: the new chat state
        :type state: :class:`~aioxmpp.chatstates.ChatState`

        :returns: whether a standalone notification must be sent for
                  this state update.
        """
        if self._state == state:
            return False

        self._state = state
        return self._strategy.sending

    def no_reply(self):
        """
        Handle that the peer did not include a chat state notification.
        """
        self._strategy.no_reply()

    def reset(self):
        """
        Handle a connection reset.
        """
        self._strategy.reset()
